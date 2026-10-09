"""BoneCast — backend Twitch (OAuth device flow + titre/catégorie Helix + overlay chat).
Incrément 1 : login, titre, catégorie, overlay. Le streaming RTMP arrive à l'incrément 2.
Config PAR COMPTE Steam : ~/.config/bonecast-<accountid>.json (tokens = secrets, chmod 600)."""
import os
import sys
from json import load, dump
from pathlib import Path
from asyncio import Lock, create_task, current_task as _current_task
from time import time

from decky import logger, DECKY_PLUGIN_DIR  # type: ignore

sys.path.append(DECKY_PLUGIN_DIR)
import bonecast_env as bcenv  # noqa: E402
import ssl as _ssl

# plugin_loader est un binaire PyInstaller figé : son python n'expose pas les CA
# du système par défaut → toute requête HTTPS échoue avec « Cannot connect to host
# X:443 ssl:default [certificate verify failed] ». On construit un contexte SSL
# pointant explicitement sur le bundle CA système (même astuce que Steamcord/updater.py).
_SSL_CTX = None


def _ssl_context():
    global _SSL_CTX
    if _SSL_CTX is not None:
        return _SSL_CTX
    for ca in ("/etc/pki/tls/certs/ca-bundle.crt",
               "/etc/ssl/certs/ca-certificates.crt",
               "/etc/ssl/cert.pem"):
        try:
            if os.path.exists(ca):
                _SSL_CTX = _ssl.create_default_context(cafile=ca)
                return _SSL_CTX
        except Exception:
            pass
    _SSL_CTX = _ssl.create_default_context()
    return _SSL_CTX


def sys_python():
    """Python SYSTÈME (pour les bindings gi/Gst de gst_camera.py).
    /usr/bin/python n'existe pas sur Debian/Ubuntu (sauf python-is-python3) →
    résoudre python3 du PATH d'abord."""
    import shutil as _sh
    return _sh.which("python3") or _sh.which("python") or "/usr/bin/python"


async def stream_watcher(stream, is_err=False, prefix="[bonecast]"):
    """Recopie stdout/stderr d'un sous-process dans le journal Decky."""
    if stream is None:
        return
    while True:
        line = await stream.readline()
        if not line:
            break
        msg = line.decode(errors="ignore").rstrip()
        if msg:
            (logger.warning if is_err else logger.info)(f"{prefix} {msg}")


# Decky enregistre son PROPRE module `updater` dans sys.modules → un simple
# `import updater` renverrait celui-là (sans is_autoupdate_enabled). On charge
# notre fichier par chemin sous un nom unique pour éviter la collision. Depuis
# defaults/ (toujours dans le zip + synchronisé par le deploy).
import importlib.util as _ilu  # noqa: E402
_upath = Path(DECKY_PLUGIN_DIR) / "defaults" / "updater.py"
if not _upath.exists():
    _upath = Path(DECKY_PLUGIN_DIR) / "updater.py"
try:
    _uspec = _ilu.spec_from_file_location("bc_updater", str(_upath))
    updater = _ilu.module_from_spec(_uspec)
    _uspec.loader.exec_module(updater)
except Exception as _e:                       # best-effort : le plugin survit sans updater
    logger.warning(f"[updater] indisponible : {_e!r}")
    updater = None


# Nombre de vérifications de release et délai entre deux. La vérif part quelques
# secondes après le backend, c'est-à-dire souvent AVANT que le réseau soit
# joignable : les journaux de la machine de test montrent trois démarrages sur
# quatre qui meurent sur « Temporary failure in name resolution ». Rien ne
# réessayait, donc le plugin restait sur sa version jusqu'au démarrage
# suivant — qui échouait de la même façon.
UPDATE_CHECK_TRIES = 10
UPDATE_CHECK_DELAY_S = 30


async def _recheck(updater):
    """`updater.check()`, réessayé tant que c'est le réseau qui manque."""
    from asyncio import sleep as _sleep
    info = await updater.check()
    for _ in range(UPDATE_CHECK_TRIES - 1):
        if not info.get("error"):
            break
        await _sleep(UPDATE_CHECK_DELAY_S)
        info = await updater.check()
    return info


