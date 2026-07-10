# BoneCast 🦴📡

**Twitch in Steam Gaming Mode** — a [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) plugin for Steam Deck / Bazzite / SteamOS.

🌍 **Languages:** **English** · [Français](docs/README.fr.md) · [Deutsch](docs/README.de.md) · [Español](docs/README.es.md) · [Italiano](docs/README.it.md) · [Português](docs/README.pt.md) · [Nederlands](docs/README.nl.md) · [Polski](docs/README.pl.md) · [Русский](docs/README.ru.md)

> Part of the Necrosiak plugin suite, alongside
> [SkullKey](https://github.com/Necrosiak/SkullKey),
> [Steamcord](https://github.com/Necrosiak/Steamcord) and BC250-Toolkit.
> The plugin UI is translated into 9 languages and follows your SteamOS language automatically.

---

## What it does

BoneCast puts everything you need to stream to **Twitch** right in the Steam **Quick Access Menu** — no desktop, no keyboard, gamepad-friendly from login to going live.

- **One Twitch login** *(device code — gamepad friendly)*: you enter a short code on `twitch.tv/activate`, and BoneCast fetches your **stream key automatically**. No manual copy-paste, ever.
- **Go live from the QAM** — one button starts and stops the RTMP stream. A **● LIVE** badge shows while you're broadcasting.
- **Editable stream title** — set it from the plugin, changeable **even while live**.
- **Automatic game category** — read from the running Steam game (works for non-Steam shortcuts too) and updated on the fly. Falls back to *Just Chatting* when a game has no matching Twitch category.
- **Transparent chat overlay** — read-only Twitch chat drawn **over the game** in Gaming Mode (gamescope external-overlay plane), with native + **BTTV / 7TV / FFZ** emotes. Movable and styleable.
- **Live mic mute** — cut your microphone **on the stream** with one tap, without stopping the broadcast (and without muting your Discord call).
- **Stream settings per account** — resolution, fps, video/audio bitrate, keyframe interval, and an **auto-detected encoder** (NVENC ▸ VAAPI ▸ software x264). Only encoders that actually work on your hardware are offered.
- **Discord audio bridge** *(when [Steamcord](https://github.com/Necrosiak/Steamcord) is installed)*: an optional toggle mixes your **Discord voice** into the stream, so your party is heard by viewers — while you still hear them normally.

---

## How it works

Twitch has no video-push API, so going live always means an **RTMP push** under the hood. BoneCast handles it for you:

1. **OAuth device flow** logs you into Twitch and pulls your stream key, title and category through the Helix API — you never touch the key.
2. The game frame is captured from **gamescope** into a `v4l2` loopback device, and **ffmpeg** encodes it (hardware when available, software `libx264` otherwise) and pushes it to `rtmp://…/<your-key>`.
3. The **chat overlay** is a transparent WebKit surface promoted to the gamescope external-overlay plane, reading Twitch IRC anonymously and rendering emotes.

Everything is driven from the QAM and survives reboots.

---

## 📸 Screenshots

<p align="center">
  <img src="docs/img/bonecast-golive.jpg" width="60%" alt="Go live panel"/>
</p>

## Install

1. Install [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader).
2. Enable **Developer Mode** in Decky's general settings, then Decky settings → **Developer** → *Install plugin from URL*:
   `https://github.com/Necrosiak/BoneCast/releases/latest/download/BoneCast.zip`
   (or grab `BoneCast.zip` from the [Releases](https://github.com/Necrosiak/BoneCast/releases) page and install from ZIP).
3. Open the **Quick Access Menu → BoneCast**, log in to Twitch, and go live.

BoneCast **auto-updates** itself from GitHub Releases (toggleable in the plugin's *Updates* section).

---

## 🐧 Compatibility

BoneCast targets **every Linux distro** that can run Steam in Gaming Mode /
Big Picture: one build, runtime detection of everything external (ffmpeg,
libx264, v4l2loopback, GStreamer), and the exact install command for your
package manager shown in the QAM when something is missing.
Per-distro package notes: [docs/OS-NOTES.md](docs/OS-NOTES.md).

## 🐛 Issues & ideas — don't hesitate!

Found a bug, something misbehaving on your distro, or missing a feature?
**Please open an [issue](https://github.com/Necrosiak/BoneCast/issues)** —
every report directly shapes what gets built next. Include if you can:

- your distro & version (Bazzite 42, CachyOS, Ubuntu 24.04…) and your GPU (for the encoder probes)
- the plugin version and what you were doing (going live, overlay, OAuth…)
- what you expected vs what happened
- logs: `~/homebrew/logs/BoneCast/`

Feature requests and "it works!" reports on unusual setups are just as valuable.

## Credits

Created and maintained by **Necrosiak**. Part of the Necrosiak plugin suite for Steam Gaming Mode.
