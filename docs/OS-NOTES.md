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

## Virtual camera (game capture)

Same mechanism as Steamcord — the `v4l2loopback` kernel module feeds
`/dev/video42`:

| Distro | Command |
|---|---|
| Arch / CachyOS | `sudo pacman -S v4l2loopback-dkms` |
| Fedora | `sudo dnf install v4l2loopback` (RPM Fusion: `akmod-v4l2loopback`) |
| Bazzite | preinstalled |
| Debian / Ubuntu | `sudo apt install v4l2loopback-dkms` |
| openSUSE | `sudo zypper install v4l2loopback` |

Configuration (one-time, shared with Steamcord if you use both — one module,
one device):

```bash
# /etc/modprobe.d/v4l2loopback.conf
options v4l2loopback exclusive_caps=1 card_label="BoneCast" video_nr=42
# /etc/modules-load.d/v4l2loopback.conf
v4l2loopback
```

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
