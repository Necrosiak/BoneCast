#!/usr/bin/env python3
"""Overlay « regarder des lives Twitch » par-dessus le jeu (jusqu'à 4).

UNE seule fenêtre, plein écran et transparente : gamescope n'expose qu'UN
plan overlay et ne place pas les fenêtres (une fenêtre 640×360 atterrit en
haut à gauche quoi qu'on demande — constaté). Les vignettes sont donc peintes
AUX BONNES POSITIONS À L'INTÉRIEUR d'une surface plein écran.

GTK/Cairo et pas WebKit/MSE : SteamOS n'embarque aucun binding WebKitGTK
(cf. Steamcord #22), la voie web serait Bazzite-only.

Piloté par un fichier d'état relu à chaud (`state.json` dans --state-dir), sur
le modèle de l'overlay de Steamcord : le backend écrit, le helper s'adapte
sans redémarrer — changer de disposition ne coupe pas les flux.

  watch_overlay.py --state-dir ~/.local/share/bonecast/watch
"""
import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import threading
import time

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk  # noqa: E402
import cairo  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import twitch_hls  # noqa: E402


# ── Atomes gamescope ────────────────────────────────────────────────────────
def set_overlay_atom(xid):
    """GAMESCOPE_EXTERNAL_OVERLAY=1 + type OSD, en ctypes.

    python-xlib n'est pas garanti présent (absent de SteamOS) : sans ce repli,
    gamescope ne peindrait jamais la fenêtre par-dessus le jeu.
    """
    from ctypes import cdll, c_char_p, c_int, c_ulong, c_void_p, POINTER
    x = cdll.LoadLibrary("libX11.so.6")
    x.XOpenDisplay.argtypes = [c_char_p]; x.XOpenDisplay.restype = c_void_p
    x.XInternAtom.argtypes = [c_void_p, c_char_p, c_int]; x.XInternAtom.restype = c_ulong
    x.XChangeProperty.argtypes = [c_void_p, c_ulong, c_ulong, c_ulong, c_int, c_int,
                                  POINTER(c_ulong), c_int]
    x.XSync.argtypes = [c_void_p, c_int]
    x.XCloseDisplay.argtypes = [c_void_p]
    d = x.XOpenDisplay(None)
    if not d:
        raise RuntimeError("XOpenDisplay failed")
    try:
        XA_ATOM, XA_CARDINAL, REPLACE = 4, 6, 0
        one = (c_ulong * 1)(1)
        x.XChangeProperty(d, xid, x.XInternAtom(d, b"GAMESCOPE_EXTERNAL_OVERLAY", False),
                          XA_CARDINAL, 32, REPLACE, one, 1)
        types = (c_ulong * 2)(
            x.XInternAtom(d, b"_KDE_NET_WM_WINDOW_TYPE_ON_SCREEN_DISPLAY", False),
            x.XInternAtom(d, b"_NET_WM_WINDOW_TYPE_NOTIFICATION", False))
        x.XChangeProperty(d, xid, x.XInternAtom(d, b"_NET_WM_WINDOW_TYPE", False),
                          XA_ATOM, 32, REPLACE, types, 2)
        x.XSync(d, False)
    finally:
        x.XCloseDisplay(d)


def sink_input_of(pid):
    """Index du flux PulseAudio ouvert par le processus `pid`, ou None.

    Sortie texte forcée en anglais (LC_ALL=C) : en français les en-têtes sont
    traduits, et `pactl -f json` rend `(null)` sur une description accentuée.
    Timeout : un outil PipeWire pendu ne doit pas bloquer le réglage.
    """
    out = subprocess.run(["pactl", "list", "sink-inputs"], capture_output=True,
                         text=True, timeout=3,
                         env={**os.environ, "LC_ALL": "C"}).stdout
    idx = None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Sink Input #"):
            idx = line[len("Sink Input #"):]
        elif line == f'application.process.id = "{pid}"' and idx:
            return idx
    return None


