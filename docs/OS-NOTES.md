# OS notes — BoneCast on any Linux distribution

BoneCast ships **one build for every Linux distro**. Everything external is
detected at runtime; when something is missing, the QAM shows the **exact
install command for the package manager it detected** (pacman / rpm-ostree /
dnf / zypper / apt). This page sums up the system pieces streaming uses.

Base requirements: **Steam + [Decky Loader](https://decky.xyz/)** and
PipeWire audio.

## ffmpeg (encoding + RTMP push)

| Distro | Command |
|---|---|
| Arch / CachyOS | `sudo pacman -S ffmpeg` |
| Fedora | enable RPM Fusion, then `sudo dnf swap ffmpeg-free ffmpeg --allowerasing` |
| Bazzite | preinstalled |
| Debian / Ubuntu | `sudo apt install ffmpeg` |
| openSUSE | `sudo zypper install ffmpeg` (Packman repo recommended) |

⚠️ **Fedora note:** the default `ffmpeg` is *ffmpeg-free*, which has **no
libx264** — the software encoder BoneCast falls back on. BoneCast probes this
before going live and tells you; the RPM Fusion swap above fixes it.

Hardware encoders (**NVENC** on Nvidia, **VAAPI** on AMD/Intel) are probed
automatically and preferred when they actually work on your GPU.

## Game capture: no virtual camera needed

Since v0.4.1 the capture feeder hands the game frames straight to ffmpeg
through a pipe. The `v4l2loopback` module and `/dev/video42` are **no longer
used**: nothing to install or load, and no `sudo` (SteamOS doesn't load that
module, and loading it needs root). If you had set it up only for BoneCast, you
can remove it; Steamcord still uses it for its Gaming Mode camera fallback.

## GStreamer bindings (capture pipeline)

The capture feeder runs on the **system python** and needs the GObject
bindings + the PipeWire GStreamer plugin:

| Distro | Command |
|---|---|
| Arch / CachyOS | `sudo pacman -S python-gobject gst-plugin-pipewire` |
| Fedora | `sudo dnf install python3-gobject pipewire-gstreamer` |
| Bazzite | preinstalled |
| Debian / Ubuntu | `sudo apt install python3-gi gir1.2-gstreamer-1.0 gstreamer1.0-pipewire` |
| openSUSE | `sudo zypper install python3-gobject gstreamer-plugin-pipewire` |

---

Something missing for your distro?
[Open an issue](https://github.com/Necrosiak/BoneCast/issues) — reports from
non-Bazzite systems are exactly what makes this page grow.
