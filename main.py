"""BoneCast — backend Twitch (OAuth device flow + titre/catégorie Helix + overlay chat).
Incrément 1 : login, titre, catégorie, overlay. Le streaming RTMP arrive à l'incrément 2.
Config PAR COMPTE Steam : ~/.config/bonecast-<accountid>.json (tokens = secrets, chmod 600)."""
import os
import sys
from json import load, dump
from pathlib import Path
from asyncio import create_task
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


class Plugin:
    # ── OAuth Twitch (device code flow, client public — pas de secret) ───────
    _TWITCH_CLIENT_ID = "idbnwqbkqyrzesxct1ztkejyf5aj6z"
    _TWITCH_SCOPES = "channel:read:stream_key channel:manage:broadcast"
    _TWITCH_JUST_CHATTING = "509658"          # game_id « Just Chatting »
    _tw_device = None                          # état transitoire du device flow
    _overlay_proc = None
    _stream_proc = None                        # ffmpeg RTMP (live Twitch)
    _camera_feeder = None                      # gst_camera.py → /dev/video42
    _TWITCH_INGEST = "rtmp://ingest.global-contribute.live-video.net/app"
    _OVERLAY_DEFAULTS = {"opacity": 62, "fontSize": 13, "width": 360,
                         "height": 460, "pos": "tr", "badges": True, "thirdParty": True}
    # ── Réglages du stream (par compte Steam) ────────────────────────────────
    _RES_PRESETS = {"720p": (1280, 720), "800p": (1280, 800),
                    "1080p": (1920, 1080), "source": (0, 0)}
    _STREAM_DEFAULTS = {"resolution": "720p", "fps": 30, "bitrate": 4500,
                        "audio_bitrate": 160, "keyframe": 2,
                        "encoder": "auto", "mic": False, "discord_audio": False}
    _vaapi_ok = None                           # cache détection VAAPI (AMD/Intel)
    _nvenc_ok = None                           # cache détection NVENC (Nvidia)
    # ── Mute micro à la volée (n'affecte QUE le stream, pas le vocal Discord) ──
    _mic_active = False                        # micro inclus dans le stream courant ?
    _mic_so_idx = None                         # source-output ffmpeg qui capte le micro
    _mic_muted = False                         # micro coupé sur le stream (live)
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
        ov = cls._overlay_proc
        return {
            "logged_in": bool(oauth.get("access_token")),
            "login": oauth.get("login", ""),
            "key_set": bool(cfg.get("key")),
            "title": cfg.get("title", ""),
            "game_name": cfg.get("game_name", ""),
            # Chaîne de l'overlay : override manuel sinon = ta propre chaîne (login OAuth).
            "channel": cfg.get("channel") or oauth.get("login", ""),
            "overlay_on": ov is not None and ov.returncode is None,
            "overlay": {**cls._OVERLAY_DEFAULTS, **(cfg.get("overlay") or {})},
            "streaming": cls._stream_proc is not None
            and cls._stream_proc.returncode is None,
            "stream": {**cls._STREAM_DEFAULTS, **(cfg.get("stream") or {})},
            "steamcord": cls._steamcord_present(),
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

    # ── Overlay chat ─────────────────────────────────────────────────────────
    @classmethod
    def _overlay_state_dir(cls):
        try:
            acc = bcenv.steam_account_id()
        except Exception:
            acc = "default"
        return os.path.expanduser(f"~/.local/share/bonecast/twitch_overlay/{acc}")

    @classmethod
    def _write_overlay_state(cls, cfg=None):
        cfg = cls._load_cfg() if cfg is None else cfg
        d = cls._overlay_state_dir()
        os.makedirs(d, exist_ok=True)
        st = {**cls._OVERLAY_DEFAULTS, **(cfg.get("overlay") or {})}
        with open(os.path.join(d, "overlay_state.json"), "w") as f:
            dump(st, f)

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
    async def set_overlay_settings(cls, settings=None):
        try:
            cfg = cls._load_cfg()
            ov = {**cls._OVERLAY_DEFAULTS, **(cfg.get("overlay") or {})}
            for k in cls._OVERLAY_DEFAULTS:
                if isinstance(settings, dict) and settings.get(k) is not None:
                    ov[k] = settings[k]
            cfg["overlay"] = ov
            cls._save_cfg(cfg)
            cls._write_overlay_state(cfg)   # poll live par chat.html
            return {"ok": True, "overlay": ov}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @classmethod
    async def start_overlay(cls):
        cfg = cls._load_cfg()
        # Override manuel sinon = ta propre chaîne (login OAuth) → aucun pseudo à saisir.
        channel = (cfg.get("channel") or (cfg.get("oauth") or {}).get("login") or "").strip()
        if not channel:
            return {"ok": False, "error": "no_channel"}
        if cls._overlay_proc is not None and cls._overlay_proc.returncode is None:
            return {"ok": True, "already": True}
        from asyncio import create_subprocess_exec
        from subprocess import PIPE
        script = Path(DECKY_PLUGIN_DIR) / "twitch_overlay" / "overlay.py"
        if not script.exists():
            script = Path(DECKY_PLUGIN_DIR) / "defaults" / "twitch_overlay" / "overlay.py"
        d = cls._overlay_state_dir()
        cls._write_overlay_state(cfg)
        try:
            env = dict(os.environ)
            try:
                env.update(bcenv.user_env())
            except Exception:
                pass
            env.setdefault("DISPLAY", ":0")     # XWayland gamescope (over-game) ou KWin
            cls._overlay_proc = await create_subprocess_exec(
                "/usr/bin/python3", str(script),
                "--channel", channel, "--state-dir", d,
                env=env, stdout=PIPE, stderr=PIPE)
            create_task(stream_watcher(cls._overlay_proc.stdout, prefix="[overlay]"))
            create_task(stream_watcher(cls._overlay_proc.stderr, True, prefix="[overlay]"))
            logger.info(f"[overlay] démarré (#{channel})")
            return {"ok": True}
        except Exception as e:
            logger.warning(f"[overlay] start failed: {e!r}")
            return {"ok": False, "error": str(e)}

    @classmethod
    async def stop_overlay(cls):
        proc = cls._overlay_proc
        cls._overlay_proc = None
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
        return {"overlay_on": ov is not None and ov.returncode is None}

    # ── Streaming Twitch (RTMP via ffmpeg depuis la capture /dev/video42) ─────
    # Le jeu est capturé dans le loopback v4l2 /dev/video42 par gst_camera.py
    # (node PipeWire gamescope → seul chemin qui marche en mode jeu, gamescope
    # n'ayant pas de portail) ; ffmpeg le lit + le son du jeu (monitor du sink
    # par défaut), encode h264/aac et pousse en RTMP vers Twitch avec la clé
    # récupérée en OAuth. Réglages par compte Steam dans le cfg.
    @classmethod
    def _gst_environment(cls):
        """Env pour gst_camera.py : user_env (bus/affichage user + purge des LD_*
        PyInstaller) + GST_PLUGIN_PATH embarqué (libgstnice) + VAAPI radeonsi."""
        try:
            env = dict(bcenv.user_env())
        except Exception:
            env = dict(os.environ)
        gpd = str(Path(DECKY_PLUGIN_DIR) / "gst-plugins")
        if not os.path.isdir(gpd):
            gpd = str(Path(DECKY_PLUGIN_DIR) / "defaults" / "gst-plugins")
        env["GST_VAAPI_ALL_DRIVERS"] = "1"
        env["LIBVA_DRIVER_NAME"] = "radeonsi"
        env["GST_PLUGIN_PATH"] = gpd + os.pathsep + env.get("GST_PLUGIN_PATH", "")
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
    async def get_encoders(cls):
        """Liste des encodeurs utilisables + recommandation (pour le QAM).
        Ordre de préférence matériel : NVENC (Nvidia) > VAAPI (AMD/Intel) > x264."""
        nv = await cls._nvenc_available()
        va = await cls._vaapi_available()
        avail = ["software"]
        if nv:
            avail.append("nvenc")
        if va:
            avail.append("vaapi")
        rec = "nvenc" if nv else ("vaapi" if va else "software")
        return {"available": avail, "nvenc": nv, "vaapi": va, "recommended": rec}

    @classmethod
    async def set_stream_settings(cls, settings=None):
        """Persiste les réglages de qualité/encodeur (par compte)."""
        cfg = cls._load_cfg()
        st = {**cls._STREAM_DEFAULTS, **(cfg.get("stream") or {})}
        if isinstance(settings, dict):
            for k in cls._STREAM_DEFAULTS:
                if settings.get(k) is not None:
                    st[k] = settings[k]
        cfg["stream"] = st
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
        m2 = (await cls._pactl("load-module", "module-loopback",
              f"source={cls._DISCORD_SINK}.monitor",
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
    async def _start_camera_feeder(cls):
        """(Re)lance gst_camera.py qui alimente /dev/video42 avec l'écran gamescope."""
        from asyncio import create_subprocess_exec, sleep
        from subprocess import PIPE, DEVNULL
        if not os.path.exists("/dev/video42"):
            logger.warning("[stream] /dev/video42 absent — v4l2loopback non chargé.")
            return False
        try:
            killer = await create_subprocess_exec(
                "pkill", "-f", "gst_camera.py",
                stdout=DEVNULL, stderr=DEVNULL, env=bcenv.user_env())
            await killer.wait()
            await sleep(0.5)
        except Exception:
            pass
        script = Path(DECKY_PLUGIN_DIR) / "gst_camera.py"
        if not script.exists():
            script = Path(DECKY_PLUGIN_DIR) / "defaults" / "gst_camera.py"
        cls._camera_feeder = await create_subprocess_exec(
            "/usr/bin/python", str(script),
            env=cls._gst_environment(), stdout=PIPE, stderr=PIPE)
        create_task(stream_watcher(cls._camera_feeder.stdout, prefix="[gstcam]"))
        create_task(stream_watcher(cls._camera_feeder.stderr, True, prefix="[gstcam]"))
        await sleep(2)     # laisser le pipeline s'établir
        return True

    @classmethod
    async def _stop_camera_feeder(cls):
        from asyncio import create_subprocess_exec
        from subprocess import DEVNULL
        try:
            killer = await create_subprocess_exec(
                "pkill", "-f", "gst_camera.py",
                stdout=DEVNULL, stderr=DEVNULL, env=bcenv.user_env())
            await killer.wait()
        except Exception:
            pass
        fd = cls._camera_feeder
        cls._camera_feeder = None
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
        import shutil as _sh
        if _sh.which("pacman"):
            return f"sudo pacman -S {arch}"
        if _sh.which("rpm-ostree"):
            return f"rpm-ostree install {fedora}"
        if _sh.which("dnf"):
            return f"sudo dnf install {fedora}"
        if _sh.which("apt"):
            return f"sudo apt install {debian}"
        return f"install: {arch}"

    @classmethod
    async def _v4l2_hint(cls):
        """Distingue « module pas installé » (installer le paquet) de « installé
        mais pas chargé » (modprobe/reboot) pour donner LA bonne commande."""
        from asyncio import create_subprocess_exec
        from subprocess import DEVNULL
        try:
            p = await create_subprocess_exec("modinfo", "v4l2loopback",
                                             stdout=DEVNULL, stderr=DEVNULL)
            installed = (await p.wait()) == 0
        except Exception:
            installed = False
        if installed:
            return ("v4l2loopback installé mais pas chargé : sudo modprobe v4l2loopback "
                    "video_nr=42 card_label=BoneCast exclusive_caps=1 (puis réessaie)")
        pkg = cls._pkg_hint("v4l2loopback-dkms", "v4l2loopback", "v4l2loopback-dkms")
        return (f"module v4l2loopback manquant : {pkg} puis sudo modprobe "
                "v4l2loopback video_nr=42 card_label=BoneCast exclusive_caps=1")

    @classmethod
    async def start_stream(cls):
        from asyncio import create_subprocess_exec, sleep
        from subprocess import PIPE
        import shutil as _sh
        # stand-alone : ffmpeg est requis (encodage + push RTMP) — présent sur
        # Bazzite, pas garanti ailleurs.
        if not _sh.which("ffmpeg"):
            return {"ok": False, "error": "no_ffmpeg",
                    "hint": cls._pkg_hint("ffmpeg", "ffmpeg", "ffmpeg")}
        cfg = cls._load_cfg()
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
        if cls._stream_proc is not None and cls._stream_proc.returncode is None:
            return {"ok": True, "already": True}
        if not os.path.exists("/dev/video42"):
            return {"ok": False, "error": "no_loopback",
                    "hint": await cls._v4l2_hint()}
        # S'assurer que la capture jeu alimente /dev/video42.
        if not (cls._camera_feeder is not None
                and cls._camera_feeder.returncode is None):
            if not await cls._start_camera_feeder():
                return {"ok": False, "error": "no_loopback",
                        "hint": await cls._v4l2_hint()}
            await sleep(1)
        ingest = cfg.get("ingest") or cls._TWITCH_INGEST
        st = {**cls._STREAM_DEFAULTS, **(cfg.get("stream") or {})}
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
        # Entrées : vidéo (loopback jeu) + son du jeu (idx 1) + micro + Discord.
        # thread_queue_size + genpts = tampons plus larges + PTS régénérés →
        # évite les « backward in time »/underruns qui font tomber le RTMP.
        args = ["ffmpeg", "-hide_banner", "-loglevel", "warning", "-fflags", "+genpts",
                "-thread_queue_size", "512", "-f", "v4l2", "-i", "/dev/video42",
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
                     "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
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
                 "-max_muxing_queue_size", "1024",
                 "-f", "flv", f"{ingest}/{key}"]
        logger.info(f"[stream] encodeur={enc} {w or 'source'}x{h or ''}@{fps} "
                    f"{vb}kbps mic={bool(mic_src)} discord={bool(discord_on and disc_mon)}")
        try:
            cls._stream_proc = await create_subprocess_exec(
                *args, stdout=PIPE, stderr=PIPE, env=bcenv.user_env())
            create_task(stream_watcher(cls._stream_proc.stdout, prefix="[stream]"))
            create_task(stream_watcher(cls._stream_proc.stderr, True, prefix="[stream]"))
            create_task(cls._watch_stream_exit(cls._stream_proc))
            # Micro : prépare le mute à la volée (découvre le source-output ffmpeg).
            cls._reset_mic_state()
            if mic_src:
                cls._mic_active = True
                create_task(cls._discover_mic_so(mic_src, cls._stream_proc.pid))
            logger.info("[stream] live démarré vers Twitch")
            return {"ok": True}
        except Exception as e:
            logger.warning(f"[stream] start failed: {e!r}")
            await cls._audio_bridge_stop()       # ne pas laisser Vesktop déplacé
            cls._reset_mic_state()
            return {"ok": False, "error": str(e)}

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

    @classmethod
    async def stop_stream(cls):
        import signal as _sig
        from asyncio import wait_for
        proc = cls._stream_proc
        cls._stream_proc = None
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
        await cls._stop_camera_feeder()
        await cls._audio_bridge_stop()           # remet Vesktop sur la vraie sortie
        cls._reset_mic_state()
        logger.info("[stream] live arrêté")
        return {"ok": True}

    @classmethod
    async def get_stream_status(cls):
        p = cls._stream_proc
        live = p is not None and p.returncode is None
        if not live:
            cls._reset_mic_state()
        return {"streaming": live, "mic": live and cls._mic_active,
                "mic_muted": cls._mic_muted}

    # ── Cycle de vie ─────────────────────────────────────────────────────────
    @classmethod
    # ── Auto-update (release-based, comme le reste de la suite) ───────────────
    @classmethod
    async def _autoupdate_check(cls):
        """Vérif silencieuse au boot : si activé et qu'une release plus récente
        existe, télécharge + décompresse par-dessus le plugin puis recharge."""
        if updater is None:
            return
        try:
            if not updater.is_autoupdate_enabled():
                return
            info = await updater.check()
            if not info.get("update_available"):
                return
            logger.info(f"[updater] {info['latest']} dispo (installé "
                        f"{info['current']}) — application auto")
            if await updater.apply(info["url"]):
                from asyncio import sleep as _sleep
                logger.info("[updater] mise à jour installée — rechargement")
                await _sleep(2)
                updater.restart_loader()
        except Exception as e:
            logger.warning(f"[updater] auto-check: {e!r}")

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
            return False
        ok = await updater.apply(url)
        if ok:
            from asyncio import sleep as _sleep
            await _sleep(1)
            updater.restart_loader()
        return ok

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
            await cls._audio_bridge_stop()       # défait le pont audio Discord
        except Exception:
            pass
        cls._reset_mic_state()
        logger.info("BoneCast backend déchargé")