# ── Dispositions ────────────────────────────────────────────────────────────
# Chaque disposition rend une liste de rectangles (x, y, w, h) EN FRACTIONS de
# l'écran, dans l'ordre des flux. Travailler en fractions garde le même rendu
# du 1280×800 d'un Deck au 1920×1080 d'un téléviseur.
LAYOUTS = {
    1: {
        "corner_br":  lambda: [(0.62, 0.60, 0.36, 0.36)],
        "corner_bl":  lambda: [(0.02, 0.60, 0.36, 0.36)],
        "corner_tr":  lambda: [(0.62, 0.04, 0.36, 0.36)],
        "corner_tl":  lambda: [(0.02, 0.04, 0.36, 0.36)],
        "side_right": lambda: [(0.60, 0.22, 0.38, 0.56)],
        "side_left":  lambda: [(0.02, 0.22, 0.38, 0.56)],
        "full":       lambda: [(0.0, 0.0, 1.0, 1.0)],
    },
    2: {
        "side_by_side": lambda: [(0.02, 0.30, 0.47, 0.40), (0.51, 0.30, 0.47, 0.40)],
        "stacked":      lambda: [(0.62, 0.08, 0.36, 0.40), (0.62, 0.52, 0.36, 0.40)],
        "stacked_left": lambda: [(0.02, 0.08, 0.36, 0.40), (0.02, 0.52, 0.36, 0.40)],
        "pip":          lambda: [(0.0, 0.0, 1.0, 1.0), (0.72, 0.70, 0.26, 0.26)],
    },
    3: {
        "one_plus_two": lambda: [(0.02, 0.22, 0.60, 0.56),
                                 (0.64, 0.22, 0.34, 0.27),
                                 (0.64, 0.51, 0.34, 0.27)],
        "row":          lambda: [(0.01, 0.36, 0.32, 0.28),
                                 (0.34, 0.36, 0.32, 0.28),
                                 (0.67, 0.36, 0.32, 0.28)],
        "column":       lambda: [(0.68, 0.03, 0.30, 0.30),
                                 (0.68, 0.35, 0.30, 0.30),
                                 (0.68, 0.67, 0.30, 0.30)],
        "column_left":  lambda: [(0.02, 0.03, 0.30, 0.30),
                                 (0.02, 0.35, 0.30, 0.30),
                                 (0.02, 0.67, 0.30, 0.30)],
    },
    4: {
        "grid":         lambda: [(0.02, 0.06, 0.47, 0.42), (0.51, 0.06, 0.47, 0.42),
                                 (0.02, 0.52, 0.47, 0.42), (0.51, 0.52, 0.47, 0.42)],
        "one_plus_three": lambda: [(0.02, 0.18, 0.62, 0.64),
                                   (0.66, 0.18, 0.32, 0.20),
                                   (0.66, 0.40, 0.32, 0.20),
                                   (0.66, 0.62, 0.32, 0.20)],
        "row":          lambda: [(0.01, 0.38, 0.243, 0.24), (0.255, 0.38, 0.243, 0.24),
                                 (0.502, 0.38, 0.243, 0.24), (0.749, 0.38, 0.243, 0.24)],
    },
}
DEFAULT_LAYOUT = {1: "corner_br", 2: "side_by_side", 3: "one_plus_two", 4: "grid"}

# Gamescope peut laisser apparaître sa barre supérieure (et parfois la barre
# inférieure) au-dessus d'un external overlay, notamment pendant le QAM. Sans
# zone sûre, une vignette « haut » commence à 4 % de l'écran : 43 px en 1080p,
# soit sous une barre Steam d'environ 52 px. Les valeurs en fractions restent
# donc portables au Deck comme à une TV, sans cacher les contrôles système.
SAFE_TOP_FRACTION = 0.065
SAFE_BOTTOM_FRACTION = 0.040
SAFE_TOP_MIN_PX = 48
SAFE_BOTTOM_MIN_PX = 32


