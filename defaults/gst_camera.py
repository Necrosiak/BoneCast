#!/usr/bin/env python
# BoneCast : lancé avec --stdout, ce feeder écrit ses images brutes (YUY2
# 1280x720@30) sur sa sortie standard, reliée par un tuyau à l'entrée de ffmpeg.
# Plus de /dev/video42 : le module v4l2loopback n'est pas chargé sur SteamOS
# (BoneCast #1, Steam Deck OLED) et le charger exige sudo. L'écran pause (BRB)
# est alors fabriqué ici : SIGUSR1 = pause, SIGUSR2 = retour au jeu.
#
# Mode historique (sans --stdout) : feeder « webcam virtuelle » : capture l'écran gamescope (node PipeWire direct —
# le SEUL chemin qui marche en mode jeu, gamescope n'ayant pas de portail) et le
# pousse dans /dev/video42 (v4l2loopback "Steamcord Screen"). Discord l'utilise
# ensuite comme CAMÉRA (getUserMedia), ce qui contourne entièrement le partage
# d'écran Go Live (portail → écran noir en gamescope).
#
# Tourne comme sous-process (stdout/stderr capturés par stream_watcher → préfixe
# [gstcam] au journal Steamcord). Boucle de reconnexion : le node gamescope
# n'existe que pendant le jeu et change d'id → on le re-cherche tant qu'absent.

import fcntl
import os
import signal
import struct
import sys
import threading
import time
import json
import logging
from subprocess import getoutput, run, TimeoutExpired
from gi import require_version  # type: ignore

STDOUT_MODE = "--stdout" in sys.argv
OUT_FD = None
if STDOUT_MODE:
    # La sortie standard ne transporte plus que des images : on la garde sur un
    # fd à part et on renvoie le fd 1 vers stderr, pour qu'un print ou un
    # message de bibliothèque ne puisse jamais s'intercaler dans une image.
    OUT_FD = os.dup(1)
    os.dup2(2, 1)
logging.basicConfig(level=logging.INFO, stream=sys.stderr if STDOUT_MODE else sys.stdout,
                    format="%(levelname)s %(name)s: %(message)s", force=True)
log = logging.getLogger("screencam")

require_version("Gst", "1.0")
from gi.repository import Gst, GLib  # type: ignore

DEVICE = "/dev/video42"
# Discord/Chromium aime un format simple et borné. YUY2 720p30 = sûr.
WIDTH, HEIGHT, FPS = 1280, 720, 30

# --- Écriture write() dans le loopback (remplace v4l2sink MMAP + keepalive) ---
# v4l2loopback n'accepte qu'UN SEUL lecteur en streaming : l'ancien lecteur
# « keepalive » occupait cette place → Discord recevait NotReadableError
# (« Could not start video source ») en ouvrant la caméra → self_video annoncé
# au gateway mais AUCUNE frame envoyée = écran vide chez les autres (prouvé via
# CDP le 02/07). En sortie write() (comme ffmpeg/OBS), le writer n'a besoin
# d'AUCUN lecteur pour survivre ET le device s'annonce CAPTURE (exclusive_caps)
# tant qu'on le tient ouvert → Discord devient le lecteur unique. NB : gst
# v4l2sink io-mode=rw ne déclenche PAS le flip CAPTURE, d'où le S_FMT manuel.
VIDIOC_S_FMT = 0xC0D05605  # _IOWR('V', 5, struct v4l2_format), x86_64
V4L2_BUF_TYPE_VIDEO_OUTPUT = 2
V4L2_FIELD_NONE = 1
FOURCC_YUYV = 0x56595559


