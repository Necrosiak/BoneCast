"""Helpers env / compte Steam pour BoneCast (portés de Steamcord/vesktop.py)."""
import os
import re
from pathlib import Path

_STEAM_ROOTS = ("~/.steam/steam", "~/.local/share/Steam", "~/.steam/root")


def steam_account_id():
    """AccountID (32-bit, str) de la session Steam ACTIVE. registry.vdf ActiveUser
    d'abord (mis à jour live au switch de compte ; 0 = déconnecté, ignoré), sinon
    loginusers.vdf MostRecent (SteamID64 → accountid). 'default' en dernier recours."""
    try:
        reg = (Path.home() / ".steam/registry.vdf").read_text(errors="ignore")
        m = re.search(r'"ActiveUser"\s+"(\d+)"', reg)
        if m and m.group(1) != "0":
            return m.group(1)
    except OSError:
        pass
    for root in _STEAM_ROOTS:
        p = Path(os.path.expanduser(root)) / "config/loginusers.vdf"
        try:
            data = p.read_text(errors="ignore")
        except OSError:
            continue
        for m in re.finditer(r'"(\d{17})"\s*\{(.*?)\}', data, re.S):
            sid, block = m.groups()
            if re.search(r'"MostRecent"\s+"1"', block):
                return str(int(sid) - 76561197960265728)
    return "default"


def user_env():
    """Env pour joindre le bus/affichage user + éviter le libcrypto de PyInstaller.
    Le backend est lancé par plugin_loader (root) et hérite d'un env root cassé →
    on redérive XDG_RUNTIME_DIR/DBUS depuis notre uid réel et on purge LD_* PyInstaller."""
    uid = os.getuid()
    rt = f"/run/user/{uid}"
    env = {**os.environ,
           "XDG_RUNTIME_DIR": rt,
           "DBUS_SESSION_BUS_ADDRESS": f"unix:path={rt}/bus"}
    orig = env.pop("LD_LIBRARY_PATH_ORIG", None)
    if orig is not None:
        env["LD_LIBRARY_PATH"] = orig
    else:
        env.pop("LD_LIBRARY_PATH", None)
    env.pop("LD_PRELOAD", None)
    return env


def steam_display_env():
    """DISPLAY/XAUTHORITY/WAYLAND_DISPLAY de la VRAIE session graphique, lus dans
    l'environ du process Steam (~/.steampid). L'env de plugin_loader n'a pas
    XAUTHORITY → le serveur X refuse la connexion (« Authorization required »)
    et tout process GTK (overlay chat) meurt avant d'afficher quoi que ce soit.
    Fallback : cookie xauth_* de /run/user/<uid> (KDE le pose là)."""
    out = {}
    try:
        pid = open(os.path.expanduser("~/.steampid")).read().strip()
        with open(f"/proc/{pid}/environ", "rb") as f:
            for item in f.read().split(b"\0"):
                k, _, v = item.partition(b"=")
                if k in (b"DISPLAY", b"XAUTHORITY", b"WAYLAND_DISPLAY"):
                    out[k.decode()] = v.decode(errors="ignore")
    except Exception:
        pass
    if "XAUTHORITY" not in out:
        import glob
        cookies = sorted(glob.glob(f"/run/user/{os.getuid()}/xauth_*"))
        if cookies:
            out["XAUTHORITY"] = cookies[-1]
    return out