def compute_rects(n, layout, sw, sh, scale=1.0):
    """Rectangles en pixels pour n flux. `scale` rétrécit/agrandit autour du
    centre de chaque vignette, sans jamais sortir de la zone sûre.

    La disposition « plein écran » garde volontairement l'écran entier.
    """
    n = max(1, min(4, n))
    table = LAYOUTS[n]
    fracs = table.get(layout, table[DEFAULT_LAYOUT[n]])()
    full_screen = layout == "full"
    top = 0 if full_screen else max(SAFE_TOP_MIN_PX, round(sh * SAFE_TOP_FRACTION))
    bottom = 0 if full_screen else max(SAFE_BOTTOM_MIN_PX, round(sh * SAFE_BOTTOM_FRACTION))
    usable_h = max(2, sh - top - bottom)
    out = []
    for (fx, fy, fw, fh) in fracs:
        w, h = fw * sw * scale, fh * sh * scale
        if not full_screen:
            h = fh * usable_h * scale
        cx = (fx + fw / 2) * sw
        cy = top + (fy + fh / 2) * usable_h
        x, y = cx - w / 2, cy - h / 2
        x = max(0, min(sw - w, x))
        y = max(top, min(sh - bottom - h, y))
        # Dimensions paires : un scaler ffmpeg refuse les tailles impaires.
        out.append((int(x), int(y), max(2, int(w) // 2 * 2), max(2, int(h) // 2 * 2)))
    return out


# ── Un flux ─────────────────────────────────────────────────────────────────
class Feed:
    """Un live : un ffmpeg vidéo → BGRA brut, plus l'audio à la demande."""

    def __init__(self, login, max_fps=30, oauth_token=None, on_frame=None):
        self.login = login
        self.max_fps = max_fps
        self.oauth_token = oauth_token
        self.on_frame = on_frame        # callback(feed) appelé à chaque image
        self.w = self.h = 0
        self.frame = None
        self.lock = threading.Lock()
        self.proc = None
        self.audio_proc = None
        self.audio_base = 1.0       # volume cuit dans le filtre ffmpeg au départ
        self.audio_volume = 1.0     # volume effectif demandé
        self.audio_retry_at = 0     # anti-boucle si ffmpeg audio meurt aussitôt
        self._vol_lock = threading.Lock()
        self._vol_target = None
        self._vol_busy = False
        self.thread = None
        self.stop = False
        self.paused = False
        self.error = None
        self.quality = None
        self.qualities = []
        self.frames = 0
        self.gen = 0              # incrémenté à chaque image (le rendu l'observe)
        self.drawn_gen = -1       # dernière génération effectivement peinte
        self.ended = False        # le live s'est arrêté (ou la connexion a lâché)
        self.retry_at = 0         # prochaine tentative de reconnexion
        self.dx = self.dy = 0     # offset de centrage de la vidéo dans son rect
        self.box = (0, 0)         # boîte (w,h) allouée par la disposition

    # La qualité suit la taille d'AFFICHAGE : décoder du 1080p pour une
    # vignette de 360 px coûte 0,81 cœur au lieu de 0,08, pour un résultat
    # identique à l'écran (mesuré le 24/07).
    def start(self, box_w, box_h):
        self.stop = False
        self.box = (box_w, box_h)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _fit(self, aspect):
        # Plus grande taille au ratio `aspect` qui tient dans la boîte, centrée
        # (letterbox). On prend le ratio RÉEL de la source, pas un 16:9 supposé.
        box_w, box_h = self.box
        vw = box_w
        vh = vw / aspect
        if vh > box_h:
            vh = box_h
            vw = vh * aspect
        self.w = max(2, int(vw) // 2 * 2)
        self.h = max(2, int(vh) // 2 * 2)
        self.dx = (box_w - self.w) // 2
        self.dy = (box_h - self.h) // 2

    def _run(self):
        try:
            q, qs = twitch_hls.resolve(self.login, target_height=self.h,
                                       max_fps=self.max_fps,
                                       oauth_token=self.oauth_token)
            self.qualities = qs
            self.quality = q
            aspect = (q["width"] / q["height"]) if q.get("height") else 16 / 9
            self._fit(aspect)
        except twitch_hls.OfflineError as e:
            # Chaîne hors ligne : ce n'est pas une panne, c'est un état. On
            # l'affiche et on retentera — un streamer qui s'arrête peut
            # revenir, et rester sur un carré noir muet n'apprend rien
            # (vécu : kamet0 a terminé son live en plein test, l'overlay est
            # resté noir sans un mot).
            self.error = str(e)
            self.ended = True
            self.retry_at = time.time() + 30
            return
        except Exception as e:
            self.error = str(e)
            self.ended = True
            self.retry_at = time.time() + 30
            return
        # Config IDENTIQUE au prototype que le user a validé « parfait » :
        # nobuffer + low_delay + -re + reconnexion HTTP. Ne plus s'en écarter
        # sans raison — chaque variation testée a empiré la fluidité.
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error",
               "-reconnect", "1", "-reconnect_streamed", "1",
               "-reconnect_delay_max", "5",
               "-fflags", "nobuffer", "-flags", "low_delay",
               "-re", "-i", q["url"], "-an",
               "-vf", f"scale={self.w}:{self.h}",
               "-pix_fmt", "bgra", "-f", "rawvideo", "-"]
        try:
            # stderr conservé : un flux qui reste noir doit pouvoir dire
            # pourquoi (jeter stderr, c'est se priver du seul motif).
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)
            threading.Thread(target=self._drain_stderr, daemon=True).start()
        except Exception as e:
            self.error = f"ffmpeg: {e}"
            return
        size = self.w * self.h * 4
        while not self.stop:
            # read() sur un pipe rend ce qui est DISPONIBLE (~64 Ko), pas la
            # trame : il faut boucler, sinon la 1re lecture partielle passe
            # pour une fin de flux et l'overlay reste noir.
            chunks, got = [], 0
            while got < size:
                part = self.proc.stdout.read(size - got)
                if not part:
                    break
                chunks.append(part); got += len(part)
            if got < size:
                # Flux terminé (live coupé, réseau perdu) : on SORT au lieu de
                # tourner à vide — sinon le compteur s'emballe (997 « fps »
                # observés) et l'écran reste noir sans explication.
                self.ended = True
                self.retry_at = time.time() + 15
                if not self.error:
                    self.error = "flux interrompu"
                break
            if self.paused:
                continue
            with self.lock:
                self.frame = b"".join(chunks)
                self.frames += 1
                self.bytes = getattr(self, "bytes", 0) + got
            self.gen += 1
            # Redraw déclenché à l'image, comme le prototype fluide : idle_add
            # en priorité BASSE (PRIORITY_DEFAULT_IDLE) — exactement son réglage.
            if self.on_frame and not self.paused:
                self.on_frame(self)
        self._kill(self.proc); self.proc = None

    # ── Audio : un seul flux sonore à la fois (on ne peut pas écouter 4
    # personnes en même temps). Process séparé → changer de flux sonore ne
    # coupe pas la vidéo, et on ne décode l'audio que là où on l'écoute.
    def audio_alive(self):
        return self.audio_proc is not None and self.audio_proc.poll() is None

    def audio_on(self, volume=1.0):
        if self.audio_alive() or not self.quality or time.time() < self.audio_retry_at:
            return
        self.audio_off()
        volume = max(0.0, min(2.0, volume))
        from shutil import which
        live = which("pactl") is not None
        # Avec pactl, le volume est posé EN ABSOLU sur le flux dès qu'il existe,
        # jamais cuit dans le filtre : WirePlumber réapplique le volume mémorisé
        # pour « BoneCast » à chaque nouveau flux, et un filtre en plus
        # atténuerait deux fois (40 % × 40 % mesuré le 15/09). Le volume
        # mémorisé étant le dernier réglage, il n'y a pas de pic au départ.
        # ⛔ state.restore-props=false n'est PAS la solution : le flux démarre
        # alors à 0 %, même sous un nom neuf (mesuré 3 fois).
        self.audio_base = 1.0 if live else volume
        self.audio_volume = volume
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error",
               "-re", "-i", self.quality["url"], "-vn"]
        if not live:
            cmd += ["-af", f"volume={volume:.2f}"]
        cmd += ["-f", "pulse", "-name", "BoneCast", "-buffer_duration", "80",
                f"BoneCast · {self.login}"]
        # Toujours la sortie PAR DÉFAUT : sans ça, WirePlumber mémorise la
        # sortie d'un flux déplacé à la main (par nom d'application) et y
        # renvoie tous les suivants — mesuré le 15/09 : témoin renvoyé vers
        # l'ancienne sortie, flux avec cette propriété sur la sortie par défaut.
        # Sans cible fixée, le flux suit aussi un changement de sortie par
        # défaut en cours de lecture (linking.follow-default-target).
        env = dict(os.environ)
        env["PULSE_PROP"] = " ".join(filter(None, [env.get("PULSE_PROP", ""),
                                                  "state.restore-target=false"]))
        try:
            self.audio_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                               stderr=subprocess.DEVNULL, env=env)
            self.audio_retry_at = time.time() + 5
            if live:
                self._queue_volume(self.audio_proc.pid, volume)
        except Exception as e:
            self.error = f"audio: {e}"
            self.audio_retry_at = time.time() + 30

    def set_volume(self, volume):
        """Change le volume SANS couper le son quand c'est possible.

        pactl règle le flux de CE ffmpeg (repéré par son PID) en proportion du
        volume cuit au départ. Relancer ffmpeg à chaque cran du curseur
        couperait le son une à deux secondes (reconnexion HLS).
        """
        volume = max(0.0, min(2.0, volume))
        if abs(volume - self.audio_volume) < 0.005:
            return
        if not self.audio_alive():
            self.audio_volume = volume
            return
        from shutil import which
        base = self.audio_base
        ratio = volume / base if base >= 0.05 else None
        if ratio is None or ratio > 4 or not which("pactl"):
            # Volume de départ nul (rien à multiplier) ou hors d'échelle :
            # seul un redémarrage avec le nouveau filtre est juste.
            self.audio_off()
            self.audio_retry_at = 0
            self.audio_on(volume)
            return
        self.audio_volume = volume
        self._queue_volume(self.audio_proc.pid, ratio)

    def _queue_volume(self, pid, ratio):
        with self._vol_lock:
            self._vol_target = (pid, ratio)
            if self._vol_busy:
                return
            self._vol_busy = True
        threading.Thread(target=self._volume_worker, daemon=True).start()

    def _volume_worker(self):
        # Un seul pactl à la fois, toujours sur la DERNIÈRE valeur : un curseur
        # balayé rapidement ne doit pas empiler des appels qui se doublent.
        while True:
            with self._vol_lock:
                job, self._vol_target = self._vol_target, None
                if job is None:
                    self._vol_busy = False
                    return
            pid, ratio = job
            try:
                # Au démarrage, le flux PulseAudio n'existe qu'une fois la
                # connexion HLS établie : on l'attend (≤ 8 s) au lieu de perdre
                # le réglage. Une valeur plus récente interrompt l'attente.
                idx = sink_input_of(pid)
                deadline = time.time() + 8
                while not idx and time.time() < deadline and self._vol_target is None \
                        and self.audio_proc is not None and self.audio_proc.pid == pid:
                    time.sleep(0.3)
                    idx = sink_input_of(pid)
                if idx:
                    subprocess.run(["pactl", "set-sink-input-volume", idx,
                                    f"{round(ratio * 100)}%"], timeout=3,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"[watch] volume {self.login}: {e}", flush=True)

    def audio_off(self):
        self._kill(self.audio_proc); self.audio_proc = None

    def _drain_stderr(self):
        try:
            for line in iter(self.proc.stderr.readline, b""):
                txt = line.decode(errors="replace").strip()
                if txt:
                    self.error = txt
                    print(f"[watch] {self.login} ffmpeg: {txt}", flush=True)
        except Exception:
            pass

    @staticmethod
    def _kill(p):
        if not p:
            return
        try:
            p.kill(); p.wait(timeout=3)
        except Exception:
            pass

    def close(self):
        self.stop = True
        self.audio_off()
        self._kill(self.proc)


# ── Overlay ─────────────────────────────────────────────────────────────────
class WatchOverlay:
    def __init__(self, state_dir, oauth_token=None):
        self.state_dir = state_dir
        self.oauth_token = oauth_token
        self.state_file = os.path.join(state_dir, "state.json")
        self.feeds = {}          # login → Feed
        self.order = []          # ordre d'affichage
        self.rects = []
        self.layout = None
        self.focus = None        # login affiché en grand, seul
        self.audio = None
        self.volume = 1.0
        self.scale = 1.0
        self.opacity = 1.0
        self.max_fps = 30
        self.area = None
        self.mtime = 0
        self.sw = self.sh = 0
        self.rect_of = {}        # login → (x,y,w,h) courant, pour le redraw ciblé
        # Un lecteur peut produire 30 images/s alors que GTK est momentanément
        # occupé. Une idle GTK par image finit alors par remplir sa file et
        # affamer le lecteur du pipe ffmpeg. On ne garde qu'un repaint en
        # attente par flux : le prochain dessin prend toujours la frame la plus
        # récente, les frames intermédiaires n'ont aucune valeur à l'écran.
        self._redraw_pending = set()
        self._redraw_lock = threading.Lock()

    # ── état ────────────────────────────────────────────────────────────────
    def _feed_frame(self, feed):
        if not self.area or feed.login not in self.rect_of:
            return
        with self._redraw_lock:
            if feed.login in self._redraw_pending:
                return
            self._redraw_pending.add(feed.login)
        GLib.idle_add(self._redraw_feed, feed.login,
                      priority=GLib.PRIORITY_DEFAULT_IDLE)

    def _redraw_feed(self, login):
        """Exécute dans GTK un unique redraw coalescé pour un flux."""
        with self._redraw_lock:
            self._redraw_pending.discard(login)
        r = self.rect_of.get(login)
        if r and self.area:
            self.area.queue_draw_area(*r)
        return GLib.SOURCE_REMOVE

    def read_state(self):
        try:
            m = os.path.getmtime(self.state_file)
        except OSError:
            return
        if m == self.mtime:
            return
        self.mtime = m
        try:
            with open(self.state_file) as f:
                st = json.load(f)
        except Exception as e:
            print(f"[watch] état illisible: {e}", flush=True)
            return
        self.apply(st)

    def apply(self, st):
        # `queue_draw_area` ne redessine que la région demandée. Mémoriser
        # l'ancienne position avant de modifier les rectangles est essentiel :
        # sans son invalidation, son dernier pixel reste dans la fenêtre
        # transparente après un déplacement (vignette fantôme figée).
        old_rects = tuple(self.rects)
        logins = [str(x).lower() for x in (st.get("streams") or [])][:4]
        self.layout = st.get("layout")
        self.focus = (st.get("focus") or "").lower() or None
        self.audio = (st.get("audio") or "").lower() or None
        self.volume = float(st.get("volume", 1.0))
        self.scale = max(0.4, min(1.6, float(st.get("scale", 1.0))))
        self.opacity = max(0.15, min(1.0, float(st.get("opacity", 1.0))))
        self.max_fps = int(st.get("max_fps", 30) or 30)

        # Le focus n'affiche qu'un flux : les autres sont MIS EN PAUSE, pas
        # seulement cachés — sinon on paierait quatre décodages pour n'en
        # regarder qu'un.
        visible = [self.focus] if self.focus and self.focus in logins else logins
        self.order = visible
        self.rects = compute_rects(len(visible), self.layout,
                                   self.sw, self.sh, self.scale)
        self.rect_of = {lg: self.rects[i] for i, lg in enumerate(visible)
                        if i < len(self.rects)}
        if self.area:
            # L'ancien rectangle est repeint transparent par `on_draw`, le
            # nouveau reçoit immédiatement l'image courante.
            for r in {*old_rects, *self.rects}:
                self.area.queue_draw_area(*r)

        for lg in list(self.feeds):
            if lg not in logins:
                self.feeds.pop(lg).close()

        for i, lg in enumerate(visible):
            x, y, w, h = self.rects[i]
            f = self.feeds.get(lg)
            if f is None:
                f = self.feeds[lg] = Feed(lg, self.max_fps, self.oauth_token, self._feed_frame)
                f.start(w, h)
            elif f.box != (w, h):
                # Boîte changée → relancer ffmpeg au bon scale (qualité source
                # réévaluée au passage).
                f.close()
                f = self.feeds[lg] = Feed(lg, self.max_fps, self.oauth_token, self._feed_frame)
                f.start(w, h)
            f.paused = False

        for lg, f in self.feeds.items():
            f.paused = lg not in visible
            if lg == self.audio and lg in visible:
                f.audio_on(self.volume)
                f.set_volume(self.volume)
            else:
                f.audio_off()

    # ── rendu ───────────────────────────────────────────────────────────────
    def on_draw(self, _w, cr):
        self._draws = getattr(self, "_draws", 0) + 1
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        for i, lg in enumerate(self.order):
            if i >= len(self.rects):
                break
            x, y, w, h = self.rects[i]
            f = self.feeds.get(lg)
            if not f:
                continue
            with f.lock:
                buf = f.frame
            if buf and f.w and f.h:
                self._painted = getattr(self, "_painted", 0) + 1
                surf = cairo.ImageSurface.create_for_data(
                    bytearray(buf), cairo.FORMAT_ARGB32, f.w, f.h, f.w * 4)
                cr.save()
                # Clip à la zone IMAGE (pas à la boîte) : on peint pile la
                # vidéo 16:9, rien autour — pas de bande noire, le jeu reste
                # visible autour de la vignette.
                cr.rectangle(x + f.dx, y + f.dy, f.w, f.h); cr.clip()
                cr.set_source_surface(surf, x + f.dx, y + f.dy)
                if self.opacity >= 0.999:
                    cr.paint()
                else:
                    cr.paint_with_alpha(self.opacity)
                cr.restore()
            else:
                # Cadre d'attente + motif d'échec : un carré noir muet ne dit
                # pas si la chaîne est hors ligne ou si le flux rame.
                cr.set_source_rgba(0, 0, 0, 0.55 * self.opacity)
                cr.rectangle(x, y, w, h); cr.fill()
                cr.set_source_rgba(1, 1, 1, 0.85 * self.opacity)
                cr.select_font_face("sans", cairo.FONT_SLANT_NORMAL,
                                    cairo.FONT_WEIGHT_NORMAL)
                cr.set_font_size(max(11, min(20, h / 12)))
                msg = (f"{lg} — {f.error}" if f.error else f"{lg} — connexion…")
                cr.move_to(x + 12, y + h / 2)
                cr.show_text(msg[:60])
            if self.audio == lg and f and f.frame is not None:
                cr.set_source_rgba(0.57, 0.27, 1.0, 0.9 * self.opacity)  # violet Twitch
                cr.set_line_width(3)
                cr.rectangle(x + f.dx + 1.5, y + f.dy + 1.5, f.w - 3, f.h - 3)
                cr.stroke()
        return False

    def retry_ended(self):
        """Relance les flux terminés — un live qui s'arrête peut reprendre."""
        now = time.time()
        for lg, f in list(self.feeds.items()):
            if f.ended and f.retry_at and now >= f.retry_at and not f.paused:
                bw, bh = f.box
                f.close()
                nf = self.feeds[lg] = Feed(lg, self.max_fps, self.oauth_token, self._feed_frame)
                nf.start(bw or 640, bh or 360)
                print(f"[watch] {lg} : nouvelle tentative de connexion", flush=True)

    def tick(self):
        self.read_state()
        self.retry_ended()
        # Le son n'est lancé par `apply` que si la qualité est déjà résolue.
        # Un flux recréé (reconnexion, changement de taille) la résout plus
        # tard dans son thread : sans ce rattrapage, le son restait coupé
        # pour de bon jusqu'au prochain changement de réglage.
        f = self.feeds.get(self.audio) if self.audio else None
        if f and self.audio in self.order and f.frame is not None and not f.paused:
            f.audio_on(self.volume)
        # léger coup de pinceau périodique : rafraîchit le cadre d'attente et
        # les messages d'erreur des flux SANS image (sinon figés jusqu'au
        # prochain changement d'état).
        if self.area:
            for lg, r in self.rect_of.items():
                f = self.feeds.get(lg)
                if f and (f.frame is None or f.paused):
                    self.area.queue_draw_area(*r)
        now = time.time()
        if now - getattr(self, "_last_log", 0) > 5:
            self._last_log = now
            etat = ", ".join(
                f"{lg}:{f.frames}img/{getattr(f,'bytes',0)/1e6:.0f}Mo"
                f"{'/pause' if f.paused else ''}"
                f"{'/' + f.error[:30] if f.error else ''}"
                for lg, f in self.feeds.items())
            print(f"[watch] rects={self.rects} order={self.order} | {etat} "
                  f"| draws={getattr(self,'_draws',0)} "
                  f"peints={getattr(self,'_painted',0)}", flush=True)
        return True

    def run(self):
        win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        win.set_app_paintable(True)
        win.set_decorated(False)
        win.set_accept_focus(False)
        win.set_focus_on_map(False)
        win.set_keep_above(True)
        vis = win.get_screen().get_rgba_visual()
        if vis:
            win.set_visual(vis)
        geo = Gdk.Display.get_default().get_monitor(0).get_geometry()
        self.sw, self.sh = geo.width, geo.height
        win.set_default_size(self.sw, self.sh)

        self.area = Gtk.DrawingArea()
        self.area.connect("draw", self.on_draw)
        win.add(self.area)

        def on_realize(_w):
            gw = win.get_window()
            set_overlay_atom(gw.get_xid())
            try:
                gw.input_shape_combine_region(cairo.Region(), 0, 0)
            except Exception as e:
                print(f"[watch] input passthrough KO: {e}", flush=True)
            v = win.get_visual()
            sc = win.get_screen()
            print(f"[watch] overlay {self.sw}x{self.sh} prêt | "
                  f"composité={sc.is_composited()} rgba_dispo={sc.get_rgba_visual() is not None} "
                  f"profondeur={v.get_depth() if v else '?'} "
                  f"taille_reelle={gw.get_width()}x{gw.get_height()}", flush=True)
        win.connect("realize", on_realize)
        win.show_all()

        self.read_state()
        # 200 ms : tick ne fait plus que l'état + les reconnexions. L'animation
        # est pilotée par l'arrivée des images (Feed.on_frame), comme dans le
        # prototype qui était fluide — un minuteur qui redessinait à l'aveugle
        # se désynchronisait du flux (saccade 15→1 fps constatée).
        GLib.timeout_add(200, self.tick)

        # Sans ça, un SIGTERM (arrêt par le backend, `timeout`, fin de session)
        # tue le helper mais PAS ses ffmpeg : ils continuent à décoder un flux
        # que plus personne n'affiche. Constaté en test — un ffmpeg orphelin
        # tournait encore 3 minutes après la fin de son helper.
        def _bye(*_a):
            self.shutdown()
            Gtk.main_quit()
            return GLib.SOURCE_REMOVE
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            GLib.unix_signal_add(GLib.PRIORITY_HIGH, sig, _bye)

        try:
            Gtk.main()
        finally:
            self.shutdown()

    def shutdown(self):
        for f in list(self.feeds.values()):
            f.close()
        self.feeds.clear()


def take_instance_lock(state_dir):
    """Garde une seule fenêtre GTK par état de visionnage.

    Le verrou est libéré automatiquement si le helper se termine brutalement.
    C'est le dernier garde-fou si le backend est rechargé entre deux clics QAM.
    """
    lock = open(os.path.join(state_dir, "overlay.lock"), "w")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        return None
    return lock


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-dir", default=os.path.expanduser(
        "~/.local/share/bonecast/watch"))
    ap.add_argument("--config", default="",
                    help="json de compte BoneCast (token OAuth → moins de pubs)")
    a = ap.parse_args()
    os.makedirs(a.state_dir, exist_ok=True)
    instance_lock = take_instance_lock(a.state_dir)
    if instance_lock is None:
        print("[watch] déjà lancé : seconde instance ignorée", flush=True)
        raise SystemExit(0)
    os.environ.setdefault("DISPLAY", ":0")
    token = None
    if a.config and os.path.exists(a.config):
        try:
            with open(a.config) as fh:
                token = ((json.load(fh).get("oauth") or {}).get("access_token"))
        except Exception as e:
            print(f"[watch] config illisible: {e}", flush=True)
    WatchOverlay(a.state_dir, token).run()