def open_device_out():
    """Ouvre DEVICE en écriture et déclare le format de sortie (YUYV WxH).
    Renvoie le fd ; chaque os.write() d'une frame complète = 1 frame publiée."""
    fd = os.open(DEVICE, os.O_RDWR)
    pix = struct.pack("<12I", WIDTH, HEIGHT, FOURCC_YUYV, V4L2_FIELD_NONE,
                      WIDTH * 2, WIDTH * 2 * HEIGHT, 8, 0, 0, 0, 0, 0)
    fmt = bytearray(struct.pack("<I4x", V4L2_BUF_TYPE_VIDEO_OUTPUT) + pix)
    fmt += b"\x00" * (208 - len(fmt))  # sizeof(struct v4l2_format) = 208
    try:
        fcntl.ioctl(fd, VIDIOC_S_FMT, fmt)
    except OSError:
        os.close(fd)
        raise
    return fd


# ── Sortie tuyau + écran pause (mode --stdout) ─────────────────────────────
_write_lock = threading.Lock()   # une image entière à la fois (pause vs capture)
BRB = {"on": False, "frame": None}
CUR = {"pipe": None}             # pipeline de capture en cours (pour l'arrêt propre)
_exiting = threading.Event()


def graceful_exit(reason):
    """Quitte SANS arracher le flux à gamescope.

    Mesuré le 30/09 (et déjà vu le 27/09) : gamescope 3.16.28 plante (SIGSEGV
    dans paint_pipewire → vulkan_screenshot) quand un client disparaît pendant
    qu'il dessine une image : PipeWire détruit le tampon (destroy_buffer) sous
    ses pieds. Bug de gamescope (cf. PR amont #2021, jamais fusionnée : la
    gestion de ses tampons n'est pas thread-safe) → la session de jeu redémarre.
    Un os._exit en pleine image était le déclencheur. On met d'abord le flux en
    pause (gamescope arrête de nous dessiner), on laisse finir l'image en cours,
    puis on se déconnecte proprement."""
    if _exiting.is_set():
        return
    _exiting.set()
    log.info(f"arrêt propre de la capture ({reason})")
    stop_brb_video()
    pipe = CUR["pipe"]
    try:
        if pipe is not None:
            pipe.set_state(Gst.State.PAUSED)
            pipe.get_state(1 * Gst.SECOND)
            time.sleep(0.3)
            pipe.set_state(Gst.State.NULL)
            pipe.get_state(2 * Gst.SECOND)
    except Exception as e:
        log.warning(f"arrêt propre: {e!r}")
    os._exit(0)


def write_frame(fd, data):
    """Écrit UNE image complète. Sur un tuyau, os.write peut n'en passer qu'une
    partie : sans cette boucle, ffmpeg recevrait des images décalées."""
    view = memoryview(data)
    with _write_lock:
        while view:
            n = os.write(fd, view)
            view = view[n:]


