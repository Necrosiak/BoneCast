# Lecture du chat d'un live YouTube pour l'overlay (lecture seule, sans compte).
#
# Pourquoi pas l'API YouTube Data : son quota (10 000 unités/jour) est PARTAGÉ
# par tous les utilisateurs de BoneCast, et lire le chat d'un live de 2 h en
# coûte ~7 000. On lit donc le chat comme le fait la page web de YouTube (le
# même point d'entrée que yt-dlp et chat-downloader) : aucun quota, aucune
# connexion — mais dépendant du format du site, d'où des erreurs remontées
# comme un état (« reconnexion ») plutôt qu'un plantage.
#
# Tourne dans le processus GTK de l'overlay (python système), sur un thread à
# part : les messages sont rendus à l'UI par un callback.

import json
import re
import threading
import time
import urllib.request

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")
# SOCS/CONSENT : sans eux, une IP européenne est renvoyée vers la page de
# consentement de Google au lieu du live.
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9",
           "Cookie": "SOCS=CAI; CONSENT=YES+"}
VIDEO_ID = re.compile(r"^[\w-]{11}$")


def _get(url, data=None):
    h = dict(HEADERS)
    if data is not None:
        h["Content-Type"] = "application/json"
        data = json.dumps(data).encode()
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", "replace")


def live_url(source):
    """@pseudo, ID de chaîne UC…, URL de chaîne ou de vidéo → URL à résoudre."""
    s = (source or "").strip()
    if VIDEO_ID.match(s) and not s.startswith("UC"):
        return None                                  # déjà un ID de vidéo
    if s.startswith("http"):
        if "watch?v=" in s or "youtu.be/" in s or "/live/" in s:
            return s
        return s.rstrip("/") + "/live"
    if s.startswith("UC"):
        return f"https://www.youtube.com/channel/{s}/live"
    return f"https://www.youtube.com/@{s.lstrip('@')}/live"


LIVE_HINT = "/tmp/bonecast-yt-live.json"


def live_hint(source):
    """Vidéo du live que BoneCast vient de lancer sur CETTE chaîne (privé ou non
    répertorié compris : ils n'apparaissent pas sur /live), sinon None."""
    try:
        with open(LIVE_HINT) as f:
            h = json.load(f)
    except Exception:
        return None
    s = (source or "").strip()
    if h.get("video") and h.get("channel") and h.get("channel") in s:
        return h["video"]
    return None


def resolve_video(source):
    """ID de la vidéo en direct, ou None si la chaîne n'est pas en live."""
    s = (source or "").strip()
    url = live_url(s)
    if url is None:
        return s
    m = re.search(r"(?:watch\?v=|youtu\.be/|/live/)([\w-]{11})", url)
    if m:
        return m.group(1)
    html = _get(url)
    # Hors live, /live renvoie la page de la chaîne : l'URL canonique n'est
    # alors PAS une vidéo.
    m = re.search(r'<link rel="canonical" href="https://www\.youtube\.com/watch\?v=([\w-]{11})"', html)
    if not m or ('"isLive":true' not in html and '"isLiveNow":true' not in html):
        return None
    return m.group(1)


def _runs(runs):
    out = []
    for r in runs or []:
        if "text" in r:
            out.append({"t": r["text"]})
        elif "emoji" in r:
            e = r["emoji"]
            if not e.get("isCustomEmoji") and e.get("emojiId"):
                out.append({"t": e["emojiId"]})       # emoji Unicode standard
            else:
                thumbs = (e.get("image") or {}).get("thumbnails") or [{}]
                alt = (e.get("shortcuts") or [""])[0]
                if thumbs[0].get("url"):
                    out.append({"img": thumbs[0]["url"], "alt": alt})
                else:
                    out.append({"t": alt})
    return out


def _badge(renderer):
    kinds = set()
    for b in renderer.get("authorBadges") or []:
        br = b.get("liveChatAuthorBadgeRenderer") or {}
        icon = (br.get("icon") or {}).get("iconType", "")
        if icon == "OWNER":
            kinds.add("owner")
        elif icon == "MODERATOR":
            kinds.add("moderator")
        elif icon == "VERIFIED":
            kinds.add("verified")
        elif br.get("customThumbnail"):
            kinds.add("member")
    for k in ("owner", "moderator", "member", "verified"):
        if k in kinds:
            return k
    return ""


def _text(obj):
    """Texte d'un champ innertube : simpleText, ou runs mis bout à bout."""
    obj = obj or {}
    if "simpleText" in obj:
        return obj["simpleText"]
    return "".join(r.get("text", "") for r in obj.get("runs") or [])


