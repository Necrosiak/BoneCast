# Changelog

## 0.3.0 — 2026-07-12

> ⚠️ This release adds Twitch permissions (`clips:edit`, `user:write:chat`).
> **Existing logins must reconnect once** — the plugin detects it and asks.

### Added
- **🌍 Full UI localization** — the plugin interface is now translated into
  9 languages (EN/FR/DE/ES/IT/PT/NL/PL/RU) and follows your SteamOS language
  automatically, like the rest of the Necrosiak suite.
- **🎬 Instant clips** — while live, one button clips the last ~30 seconds
  through the Twitch API (the clip is published to your dashboard ~15 s later).
- **💬 Send chat messages** — talk in your own Twitch chat straight from the
  QAM, next to the read-only overlay.
- **⏸️ BRB mode** — one tap replaces the game feed with a clean pause screen
  and mutes your microphone; one tap brings the game back. The RTMP stream
  never drops, so viewers stay connected.
- **⏺️ Local recording** — record your session as an MKV in
  `~/Videos/BoneCast/` (localized XDG folder), either alongside the live
  stream (single-encode `tee`, no extra CPU cost) or **without streaming at
  all** via the new "record without streaming" button. The file path is shown
  when you stop.
- Status badges in the Go-live panel now distinguish **live / paused (BRB) /
  recording**.

### Fixed
- **Overlay settings finally apply live.** Position, size and opacity changes
  from the QAM had no effect: in WebKitGTK a `fetch()` on a `file://` URL
  returns HTTP status 0 even on success, so the overlay discarded every state
  update. Changes now apply within ~1 s.
- **Overlay stays visible when Big Picture has the focus** — the overlay
  window is now on the KDE on-screen-display layer (like the volume popup)
  instead of relying on keep-above, which a focused fullscreen window beats.
- The overlay no longer inherits the plugin's PyInstaller `LD_LIBRARY_PATH`
  (spurious libssl/gio warnings in the logs).
- Leftover Steamcord naming purged from the overlay (window title, default
  state directory).

## 0.2.2 — 2026-07-10

### Fixed
- **Debian/Ubuntu compatibility:** the capture feeder ran the hardcoded
  `/usr/bin/python`, which does not exist on Debian/Ubuntu. The system python
  is now resolved from `PATH`.

### Added
- **libx264 probe before going live.** Fedora's default `ffmpeg` (ffmpeg-free)
  ships without the H.264 software encoder — the stream now fails with a clear
  message pointing at the full RPM Fusion ffmpeg instead of an opaque ffmpeg
  crash. `get_encoders` also reports x264 availability.
- **GStreamer/PipeWire pre-check** before starting the capture: missing python
  bindings or `pipewiresrc` (stock Arch/Fedora/Debian) now produce the exact
  package command for your OS in the QAM (new `no_gst` error).
- openSUSE (`zypper`) is now covered by the OS-specific install hints; unknown
  stream errors now display the backend hint when available.

## 0.2.1 — 2026-07-09

### Fixed
- **Update failures are now visible.** When installing an update fails — for
  example on a root-owned local install (`Permission denied`) — the panel
  shows the exact error under the update button instead of staying on
  "installing…" forever. The silent boot-time auto-update path is unchanged
  (failures were already logged).

## 0.2.0 — 2026-07-09

### Added
- **Runtime dependency checks** — one build for every Linux distro: going live
  now verifies what the machine has.
- **ffmpeg presence check** before starting a stream, with the exact install
  command for the detected package manager (pacman / rpm-ostree / dnf / apt).
- **Better v4l2loopback errors.** The "no loopback" error now distinguishes
  "module not installed" (package + modprobe command) from "installed but not
  loaded" (modprobe only), shown right under the live button.

## 0.1.0 — 2026-07-07

Initial release — Twitch split out of Steamcord into its own plugin.

- Twitch login via OAuth device flow (gamepad friendly), stream key fetched
  automatically through the Helix API.
- Go live / stop from the QAM (gamescope → v4l2 loopback → ffmpeg → RTMP),
  hardware encoder auto-detection with software x264 fallback.
- Editable stream title and automatic game category.
- Transparent read-only chat overlay over the game (native + BTTV/7TV/FFZ
  emotes).
- Live mic mute, per-account stream settings, optional Discord audio bridge
  via Steamcord.
- Release-based auto-update.