def _pause_frame():
    """Image de pause en YUY2 : fond sombre et deux barres blanches centrées,
    la même que l'ancien écran pause dessiné par ffmpeg."""
    bg_y, bar_y, chroma = 37, 205, 128
    row_bg = bytes([bg_y, chroma, bg_y, chroma]) * (WIDTH // 2)
    row_bar = bytearray(row_bg)
    for x0 in (WIDTH // 2 - 70, WIDTH // 2 + 20):
        for x in range(x0, x0 + 50):
            row_bar[2 * x] = bar_y       # en YUY2, la luminance du pixel x est à 2x
    top, bottom = HEIGHT // 2 - 90, HEIGHT // 2 + 90
    return b"".join(bytes(row_bar) if top <= y < bottom else row_bg
                    for y in range(HEIGHT))


PAUSE_FRAME = _pause_frame() if STDOUT_MODE else None

# Écran pause perso : une image déposée à la main (mode Bureau) dans ce dossier.
# Relue à CHAQUE pause → la changer ne demande ni redémarrage ni réglage.
# Absente ou illisible = l'écran pause par défaut ci-dessus.
BRB_DIR = os.path.expanduser("~/BoneCast-BRB")
BRB_NAMES = ("brb.png", "brb.jpg", "brb.jpeg", "brb.webp")
# Animé (#1) : décodé par ffmpeg, déjà requis pour streamer, plutôt que par les
# décodeurs GStreamer, qui varient d'un système à l'autre. Une vidéo passe avant
# une image fixe. ⚠️ ffmpeg ne décode pas le webp ANIMÉ (limite connue) → gif/mp4.
BRB_VIDEO_NAMES = ("brb.mp4", "brb.webm", "brb.mkv", "brb.mov", "brb.gif")
BRB_README = """BoneCast - custom pause screen (BRB)

Put a file named brb.png (or brb.jpg / brb.webp) in this folder, or an
animated one: brb.mp4, brb.webm, brb.mkv, brb.mov or brb.gif (it loops).
BoneCast shows it on your stream when you press Pause (BRB).

- 16:9 works best (1280x720 or 1920x1080); other sizes get black bars.
- A video's sound is not used: your stream keeps its own audio.
- Animated .webp files are not supported: convert them to .gif or .mp4.
- A new file is picked up the next time you press Pause.
- Delete it to get the default pause screen back.
"""


def ensure_brb_dir():
    try:
        os.makedirs(BRB_DIR, exist_ok=True)
        readme = os.path.join(BRB_DIR, "README.txt")
        # Réécrit s'il a changé : c'est notre fichier, il suit les versions.
        try:
            with open(readme) as f:
                current = f.read()
        except OSError:
            current = None
        if current != BRB_README:
            with open(readme, "w") as f:
                f.write(BRB_README)
    except OSError as e:
        log.warning(f"dossier BRB: {e!r}")


BRB_VIDEO = {"proc": None}


def stop_brb_video():
    p = BRB_VIDEO["proc"]
    BRB_VIDEO["proc"] = None
    if p is not None and p.poll() is None:
        # kill direct : ce ffmpeg ne fait que décoder (rien à finaliser), et plus
        # personne ne lit son tuyau → bloqué en écriture, il ignorait le SIGTERM
        # et le retour au jeu attendait 2 s (mesuré le 30/09).
        try:
            p.kill()
            p.wait(timeout=1)
        except Exception:
            pass


def start_brb_video():
    """Lance la vidéo de pause en boucle ; chaque image décodée remplace
    BRB["frame"], que le métronome envoie. True si la 1re image est arrivée."""
    import subprocess
    path = next((os.path.join(BRB_DIR, n) for n in BRB_VIDEO_NAMES
                 if os.path.isfile(os.path.join(BRB_DIR, n))), None)
    if not path:
        return False
    stop_brb_video()
    BRB["frame"] = None              # sinon une image restée d une pause précédente passerait pour « démarré »
    size = WIDTH * HEIGHT * 2
    vf = (f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
          f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,fps={FPS}")
    try:
        p = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-nostdin", "-stream_loop", "-1", "-re", "-i", path,
             "-an", "-vf", vf, "-pix_fmt", "yuyv422", "-f", "rawvideo", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    except OSError as e:
        log.warning(f"écran pause animé impossible ({path}): {e!r}")
        return False
    BRB_VIDEO["proc"] = p
    first = threading.Event()

    def reader():
        while BRB_VIDEO["proc"] is p:
            buf = bytearray()
            while len(buf) < size:
                chunk = p.stdout.read(size - len(buf))
                if not chunk:
                    err = (p.stderr.read() or b"").decode(errors="ignore").strip()
                    if BRB_VIDEO["proc"] is p:
                        log.warning(f"écran pause animé arrêté ({path}): {err[:200]}")
                    first.set()
                    return
                buf += chunk
            BRB["frame"] = bytes(buf)
            first.set()
    threading.Thread(target=reader, daemon=True).start()
    first.wait(3)
    if BRB["frame"] is None:
        log.warning(f"écran pause animé illisible ({path}) → image fixe ou écran par défaut")
        stop_brb_video()
        return False
    log.info(f"écran pause animé : {path}")
    return True


def load_brb_image():
    """Image perso convertie en YUY2 WIDTHxHEIGHT (bandes noires si le format
    diffère), ou None. GStreamer est déjà là : pas de dépendance en plus."""
    path = next((os.path.join(BRB_DIR, n) for n in BRB_NAMES
                 if os.path.isfile(os.path.join(BRB_DIR, n))), None)
    if not path:
        return None
    pipe = None
    try:
        pipe = Gst.parse_launch(
            "filesrc name=src ! decodebin ! videoconvert ! videoscale ! "
            f"video/x-raw,format=YUY2,width={WIDTH},height={HEIGHT},"
            "pixel-aspect-ratio=1/1 ! appsink name=sink sync=false")
        pipe.get_by_name("src").set_property("location", path)
        pipe.set_state(Gst.State.PLAYING)
        sample = pipe.get_by_name("sink").emit("try-pull-sample", 5 * Gst.SECOND)
        if sample is None:
            raise RuntimeError("aucune image décodée")
        buf = sample.get_buffer()
        data = buf.extract_dup(0, buf.get_size())
        if len(data) != WIDTH * HEIGHT * 2:
            raise RuntimeError(f"taille inattendue {len(data)}")
        log.info(f"écran pause perso : {path}")
        return data
    except Exception as e:
        log.warning(f"écran pause perso illisible ({path}): {e!r} → écran par défaut")
        return None
    finally:
        if pipe is not None:
            pipe.set_state(Gst.State.NULL)
# Dernière image du jeu écrite + quand : le métronome la répète si gamescope
# ne livre plus rien (écran immobile, menu en pause, chargement, capture qui se
# relance). Noir tant qu'aucune n'est arrivée, pour que ffmpeg démarre tout de
# suite au lieu d'attendre la première image.
LAST = {"frame": bytes([16, 128]) * (WIDTH * HEIGHT) if STDOUT_MODE else None}


def start_metronome():
    """Garantit 30 images/s dans le tuyau, quoi que fasse la capture.

    Mesuré le 29/09 : écran immobile = gamescope n'envoie AUCUNE image ; ffmpeg
    restait bloqué sur sa lecture, ne démarrait qu'à l'écran pause, et ne
    traitait même plus le SIGINT d'arrêt (tué au bout de 6 s, fichier illisible).
    Sur un live, ce trou coupe le flux vidéo chez Twitch/YouTube."""
    period = 1.0 / FPS

    def run():
        # Échéances absolues : un sleep(period) après chaque écriture dériverait
        # d'autant que dure l'écriture (1,8 Mo par image).
        nxt = time.monotonic()
        while True:
            nxt += period
            delay = nxt - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            else:
                nxt = time.monotonic()       # en retard : on repart, sans rafale
            try:
                frame = (BRB["frame"] or PAUSE_FRAME) if BRB["on"] else LAST["frame"]
                write_frame(OUT_FD, frame)
            except BrokenPipeError:
                graceful_exit("tuyau fermé par ffmpeg")
            except OSError:
                pass
    threading.Thread(target=run, daemon=True).start()


def start_brb_listener():
    """Écran pause piloté par signaux, reçus par un thread dédié (sigwait) :
    indépendant de la boucle GLib, donc aussi pendant qu'une capture se relance.
    Les deux signaux sont bloqués AVANT que GStreamer ne crée ses threads."""
    # SIGTERM aussi (arrêt demandé par le backend) : reçu ici, il passe par
    # l'arrêt propre au lieu de tuer le process au milieu d'une image.
    sigs = {signal.SIGUSR1, signal.SIGUSR2, signal.SIGTERM}
    signal.pthread_sigmask(signal.SIG_BLOCK, sigs)

    def run():
        while True:
            sig = signal.sigwait(sigs)
            if sig == signal.SIGTERM:
                graceful_exit("SIGTERM")
                continue
            if sig == signal.SIGUSR1:
                # Chargée AVANT d'afficher : jamais une image à moitié prête.
                BRB["frame"] = None
                if not start_brb_video():
                    BRB["frame"] = load_brb_image()
            else:
                stop_brb_video()
            BRB["on"] = sig == signal.SIGUSR1
            log.info("écran pause " + ("affiché" if BRB["on"] else "retiré"))
    ensure_brb_dir()
    threading.Thread(target=run, daemon=True).start()


def _pw_dump(timeout=5):
    """Sortie de `pw-dump`, ou None. JAMAIS `getoutput()` nu ici.

    Un `pw-dump` coincé ne rend jamais la main et ne lève rien : le `except`
    d'en dessous ne se déclenchait donc pas, et le feeder restait pendu jusqu'au
    redémarrage du plugin. Et le blocage se propage — un seul client pendu fait
    taire tous les `pw-dump` suivants, donc on le purge avant de renoncer.

    Mesuré le 31/08 sur la BC-250 : `pactl` répondait parfaitement pendant que
    `pw-dump` et `pw-cli` étaient muets ; il y avait UN client pendu, et le tuer
    a tout rétabli sur-le-champ. Ce n'est pas PipeWire qui meurt.
    """
    try:
        return run(["pw-dump"], capture_output=True, text=True,
                   timeout=timeout).stdout
    except TimeoutExpired:
        log.warning(f"pw-dump muet après {timeout}s — purge des clients pendus")
        try:
            run(["pkill", "-x", "pw-dump"], timeout=5)
        except Exception:
            pass
    except Exception as e:
        log.warning(f"pw-dump KO: {e!r}")
    return None


def find_screen_node():
    """Node PipeWire de l'écran gamescope (publie l'écran complet en mode jeu).
    Renvoie l'id (str) ou None."""
    out = _pw_dump()
    if out is None:
        return None
    try:
        data = json.loads(out)
    except Exception as e:
        log.warning(f"pw-dump illisible: {e!r}")
        return None
    vids = []
    for n in data:
        if not str(n.get("type", "")).endswith("Node"):
            continue
        p = (n.get("info", {}) or {}).get("props", {}) or {}
        mc = str(p.get("media.class", ""))
        name = str(p.get("node.name", ""))
        desc = str(p.get("node.description", ""))
        blob = (mc + " " + name + " " + desc).lower()
        # NE JAMAIS capturer notre PROPRE loopback (/dev/video42 « Steamcord Screen »)
        # ni un autre périphérique v4l2 : sinon le feeder se filme lui-même = écran
        # noir. Le node 58 (v4l2_input…video42, classe Video/Source, nom « …screen »)
        # matchait à la fois "screen" ET "video/source" → il était choisi à tort,
        # en Bureau ET potentiellement en gamemode (selon l'ordre de pw-dump).
        if ("video42" in blob or "steamcord" in blob or "loopback" in blob
                or "v4l2" in name.lower()):
            continue
        if "video/source" in mc.lower() or "gamescope" in blob or "screen" in blob or "video/output" in mc.lower():
            vids.append((n.get("id"), name, mc))
    if vids:
        log.info(f"nodes vidéo candidats: {vids}")
    for nid, name, mc in vids:
        if "gamescope" in name.lower() or "screen" in name.lower():
            return str(nid)
    for nid, name, mc in vids:
        if "video/source" in mc.lower():
            return str(nid)
    return None


def find_x_display():
    """Display X imbriqué de gamescope où le JEU est rendu. gamescope crée un X
    nested (typiquement :1) pour le contenu jeu, :0 = UI Steam. On préfère :1.
    Inspiré de decky-streamer (ximagesrc DISPLAY=:1, capture fiable sans portail
    ni node PipeWire). Renvoie ":1"/":0" ou None."""
    try:
        socks = getoutput("ls /tmp/.X11-unix/ 2>/dev/null")
    except Exception as e:
        log.warning(f"ls .X11-unix KO: {e!r}")
        socks = ""
    order = []
    if "X1" in socks:
        order.append(":1")
    if "X0" in socks:
        order.append(":0")
    if not order:
        order = [":0"]
    log.info(f"displays X candidats: {socks!r} → essai {order}")
    return order[0]


def build_pipeline(backend, node=None, display=None):
    """backend = 'pipewire' (node gamescope) | 'ximagesrc' (X nested :1)."""
    if backend == "ximagesrc":
        src = (f"ximagesrc display-name={display} use-damage=0 "
               f"show-pointer=false do-timestamp=true")
    else:
        src = (f"pipewiresrc path={node}" if node else "pipewiresrc") + " do-timestamp=true"
    desc = (
        f"{src} ! videoconvert ! videoscale ! videorate ! "
        f"video/x-raw,format=YUY2,width={WIDTH},height={HEIGHT},framerate={FPS}/1 ! "
        f"appsink name=asink emit-signals=true max-buffers=4 drop=true sync=false"
    )
    log.info(f"Pipeline ({backend}): " + desc)
    return Gst.parse_launch(desc)


def run_backend(backend, node, display):
    """Lance un pipeline pour un backend donné. Renvoie True si arrêt normal
    (EOS/stop), False si erreur GStreamer (→ l'appelant bascule de backend)."""
    loop = GLib.MainLoop()
    ok = {"value": True}
    pipe = build_pipeline(backend, node=node, display=display)
    CUR["pipe"] = pipe
    bus = pipe.get_bus()
    bus.add_signal_watch()

    # GLib.timeout_add pose ses callbacks sur le contexte GLOBAL, pas sur ce loop.
    # Sans nettoyage, les retries en attente d'une itération qui a échoué se
    # redéclenchent TOUS dans l'itération suivante (« 7× démarré d'un coup » +
    # tempête → fuite FD). On trace chaque source et on les retire à la sortie.
    sources = []

    def add_timeout(ms, fn):
        sid = GLib.timeout_add(ms, fn)
        sources.append(sid)
        return sid

    # Le device doit être ouvert + S_FMT AVANT que Discord n'énumère : c'est la
    # présence du writer qui fait annoncer CAPTURE (exclusive_caps=1).
    if STDOUT_MODE:
        dev_fd = OUT_FD
    else:
        try:
            dev_fd = open_device_out()
            log.info(f"{DEVICE} ouvert en écriture (S_FMT YUYV {WIDTH}x{HEIGHT}) — "
                     f"device annoncé CAPTURE, Discord sera le lecteur unique")
        except OSError as e:
            log.error(f"ouverture {DEVICE} KO: {e!r}")
            return False
    out_name = "stdout" if STDOUT_MODE else DEVICE

    def on_error(_bus, msg):
        err, dbg = msg.parse_error()
        log.error(f"gst error ({backend}): {err} | {dbg}")
        ok["value"] = False
        loop.quit()

    bus.connect("message::error", on_error)
    bus.connect("message::eos", lambda *_: (log.info("EOS"), loop.quit()))

    # --- Écriture des frames + compteur -----------------------------------
    # set_state(PLAYING) ne prouve PAS que gamescope livre des buffers : on
    # compte les frames réellement écrites + on loggue les caps négociées une
    # seule fois. Verdict net : >0 frames/s = ça coule (problème côté Discord) ;
    # 0 frame = gamescope ne capture rien (source à changer). Log ~1×/10s.
    stats = {"n": 0, "logged_caps": False, "last_log": 0.0}
    # Snapshot diag : on copie la ~90e frame réellement écrite et on l'encode en
    # JPEG hors du thread de streaming. (Un 2e lecteur v4l2src est proscrit :
    # v4l2loopback n'accepte qu'un lecteur, ce serait voler la place de Discord.)
    snapbuf = {"data": None, "caps": None}

    def on_sample(sink):
        sample = sink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.OK
        buf = sample.get_buffer()
        got, mi = buf.map(Gst.MapFlags.READ)
        if not got:
            return Gst.FlowReturn.OK
        try:
            data = bytes(mi.data)
        finally:
            buf.unmap(mi)
        try:
            if STDOUT_MODE:
                # On DÉPOSE l'image, on n'écrit pas : ce thread est celui de
                # PipeWire, et une écriture dans le tuyau bloque dès que ffmpeg
                # prend du retard. Seul le métronome écrit. (29/09 : un premier
                # enregistrement a fait boucler l'audio de tout le système, sans
                # erreur PipeWire mesurable ensuite ; précaution, cause non prouvée.)
                LAST["frame"] = data
            else:
                os.write(dev_fd, data)
        except BrokenPipeError:
            # ffmpeg est parti (live arrêté) : plus rien à alimenter.
            log.info("tuyau fermé par ffmpeg — arrêt du feeder")
            os._exit(0)
        except OSError as e:
            log.error(f"write {out_name} KO: {e!r}")
            ok["value"] = False
            loop.quit()
            return Gst.FlowReturn.ERROR
        stats["n"] += 1
        # 90e frame → snapshot diag one-shot ; ensuite copie rafraîchie toutes
        # les ~60 frames (2s) pour l'aperçu QAM encodé par write_preview.
        if not STDOUT_MODE and (stats["n"] == 90 or stats["n"] % 60 == 0):
            snapbuf["data"] = data
            snapbuf["caps"] = sample.get_caps()
            if stats["n"] == 90:
                add_timeout(0, write_snapshot)
        now = time.monotonic()
        if not stats["logged_caps"]:
            caps = sample.get_caps()
            log.info(f"PREMIÈRE FRAME écrite vers {out_name} — caps négociées: "
                     f"{caps.to_string() if caps else '?'}")
            stats["logged_caps"] = True
            stats["last_log"] = now
        elif now - stats["last_log"] >= 10.0:
            log.info(f"frames écrites vers {out_name}: total={stats['n']}")
            stats["last_log"] = now
        return Gst.FlowReturn.OK

    asink = pipe.get_by_name("asink")
    if asink is not None:
        asink.connect("new-sample", on_sample)
    # Filet : si AUCUNE frame n'est arrivée après 5s, on le crie fort.
    def warn_if_no_frames():
        if stats["n"] == 0:
            log.warning(f"AUCUNE frame poussée vers {out_name} après 5s "
                        f"(backend={backend}, node={node}) — gamescope ne livre "
                        f"rien sur cette source → écran noir garanti.")
        return False
    add_timeout(5000, warn_if_no_frames)

    # --- Snapshot diagnostic --------------------------------------------
    # Encode en JPEG la frame copiée par la sonde (voir snapbuf). Permet de
    # TRANCHER : image noire → gamescope ne livre rien d'utile (changer de
    # source) ; vraie image → le contenu est bon, le noir vient de Discord.
    SNAP = os.path.expanduser("~/steamcord-snap.jpg")

    def encode_snapbuf(path):
        """Encode la frame copiée par la sonde en JPEG → path. (ok, détail)."""
        sp = Gst.parse_launch(
            f"appsrc name=snapsrc ! videoconvert ! jpegenc ! "
            f"filesink location={path}")
        asrc = sp.get_by_name("snapsrc")
        asrc.set_property("caps", snapbuf["caps"])
        asrc.set_property("format", Gst.Format.TIME)
        sp.set_state(Gst.State.PLAYING)
        asrc.emit("push-buffer", Gst.Buffer.new_wrapped(snapbuf["data"]))
        asrc.emit("end-of-stream")
        msg = sp.get_bus().timed_pop_filtered(
            5 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR)
        sp.set_state(Gst.State.NULL)
        size = os.path.getsize(path) if os.path.exists(path) else 0
        if msg is not None and msg.type == Gst.MessageType.ERROR:
            e, d = msg.parse_error()
            return False, f"encode: {e} | {d}"
        if size <= 0:
            return False, f"fichier vide ({path})"
        return True, f"{size} octets"

    def write_snapshot():
        try:
            ok2, detail = encode_snapbuf(SNAP)
            if ok2:
                log.info(f"snapshot écrit → {SNAP} ({detail}) — frame "
                         f"réellement poussée vers {DEVICE}")
            else:
                log.warning(f"snapshot KO: {detail}")
        except Exception as e:
            log.warning(f"snapshot KO: {e!r}")
        return False

    # --- Aperçu QAM -------------------------------------------------------
    # Le CEF de Steam (QAM) ne peut PAS ouvrir /dev/video42 par getUserMedia
    # en gamescope (pas d'accès caméra) — vu 02/07 : le SelfPreview affichait
    # « aucun écran mode jeu » alors que le pipeline coulait. À la place, on
    # encode la dernière frame copiée toutes les 2s vers PREVIEW (tmpfs,
    # écriture atomique), servi en base64 par main.get_camera_preview().
    PREVIEW = "/tmp/steamcord-preview.jpg"

    def write_preview():
        if snapbuf["data"] is None:
            return True
        try:
            ok2, _ = encode_snapbuf(PREVIEW + ".tmp")
            if ok2:
                os.replace(PREVIEW + ".tmp", PREVIEW)
        except Exception:
            pass
        return True  # timer répétitif

    if not STDOUT_MODE:
        add_timeout(2000, write_preview)

    ret = pipe.set_state(Gst.State.PLAYING)
    log.info(f"set_state(PLAYING) → {ret} (backend={backend}, device={DEVICE}, node={node}, display={display})")
    try:
        loop.run()
    finally:
        # Retirer TOUS les timeouts encore en attente (sinon ils refireront dans
        # l'itération suivante → tempête de pipelines + fuite FD).
        for sid in sources:
            try:
                GLib.source_remove(sid)
            except Exception:
                pass
        pipe.set_state(Gst.State.NULL)
        # Fermer le writer EN DERNIER : le device repasse OUTPUT-only à la
        # fermeture (exclusive_caps) et disparaît des videoinputs de Discord.
        # En mode tuyau, on le GARDE : le pipeline suivant écrit dans le même.
        if not STDOUT_MODE:
            try:
                os.close(dev_fd)
            except OSError:
                pass
    return ok["value"]


def main():
    if STDOUT_MODE:
        start_brb_listener()             # avant Gst.init : masque hérité par ses threads
        start_metronome()
    Gst.init(None)

    # On tente d'abord le node PipeWire gamescope (capture "officielle"), mais
    # sans s'éterniser : il est capricieux/absent. Attente courte (~30s).
    node = None
    for _ in range(15):
        node = find_screen_node()
        if node:
            break
        log.info("aucun node écran PipeWire pour l'instant, attente…")
        time.sleep(2)
    display = find_x_display()

    # Stratégies de capture, par ordre de préférence, avec bascule auto en cas
    # d'erreur GStreamer (boucle infinie jusqu'à arrêt explicite) :
    #   1. pipewiresrc path=<node gamescope>   (si node trouvé)
    #   2. pipewiresrc            (plain, PipeWire choisit la source par défaut —
    #      c'est le chemin par défaut de decky-streamer, souvent le plus fiable)
    #   3. ximagesrc display=:1   (X nested du jeu — dernier recours)
    strategies = []
    if node:
        strategies.append(("pipewire", node, None))
    strategies.append(("pipewire", None, None))
    strategies.append(("ximagesrc", None, display))

    i = 0
    fails = 0
    while True:
        backend, n, disp = strategies[i % len(strategies)]
        normal = run_backend(backend, n, disp)
        if normal:
            break  # arrêt demandé (process tué par stop_screen_camera)
        # erreur → stratégie suivante, petite pause anti-boucle-folle.
        # Si le node a disparu (jeu quitté), on re-cherche pour le prochain tour.
        if n and not find_screen_node():
            try:
                strategies = [s for s in strategies if not (s[0] == "pipewire" and s[1])]
            except Exception:
                pass
        i += 1
        fails += 1
        # Backoff progressif : quand AUCUNE source ne marche (typiquement hors
        # gamescope, en Bureau), spinner à 2s épuisait les FD. On plafonne à 30s.
        time.sleep(min(2 + fails, 30))


if __name__ == "__main__":
    main()