class Plugin:
    # ── OAuth Twitch (device code flow, client public — pas de secret) ───────
    _TWITCH_CLIENT_ID = "idbnwqbkqyrzesxct1ztkejyf5aj6z"
    # clips:edit = bouton « Clip » ; user:write:chat = envoi de messages chat ;
    # user:read:follows = liste des chaînes suivies actuellement en direct.
    # moderator:read:followers = nouveaux followers affichés dans l'overlay.
    # Les logins existants n'ont PAS ces scopes → les endpoints renvoient 401 et
    # le front invite à se reconnecter (device flow re-demande tout).
    _TWITCH_SCOPES = ("channel:read:stream_key channel:manage:broadcast "
                      "clips:edit user:write:chat user:read:follows")
    # moderator:read:followers (follows dans l overlay) : code prêt mais PAS
    # encore demandé — à ajouter ici quand la fonction sera testée et livrée.
    _TWITCH_JUST_CHATTING = "509658"          # game_id « Just Chatting »
    _tw_device = None                          # état transitoire du device flow
    _overlay_proc = None
    _overlay_platform = None                   # "twitch" | "youtube" (un overlay à la fois)
    _watch_proc = None                          # helper GTK : lives Twitch par-dessus le jeu
    _watch_start_lock = None                    # évite deux starts QAM simultanés
    _start_stream_lock = None                   # un seul lancement de live à la fois
    _start_overlay_lock = None                  # un seul lancement d'overlay à la fois
    _stream_proc = None                        # ffmpeg RTMP (live Twitch ou YouTube)
    _stream_platform = None                    # "twitch" | "youtube" | "record" (un seul à la fois)
    _camera_feeder = None                      # gst_camera.py --stdout → tuyau → ffmpeg
    # Reprise du live (BoneCast #1, demandé par dreemur-e) : réseau coupé, ffmpeg
    # mort, « Arrêter » par erreur ou redémarrage de la machine → pendant
    # `resume_window` secondes le live peut reprendre SANS en créer un nouveau
    # (même live YouTube, même lien pour les spectateurs).
    _RESUME_CHOICES = (0, 15, 30, 60, 120)
    _resume = None                             # {"platform", "until"} : reconnexion auto en cours
    _yt_end_task = None                        # fin YouTube différée (arrêt manuel / reboot)
    _stream_started = 0.0
    _pending_stream_alert = None
    _stream_alert_seq = 0
    _TWITCH_INGEST = "rtmp://ingest.global-contribute.live-video.net/app"
    _OVERLAY_DEFAULTS = {"opacity": 62, "fontSize": 13, "width": 360,
                         "height": 460, "pos": "tr", "badges": True, "thirdParty": True}
    _WATCH_DEFAULTS = {"streams": [], "layout": "corner_br", "scale": 1.0,
                       "opacity": 0.5, "max_fps": 30, "audio": "", "volume": 1.0}
    # ── Réglages du stream (par compte Steam) ────────────────────────────────
    _RES_PRESETS = {"720p": (1280, 720), "800p": (1280, 800),
                    "1080p": (1920, 1080), "source": (0, 0)}
    _STREAM_DEFAULTS = {"resolution": "720p", "fps": 30, "bitrate": 4500,
                        "audio_bitrate": 160, "keyframe": 2,
                        "encoder": "auto", "mic": False, "discord_audio": False,
                        "record": False, "effort": "balanced"}
    # Effort de l'encodeur LOGICIEL (x264) : moins d'effort = moins de CPU (le jeu
    # garde ses images sur un Deck), plus d'effort = image plus nette au même débit.
    # Idée de dreemur-e (BoneCast #1).
    _X264_PRESETS = {"light": "superfast", "balanced": "veryfast", "quality": "faster"}
    _vaapi_ok = None                           # cache détection VAAPI (AMD/Intel)
    _nvenc_ok = None                           # cache détection NVENC (Nvidia)
    _x264_ok = None                            # cache détection libx264 (ffmpeg-free Fedora = absent)
    _gst_py_ok = False                         # cache : bindings gi/Gst du python système OK
    # ── Mute micro à la volée (n'affecte QUE le stream, pas le vocal Discord) ──
    _mic_active = False                        # micro inclus dans le stream courant ?
    _mic_so_idx = None                         # source-output ffmpeg qui capte le micro
    _mic_muted = False                         # micro coupé sur le stream (live)
    # ── BRB (pause à l'antenne) + enregistrement local ────────────────────────
    _brb_on = False                            # écran pause affiché par le feeder (SIGUSR1/2)
    _brb_restore_mic = False                   # micro auto-muté par le BRB → à rétablir
    _record_path = None                        # fichier mkv du live/enregistrement courant
    _record_only = False                       # session sans RTMP (enregistrement seul)
    # ── Pont audio Discord (activable si Steamcord présent) ───────────────────
    _DISCORD_SINK = "bonecast_discord"         # sink dédié à la voix Discord
    _ba_modules = []                           # modules pactl chargés (null-sink+loopback)
    _ba_watch = None                           # tâche watcher (re-déplace Vesktop)
    _ba_real_sink = None                       # vraie sortie (l'user entend Discord)

    # ── Config par compte Steam ─────────────────────────────────────────────
    @classmethod
    def _cfg_path(cls):
        try:
            acc = bcenv.steam_account_id()
        except Exception:
            acc = "default"
        return os.path.expanduser(f"~/.config/bonecast-{acc}.json")

    @classmethod
    def _load_cfg(cls):
        try:
            with open(cls._cfg_path()) as f:
                return load(f)
        except Exception:
            return {}

    @classmethod
    def _save_cfg(cls, cfg):
        p = cls._cfg_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            dump(cfg, f)
        os.chmod(p, 0o600)     # tokens + clé = secrets

    @classmethod
    async def get_config(cls):
        """État exposé au frontend — JAMAIS de token/clé en clair."""
        cfg = cls._load_cfg()
        oauth = cfg.get("oauth") or {}
        yt = cfg.get("youtube") or {}
        ov = cls._overlay_proc
        ov_on = ov is not None and ov.returncode is None
        ov_pf = cls._overlay_platform if ov_on else None
        return {
            "logged_in": bool(oauth.get("access_token")),
            "login": oauth.get("login", ""),
            "key_set": bool(cfg.get("key")),
            "title": cfg.get("title", ""),
            "game_name": cfg.get("game_name", ""),
            # Chaîne de l'overlay : override manuel sinon = ta propre chaîne (login OAuth).
            "channel": cfg.get("channel") or oauth.get("login", ""),
            "overlay_on": ov_pf == "twitch",
            "overlay_platform": ov_pf,
            "overlay": {**cls._OVERLAY_DEFAULTS, **(cfg.get("overlay") or {})},
            "watching": cls._watch_proc is not None and cls._watch_proc.returncode is None,
            "watch": {**cls._WATCH_DEFAULTS, **(cfg.get("watch") or {})},
            "streaming": cls._stream_proc is not None
            and cls._stream_proc.returncode is None,
            "stream": {**cls._STREAM_DEFAULTS, **(cfg.get("stream") or {})},
            "steamcord": cls._steamcord_present(),
            "platform": cls._stream_platform if (cls._stream_proc is not None
                                                 and cls._stream_proc.returncode is None) else None,
            "youtube": {
                "login_available": cls._yt_login_available(),
                "logged_in": bool((yt.get("oauth") or {}).get("access_token")),
                "channel": yt.get("channel_title", ""),
                "key_set": bool(yt.get("key")),
                "title": yt.get("title", ""),
                "privacy": yt.get("privacy") if yt.get("privacy") in cls._YT_PRIVACY else "public",
                "latency": yt.get("latency") if yt.get("latency") in cls._YT_LATENCY else "normal",
                "stream": {**cls._STREAM_DEFAULTS, **(yt.get("stream") or {})},
                "chat_channel": yt.get("chat_channel", ""),
                "chat_source": cls._yt_chat_source(cfg),
                "can_send": bool((yt.get("oauth") or {}).get("access_token")),
                "overlay_on": ov_pf == "youtube",
                "overlay": {**cls._OVERLAY_DEFAULTS, **(yt.get("overlay") or {})},
            },
        }

    @staticmethod
    def _steamcord_present():
        """Steamcord installé ? → active l'option « son Discord dans le stream »."""
        return os.path.isdir(os.path.expanduser("~/homebrew/plugins/Steamcord"))

    # ── HTTP ────────────────────────────────────────────────────────────────
    @classmethod
    async def _http(cls, method, url, *, headers=None, data=None,
                    params=None, json_body=None):
        import aiohttp
        from json import loads
        conn = aiohttp.TCPConnector(ssl=_ssl_context())
        async with aiohttp.ClientSession(connector=conn) as s:
            async with s.request(method, url, headers=headers, data=data,
                                 params=params, json=json_body) as r:
                txt = await r.text()
                try:
                    body = loads(txt) if txt else {}
                except Exception:
                    body = {"raw": txt}
                return r.status, body

    # ── OAuth device flow ───────────────────────────────────────────────────
    @classmethod
    async def _store_tokens(cls, tok):
        cfg = cls._load_cfg()
        oauth = cfg.get("oauth") or {}
        oauth["access_token"] = tok["access_token"]
        if tok.get("refresh_token"):
            oauth["refresh_token"] = tok["refresh_token"]
        oauth["expires_at"] = time() + int(tok.get("expires_in", 3600))
        st, v = await cls._http(
            "GET", "https://id.twitch.tv/oauth2/validate",
            headers={"Authorization": f"Bearer {tok['access_token']}"})
        if st == 200:
            oauth["user_id"] = v.get("user_id", "")
            oauth["login"] = v.get("login", "")
            oauth["scopes"] = v.get("scopes", [])
        cfg["oauth"] = oauth
        cls._save_cfg(cfg)
        try:
            await cls.fetch_stream_key()
        except Exception as e:
            logger.warning(f"[twitch] fetch key: {e!r}")

    @classmethod
    async def auth_start(cls):
        """Démarre le device flow → code à saisir sur twitch.tv/activate."""
        try:
            st, body = await cls._http(
                "POST", "https://id.twitch.tv/oauth2/device",
                data={"client_id": cls._TWITCH_CLIENT_ID, "scopes": cls._TWITCH_SCOPES})
            if st != 200 or "device_code" not in body:
                return {"ok": False, "error": body.get("message") or f"http {st}"}
            cls._tw_device = {
                "device_code": body["device_code"],
                "interval": int(body.get("interval", 5)),
                "expires_at": time() + int(body.get("expires_in", 1800)),
            }
            return {"ok": True, "user_code": body["user_code"],
                    "verification_uri": body.get("verification_uri")
                    or "https://www.twitch.tv/activate",
                    "interval": int(body.get("interval", 5))}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @classmethod
    async def auth_poll(cls):
        """Poll-é par le frontend : 'pending' jusqu'à l'autorisation, puis 'ok'."""
        dev = cls._tw_device
        if not dev:
            return {"status": "idle"}
        if time() > dev["expires_at"]:
            cls._tw_device = None
            return {"status": "expired"}
        try:
            st, body = await cls._http(
                "POST", "https://id.twitch.tv/oauth2/token",
                data={"client_id": cls._TWITCH_CLIENT_ID,
                      "scopes": cls._TWITCH_SCOPES,
                      "device_code": dev["device_code"],
                      "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
            if st == 200 and body.get("access_token"):
                cls._tw_device = None
                await cls._store_tokens(body)
                cfg = cls._load_cfg()
                return {"status": "ok", "login": (cfg.get("oauth") or {}).get("login", "")}
            msg = str(body.get("message", "")).lower()
            if "expired" in msg:
                cls._tw_device = None
                return {"status": "expired"}
            if "denied" in msg:
                cls._tw_device = None
                return {"status": "denied"}
            return {"status": "pending"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @classmethod
    async def logout(cls):
        try:
            cfg = cls._load_cfg()
            cfg.pop("oauth", None)
            cfg.pop("key", None)
            cls._save_cfg(cfg)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Helix ────────────────────────────────────────────────────────────────
    @classmethod
    async def _bearer(cls):
        cfg = cls._load_cfg()
        oauth = cfg.get("oauth") or {}
        at = oauth.get("access_token")
        if not at:
            return None
        if time() < oauth.get("expires_at", 0) - 60:
            return at
        rt = oauth.get("refresh_token")
        if not rt:
            return None
        st, body = await cls._http(
            "POST", "https://id.twitch.tv/oauth2/token",
            data={"client_id": cls._TWITCH_CLIENT_ID,
                  "grant_type": "refresh_token", "refresh_token": rt})
        if st == 200 and body.get("access_token"):
            await cls._store_tokens(body)
            return body["access_token"]
        return None

    @classmethod
    async def _api(cls, method, path, *, params=None, json_body=None):
        at = await cls._bearer()
        if not at:
            return None, {"error": "not_logged_in"}
        headers = {"Authorization": f"Bearer {at}", "Client-Id": cls._TWITCH_CLIENT_ID}
        return await cls._http(method, "https://api.twitch.tv/helix/" + path,
                               headers=headers, params=params, json_body=json_body)

    @classmethod
    def _broadcaster_id(cls):
        return (cls._load_cfg().get("oauth") or {}).get("user_id", "")

    @classmethod
    async def get_followed_live(cls):
        """Retourne les lives des chaînes suivies, rafraîchis à la demande.

        L'endpoint Helix est paginé : on le parcourt entièrement plutôt que de
        masquer les lives au-delà de la première centaine. Seules les données
        utiles au QAM sont renvoyées, jamais le token OAuth.
        """
        cfg = cls._load_cfg()
        oauth = cfg.get("oauth") or {}
        if not oauth.get("access_token") or not oauth.get("user_id"):
            return {"ok": False, "error": "not_logged_in"}
        if "user:read:follows" not in (oauth.get("scopes") or []):
            return {"ok": False, "error": "missing_follow_scope"}
        lives, after = [], None
        # Une limite haute protège le QAM d'une réponse anormalement paginée,
        # tout en couvrant largement plus que les lives suivis usuels.
        for _page in range(20):
            params = {"user_id": oauth["user_id"], "first": 100}
            if after:
                params["after"] = after
            status, body = await cls._api("GET", "streams/followed", params=params)
            if status != 200:
                logger.warning(f"[watch] followed lives failed: http {status} {body!r}")
                if status in (401, 403):
                    return {"ok": False, "error": "missing_follow_scope"}
                return {"ok": False, "error": "followed_live_failed"}
            for stream in (body or {}).get("data") or []:
                login = str(stream.get("user_login") or "").lower()
                if login:
                    lives.append({
                        "login": login,
                        "name": stream.get("user_name") or login,
                        "title": stream.get("title") or "",
                        "game": stream.get("game_name") or "",
                        "viewers": int(stream.get("viewer_count") or 0),
                        # URL modèle Twitch ({width}×{height}), rendue par le
                        # frontend à une taille légère adaptée au QAM.
                        "thumbnail": stream.get("thumbnail_url") or "",
                    })
            after = ((body or {}).get("pagination") or {}).get("cursor")
            if not after:
                break
        return {"ok": True, "streams": lives}

    @classmethod
    async def fetch_stream_key(cls):
        """Récupère la clé de stream via l'API → cfg['key'] (jamais renvoyée au front)."""
        bid = cls._broadcaster_id()
        if not bid:
            return None
        st, body = await cls._api("GET", "streams/key", params={"broadcaster_id": bid})
        data = (body or {}).get("data") or []
        if st == 200 and data and data[0].get("stream_key"):
            cfg = cls._load_cfg()
            cfg["key"] = data[0]["stream_key"]
            cls._save_cfg(cfg)
            return cfg["key"]
        return None

    @classmethod
    async def _resolve_game(cls, name):
        name = (name or "").strip()
        if not name:
            return cls._TWITCH_JUST_CHATTING
        st, body = await cls._api("GET", "games", params={"name": name})
        data = (body or {}).get("data") or []
        return data[0].get("id") if data else None

    @classmethod
    async def update_channel(cls, title=None, game_name=None):
        """MAJ titre et/ou catégorie (PATCH /helix/channels) — marche en direct."""
        bid = cls._broadcaster_id()
        if not bid:
            return {"ok": False, "error": "not_logged_in"}
        cfg = cls._load_cfg()
        payload = {}
        if title is not None:
            payload["title"] = str(title)[:140]
            cfg["title"] = payload["title"]
        if game_name is not None:
            gid = await cls._resolve_game(game_name)
            cfg["game_name"] = game_name
            if gid:
                payload["game_id"] = gid   # sinon jeu absent du catalogue → on garde l'ancienne
        cls._save_cfg(cfg)
        if not payload:
            return {"ok": True, "no_change": True}
        st, body = await cls._api("PATCH", "channels",
                                  params={"broadcaster_id": bid}, json_body=payload)
        if st in (200, 204):
            return {"ok": True, "game_matched": "game_id" in payload}
        return {"ok": False, "error": (body or {}).get("message") or f"http {st}"}

    @classmethod
    async def set_title(cls, title: str = ""):
        return await cls.update_channel(title=title)

    @classmethod
    async def set_game(cls, game_name: str = ""):
        return await cls.update_channel(game_name=game_name)

    # ── YouTube ──────────────────────────────────────────────────────────────
    # Même modèle que Twitch : connexion par code (google.com/device), puis la
    # clé de stream et le live sont créés par l'API. La clé MANUELLE reste en
    # secours : tant que Google n'a pas vérifié l'appli, la connexion est
    # plafonnée (comptes de test) et les jetons expirent au bout de 7 jours.
    #
    # Client « TV et appareils à saisie limitée » : Google exige le secret dans
    # ce flux, mais le déclare lui-même non confidentiel pour ce type de client
    # (il est embarqué dans chaque appli de TV). Vide = connexion masquée.
    _YT_CLIENT_ID = "617671992109-u15vhd4phh25qgjnnp0j20ej42i39b1h.apps.googleusercontent.com"
    _YT_CLIENT_SECRET = "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"
    _YT_SCOPE = "https://www.googleapis.com/auth/youtube"
    _YT_INGEST = "rtmp://a.rtmp.youtube.com/live2"
    _YT_API = "https://www.googleapis.com/youtube/v3/"
    _YT_GAMING = "20"                          # catégorie « Jeux vidéo »
    _YT_PRIVACY = ("public", "unlisted", "private")
    # contentDetails.latencyPreference de liveBroadcasts. « normal » ≈ 20 s de
    # retard (mesuré par dreemur-e, #1) ; ultraLow ≈ 5 s mais YouTube y coupe
    # certaines options (sous-titres, 1440p et plus). Défaut YouTube = normal.
    _YT_LATENCY = ("normal", "low", "ultraLow")
    _yt_device = None

    @classmethod
    def _yt_cfg(cls, cfg=None):
        cfg = cfg if cfg is not None else cls._load_cfg()
        return cfg.setdefault("youtube", {})

    @classmethod
    def _yt_login_available(cls):
        return bool(cls._YT_CLIENT_ID and cls._YT_CLIENT_SECRET)

    @classmethod
    async def yt_auth_start(cls):
        if not cls._yt_login_available():
            return {"ok": False, "error": "login_unavailable"}
        try:
            st, body = await cls._http(
                "POST", "https://oauth2.googleapis.com/device/code",
                data={"client_id": cls._YT_CLIENT_ID, "scope": cls._YT_SCOPE})
            if st != 200 or "device_code" not in body:
                return {"ok": False, "error": body.get("error_description")
                        or body.get("error") or f"http {st}"}
            cls._yt_device = {
                "device_code": body["device_code"],
                "interval": int(body.get("interval", 5)),
                "expires_at": time() + int(body.get("expires_in", 1800)),
            }
            return {"ok": True, "user_code": body["user_code"],
                    "verification_uri": body.get("verification_url")
                    or "https://www.google.com/device"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @classmethod
    async def yt_auth_poll(cls):
        dev = cls._yt_device
        if not dev:
            return {"status": "idle"}
        if time() > dev["expires_at"]:
            cls._yt_device = None
            return {"status": "expired"}
        try:
            st, body = await cls._http(
                "POST", "https://oauth2.googleapis.com/token",
                data={"client_id": cls._YT_CLIENT_ID,
                      "client_secret": cls._YT_CLIENT_SECRET,
                      "device_code": dev["device_code"],
                      "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
            if st == 200 and body.get("access_token"):
                cls._yt_device = None
                await cls._yt_store_tokens(body)
                return {"status": "ok", "login": cls._yt_cfg().get("channel_title", "")}
            err = str(body.get("error", ""))
            if err == "expired_token":
                cls._yt_device = None
                return {"status": "expired"}
            if err == "access_denied":
                cls._yt_device = None
                return {"status": "denied"}
            return {"status": "pending"}       # authorization_pending / slow_down
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @classmethod
    async def _yt_store_tokens(cls, tok):
        cfg = cls._load_cfg()
        yt = cls._yt_cfg(cfg)
        oauth = yt.get("oauth") or {}
        oauth["access_token"] = tok["access_token"]
        if tok.get("refresh_token"):
            oauth["refresh_token"] = tok["refresh_token"]
        oauth["expires_at"] = time() + int(tok.get("expires_in", 3600))
        yt["oauth"] = oauth
        cls._save_cfg(cfg)
        # Nom de la chaîne, pour l'afficher comme « @login » côté Twitch.
        st, body = await cls._yt_api("GET", "channels",
                                     params={"part": "snippet", "mine": "true"})
        items = (body or {}).get("items") or []
        if st == 200 and items:
            sn = items[0].get("snippet") or {}
            cfg = cls._load_cfg()
            yt = cls._yt_cfg(cfg)
            yt["channel_title"] = sn.get("title", "")
            yt["channel_id"] = items[0].get("id", "")
            yt["channel_handle"] = sn.get("customUrl", "")
            cls._save_cfg(cfg)

    @classmethod
    async def yt_logout(cls):
        cfg = cls._load_cfg()
        yt = cls._yt_cfg(cfg)
        for k in ("oauth", "channel_title", "channel_handle", "channel_id", "stream_id",
                  "api_key", "api_ingest", "broadcast_id", "live_chat_id"):
            yt.pop(k, None)
        cls._save_cfg(cfg)
        return {"ok": True}

    @classmethod
    async def _yt_bearer(cls):
        oauth = cls._yt_cfg().get("oauth") or {}
        at = oauth.get("access_token")
        if not at:
            return None
        if time() < oauth.get("expires_at", 0) - 60:
            return at
        rt = oauth.get("refresh_token")
        if not rt:
            return None
        st, body = await cls._http(
            "POST", "https://oauth2.googleapis.com/token",
            data={"client_id": cls._YT_CLIENT_ID,
                  "client_secret": cls._YT_CLIENT_SECRET,
                  "grant_type": "refresh_token", "refresh_token": rt})
        if st == 200 and body.get("access_token"):
            cfg = cls._load_cfg()
            o = cls._yt_cfg(cfg).setdefault("oauth", {})
            o["access_token"] = body["access_token"]
            o["expires_at"] = time() + int(body.get("expires_in", 3600))
            cls._save_cfg(cfg)
            return body["access_token"]
        if (body or {}).get("error") == "invalid_grant":
            # Jeton révoqué ou expiré (7 jours en mode test chez Google) :
            # on se déconnecte proprement plutôt que d'échouer à chaque live.
            logger.info("[youtube] refresh refusé (invalid_grant) — déconnexion")
            await cls.yt_logout()
        return None

    @classmethod
    async def _yt_api(cls, method, path, *, params=None, json_body=None):
        at = await cls._yt_bearer()
        if not at:
            return None, {"error": "not_logged_in"}
        return await cls._http(method, cls._YT_API + path,
                               headers={"Authorization": f"Bearer {at}"},
                               params=params, json_body=json_body)

    @staticmethod
    def _yt_error(body, st):
        err = (body or {}).get("error")
        if isinstance(err, dict):
            reason = ((err.get("errors") or [{}])[0]).get("reason") or ""
            return reason or err.get("message") or f"http {st}"
        return str(err or f"http {st}")

    @classmethod
    async def _yt_ensure_stream(cls):
        """Flux d'ingestion réutilisable → (clé, url d'ingestion), créé une fois."""
        yt = cls._yt_cfg()
        sid = yt.get("stream_id")
        if sid:
            st, body = await cls._yt_api("GET", "liveStreams",
                                         params={"part": "cdn", "id": sid})
            items = (body or {}).get("items") or []
            if st == 200 and items:
                ing = (items[0].get("cdn") or {}).get("ingestionInfo") or {}
                if ing.get("streamName"):
                    return ing["streamName"], ing.get("ingestionAddress") or cls._YT_INGEST
        st, body = await cls._yt_api(
            "POST", "liveStreams", params={"part": "snippet,cdn,contentDetails"},
            json_body={"snippet": {"title": "BoneCast"},
                       "cdn": {"ingestionType": "rtmp", "resolution": "variable",
                               "frameRate": "variable"},
                       "contentDetails": {"isReusable": True}})
        if st not in (200, 201):
            raise RuntimeError(cls._yt_error(body, st))
        ing = (body.get("cdn") or {}).get("ingestionInfo") or {}
        cfg = cls._load_cfg()
        y = cls._yt_cfg(cfg)
        y["stream_id"] = body.get("id")
        cls._save_cfg(cfg)
        return ing.get("streamName"), ing.get("ingestionAddress") or cls._YT_INGEST

    @classmethod
    async def _yt_create_broadcast(cls):
        """Crée le live (titre, visibilité), démarrage/arrêt auto, lié au flux."""
        cfg = cls._load_cfg()
        yt = cls._yt_cfg(cfg)
        title = (yt.get("title") or "").strip() or "BoneCast live"
        privacy = yt.get("privacy") if yt.get("privacy") in cls._YT_PRIVACY else "public"
        latency = yt.get("latency") if yt.get("latency") in cls._YT_LATENCY else "normal"
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        st, body = await cls._yt_api(
            "POST", "liveBroadcasts", params={"part": "snippet,status,contentDetails"},
            json_body={"snippet": {"title": title[:100], "scheduledStartTime": now},
                       "status": {"privacyStatus": privacy,
                                  "selfDeclaredMadeForKids": False},
                       # autoStart : YouTube passe le live à l'antenne dès que
                       # le flux arrive ; pas de phase « test » sans moniteur.
                       "contentDetails": {"latencyPreference": latency,
                                          "enableAutoStart": True,
                                          "enableAutoStop": cls._resume_window() < 60,
                                          "monitorStream": {"enableMonitorStream": False}}})
        if st not in (200, 201):
            raise RuntimeError(cls._yt_error(body, st))
        bid = body.get("id")
        sid = yt.get("stream_id")
        st, b2 = await cls._yt_api("POST", "liveBroadcasts/bind",
                                   params={"part": "id", "id": bid, "streamId": sid})
        if st != 200:
            raise RuntimeError(cls._yt_error(b2, st))
        cfg = cls._load_cfg()
        y = cls._yt_cfg(cfg)
        y["broadcast_id"] = bid
        y["live_chat_id"] = (body.get("snippet") or {}).get("liveChatId", "")
        cls._save_cfg(cfg)
        cls._yt_write_live_hint(y.get("channel_id", ""), bid)
        # Catégorie « Jeux vidéo » : l'API ne permet pas de choisir le jeu.
        await cls._yt_api("PUT", "videos", params={"part": "snippet"},
                          json_body={"id": bid, "snippet": {"title": title[:100],
                                                            "categoryId": cls._YT_GAMING}})
        return bid

    @classmethod
    def _yt_schedule_end(cls, delay):
        """Termine le live YouTube dans `delay` s, sauf reprise d'ici là. L'échéance
        est aussi écrite dans la config : après un redémarrage, _main la reprend."""
        from asyncio import sleep
        if cls._yt_end_task is not None:
            cls._yt_end_task.cancel()
        cfg = cls._load_cfg()
        if not cls._yt_cfg(cfg).get("broadcast_id"):
            return
        cls._yt_cfg(cfg)["broadcast_end_at"] = int(time() + delay)
        cls._save_cfg(cfg)

        async def _later():
            await sleep(delay)
            cls._yt_end_task = None
            if cls._stream_platform == "youtube" or (cls._resume or {}).get("platform") == "youtube":
                return                           # repris entre-temps
            logger.info("[youtube] pas de reprise → live terminé")
            await cls._yt_end_broadcast()
        cls._yt_end_task = create_task(_later())

    @classmethod
    async def _yt_reuse_broadcast(cls):
        """Un live YouTube de cette session est encore ouvert (coupure, Arrêter par
        erreur, redémarrage) → on le reprend au lieu d'en créer un nouveau."""
        bid = cls._yt_cfg().get("broadcast_id")
        if not bid:
            return False
        try:
            st, body = await cls._yt_api("GET", "liveBroadcasts",
                                         params={"part": "status", "id": bid})
            items = (body or {}).get("items") or [] if st == 200 else []
            life = ((items[0].get("status") or {}).get("lifeCycleStatus") if items else None)
        except Exception as e:
            logger.warning(f"[youtube] état du live précédent: {e!r}")
            life = None
        if life in ("ready", "testStarting", "testing", "liveStarting", "live"):
            if cls._yt_end_task is not None:
                cls._yt_end_task.cancel()
                cls._yt_end_task = None
            cfg = cls._load_cfg()
            cls._yt_cfg(cfg).pop("broadcast_end_at", None)
            cls._save_cfg(cfg)
            logger.info(f"[youtube] reprise du live {bid} ({life})")
            return True
        logger.info(f"[youtube] live précédent {bid} non repris ({life})")
        await cls._yt_end_broadcast()            # range broadcast_id / indice du chat
        return False

    @classmethod
    async def _yt_end_broadcast(cls):
        """Termine le live côté YouTube (l'arrêt auto prend sinon ~1 min)."""
        if cls._yt_end_task is not None and cls._yt_end_task is not _current_task():
            cls._yt_end_task.cancel()
        cls._yt_end_task = None
        bid = cls._yt_cfg().get("broadcast_id")
        if not bid:
            return
        try:
            await cls._yt_api("POST", "liveBroadcasts/transition",
                              params={"part": "id", "id": bid, "broadcastStatus": "complete"})
        except Exception:
            pass
        cfg = cls._load_cfg()
        cls._yt_cfg(cfg).pop("broadcast_id", None)
        cls._yt_cfg(cfg).pop("broadcast_end_at", None)
        cls._save_cfg(cfg)
        cls._yt_write_live_hint("", "")

    # Un live privé ou non répertorié n'apparaît PAS sur /channel/<id>/live :
    # l'overlay attendait à l'infini (test 29/09). On lui donne l'ID de la vidéo
    # qu'on vient de créer ; yt_chat.py relit ce fichier à chaque tentative, donc
    # un overlay ouvert avant le live le trouve aussi. Vide = plus de live.
    _YT_LIVE_HINT = "/tmp/bonecast-yt-live.json"

    @classmethod
    def _yt_write_live_hint(cls, channel_id, video_id):
        try:
            if not video_id:
                if os.path.exists(cls._YT_LIVE_HINT):
                    os.remove(cls._YT_LIVE_HINT)
                return
            with open(cls._YT_LIVE_HINT, "w") as f:
                dump({"channel": channel_id, "video": video_id}, f)
        except Exception as e:
            logger.warning(f"[youtube] live hint: {e!r}")

    @classmethod
    def _yt_chat_source(cls, cfg=None):
        """Chaîne dont l'overlay lit le chat : saisie manuelle, sinon sa propre
        chaîne quand on est connecté (comme pour Twitch)."""
        yt = (cfg if cfg is not None else cls._load_cfg()).get("youtube") or {}
        return (yt.get("chat_channel") or yt.get("channel_id") or "").strip()

    @classmethod
    async def yt_send_chat(cls, message: str = ""):
        """Message dans le chat de SON live YouTube (connexion requise)."""
        message = (message or "").strip()
        if not message:
            return {"ok": False, "error": "empty"}
        yt = cls._yt_cfg()
        if not (yt.get("oauth") or {}).get("access_token"):
            return {"ok": False, "error": "not_logged_in"}
        chat_id = yt.get("live_chat_id")
        if not chat_id or cls._stream_platform != "youtube":
            return {"ok": False, "error": "not_live"}
        st, body = await cls._yt_api(
            "POST", "liveChat/messages", params={"part": "snippet"},
            json_body={"snippet": {"liveChatId": chat_id, "type": "textMessageEvent",
                                   "textMessageDetails": {"messageText": message[:200]}}})
        if st in (200, 201):
            return {"ok": True}
        return {"ok": False, "error": cls._yt_error(body, st)}

    @classmethod
    async def yt_set_settings(cls, settings=None):
        """Titre, visibilité, clé manuelle (chaîne vide = effacer la clé)."""
        cfg = cls._load_cfg()
        yt = cls._yt_cfg(cfg)
        s = settings if isinstance(settings, dict) else {}
        if isinstance(s.get("title"), str):
            yt["title"] = s["title"].strip()[:100]
        if s.get("privacy") in cls._YT_PRIVACY:
            yt["privacy"] = s["privacy"]
        if s.get("latency") in cls._YT_LATENCY:
            yt["latency"] = s["latency"]
        if isinstance(s.get("chat_channel"), str):
            yt["chat_channel"] = s["chat_channel"].strip()
        if isinstance(s.get("key"), str):
            k = s["key"].strip()
            if k:
                yt["key"] = k
            else:
                yt.pop("key", None)
        cls._save_cfg(cfg)
        title_live = False
        # En direct : le titre part aussi sur le live en cours.
        if "title" in s and cls._stream_platform == "youtube" and yt.get("broadcast_id") \
                and (yt.get("oauth") or {}).get("access_token"):
            st, _ = await cls._yt_api(
                "PUT", "videos", params={"part": "snippet"},
                json_body={"id": yt["broadcast_id"],
                           "snippet": {"title": yt.get("title") or "BoneCast live",
                                       "categoryId": cls._YT_GAMING}})
            title_live = st == 200
        return {"ok": True, "title_live": title_live}

    # ── Overlay chat ─────────────────────────────────────────────────────────
    @classmethod
    def _overlay_state_dir(cls, platform="twitch"):
        try:
            acc = bcenv.steam_account_id()
        except Exception:
            acc = "default"
        sub = "youtube_overlay" if platform == "youtube" else "twitch_overlay"
        return os.path.expanduser(f"~/.local/share/bonecast/{sub}/{acc}")

    @classmethod
    def _overlay_holder(cls, cfg, platform):
        """Réglages d'apparence : ceux de Twitch à la racine, ceux de YouTube à part."""
        return cls._yt_cfg(cfg) if platform == "youtube" else cfg

    @classmethod
    def _write_overlay_state(cls, cfg=None, platform="twitch"):
        cfg = cls._load_cfg() if cfg is None else cfg
        d = cls._overlay_state_dir(platform)
        os.makedirs(d, exist_ok=True)
        st = {**cls._OVERLAY_DEFAULTS, **(cls._overlay_holder(cfg, platform).get("overlay") or {})}
        with open(os.path.join(d, "overlay_state.json"), "w") as f:
            dump(st, f)

    @staticmethod
    def _scope_error(st, body):
        """401/403 Helix = token sans le scope (login antérieur à l'ajout) →
        le front invite à se reconnecter (le device flow re-demande tout)."""
        if st in (401, 403):
            return {"ok": False, "error": "missing_scope",
                    "detail": (body or {}).get("message", "")}
        return None

    @classmethod
    async def create_clip(cls):
        """Clip des ~30 dernières secondes du live (POST /helix/clips)."""
        bid = cls._broadcaster_id()
        if not bid:
            return {"ok": False, "error": "not_logged_in"}
        st, body = await cls._api("POST", "clips", params={"broadcaster_id": bid})
        if err := cls._scope_error(st, body):
            return err
        data = (body or {}).get("data") or []
        if st == 202 and data and data[0].get("id"):
            logger.info(f"[clip] créé: {data[0]['id']}")
            return {"ok": True, "id": data[0]["id"],
                    "edit_url": data[0].get("edit_url", "")}
        # 404 = pas en live (Twitch ne peut clipper qu'un stream actif)
        if st == 404:
            return {"ok": False, "error": "not_live"}
        return {"ok": False, "error": (body or {}).get("message") or f"http {st}"}

    @classmethod
    async def send_chat(cls, message: str = ""):
        """Envoie un message dans SON chat (POST /helix/chat/messages)."""
        message = (message or "").strip()
        if not message:
            return {"ok": False, "error": "empty"}
        bid = cls._broadcaster_id()
        if not bid:
            return {"ok": False, "error": "not_logged_in"}
        st, body = await cls._api(
            "POST", "chat/messages",
            json_body={"broadcaster_id": bid, "sender_id": bid,
                       "message": message[:500]})
        if err := cls._scope_error(st, body):
            return err
        data = (body or {}).get("data") or []
        if st == 200 and data and data[0].get("is_sent"):
            return {"ok": True}
        drop = (data[0].get("drop_reason") or {}) if data else {}
        return {"ok": False,
                "error": drop.get("message") or (body or {}).get("message")
                or f"http {st}"}

    @classmethod
    async def set_channel(cls, channel: str = ""):
        try:
            cfg = cls._load_cfg()
            cfg["channel"] = (channel or "").strip().lstrip("#").lower()
            cls._save_cfg(cfg)
            return {"ok": True, "channel": cfg["channel"]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @classmethod
    async def set_overlay_settings(cls, settings=None, platform="twitch"):
        try:
            cfg = cls._load_cfg()
            holder = cls._overlay_holder(cfg, platform)
            ov = {**cls._OVERLAY_DEFAULTS, **(holder.get("overlay") or {})}
            for k in cls._OVERLAY_DEFAULTS:
                if isinstance(settings, dict) and settings.get(k) is not None:
                    ov[k] = settings[k]
            holder["overlay"] = ov
            cls._save_cfg(cfg)
            cls._write_overlay_state(cfg, platform)   # poll live par chat.html
            return {"ok": True, "overlay": ov}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @classmethod
    async def start_overlay(cls, platform="twitch"):
        # Même course que start_stream (le processus n'existe qu'après l'await
        # de create_subprocess_exec) : un seul overlay, Twitch OU YouTube.
        if cls._start_overlay_lock is None:
            cls._start_overlay_lock = Lock()
        async with cls._start_overlay_lock:
            return await cls._start_overlay_unlocked(platform)

    @classmethod
    async def _start_overlay_unlocked(cls, platform="twitch"):
        platform = "youtube" if platform == "youtube" else "twitch"
        if cls._overlay_proc is not None and cls._overlay_proc.returncode is None:
            if cls._overlay_platform == platform:
                return {"ok": True, "already": True}
            return {"ok": False, "error": "busy", "platform": cls._overlay_platform}
        cfg = cls._load_cfg()
        if platform == "youtube":
            channel = cls._yt_chat_source(cfg)
            extra = ["--platform", "youtube", "--yt-source", channel]
        else:
            # Override manuel sinon = ta propre chaîne (login OAuth) → aucun pseudo à saisir.
            channel = (cfg.get("channel") or (cfg.get("oauth") or {}).get("login") or "").strip()
            extra = ["--channel", channel]
        if not channel:
            return {"ok": False, "error": "no_channel"}
        from asyncio import create_subprocess_exec
        from subprocess import PIPE
        script = Path(DECKY_PLUGIN_DIR) / "twitch_overlay" / "overlay.py"
        if not script.exists():
            script = Path(DECKY_PLUGIN_DIR) / "defaults" / "twitch_overlay" / "overlay.py"
        d = cls._overlay_state_dir(platform)
        cls._write_overlay_state(cfg, platform)
        try:
            # Base = user_env() DIRECTEMENT (pas de .update() sur os.environ :
            # update ne peut pas RETIRER le LD_LIBRARY_PATH PyInstaller, et ce
            # /tmp/_MEI* casse libcurl/gio dans WebKit).
            try:
                env = dict(bcenv.user_env())
            except Exception:
                env = dict(os.environ)
            try:
                # DISPLAY/XAUTHORITY de la vraie session (env plugin_loader = pas
                # de cookie X → « Authorization required » et GTK meurt).
                env.update(bcenv.steam_display_env())
            except Exception:
                pass
            env.setdefault("DISPLAY", ":0")     # XWayland gamescope (over-game) ou KWin
            cls._overlay_proc = await create_subprocess_exec(
                "/usr/bin/python3", str(script), *extra, "--state-dir", d,
                env=env, stdout=PIPE, stderr=PIPE)
            cls._overlay_platform = platform
            create_task(stream_watcher(cls._overlay_proc.stdout, prefix="[overlay]"))
            create_task(stream_watcher(cls._overlay_proc.stderr, True, prefix="[overlay]"))
            logger.info(f"[overlay] démarré ({platform}: {channel})")
            if platform == "twitch":
                cls._start_follows(d, cls._overlay_proc)
            return {"ok": True}
        except Exception as e:
            logger.warning(f"[overlay] start failed: {e!r}")
            return {"ok": False, "error": str(e)}

    # ── Nouveaux followers Twitch → overlay ────────────────────────────────
    # Les follows ne passent PAS par l'IRC (contrairement aux subs/raids/bits) :
    # Helix /channels/followers, lu toutes les 15 s tant que l'overlay Twitch
    # tourne. Le 1er appel sert de référence (pas de rafale d'anciens follows),
    # la suite est écrite dans follows.json, que chat.html relit comme son
    # fichier de réglages. Sans le scope (login antérieur) : rien, et le QAM
    # propose de se reconnecter.
    _follows_task = None
    _FOLLOWS_EVERY = 15

    @classmethod
    def _start_follows(cls, d, proc):
        oauth = cls._load_cfg().get("oauth") or {}
        if "moderator:read:followers" not in (oauth.get("scopes") or []):
            return
        if cls._follows_task is not None and not cls._follows_task.done():
            cls._follows_task.cancel()
        cls._follows_task = create_task(cls._follows_loop(d, proc))

    @classmethod
    def _write_follows(cls, d, events):
        path = os.path.join(d, "follows.json")
        try:
            with open(path + ".tmp", "w") as f:
                dump({"events": events}, f)
            os.replace(path + ".tmp", path)
        except Exception as e:
            logger.warning(f"[follows] écriture: {e!r}")

    @classmethod
    async def _follows_loop(cls, d, proc):
        from asyncio import sleep
        bid = cls._broadcaster_id()
        if not bid:
            return
        seen, events = None, []
        cls._write_follows(d, events)
        while cls._overlay_proc is proc and proc.returncode is None:
            try:
                st, body = await cls._api("GET", "channels/followers",
                                          params={"broadcaster_id": bid, "first": 20})
                if st in (401, 403):
                    logger.info(f"[follows] refusé (http {st}) — arrêt")
                    return
                if st == 200:
                    data = (body or {}).get("data") or []
                    if seen is None:
                        seen = {x.get("user_id") for x in data}
                    else:
                        new = [x for x in reversed(data) if x.get("user_id") not in seen]
                        for x in new:
                            seen.add(x.get("user_id"))
                            events.append({"id": x.get("user_id", ""),
                                           "name": x.get("user_name") or x.get("user_login", ""),
                                           "at": x.get("followed_at", "")})
                        if new:
                            events = events[-30:]
                            cls._write_follows(d, events)
            except Exception as e:
                logger.warning(f"[follows] {e!r}")
            await sleep(cls._FOLLOWS_EVERY)

    @classmethod
    async def stop_overlay(cls):
        proc = cls._overlay_proc
        cls._overlay_proc = None
        cls._overlay_platform = None
        if cls._follows_task is not None and not cls._follows_task.done():
            cls._follows_task.cancel()
        cls._follows_task = None
        if proc is not None and proc.returncode is None:
            try:
                proc.terminate()
                from asyncio import wait_for
                try:
                    await wait_for(proc.wait(), timeout=2)
                except Exception:
                    proc.kill()
            except Exception:
                pass
        return {"ok": True}

    @classmethod
    async def get_overlay_status(cls):
        ov = cls._overlay_proc
        on = ov is not None and ov.returncode is None
        return {"overlay_on": on, "platform": cls._overlay_platform if on else None}

    # ── Visionnage Twitch : helper GTK/Cairo au-dessus de gamescope ─────────
    @classmethod
    def _watch_state_dir(cls):
        """État sans secret, relu à chaud par watch_overlay.py."""
        return os.path.expanduser("~/.local/share/bonecast/watch")

    @classmethod
    def _watch_settings(cls, cfg):
        raw = {**cls._WATCH_DEFAULTS, **(cfg.get("watch") or {})}
        # Les logins Twitch ne contiennent que lettres, chiffres et _. Cette
        # validation évite d'écrire des valeurs surprenantes dans le helper.
        import re
        streams = []
        for login in raw.get("streams") or []:
            login = str(login).strip().lower().lstrip("@")
            if re.fullmatch(r"[a-z0-9_]{1,25}", login) and login not in streams:
                streams.append(login)
            if len(streams) == 4:
                break
        return {
            "streams": streams,
            "layout": str(raw.get("layout") or "corner_br"),
            "scale": max(0.4, min(1.6, float(raw.get("scale", 1.0)))),
            "opacity": max(0.15, min(1.0, float(raw.get("opacity", 1.0)))),
            "max_fps": 60 if int(raw.get("max_fps", 30)) >= 60 else 30,
            "audio": str(raw.get("audio") or "").strip().lower().lstrip("@"),
            "volume": max(0.0, min(2.0, float(raw.get("volume", 1.0)))),
        }

    @classmethod
    def _write_watch_state(cls, cfg):
        d = cls._watch_state_dir()
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "state.json")
        tmp = p + ".new"
        with open(tmp, "w") as f:
            dump(cls._watch_settings(cfg), f)
        os.replace(tmp, p)  # le helper ne lit jamais un JSON à moitié écrit

    @classmethod
    async def set_watch_settings(cls, settings=None):
        try:
            cfg = cls._load_cfg()
            watch = {**cls._WATCH_DEFAULTS, **(cfg.get("watch") or {})}
            if isinstance(settings, dict):
                for key in cls._WATCH_DEFAULTS:
                    if key in settings:
                        watch[key] = settings[key]
            cfg["watch"] = watch
            cls._save_cfg(cfg)
            cls._write_watch_state(cfg)
            return {"ok": True, "watch": cls._watch_settings(cfg)}
        except Exception as e:
            logger.warning(f"[watch] settings failed: {e!r}")
            return {"ok": False, "error": str(e)}

    @classmethod
    async def start_watch(cls):
        # Le frontend peut réémettre l'action avant que create_subprocess_exec
        # ait renvoyé son PID. Sans verrou, les deux appels voient `_watch_proc`
        # à None et créent deux fenêtres GTK superposées.
        if cls._watch_start_lock is None:
            cls._watch_start_lock = Lock()
        async with cls._watch_start_lock:
            cfg = cls._load_cfg()
            watch = cls._watch_settings(cfg)
            if not watch["streams"]:
                return {"ok": False, "error": "no_watch_stream"}
            if cls._watch_proc is not None and cls._watch_proc.returncode is None:
                return {"ok": True, "already": True}
            script = Path(DECKY_PLUGIN_DIR) / "watch_overlay.py"
            if not script.exists():
                script = Path(DECKY_PLUGIN_DIR) / "defaults" / "watch_overlay.py"
            if not script.exists():
                return {"ok": False, "error": "watch_helper_missing"}
            cls._write_watch_state(cfg)
            from asyncio import create_subprocess_exec
            from subprocess import PIPE
            try:
                env = dict(bcenv.user_env())
                env.update(bcenv.steam_display_env())
                env.setdefault("DISPLAY", ":0")
                cls._watch_proc = await create_subprocess_exec(
                    sys_python(), str(script), "--state-dir", cls._watch_state_dir(),
                    env=env, stdout=PIPE, stderr=PIPE)
                create_task(stream_watcher(cls._watch_proc.stdout, prefix="[watch]"))
                create_task(stream_watcher(cls._watch_proc.stderr, True, prefix="[watch]"))
                logger.info(f"[watch] démarré : {', '.join(watch['streams'])}")
                return {"ok": True}
            except Exception as e:
                logger.warning(f"[watch] start failed: {e!r}")
                return {"ok": False, "error": str(e)}

    @classmethod
    async def stop_watch(cls):
        proc = cls._watch_proc
        cls._watch_proc = None
        if proc is not None and proc.returncode is None:
            try:
                proc.terminate()
                from asyncio import wait_for
                await wait_for(proc.wait(), timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        return {"ok": True}

    # ── Streaming (RTMP via ffmpeg, images du jeu par un tuyau) ────────────────
    # Le jeu est capturé par gst_camera.py --stdout, qui écrit dans un tuyau lu par ffmpeg
    # (node PipeWire gamescope → seul chemin qui marche en mode jeu, gamescope
    # n'ayant pas de portail) ; ffmpeg le lit + le son du jeu (monitor du sink
    # par défaut), encode h264/aac et pousse en RTMP vers Twitch avec la clé
    # récupérée en OAuth. Réglages par compte Steam dans le cfg.
    @classmethod
    def _gst_environment(cls):
        """Env pour gst_camera.py : user_env (bus/affichage user + purge des LD_*
        PyInstaller) + VAAPI radeonsi."""
        try:
            env = dict(bcenv.user_env())
        except Exception:
            env = dict(os.environ)
        env["GST_VAAPI_ALL_DRIVERS"] = "1"
        env["LIBVA_DRIVER_NAME"] = "radeonsi"
        return env

    @classmethod
    async def _pactl_default(cls, what):
        """`pactl get-default-sink|get-default-source` (env user)."""
        from asyncio import create_subprocess_exec
        from subprocess import PIPE, DEVNULL
        try:
            p = await create_subprocess_exec(
                "pactl", what, stdout=PIPE, stderr=DEVNULL, env=bcenv.user_env())
            out, _ = await p.communicate()
            return out.decode().strip()
        except Exception:
            return ""

    @classmethod
    async def _default_monitor(cls):
        """Nom PulseAudio du monitor du sink par défaut (= son du jeu)."""
        sink = await cls._pactl_default("get-default-sink")
        return f"{sink}.monitor" if sink else "@DEFAULT_MONITOR@"

    @classmethod
    async def _default_source(cls):
        """Source micro par défaut (pour l'option « ajouter le micro »)."""
        src = await cls._pactl_default("get-default-source")
        return src or "@DEFAULT_SOURCE@"

    # ── Détection des encodeurs (matériel VAAPI si dispo, sinon logiciel) ─────
    @classmethod
    async def _vaapi_available(cls):
        """True si ffmpeg peut encoder en H264 matériel (VAAPI) sur ce GPU.
        Testé une fois puis mis en cache. Sur BC-250 (cyan_skillfish) = False
        (pas d'encode matériel) → on reste en logiciel x264."""
        if cls._vaapi_ok is not None:
            return cls._vaapi_ok
        from asyncio import create_subprocess_exec, wait_for
        from subprocess import DEVNULL
        ok = False
        dev = "/dev/dri/renderD128"
        if os.path.exists(dev):
            try:
                p = await create_subprocess_exec(
                    "ffmpeg", "-hide_banner", "-loglevel", "error",
                    "-init_hw_device", f"vaapi=va:{dev}", "-filter_hw_device", "va",
                    "-f", "lavfi", "-i", "testsrc=size=640x480:rate=30",
                    "-vf", "format=nv12,hwupload", "-c:v", "h264_vaapi",
                    "-t", "0.3", "-f", "null", "-",
                    stdout=DEVNULL, stderr=DEVNULL, env=bcenv.user_env())
                ok = (await wait_for(p.wait(), timeout=12)) == 0
            except Exception:
                ok = False
        cls._vaapi_ok = ok
        logger.info(f"[stream] encode matériel VAAPI = {'dispo' if ok else 'indisponible'}")
        return ok

    @classmethod
    async def _nvenc_available(cls):
        """True si ffmpeg peut encoder en H264 matériel NVENC (GPU Nvidia).
        Testé une fois puis mis en cache."""
        if cls._nvenc_ok is not None:
            return cls._nvenc_ok
        from asyncio import create_subprocess_exec, wait_for
        from subprocess import DEVNULL
        ok = False
        try:
            p = await create_subprocess_exec(
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc=size=640x480:rate=30",
                "-c:v", "h264_nvenc", "-t", "0.3", "-f", "null", "-",
                stdout=DEVNULL, stderr=DEVNULL, env=bcenv.user_env())
            ok = (await wait_for(p.wait(), timeout=12)) == 0
        except Exception:
            ok = False
        cls._nvenc_ok = ok
        logger.info(f"[stream] encode matériel NVENC = {'dispo' if ok else 'indisponible'}")
        return ok

    @classmethod
    async def _x264_available(cls):
        """True si le ffmpeg présent embarque libx264 (l'encodeur logiciel du
        fallback). Le `ffmpeg` par défaut de Fedora (ffmpeg-free) ne l'a PAS —
        il faut le ffmpeg complet de RPM Fusion. Testé une fois puis en cache."""
        if cls._x264_ok is not None:
            return cls._x264_ok
        from asyncio import create_subprocess_exec, wait_for
        from subprocess import DEVNULL
        ok = False
        try:
            p = await create_subprocess_exec(
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc=size=64x64:rate=10",
                "-c:v", "libx264", "-t", "0.2", "-f", "null", "-",
                stdout=DEVNULL, stderr=DEVNULL, env=bcenv.user_env())
            ok = (await wait_for(p.wait(), timeout=12)) == 0
        except Exception:
            ok = False
        cls._x264_ok = ok
        logger.info(f"[stream] encode logiciel libx264 = {'dispo' if ok else 'ABSENT (ffmpeg-free ?)'}")
        return ok

    @classmethod
    async def _gst_python_hint(cls):
        """None si le python système a gi + Gst + pipewiresrc (requis par
        gst_camera.py), sinon le hint d'install pour cet OS. Présents sur
        Bazzite/SteamOS, pas sur Arch/Fedora/Debian de base."""
        if cls._gst_py_ok:
            return None
        from asyncio import create_subprocess_exec
        from subprocess import DEVNULL
        try:
            p = await create_subprocess_exec(
                sys_python(), "-c",
                "import gi; gi.require_version('Gst','1.0'); "
                "from gi.repository import Gst; Gst.init(None); "
                "raise SystemExit(0 if Gst.ElementFactory.find('pipewiresrc') else 1)",
                stdout=DEVNULL, stderr=DEVNULL, env=bcenv.user_env())
            if (await p.wait()) == 0:
                cls._gst_py_ok = True
                return None
        except Exception:
            pass
        return ("GStreamer/PipeWire Python bindings missing for the game capture: "
                + cls._pkg_hint("python-gobject gst-plugin-pipewire",
                                "python3-gobject pipewire-gstreamer",
                                "python3-gi gir1.2-gstreamer-1.0 gstreamer1.0-pipewire"))

    @classmethod
    async def get_encoders(cls):
        """Liste des encodeurs utilisables + recommandation (pour le QAM).
        Ordre de préférence matériel : NVENC (Nvidia) > VAAPI (AMD/Intel) > x264."""
        nv = await cls._nvenc_available()
        va = await cls._vaapi_available()
        x2 = await cls._x264_available()
        avail = ["software"]
        if nv:
            avail.append("nvenc")
        if va:
            avail.append("vaapi")
        rec = "nvenc" if nv else ("vaapi" if va else "software")
        return {"available": avail, "nvenc": nv, "vaapi": va, "x264": x2,
                "recommended": rec}

    @classmethod
    async def set_stream_settings(cls, settings=None, platform="twitch"):
        """Persiste les réglages de qualité/encodeur (par compte ET par plateforme :
        Twitch et YouTube ont chacun les leurs, rien n'est partagé entre eux)."""
        cfg = cls._load_cfg()
        holder = cls._yt_cfg(cfg) if platform == "youtube" else cfg
        st = {**cls._STREAM_DEFAULTS, **(holder.get("stream") or {})}
        if isinstance(settings, dict):
            for k in cls._STREAM_DEFAULTS:
                if settings.get(k) is not None:
                    st[k] = settings[k]
        holder["stream"] = st
        cls._save_cfg(cfg)
        return {"ok": True, "stream": st}

    # ── Pont audio Discord ───────────────────────────────────────────────────
    # Sur un système à sink unique, jeu ET Discord jouent sur la même sortie →
    # impossible de les séparer via le monitor. On isole donc Vesktop dans un
    # null-sink `bonecast_discord` (+ loopback vers la vraie sortie pour que
    # l'user entende toujours Discord) → le sink par défaut ne contient plus que
    # le jeu. Le stream capture le jeu seul, et ajoute le monitor Discord en
    # amix seulement si la case « son Discord » est cochée.
    @classmethod
    async def _pactl(cls, *args, want_json=False):
        from asyncio import create_subprocess_exec
        from subprocess import PIPE, DEVNULL
        pre = ("-f", "json") if want_json else ()
        p = await create_subprocess_exec(
            "pactl", *pre, *args, stdout=PIPE, stderr=DEVNULL, env=bcenv.user_env())
        out, _ = await p.communicate()
        return out.decode()

    @staticmethod
    def _is_vesktop_stream(s):
        props = s.get("properties", {}) or {}
        blob = " ".join(str(v) for v in props.values()).lower()
        return ("vesktop" in blob) or ("discord" in blob) or ("electron" in blob)

    @classmethod
    async def _sink_index(cls, name):
        from json import loads
        try:
            for s in loads(await cls._pactl("list", "sinks", want_json=True) or "[]"):
                if s.get("name") == name:
                    return s.get("index")
        except Exception:
            pass
        return None

    @classmethod
    async def _source_index(cls, name):
        from json import loads
        try:
            for s in loads(await cls._pactl("list", "sources", want_json=True) or "[]"):
                if s.get("name") == name:
                    return s.get("index")
        except Exception:
            pass
        return None

    @classmethod
    async def _move_vesktop(cls, target):
        """Déplace les flux Vesktop vers `target`, mais SEULEMENT ceux qui n'y sont
        pas déjà (un move idempotent toutes les 4 s glitcherait l'audio Discord)."""
        from json import loads
        try:
            tgt_idx = await cls._sink_index(target)
            for si in loads(await cls._pactl("list", "sink-inputs", want_json=True) or "[]"):
                if cls._is_vesktop_stream(si) and si.get("sink") != tgt_idx:
                    await cls._pactl("move-sink-input", str(si.get("index")), target)
        except Exception as e:
            logger.warning(f"[audio] move vesktop → {target}: {e!r}")

    @classmethod
    async def _audio_bridge_cleanup(cls):
        """Décharge tout résidu de pont (survit à un restart plugin_loader).
        NB : `pactl list modules -f json` n'a pas d'index fiable → format court."""
        try:
            out = await cls._pactl("list", "short", "modules")
            for line in out.splitlines():
                if cls._DISCORD_SINK in line:
                    idx = line.split("\t", 1)[0].strip()
                    if idx.isdigit():
                        await cls._pactl("unload-module", idx)
        except Exception:
            pass
        cls._ba_modules = []

    @classmethod
    async def _audio_bridge_start(cls):
        """Isole Vesktop dans bonecast_discord ; renvoie le monitor Discord."""
        from asyncio import create_task, sleep
        cls._ba_real_sink = (await cls._pactl("get-default-sink")).strip()
        await cls._audio_bridge_cleanup()
        m1 = (await cls._pactl("load-module", "module-null-sink",
              f"sink_name={cls._DISCORD_SINK}",
              "sink_properties=device.description=BoneCast-Discord")).strip()
        # ⚠️ « source=<sink>.monitor » seul NE SUFFIT PAS : WirePlumber voit une
        # cible de type sortie pour un flux de capture et se rabat sur le monitor
        # de la sortie PAR DÉFAUT = le casque → casque renvoyé dans le casque avec
        # 60 ms de retard = écho infini pendant tout le live (mesuré 01/10,
        # pw-link). stream.capture.sink + dont_move = le bon monitor, et jamais
        # de repli sur un autre.
        m2 = (await cls._pactl("load-module", "module-loopback",
              f"source={cls._DISCORD_SINK}.monitor", "source_dont_move=true",
              "source_input_properties=stream.capture.sink=true",
              f"sink={cls._ba_real_sink}", "latency_msec=60")).strip()
        cls._ba_modules = [m for m in (m1, m2) if m.isdigit()]
        await cls._move_vesktop(cls._DISCORD_SINK)

        async def _watch():
            while True:
                await sleep(4)
                await cls._move_vesktop(cls._DISCORD_SINK)
        cls._ba_watch = create_task(_watch())
        return f"{cls._DISCORD_SINK}.monitor"

    @classmethod
    async def _audio_bridge_stop(cls):
        if cls._ba_watch is not None:
            try:
                cls._ba_watch.cancel()
            except Exception:
                pass
            cls._ba_watch = None
        if cls._ba_real_sink:                    # remet Vesktop sur la vraie sortie
            await cls._move_vesktop(cls._ba_real_sink)
        for m in list(cls._ba_modules):
            try:
                await cls._pactl("unload-module", m)
            except Exception:
                pass
        cls._ba_modules = []
        cls._ba_real_sink = None

    @classmethod
    async def _capture_size(cls, w, h):
        """Taille à laquelle le feeder capture : 720p/800p/1080p telles quelles ;
        « source » (0, 0) = taille native de l'écran jeu, lue par le feeder dans
        les formats annoncés par PipeWire SANS s'y connecter (idée et code de
        dreemur-e, BoneCast #1), plafonnée à 1080p : en 4K, le tuyau devrait
        faire passer ~500 Mo/s."""
        if w:
            return w, h
        from asyncio import create_subprocess_exec, wait_for
        from subprocess import PIPE, DEVNULL
        try:
            p = await create_subprocess_exec(
                sys_python(), str(cls._feeder_script()), "--probe-size",
                env=cls._gst_environment(), stdin=DEVNULL, stdout=PIPE, stderr=DEVNULL)
            out, _ = await wait_for(p.communicate(), timeout=15)
            cw, ch = (int(v) for v in out.decode().strip().split("x"))
            if cw > 0 and ch > 0:
                k = min(1.0, 1920 / cw, 1080 / ch)
                return int(cw * k) & ~1, int(ch * k) & ~1
        except Exception as e:
            logger.warning(f"[stream] taille native illisible ({e!r}) → 1280x720")
        return 1280, 720

    @classmethod
    async def _start_camera_feeder(cls, out_fd, size=(1280, 720), fps=30):
        """Lance gst_camera.py --stdout : il capture l'écran gamescope et écrit
        les images brutes (YUY2 1280x720@30) dans `out_fd`, un tuyau dont ffmpeg
        lit l'autre bout. Plus de /dev/video42 : v4l2loopback n'est pas chargé
        sur SteamOS et le charger demande sudo (BoneCast #1)."""
        from asyncio import create_subprocess_exec
        from subprocess import PIPE, DEVNULL
        await cls._stop_camera_feeder()
        cls._camera_feeder = await create_subprocess_exec(
            sys_python(), str(cls._feeder_script()), "--stdout",
            "--size", f"{size[0]}x{size[1]}", "--fps", str(int(fps)),
            env=cls._gst_environment(), stdin=DEVNULL, stdout=out_fd, stderr=PIPE)
        create_task(stream_watcher(cls._camera_feeder.stderr, True, prefix="[gstcam]"))
        return True

    @staticmethod
    def _feeder_script():
        script = Path(DECKY_PLUGIN_DIR) / "gst_camera.py"
        if not script.exists():
            script = Path(DECKY_PLUGIN_DIR) / "defaults" / "gst_camera.py"
        return script

    @classmethod
    async def _stop_camera_feeder(cls):
        # pkill ciblé sur NOTRE script : un « pkill -f gst_camera.py » tuait aussi
        # le feeder de Steamcord (même nom de fichier, autre plugin).
        from asyncio import create_subprocess_exec, sleep, wait_for
        from subprocess import DEVNULL
        # D'abord SIGTERM et on LAISSE le feeder se déconnecter proprement de
        # gamescope (pause, fin de l'image en cours, puis NULL) : l'arracher en
        # pleine image fait planter gamescope (30/09, SIGSEGV paint_pipewire →
        # session de jeu relancée). Le kill ne sert plus que de filet.
        fd0 = cls._camera_feeder
        if fd0 is not None and fd0.returncode is None:
            try:
                fd0.terminate()
                await wait_for(fd0.wait(), timeout=3)
            except Exception:
                pass
        try:
            killer = await create_subprocess_exec(
                "pkill", "-f", str(cls._feeder_script()),
                stdout=DEVNULL, stderr=DEVNULL, env=bcenv.user_env())
            await killer.wait()
        except Exception:
            pass
        fd = cls._camera_feeder
        cls._camera_feeder = None
        cls._brb_on = False
        if fd is not None:
            try:
                fd.kill()
                await fd.wait()
            except Exception:
                pass

    # ── stand-alone : une seule version pour tous les OS ────────────────────────
    # Le plugin vérifie ce que la machine a et dit exactement quoi installer.
    @staticmethod
    def _pkg_hint(arch, fedora, debian):
        """Commande d'installation pour CET OS — en anglais : ces textes vont tels
        quels dans le QAM (BoneCast #1 : un Deck en anglais recevait du français)."""
        import shutil as _sh
        # SteamOS a pacman mais un système en lecture seule : proposer
        # « sudo pacman -S » y est au mieux inutile, au pire dangereux.
        try:
            with open("/etc/os-release") as f:
                if "ID=steamos" in f.read():
                    return (f"missing on this SteamOS install ({arch}) — SteamOS is read-only, "
                            "please report it on the BoneCast GitHub issues")
        except OSError:
            pass
        if _sh.which("pacman"):
            return f"sudo pacman -S {arch}"
        if _sh.which("rpm-ostree"):
            return f"rpm-ostree install {fedora}"
        if _sh.which("dnf"):
            return f"sudo dnf install {fedora}"
        if _sh.which("zypper"):
            return f"sudo zypper install {fedora}"
        if _sh.which("apt"):
            return f"sudo apt install {debian}"
        return f"install: {arch}"

    @classmethod
    async def start_stream(cls, record_only=False, platform="twitch"):
        # Le test « un live tourne déjà ? » précède 1 à 2 s d'attentes (API
        # YouTube/Twitch, sondes d'encodeur) avant que ffmpeg n'existe : deux
        # lancements rapprochés (Twitch puis YouTube, ou double appui) passaient
        # tous les deux → deux ffmpeg, dont un orphelin. Le verrou fait attendre
        # le second, qui voit alors le live en cours et répond « busy ».
        cls._resume = None                        # l'utilisateur reprend la main
        return await cls._start_stream_locked(record_only, platform)

    @classmethod
    async def _start_stream_locked(cls, record_only=False, platform="twitch"):
        if cls._start_stream_lock is None:
            cls._start_stream_lock = Lock()
        async with cls._start_stream_lock:
            return await cls._start_stream_unlocked(record_only, platform)

    @classmethod
    async def _start_stream_unlocked(cls, record_only=False, platform="twitch"):
        from asyncio import create_subprocess_exec, sleep
        from subprocess import PIPE
        import shutil as _sh
        # stand-alone : ffmpeg est requis (encodage + push RTMP) — présent sur
        # Bazzite, pas garanti ailleurs.
        if not _sh.which("ffmpeg"):
            return {"ok": False, "error": "no_ffmpeg",
                    "hint": cls._pkg_hint("ffmpeg", "ffmpeg", "ffmpeg")}
        platform = "youtube" if platform == "youtube" else "twitch"
        want = "record" if record_only else platform
        # UN seul live à la fois : c'est le même ffmpeg, la même capture et le
        # même micro. Lancer YouTube pendant un live Twitch (ou l'inverse) est
        # refusé, jamais un second encodage en parallèle.
        if cls._stream_proc is not None and cls._stream_proc.returncode is None:
            if cls._stream_platform == want:
                return {"ok": True, "already": True}
            return {"ok": False, "error": "busy", "platform": cls._stream_platform}
        cfg = cls._load_cfg()
        key = None
        ingest = None
        yt_broadcast = False
        if not record_only and platform == "twitch":
            # Connecté en OAuth → rafraîchit la clé (elle peut tourner) avant de passer live.
            if (cfg.get("oauth") or {}).get("access_token"):
                try:
                    await cls.fetch_stream_key()
                except Exception:
                    pass
                cfg = cls._load_cfg()
            key = cfg.get("key")
            if not key:
                return {"ok": False, "error": "no_key"}
            ingest = cfg.get("ingest") or cls._TWITCH_INGEST
        elif not record_only:
            yt = cfg.get("youtube") or {}
            if (yt.get("oauth") or {}).get("access_token"):
                # Connecté : flux réutilisable + un live créé à chaque passage
                # à l'antenne (titre, visibilité, démarrage automatique).
                try:
                    key, ingest = await cls._yt_ensure_stream()
                    if not await cls._yt_reuse_broadcast():
                        await cls._yt_create_broadcast()
                        yt_broadcast = True
                except Exception as e:
                    logger.warning(f"[youtube] préparation du live: {e!r}")
                    return {"ok": False, "error": "yt_api", "hint": str(e)}
            else:
                key = yt.get("key")
                ingest = yt.get("ingest") or cls._YT_INGEST
            if not key:
                return {"ok": False, "error": "no_yt_key"}
        gst_hint = await cls._gst_python_hint()
        if gst_hint:
            return {"ok": False, "error": "no_gst", "hint": gst_hint}
        holder = (cfg.get("youtube") or {}) if platform == "youtube" else cfg
        st = {**cls._STREAM_DEFAULTS, **(holder.get("stream") or {})}
        discord_on = bool(st.get("discord_audio"))
        # Pont audio Discord : si Steamcord présent, isole Vesktop dans son sink
        # → le sink par défaut ne contient plus que le jeu ; le monitor Discord
        # sert d'entrée à part (ajouté au mix seulement si la case est cochée).
        disc_mon = None
        if cls._steamcord_present():
            try:
                disc_mon = await cls._audio_bridge_start()
                await sleep(0.4)
            except Exception as e:
                logger.warning(f"[audio] bridge start: {e!r}")
                disc_mon = None
        mon = await cls._default_monitor()   # après le pont = son du jeu seul
        w, h = cls._RES_PRESETS.get(st["resolution"], (1280, 720))
        fps = int(st["fps"]); vb = int(st["bitrate"]); ab = int(st["audio_bitrate"])
        # Taille et cadence de la CAPTURE = celles du stream (avant : 1280x720@30
        # fixe, BoneCast #1). Voir _capture_size pour « source ».
        cap_w, cap_h = await cls._capture_size(w, h)
        cap_fps = fps if fps in (30, 60) else 30
        gop = max(1, int(st.get("keyframe", 2)) * fps)   # keyframe toutes les N s (Twitch = 2 s)
        # Résout l'encodeur : auto = meilleur matériel dispo, sinon respecte le choix
        # mais retombe en logiciel si le matériel demandé n'est pas là.
        enc = st.get("encoder", "auto")
        if enc == "auto":
            if await cls._nvenc_available():
                enc = "nvenc"
            elif await cls._vaapi_available():
                enc = "vaapi"
            else:
                enc = "software"
        elif enc == "nvenc" and not await cls._nvenc_available():
            enc = "software"
        elif enc == "vaapi" and not await cls._vaapi_available():
            enc = "software"
        # fallback logiciel : vérifier que le ffmpeg présent a bien libx264
        # (le ffmpeg-free de Fedora ne l'a pas → erreur claire, pas un crash).
        if enc == "software" and not await cls._x264_available():
            return {"ok": False, "error": "no_x264",
                    "hint": "this ffmpeg has no libx264 (Fedora's ffmpeg-free?) — "
                            "install the full ffmpeg (Fedora: enable RPM Fusion, then "
                            "sudo dnf swap ffmpeg-free ffmpeg --allowerasing)"}
        # Entrées : vidéo (tuyau du feeder) + son du jeu (idx 1) + micro + Discord.
        # thread_queue_size + genpts = tampons plus larges + PTS régénérés →
        # évite les « backward in time »/underruns qui font tomber le RTMP.
        # Vidéo : images brutes du feeder par un tuyau (stdin de ffmpeg).
        # Horodatées à la RÉCEPTION : gamescope n'envoie une image que quand
        # l'écran change, et des horodatages « au compteur » comprimeraient le
        # temps (vidéo en avance sur le son) ; le filtre fps= comble ensuite.
        args = ["ffmpeg", "-hide_banner", "-loglevel", "warning", "-fflags", "+genpts",
                "-thread_queue_size", "512", "-use_wallclock_as_timestamps", "1",
                "-f", "rawvideo", "-pix_fmt", "yuyv422", "-video_size", f"{cap_w}x{cap_h}",
                "-framerate", str(cap_fps), "-i", "pipe:0",
                "-thread_queue_size", "512", "-f", "pulse", "-i", mon]
        audio_idx = [1]                       # entrées audio à mixer (1 = jeu)
        nxt = 2
        mic_src = None
        if st.get("mic"):
            s = await cls._default_source()
            if s and not s.startswith("@"):
                mic_src = s
                args += ["-thread_queue_size", "512", "-f", "pulse", "-i", mic_src]
                audio_idx.append(nxt); nxt += 1
        if discord_on and disc_mon:
            args += ["-thread_queue_size", "512", "-f", "pulse", "-i", disc_mon]
            audio_idx.append(nxt); nxt += 1
        # Vidéo : encodeur matériel (NVENC/VAAPI) si dispo/choisi, sinon logiciel x264.
        if enc == "nvenc":
            # NVENC prend le yuv420p en mémoire système (upload interne, pas de hwupload).
            vf = ([f"scale={w}:{h}"] if w else []) + [f"fps={fps}"]
            args += ["-vf", ",".join(vf),
                     "-c:v", "h264_nvenc", "-preset", "p5", "-tune", "ll",
                     "-rc", "cbr", "-pix_fmt", "yuv420p",
                     "-b:v", f"{vb}k", "-maxrate", f"{vb}k", "-bufsize", f"{vb * 2}k",
                     "-g", str(gop)]
        elif enc == "vaapi":
            vf = [f"fps={fps}", "format=nv12", "hwupload"]
            if w:
                vf.append(f"scale_vaapi=w={w}:h={h}")
            args += ["-vaapi_device", "/dev/dri/renderD128", "-vf", ",".join(vf),
                     "-c:v", "h264_vaapi", "-rc_mode", "CBR",
                     "-b:v", f"{vb}k", "-maxrate", f"{vb}k", "-g", str(gop)]
        else:
            vf = ([f"scale={w}:{h}"] if w else []) + [f"fps={fps}"]
            args += ["-vf", ",".join(vf),
                     "-c:v", "libx264",
                     "-preset", cls._X264_PRESETS.get(st.get("effort"), "veryfast"),
                     "-tune", "zerolatency",
                     "-pix_fmt", "yuv420p",
                     "-g", str(gop), "-keyint_min", str(gop),
                     "-b:v", f"{vb}k", "-maxrate", f"{vb}k", "-bufsize", f"{vb * 2}k"]
        # Audio : son du jeu seul, ou mixé (micro et/ou Discord) via amix.
        # aresample=async=1 recale l'audio sur une horloge continue (comble/coupe
        # les trous des monitors PulseAudio) → PTS monotones = Twitch ne coupe plus.
        if len(audio_idx) == 1:
            args += ["-map", "0:v", "-map", "1:a",
                     "-af", "aresample=async=1:first_pts=0"]
        else:
            mix = "".join(f"[{i}:a]" for i in audio_idx)
            args += ["-filter_complex",
                     f"{mix}amix=inputs={len(audio_idx)}:duration=longest:dropout_transition=0[mx];"
                     f"[mx]aresample=async=1:first_pts=0[aout]",
                     "-map", "0:v", "-map", "[aout]"]
        args += ["-c:a", "aac", "-b:a", f"{ab}k", "-ar", "44100",
                 "-max_muxing_queue_size", "1024"]
        # Sorties : RTMP seul, mkv seul (enregistrement), ou les deux via tee.
        # mkv = conteneur qui survit à un crash (contrairement au mp4).
        rec = record_only or bool(st.get("record"))
        cls._record_path = cls._new_record_path() if rec else None
        cls._record_only = record_only
        if record_only:
            args += ["-f", "matroska", cls._record_path]
        elif rec:
            # Une coupure RTMP doit arrêter ffmpeg : le watchdog peut alors
            # reprendre le live ou prévenir l'utilisateur. onfail=ignore
            # laissait l'enregistrement tourner avec un faux statut « LIVE ».
            args += ["-flags", "+global_header", "-f", "tee",
                     f"[f=flv:onfail=abort]{ingest}/{key}"
                     f"|[f=matroska]{cls._record_path}"]
        else:
            args += ["-f", "flv", f"{ingest}/{key}"]
        logger.info(f"[stream] encodeur={enc} {w or 'source'}x{h or ''}@{fps} "
                    f"{vb}kbps mic={bool(mic_src)} discord={bool(discord_on and disc_mon)} "
                    f"record={cls._record_path or '-'} record_only={record_only}")
        rfd, wfd = os.pipe()
        try:
            # ffmpeg d'abord (il lit le bout de lecture), puis le feeder qui
            # écrit dans l'autre bout ; le parent ferme ses deux copies ensuite,
            # sinon ffmpeg ne verrait jamais la fin du flux.
            cls._stream_proc = await create_subprocess_exec(
                *args, stdin=rfd, stdout=PIPE, stderr=PIPE, env=bcenv.user_env())
            await cls._start_camera_feeder(wfd, (cap_w, cap_h), cap_fps)
            os.close(rfd); os.close(wfd)
            rfd = wfd = None
            create_task(stream_watcher(cls._stream_proc.stdout, prefix="[stream]"))
            create_task(stream_watcher(cls._stream_proc.stderr, True, prefix="[stream]"))
            create_task(cls._watch_stream_exit(cls._stream_proc))
            # Micro : prépare le mute à la volée (découvre le source-output ffmpeg).
            cls._reset_mic_state()
            if mic_src:
                cls._mic_active = True
                create_task(cls._discover_mic_so(mic_src, cls._stream_proc.pid))
            cls._stream_platform = want
            cls._stream_started = time()
            logger.info(f"[stream] démarré : {want}")
            return {"ok": True}
        except Exception as e:
            logger.warning(f"[stream] start failed: {e!r}")
            for fdx in (rfd, wfd):
                if fdx is not None:
                    try:
                        os.close(fdx)
                    except OSError:
                        pass
            if cls._stream_proc is not None and cls._stream_proc.returncode is None:
                cls._stream_proc.kill()
            cls._stream_proc = None
            await cls._stop_camera_feeder()
            await cls._audio_bridge_stop()       # ne pas laisser Vesktop déplacé
            cls._reset_mic_state()
            if yt_broadcast:
                await cls._yt_end_broadcast()    # pas de live YouTube fantôme
            return {"ok": False, "error": str(e)}

    @classmethod
    async def _watch_stream_exit(cls, proc):
        """ffmpeg s'arrête SANS stop_stream (réseau coupé, clé refusée…) : on
        range comme un arrêt normal, sinon capture, pont audio et live YouTube
        resteraient ouverts. Était appelé depuis le premier commit sans avoir
        jamais été écrit : le démarrage levait une erreur APRÈS avoir lancé
        ffmpeg, et le QAM affichait un échec alors que le live tournait."""
        try:
            await proc.wait()
        except Exception:
            return
        if cls._stream_proc is not proc:
            return                               # arrêt demandé : stop_stream s'en charge
        logger.warning(f"[stream] ffmpeg s'est arrêté seul (code {proc.returncode})")
        plat = cls._stream_platform
        win = cls._resume_window()
        now = time()
        until = None
        if win and plat in ("twitch", "youtube"):
            prev = cls._resume_until_prev
            if prev and now < prev and now - cls._stream_started < 20:
                until = prev                     # la reprise vient de retomber : même fenêtre
            elif now - cls._stream_started >= 10:
                until = now + win                # coupure d'un live qui tournait
            # < 10 s sans reprise en cours = clé refusée, mauvais réglage… :
            # relancer en boucle ne ferait que répéter l'erreur.
        if until is None:
            await cls.stop_stream()
            cls._queue_stream_alert(plat, proc.returncode)
            return
        await cls._teardown_stream()
        cls._resume = {"platform": plat, "until": until}
        cls._resume_until_prev = until
        logger.info(f"[stream] reprise auto : {plat}, jusqu'à {int(until - now)} s")
        create_task(cls._auto_resume(cls._resume))

    _resume_until_prev = 0.0

    @classmethod
    def _queue_stream_alert(cls, platform, exit_code=None):
        if platform in ("twitch", "youtube"):
            cls._stream_alert_seq += 1
            cls._pending_stream_alert = {"platform": platform,
                                         "exit_code": exit_code,
                                         "at": int(time()),
                                         "id": cls._stream_alert_seq}
            logger.warning(f"[stream] alerte : live {platform} terminé sans demande")

    @classmethod
    async def get_stream_alert(cls):
        """L'alerte reste disponible jusqu'à confirmation par le frontend."""
        return cls._pending_stream_alert or {}

    @classmethod
    async def ack_stream_alert(cls, alert_id):
        if cls._pending_stream_alert and cls._pending_stream_alert["id"] == alert_id:
            cls._pending_stream_alert = None
        return {"ok": True}

    @classmethod
    def _resume_window(cls):
        v = cls._load_cfg().get("resume_window", 15)
        return v if v in cls._RESUME_CHOICES else 15

    @classmethod
    async def get_resume_window(cls):
        return {"seconds": cls._resume_window()}

    @classmethod
    async def set_resume_window(cls, seconds=15):
        try:
            seconds = int(seconds)
        except (TypeError, ValueError):
            return {"ok": False}
        if seconds not in cls._RESUME_CHOICES:
            return {"ok": False}
        cfg = cls._load_cfg()
        cfg["resume_window"] = seconds
        cls._save_cfg(cfg)
        return {"ok": True, "seconds": seconds}

    @classmethod
    async def _ingest_reachable(cls, platform):
        """Le serveur RTMP répond ? Évite de relancer capture + ffmpeg toutes les
        3 s pendant que le wifi redémarre (chaque relance = un client gamescope)."""
        from asyncio import open_connection, wait_for
        from urllib.parse import urlparse
        cfg = cls._load_cfg()
        if platform == "youtube":
            yt = cfg.get("youtube") or {}
            url = yt.get("api_ingest") or yt.get("ingest") or cls._YT_INGEST
        else:
            url = cfg.get("ingest") or cls._TWITCH_INGEST
        u = urlparse(url)
        port = u.port or (443 if u.scheme == "rtmps" else 1935)
        try:
            _r, w = await wait_for(open_connection(u.hostname, port), timeout=3)
            w.close()
            return True
        except Exception:
            return False

    @classmethod
    async def _auto_resume(cls, ticket):
        from asyncio import sleep
        plat = ticket["platform"]
        while cls._resume is ticket and time() < ticket["until"]:
            if await cls._ingest_reachable(plat):
                if cls._resume is not ticket:
                    return
                r = await cls._start_stream_locked(False, plat)
                if cls._resume is not ticket:
                    return                       # Arrêter / Démarrer pendant la relance
                if r.get("ok"):
                    cls._resume = None
                    logger.info(f"[stream] live repris : {plat}")
                    return
                logger.warning(f"[stream] reprise ratée : {r.get('error')}")
            await sleep(3)
        if cls._resume is ticket:
            cls._resume = None
            cls._resume_until_prev = 0.0
            logger.warning("[stream] fenêtre de reprise écoulée → live terminé")
            if plat == "youtube":
                await cls._yt_end_broadcast()
            cls._queue_stream_alert(plat)

    @classmethod
    async def _discover_mic_so(cls, mic_src, pid):
        """Trouve le source-output que ffmpeg crée pour capter le micro (matché par
        PID ffmpeg + source micro), afin de pouvoir le muter à la volée SANS toucher
        la capture Discord du même micro (Discord a son propre source-output)."""
        from json import loads
        from asyncio import sleep
        src_idx = await cls._source_index(mic_src)
        if src_idx is None:
            logger.warning(f"[mic] source {mic_src} introuvable → mute live indispo")
            return
        for _ in range(20):                    # ffmpeg met ~1 s à se connecter à Pulse
            if cls._stream_proc is None or cls._stream_proc.returncode is not None:
                return
            try:
                sos = loads(await cls._pactl("list", "source-outputs",
                                             want_json=True) or "[]")
                for so in sos:
                    props = so.get("properties", {}) or {}
                    if str(props.get("application.process.id")) == str(pid) \
                       and so.get("source") == src_idx:
                        cls._mic_so_idx = so.get("index")
                        # applique l'état voulu si l'user a cliqué avant la découverte
                        await cls._pactl("set-source-output-mute",
                                         str(cls._mic_so_idx),
                                         "1" if cls._mic_muted else "0")
                        logger.info(f"[mic] source-output ffmpeg={cls._mic_so_idx} "
                                    f"(muted={cls._mic_muted})")
                        return
            except Exception as e:
                logger.warning(f"[mic] discover: {e!r}")
            await sleep(0.4)
        logger.warning("[mic] source-output ffmpeg non trouvé → mute live indispo")

    @classmethod
    async def set_mic_mute(cls, muted):
        """Coupe/rétablit le micro SUR LE STREAM à la volée (n'affecte pas Discord)."""
        cls._mic_muted = bool(muted)
        if cls._mic_so_idx is not None:
            await cls._pactl("set-source-output-mute", str(cls._mic_so_idx),
                             "1" if cls._mic_muted else "0")
        logger.info(f"[mic] mute={cls._mic_muted} (so={cls._mic_so_idx})")
        return {"ok": True, "muted": cls._mic_muted}

    @classmethod
    def _reset_mic_state(cls):
        cls._mic_active = False
        cls._mic_so_idx = None
        cls._mic_muted = False

    # ── Enregistrement local ───────────────────────────────────────────────────
    @staticmethod
    def _videos_dir():
        """Dossier Vidéos de l'user (XDG, localisé « Vidéos » en FR) + /BoneCast."""
        home = os.path.expanduser("~")
        base = os.path.join(home, "Videos")
        try:
            with open(os.path.join(home, ".config", "user-dirs.dirs")) as f:
                for line in f:
                    if line.startswith("XDG_VIDEOS_DIR="):
                        raw = line.split("=", 1)[1].strip().strip('"')
                        base = raw.replace("$HOME", home)
                        break
        except Exception:
            pass
        path = os.path.join(base, "BoneCast")
        os.makedirs(path, exist_ok=True)
        return path

    # Carte SD, disque externe (#1 : « out of space ») : tout système de fichiers
    # monté sous /run/media, /media ou /mnt où l'utilisateur peut écrire. Les
    # enregistrements vont dans <disque>/BoneCast. Stocké en config globale (pas
    # par plateforme : c'est le même fichier quel que soit le live).
    _MEDIA_ROOTS = ("/run/media/", "/media/", "/mnt/")

    @classmethod
    def _external_drives(cls):
        seen, out = set(), []
        try:
            with open("/proc/self/mounts") as f:
                lines = f.read().splitlines()
        except OSError:
            return out
        for line in lines:
            parts = line.split()
            if len(parts) < 3:
                continue
            target = parts[1].replace("\\040", " ")
            if parts[2] in ("autofs", "tmpfs", "proc", "sysfs", "squashfs"):
                continue
            if not target.startswith(cls._MEDIA_ROOTS) or target in seen:
                continue
            seen.add(target)
            if os.path.isdir(target) and os.access(target, os.W_OK):
                out.append(target)
        return out

    @staticmethod
    def _free_gb(path):
        import shutil as _sh
        try:
            return round(_sh.disk_usage(path).free / 1e9, 1)
        except OSError:
            return None

    @classmethod
    def _record_dir(cls):
        """Dossier choisi s'il est encore là (carte SD retirée → stockage interne)."""
        drive = (cls._load_cfg().get("record_drive") or "").strip()
        if drive and drive in cls._external_drives():
            path = os.path.join(drive, "BoneCast")
            try:
                os.makedirs(path, exist_ok=True)
                return path
            except OSError as e:
                logger.warning(f"[record] {path} inutilisable ({e!r}) → stockage interne")
        elif drive:
            logger.info(f"[record] {drive} absent → stockage interne")
        return cls._videos_dir()

    @classmethod
    async def get_record_locations(cls):
        drive = (cls._load_cfg().get("record_drive") or "").strip()
        drives = cls._external_drives()
        home = cls._videos_dir()
        opts = [{"id": "", "path": home, "internal": True, "free_gb": cls._free_gb(home)}]
        for d in drives:
            opts.append({"id": d, "path": os.path.join(d, "BoneCast"),
                         "name": os.path.basename(d.rstrip("/")) or d,
                         "internal": False, "free_gb": cls._free_gb(d)})
        return {"selected": drive if drive in drives else "", "options": opts,
                "missing": drive if drive and drive not in drives else ""}

    @classmethod
    async def set_record_drive(cls, drive: str = ""):
        drive = (drive or "").strip()
        if drive and drive not in cls._external_drives():
            return {"ok": False, "error": "not_available"}
        cfg = cls._load_cfg()
        if drive:
            cfg["record_drive"] = drive
        else:
            cfg.pop("record_drive", None)
        cls._save_cfg(cfg)
        return {"ok": True}

    @classmethod
    def _new_record_path(cls):
        from datetime import datetime
        name = datetime.now().strftime("bonecast-%Y%m%d-%H%M%S.mkv")
        return os.path.join(cls._record_dir(), name)

    # ── BRB : pause à l'antenne sans couper le live ────────────────────────────
    # Le feeder remplace lui-même les images du jeu par une image de pause (fond
    # sombre, deux barres) sur SIGUSR1, et reprend sur SIGUSR2 : le tuyau vers
    # ffmpeg ne s'interrompt jamais, donc le live ne décroche pas.
    @classmethod
    async def brb_start(cls):
        """Écran pause à l'antenne : le feeder remplace les images du jeu par
        l'image de pause (SIGUSR1) ; le live continue sans coupure."""
        import signal as _sig
        if cls._stream_proc is None or cls._stream_proc.returncode is not None:
            return {"ok": False, "error": "not_streaming"}
        if cls._brb_on:
            return {"ok": True, "already": True}
        feeder = cls._camera_feeder
        if feeder is None or feeder.returncode is not None:
            return {"ok": False, "error": "no_feeder"}
        try:
            feeder.send_signal(_sig.SIGUSR1)
        except Exception as e:
            logger.warning(f"[brb] start failed: {e!r}")
            return {"ok": False, "error": str(e)}
        cls._brb_on = True
        # micro coupé pendant la pause (rétabli au retour s'il était ouvert)
        cls._brb_restore_mic = cls._mic_active and not cls._mic_muted
        if cls._brb_restore_mic:
            await cls.set_mic_mute(True)
        logger.info("[brb] pause à l'antenne")
        return {"ok": True}

    @classmethod
    async def brb_stop(cls):
        import signal as _sig
        was = cls._brb_on
        cls._brb_on = False
        feeder = cls._camera_feeder
        if was and feeder is not None and feeder.returncode is None:
            try:
                feeder.send_signal(_sig.SIGUSR2)
            except Exception:
                pass
        if cls._brb_restore_mic:
            cls._brb_restore_mic = False
            await cls.set_mic_mute(False)
        if was:
            logger.info("[brb] retour à l'antenne")
        return {"ok": True}

    @classmethod
    async def stop_stream(cls):
        # Arrêter pendant une reconnexion = on abandonne la reprise auto.
        resuming = cls._resume
        cls._resume = None
        cls._resume_until_prev = 0.0
        was = cls._stream_platform or (resuming or {}).get("platform")
        rec = await cls._teardown_stream()
        if was == "youtube" and (cls._yt_cfg().get("oauth") or {}).get("access_token"):
            # « Arrêter » par erreur : le live YouTube reste ouvert le temps de
            # la fenêtre de reprise ; Démarrer le reprend, sinon il se termine.
            win = cls._resume_window()
            if win:
                cls._yt_schedule_end(win)
            else:
                await cls._yt_end_broadcast()
        logger.info(f"[stream] live arrêté{' — enregistré: ' + rec if rec else ''}")
        return {"ok": True, "record_path": rec}

    @classmethod
    async def _teardown_stream(cls):
        """Range capture, ffmpeg, pont audio et micro ; laisse le live YouTube."""
        import signal as _sig
        from asyncio import wait_for
        proc = cls._stream_proc
        cls._stream_proc = None
        cls._stream_platform = None
        # La capture s'arrête AVANT ffmpeg : sinon ffmpeg ferme le tuyau, et le
        # feeder se retrouve à quitter au milieu d'une image (gamescope SIGSEGV,
        # voir _stop_camera_feeder). ffmpeg lit alors la fin du tuyau et termine
        # le fichier normalement.
        await cls._stop_camera_feeder()
        if proc is not None and proc.returncode is None:
            try:
                # SIGINT = ffmpeg ferme la session RTMP proprement (FCUnpublish) →
                # Twitch coupe le live vite. Fallback SIGTERM puis SIGKILL.
                proc.send_signal(_sig.SIGINT)
                try:
                    await wait_for(proc.wait(), timeout=5)
                except Exception:
                    proc.terminate()
                    try:
                        await wait_for(proc.wait(), timeout=1)
                    except Exception:
                        proc.kill()
                        await proc.wait()
            except Exception:
                pass
        # BRB éventuel : tuer le writer lavfi sans relancer le feeder (le live
        # est fini) ; brb_stop ne relance le feeder que si le stream tourne.
        # (La capture est déjà arrêtée proprement AVANT ffmpeg, plus haut.)
        await cls.brb_stop()
        await cls._stop_camera_feeder()
        await cls._audio_bridge_stop()           # remet Vesktop sur la vraie sortie
        cls._reset_mic_state()
        rec = cls._record_path
        cls._record_path = None
        cls._record_only = False
        return rec

    @classmethod
    async def get_stream_status(cls):
        p = cls._stream_proc
        live = p is not None and p.returncode is None
        if not live:
            cls._reset_mic_state()
        brb = cls._brb_on
        return {"streaming": live, "platform": cls._stream_platform if live else None,
                "mic": live and cls._mic_active,
                "mic_muted": cls._mic_muted, "brb": live and brb,
                "record_path": cls._record_path if live else None,
                "record_only": live and cls._record_only,
                "resuming": None if live or not cls._resume else cls._resume["platform"],
                "resume_left": 0 if live or not cls._resume
                else max(0, int(cls._resume["until"] - time()))}

    # ── Auto-update (release-based, comme le reste de la suite) ───────────────
    # NB : il y avait ICI un `@classmethod` orphelin, resté d'un en-tête « Cycle
    # de vie » dont la méthode a bougé, qui décorait _autoupdate_check DEUX fois.
    # Le Python embarqué actuel l'accepte, mais l'enchaînement de classmethod est
    # supprimé depuis Python 3.13 : le jour où Decky change de Python, la vérif
    # de mise à jour lèverait « 'classmethod' object is not callable » au
    # démarrage. Un seul décorateur.
    @classmethod
    async def _autoupdate_check(cls):
        """Vérif silencieuse au boot : si activé et qu'une release plus récente
        existe, télécharge + décompresse par-dessus le plugin puis recharge."""
        if updater is None:
            return
        try:
            if not updater.is_autoupdate_enabled():
                return
            info = await _recheck(updater)
            if not info.get("update_available"):
                return
            logger.info(f"[updater] {info['latest']} dispo (installé "
                        f"{info['current']}) — application")
            # apply() renvoie un dict : {"ok": False, "error": …} est TOUJOURS
            # vrai, donc un échec passait pour un succès et le loader
            # redémarrait quand même — en boucle, puisque la version installée
            # n'avait pas bougé. On lit le champ, pas la vérité du dict.
            # On applique NOUS-MÊMES. Le dossier du plugin appartient à root,
            # mais tous les fichiers dedans nous appartiennent (sauf plugin.json)
            # — mesuré le 13/09 : écraser un fichier existant passe, créer une
            # entrée non. L'updater sait désormais faire le tri AVANT d'écrire.
            #
            # ⛔ Ne PAS déléguer à `utilities/install_plugin` : c'est la route du
            # Store Decky, qui déclare l'install à plugins.deckbrew.xyz. Nos
            # plugins n'y sont pas → 404 → la suite ne s'exécute pas : fichiers
            # écrits, plugin jamais rechargé, et une modale figée en travers de
            # l'interface Steam. Mesuré ici le 13/09.
            res = await updater.apply(info["url"])
            if res.get("ok"):
                from asyncio import sleep as _sleep
                await _sleep(2)
                if updater.restart_loader():
                    logger.info("[updater] mise à jour installée — rechargement")
                    return
                # Le redémarrage du loader est REFUSÉ à tout plugin non root :
                # polkit demande une authentification que personne ne peut
                # donner ici (mesuré le 22/09). Le journal disait pourtant
                # « rechargement » — d'où des machines qui restaient sur
                # l'ancienne version sans que rien ne le signale.
                logger.info(
                    f"[updater] {info['latest']} écrite sur le disque ; rechargement "
                    "refusé (plugin non root) — active au prochain démarrage de Steam"
                )
                cls._pending_update = {"version": info["latest"], "reload": True}
                return
            # Échec : le dire à l'utilisateur au lieu de le laisser sur une
            # version périmée sans le savoir. Le frontend s'en charge, lui seul
            # sait notifier.
            logger.error(f"[updater] mise à jour impossible : "
                         f"{res.get('error', 'raison inconnue')}")
            cls._pending_update = {"version": info["latest"],
                                   "error": res.get("error", "")}
        except Exception as e:
            logger.warning(f"[updater] auto-check: {e!r}")

    # Avis d'échec déposé par _autoupdate_check, retiré par le frontend qui notifie.
    _pending_update = None

    @classmethod
    async def take_pending_update(cls):
        """Rend l'avis de mise à jour impossible au frontend, une seule fois.

        Vidé à la lecture : la notification ne doit partir qu'UNE fois, pas à
        chaque ouverture du QAM.
        """
        pending, cls._pending_update = cls._pending_update, None
        return pending or {}

    @classmethod
    async def check_update(cls):
        if not updater:
            return {"update_available": False, "error": "updater indisponible"}
        return await updater.check()

    @classmethod
    async def get_version(cls):
        return updater.get_current_version() if updater else "0.0.0"

    @classmethod
    async def apply_update(cls, url):
        if not updater:
            return {"ok": False, "error": "updater unavailable"}
        res = await updater.apply(url)
        # Écrire ne suffit pas, il faut RECHARGER : c'est le frontend qui s'en
        # charge, en demandant au loader de réimporter CE plugin. On ne redémarre
        # plus plugin_loader d'ici — le backend n'en a pas le droit (voir
        # restart_loader) et ça relancerait tous les plugins pour rien.
        return res

    @classmethod
    async def get_autoupdate(cls):
        return updater.is_autoupdate_enabled() if updater else False

    @classmethod
    async def set_autoupdate(cls, enabled):
        return updater.set_autoupdate_enabled(enabled) if updater else False

    @classmethod
    async def _main(cls):
        logger.info("BoneCast backend chargé")
        create_task(cls._autoupdate_check())
        # Live YouTube encore ouvert d'avant (redémarrage, crash, mise à jour du
        # plugin) : Démarrer le reprend pendant la fenêtre, sinon on le termine.
        try:
            y = cls._yt_cfg()
            if y.get("broadcast_id"):
                end_at = y.get("broadcast_end_at") or (time() + cls._resume_window())
                cls._yt_schedule_end(max(0, end_at - time()))
        except Exception as e:
            logger.warning(f"[youtube] live resté ouvert: {e!r}")

    @classmethod
    async def _unload(cls):
        try:
            if cls._stream_proc and cls._stream_proc.returncode is None:
                cls._stream_proc.kill()
        except Exception:
            pass
        try:
            if cls._camera_feeder and cls._camera_feeder.returncode is None:
                cls._camera_feeder.kill()
        except Exception:
            pass
        try:
            if cls._overlay_proc and cls._overlay_proc.returncode is None:
                cls._overlay_proc.terminate()
        except Exception:
            pass
        try:
            if cls._watch_proc and cls._watch_proc.returncode is None:
                cls._watch_proc.terminate()
        except Exception:
            pass
        # ⚠️ Ordre voulu : tout ce qui est synchrone AVANT la moindre attente.
        # Pendant un déchargement, Decky ne redonne pas la main après une
        # suspension réelle — mesuré sur Steamcord le 22/09 : la suite ne
        # s'exécute jamais et le loader SIGKILL 5 s plus tard. `_reset_mic_state`
        # passait donc à la trappe dès que le pont audio traînait.
        cls._reset_mic_state()
        logger.info("BoneCast backend déchargé")
        try:
            await cls._audio_bridge_stop()       # défait le pont audio Discord
        except Exception:
            pass
