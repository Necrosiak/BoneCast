"""Résolution des URL de lecture HLS d'un live Twitch — stdlib uniquement.

Pourquoi pas streamlink : il tire ~73 Mo de dépendances, dont `lxml`,
`pycryptodome` et `charset_normalizer` qui embarquent des extensions C
compilées pour UNE version précise de CPython. Vendorées depuis une machine
Bazzite (3.14), elles ne se chargeraient pas sur SteamOS. Or tout ce dont on a
besoin tient en deux requêtes :

  1. `gql.twitch.tv` → jeton de lecture (value + signature)
  2. `usher.ttvnw.net` → playlist maîtresse m3u8

…et ffmpeg lit ensuite la playlist de variante directement.

Note : comme le chat anonyme déjà utilisé par BoneCast, on s'appuie sur le
Client-ID public du site web. C'est la même zone grise vis-à-vis des CGU.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

# Client-ID PUBLIC du site web Twitch (celui que tout navigateur envoie).
_WEB_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
# Hash de la requête persistée « PlaybackAccessToken ».
_PERSISTED_HASH = "0828119ded1c13477966434e15800ff57ddacf13ba1911c129dc2200705b0712"
_TIMEOUT = 15


class OfflineError(RuntimeError):
    """La chaîne n'est pas en direct (ou n'existe pas)."""


def _post_gql(payload, oauth_token=None):
    headers = {"Client-ID": _WEB_CLIENT_ID, "Content-Type": "application/json"}
    # Le token de l'utilisateur (il est déjà connecté via l'OAuth de BoneCast)
    # identifie la session auprès de Twitch : plus de pré-roll sur les chaînes
    # qu'il suit, aucune pub pour celles auxquelles il est abonné. Sans lui, le
    # flux est servi en anonyme, donc avec le MAXIMUM de pubs (écran noir
    # mid-roll — vu en test).
    # NB : on n'envoie PAS de token ici. Le token OAuth de BoneCast est émis
    # pour le Client-ID du plugin, or cette requête GQL utilise le Client-ID
    # web de Twitch → mélanger les deux renvoie 401 (vu en test). Et le user a
    # demandé de NE PAS contourner les pubs : rester anonyme est le bon défaut,
    # les pubs passent normalement. `oauth_token` est gardé pour un éventuel
    # usage futur (device-id + integrity), mais n'est pas utilisé tel quel.
    _ = oauth_token
    req = urllib.request.Request(
        "https://gql.twitch.tv/gql",
        data=json.dumps(payload).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return json.load(r)


def _access_token(login, oauth_token=None):
    d = _post_gql({
        "operationName": "PlaybackAccessToken",
        "extensions": {"persistedQuery": {
            "version": 1, "sha256Hash": _PERSISTED_HASH}},
        "variables": {"isLive": True, "login": login, "isVod": False,
                      "vodID": "", "playerType": "site"}}, oauth_token=oauth_token)
    tok = (d.get("data") or {}).get("streamPlaybackAccessToken")
    if not tok or not tok.get("value"):
        raise OfflineError(f"aucun jeton de lecture pour « {login} »")
    return tok["value"], tok["signature"]


def master_playlist(login, oauth_token=None):
    """Playlist maîtresse (texte m3u8) du live de `login`."""
    login = (login or "").strip().lower().lstrip("@")
    if not login:
        raise ValueError("chaîne vide")
    value, sig = _access_token(login, oauth_token)
    q = urllib.parse.urlencode({
        "allow_source": "true", "allow_audio_only": "true",
        "fast_bread": "true", "p": "1234567",
        "player_backend": "mediaplayer", "playlist_include_framerate": "true",
        "sig": sig, "token": value, "supported_codecs": "h264",
    })
    url = f"https://usher.ttvnw.net/api/channel/hls/{login}.m3u8?{q}"
    try:
        with urllib.request.urlopen(url, timeout=_TIMEOUT) as r:
            return r.read().decode()
    except urllib.error.HTTPError as e:
        # Twitch répond 404 quand le live vient de s'arrêter.
        raise OfflineError(f"« {login} » n'est pas en direct (HTTP {e.code})")


def qualities(login=None, playlist=None, oauth_token=None):
    """Qualités disponibles, de la meilleure à la moins bonne.

    → [{name, width, height, fps, url}]. La résolution et le framerate sont
    lus dans la playlist elle-même : on ne se fie PAS au nom, qui varie d'une
    chaîne à l'autre (« 480p » ici, « 480p30 » là — constaté en vrai).
    Une chaîne non partenaire n'est pas transcodée : elle n'expose que sa
    source, souvent 1080p60. L'UI doit le montrer plutôt que de laisser croire
    qu'un choix « basse qualité » existe toujours.
    """
    if playlist is None:
        playlist = master_playlist(login, oauth_token)
    out, name, res, fps = [], None, None, None
    for line in playlist.splitlines():
        line = line.strip()
        if line.startswith("#EXT-X-MEDIA"):
            for part in line.split(","):
                if part.startswith("NAME="):
                    name = part.split("=", 1)[1].strip('"')
        elif line.startswith("#EXT-X-STREAM-INF"):
            for part in line.split(","):
                if part.startswith("RESOLUTION="):
                    res = part.split("=", 1)[1]
                elif part.startswith("FRAME-RATE="):
                    fps = part.split("=", 1)[1]
        elif line.startswith("http"):
            w = h = 0
            if res and "x" in res:
                try:
                    w, h = (int(v) for v in res.split("x", 1))
                except ValueError:
                    w = h = 0
            try:
                f = round(float(fps)) if fps else 0
            except ValueError:
                f = 0
            if name and name.lower() != "audio_only":
                out.append({"name": name, "width": w, "height": h,
                            "fps": f, "url": line})
            name = res = fps = None
    out.sort(key=lambda q: (q["height"], q["fps"]), reverse=True)
    return out


def pick_quality(qs, target_height=0, max_fps=0):
    """La qualité la moins coûteuse qui reste digne de la taille affichée.

    Décoder du 1080p pour une vignette de 360 px de haut, c'est payer 0,81
    cœur au lieu de 0,08 (mesuré) pour un résultat identique à l'écran.
    """
    if not qs:
        return None
    usable = qs
    if max_fps:
        capped = [q for q in qs if not q["fps"] or q["fps"] <= max_fps]
        usable = capped or qs
    if target_height:
        big_enough = [q for q in usable if q["height"] >= target_height]
        if big_enough:
            return big_enough[-1]          # le plus petit qui couvre encore
    return usable[0]                        # sinon la meilleure disponible


def resolve(login, target_height=0, max_fps=0, oauth_token=None):
    """→ (qualité choisie, toutes les qualités). Lève OfflineError si hors ligne."""
    qs = qualities(login, oauth_token=oauth_token)
    if not qs:
        raise OfflineError(f"aucune piste vidéo pour « {login} »")
    return pick_quality(qs, target_height, max_fps), qs
