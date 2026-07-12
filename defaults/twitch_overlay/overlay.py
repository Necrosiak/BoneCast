#!/usr/bin/env python3
# Fenêtre overlay du chat Twitch pour Steamcord.
# WebKitGTK plein écran TRANSPARENTE chargeant chat.html ; pose l'atome
# GAMESCOPE_EXTERNAL_OVERLAY sur son window X11 (= mécanisme mangoapp) → en
# gamemode, gamescope la peint sur le plan overlay au-dessus du jeu.
#
# Usage : overlay.py --channel <login> [--state-dir <dir>]
#   --state-dir : dossier où vit overlay_state.json (piloté par le QAM), poll-é
#                 en live par la page, + data dir WebKit persistant (localStorage).
import os, sys, json, argparse
os.environ["GDK_BACKEND"] = "x11"  # window X11 sous XWayland → XID + atome settable

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, WebKit2, Gdk, GLib

HERE = os.path.dirname(os.path.abspath(__file__))
CHAT_HTML = os.path.join(HERE, "chat.html")


def set_overlay_atom(xid):
    """Pose GAMESCOPE_EXTERNAL_OVERLAY=1 (comme mangoapp) + type fenêtre OSD.
    Le type KDE « on-screen-display » (popup de volume) vit dans une couche
    KWin AU-DESSUS du plein écran ACTIF — sans lui, Big Picture focalisé
    recouvre l'overlay (la couche notification passe dessous)."""
    try:
        from Xlib import display, Xatom
        d = display.Display()
        w = d.create_resource_object("window", xid)
        w.change_property(d.intern_atom("GAMESCOPE_EXTERNAL_OVERLAY"), Xatom.CARDINAL, 32, [1])
        w.change_property(
            d.intern_atom("_NET_WM_WINDOW_TYPE"), Xatom.ATOM, 32,
            [d.intern_atom("_KDE_NET_WM_WINDOW_TYPE_ON_SCREEN_DISPLAY"),
             d.intern_atom("_NET_WM_WINDOW_TYPE_NOTIFICATION")])
        d.sync(); d.close()
        return True
    except Exception as e:
        print("[overlay] atome KO:", e, flush=True)
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True)
    ap.add_argument("--state-dir", default=os.path.expanduser("~/.local/share/bonecast/twitch_overlay"))
    args = ap.parse_args()

    channel = args.channel.strip().lstrip("#").lower()
    state_dir = args.state_dir
    os.makedirs(state_dir, exist_ok=True)
    state_path = os.path.join(state_dir, "overlay_state.json")
    # Config initiale = overlay_state.json s'il existe (posé par le QAM).
    init = {}
    try:
        with open(state_path) as f:
            init = json.load(f)
    except Exception:
        pass
    init["channel"] = channel
    init["stateUrl"] = "file://" + state_path

    # Contexte WebKit à data dir PERSISTANT → le localStorage (réglages du
    # panneau ⚙ en desktop) survit aux relances.
    dm = WebKit2.WebsiteDataManager(
        base_data_directory=os.path.join(state_dir, "wk-data"),
        base_cache_directory=os.path.join(state_dir, "wk-cache"),
    )
    ctx = WebKit2.WebContext.new_with_website_data_manager(dm)

    # Injecte window.OVERLAY_CFG AVANT le chargement du document.
    ucm = WebKit2.UserContentManager()
    script = "window.OVERLAY_CFG = %s;" % json.dumps(init)
    ucm.add_script(WebKit2.UserScript(
        script, WebKit2.UserContentInjectedFrames.ALL_FRAMES,
        WebKit2.UserScriptInjectionTime.START, None, None))

    win = Gtk.Window()
    win.set_decorated(False)
    win.set_skip_taskbar_hint(True)
    win.set_skip_pager_hint(True)
    win.set_app_paintable(True)
    win.set_title("BoneCast Twitch Chat")
    # Overlay = affichage PUR : ne doit JAMAIS prendre le focus ni manger les
    # inputs. En gamemode gamescope l'isole déjà (plan overlay), mais en
    # Bureau/Big Picture la fenêtre plein écran volait le focus de Steam →
    # plus aucun input possible. accept_focus(False) + keep_above + région
    # d'input VIDE (posée au map, plus bas) = clics/manette traversent.
    win.set_accept_focus(False)
    win.set_focus_on_map(False)
    win.set_can_focus(False)
    win.set_keep_above(True)
    win.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)

    # Taille EXPLICITE = plein écran de la sortie (gamescope over-game ne honore
    # pas toujours fullscreen() → sans taille, GTK dimensionne la fenêtre à la
    # taille naturelle du contenu, ancrée en 0,0 : la boîte de chat « bas-droite »
    # se retrouve tronquée dans le coin top-left). On force la géométrie du moniteur.
    sw, sh = 1920, 1080
    try:
        disp = Gdk.Display.get_default()
        mon = disp.get_primary_monitor() or disp.get_monitor(0)
        geo = mon.get_geometry()
        if geo.width > 0 and geo.height > 0:
            sw, sh = geo.width, geo.height
    except Exception as e:
        print("[overlay] géométrie moniteur KO, fallback 1920x1080:", e, flush=True)
    win.set_default_size(sw, sh)
    win.set_size_request(sw, sh)
    win.move(0, 0)
    win.fullscreen()

    rgba = win.get_screen().get_rgba_visual()
    if rgba:
        win.set_visual(rgba)

    wv = WebKit2.WebView(web_context=ctx, user_content_manager=ucm)
    wv.set_background_color(Gdk.RGBA(0, 0, 0, 0))
    # file:// a besoin de pouvoir fetch les CDN emotes + WSS → autorise l'accès.
    s = wv.get_settings()
    s.set_property("allow-file-access-from-file-urls", True)
    s.set_property("allow-universal-access-from-file-urls", True)
    wv.load_uri("file://" + CHAT_HTML + "?channel=" + channel)
    win.add(wv)

    def on_map(_w):
        gdk_win = win.get_window()
        xid = gdk_win.get_xid()
        ok = set_overlay_atom(xid)
        # Région d'input VIDE (X11 Shape) : la fenêtre devient transparente aux
        # clics/touches — tout passe à la fenêtre du dessous (Steam/jeu). À poser
        # après le map, sinon GTK/WebKit la réinitialise.
        try:
            import cairo
            gdk_win.input_shape_combine_region(cairo.Region(), 0, 0)
            passthrough = True
        except Exception as e:
            passthrough = False
            print("[overlay] input passthrough KO:", e, flush=True)
        print("[overlay] mapped xid=%s atom=%s passthrough=%s channel=%s"
              % (hex(xid), ok, passthrough, channel), flush=True)

    win.connect("map", on_map)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