def _event(item):
    """Événement du live (Super Chat, Super Sticker, membre, abonnements offerts)
    → dict affiché en carte dans l'overlay, ou None. Le texte vient de YouTube,
    déjà traduit dans la langue de la chaîne : rien à traduire ici."""
    r = item.get("liveChatPaidMessageRenderer")
    if r:
        return {"event": "superchat", "name": _text(r.get("authorName")),
                "badge": _badge(r), "head": _text(r.get("purchaseAmountText")),
                "runs": _runs((r.get("message") or {}).get("runs"))}
    r = item.get("liveChatPaidStickerRenderer")
    if r:
        thumbs = ((r.get("sticker") or {}).get("thumbnails")) or [{}]
        runs = [{"img": thumbs[-1]["url"], "alt": "sticker"}] if thumbs[-1].get("url") else []
        return {"event": "sticker", "name": _text(r.get("authorName")),
                "badge": _badge(r), "head": _text(r.get("purchaseAmountText")), "runs": runs}
    r = item.get("liveChatMembershipItemRenderer")
    if r:
        # Nouveau membre : headerSubtext (« Bienvenue dans … ») ; palier :
        # headerPrimaryText (« Membre depuis 3 mois ») + message éventuel.
        head = _text(r.get("headerPrimaryText")) or _text(r.get("headerSubtext"))
        runs = _runs((r.get("message") or {}).get("runs"))
        if not runs and r.get("headerPrimaryText"):
            runs = [{"t": _text(r.get("headerSubtext"))}]
        return {"event": "member", "name": _text(r.get("authorName")),
                "badge": "member", "head": head, "runs": runs}
    r = item.get("liveChatSponsorshipsGiftPurchaseAnnouncementRenderer")
    if r:
        h = ((r.get("header") or {}).get("liveChatSponsorshipsHeaderRenderer")) or {}
        return {"event": "gift", "name": _text(h.get("authorName")),
                "badge": _badge(h), "head": _text(h.get("primaryText")), "runs": []}
    return None


def parse_actions(actions):
    msgs = []
    for a in actions or []:
        item = (a.get("addChatItemAction") or {}).get("item") or {}
        ev = _event(item)
        if ev:
            msgs.append(ev)
            continue
        r = item.get("liveChatTextMessageRenderer")
        if not r:
            continue
        msgs.append({
            "name": (r.get("authorName") or {}).get("simpleText", ""),
            "badge": _badge(r),
            "runs": _runs((r.get("message") or {}).get("runs")),
        })
    return msgs


class YtChat(threading.Thread):
    """Suit le chat d'une chaîne/vidéo ; se reconnecte seul (live pas encore
    lancé, live terminé puis relancé, erreur réseau)."""

    def __init__(self, source, on_messages, on_status):
        super().__init__(daemon=True)
        self.source = source
        self.on_messages = on_messages
        self.on_status = on_status          # ("waiting" | "live" | "retry", détail)
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            try:
                vid = live_hint(self.source) or resolve_video(self.source)
                if not vid:
                    self.on_status("waiting", "")
                    self._stop.wait(30)
                    continue
                self._follow(vid)
            except Exception as e:
                self.on_status("retry", str(e)[:120])
                self._stop.wait(15)

    def _follow(self, vid):
        page = _get(f"https://www.youtube.com/live_chat?is_popout=1&v={vid}")
        key = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', page)
        ver = re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', page)
        cont = re.search(r'"continuation":"([^"]+)"', page)
        if not (key and ver and cont):
            raise RuntimeError("chat introuvable (live sans chat ?)")
        self.on_status("live", vid)
        url = ("https://www.youtube.com/youtubei/v1/live_chat/get_live_chat"
               f"?key={key.group(1)}&prettyPrint=false")
        c = cont.group(1)
        while not self._stop.is_set():
            d = json.loads(_get(url, {"context": {"client": {
                "clientName": "WEB", "clientVersion": ver.group(1)}},
                "continuation": c}))
            lc = (d.get("continuationContents") or {}).get("liveChatContinuation")
            if not lc or not lc.get("continuations"):
                return                          # live terminé → re-résoudre
            msgs = parse_actions(lc.get("actions"))
            if msgs:
                self.on_messages(msgs)
            cd = lc["continuations"][0]
            data = next(iter(cd.values()))
            c = data.get("continuation")
            if not c:
                return
            # YouTube propose 5 à 10 s entre deux lectures (timeoutMs) : c est
            # le rythme du lecteur web, pas une limite. Le suivre donnait jusqu à
            # 10 s de retard dans l overlay (test 29/09) → 2 s max.
            wait = int(data.get("timeoutMs", 2000)) / 1000
            self._stop.wait(min(max(wait, 1.0), 2.0))
