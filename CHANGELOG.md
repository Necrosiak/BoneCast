# Changelog

## 0.3.7 — 2026-09-15

### Notifications wait until you stop streaming

A Steam notification that pops up while you are live ends up in the video:
gamescope draws it over the game, and that is the picture BoneCast captures.
The same goes for a local recording, where it would end up in the file.

BoneCast now tells the other plugins when it is **streaming or recording**, and
its own notifications are **held until you stop**. It follows the *Streamer
mode* setting in [Steamcord](https://github.com/Necrosiak/Steamcord)
(Automatic, Always on, Off): with Steamcord installed, Steamcord's notifications
and the toasts of other Decky plugins are held too, and so are those of
[SkullKey](https://github.com/Necrosiak/SkullKey) and
[BC250 Toolkit](https://github.com/Necrosiak/bc250-toolkit-decky). Without
Steamcord, BoneCast's own notifications still wait while it is live or recording.

## 0.3.6 — 2026-09-15

### Watch Twitch over your game

A new **Watch** tab plays up to **four live streams on top of the game** in
Gaming Mode.

- **Followed channels that are live** are listed with a thumbnail, a LIVE badge,
  the viewer count and what they are playing. Tap a card and it plays; tap it
  again to remove it. Channels can also be typed in by name.
- **Layouts** for one to four streams — corners, left or right side, stacked,
  column, grid, picture-in-picture, full screen — plus size, opacity (50 % by
  default) and a 30 or 60 fps cap. Moving a stream no longer leaves a frozen
  copy of it behind, and nothing is drawn under the Steam bars.
- **Sound**: pick whose sound you hear. The first stream you start is heard
  right away; after that your choice is kept. The volume slider (0–150 %)
  changes the level **without cutting the sound**, and the sound comes back on
  its own after a reconnect or a resize — before, it stayed silent until the
  next setting change.
- The sound always goes to your **default audio output**, and follows it if you
  switch outputs while watching. WirePlumber remembers the output of an app
  whose stream was once moved by hand and would have sent every later stream
  there; BoneCast's watch audio opts out of that.
- Stream quality follows the size on screen: a thumbnail does not decode
  1080p.

**Reconnect to Twitch once** after updating if you want the followed-channels
list: it needs a new permission (`user:read:follows`) that existing logins do
not have. Everything else works without it.

Sound and picture are read over two separate connections; they have looked in
sync in testing, but that has not been measured.

## 0.3.5 — 2026-09-13

### Updates no longer stop at the first thing they cannot write, or at DNS

Two separate faults, both silent:

- The update was applied file by file and gave up on the first one it could not
  write — leaving the plugin **half updated**, part old code and part new. It now
  surveys everything first: a code file it cannot write cancels the update
  without touching anything, while documentation, licences and `plugin.json`
  are skipped and the update proceeds.
- The release check ran once, a few seconds after boot, which is often **before
  the network is up** — and nothing retried, so the plugin stayed on its version
  until a boot that happened to be luckier. It now retries while the failure is
  the network. On the machine this was found on, three boots out of four had
  been dying on `Temporary failure in name resolution`.

When an update genuinely cannot be applied, the plugin now says so instead of
writing one line to a log nobody reads.

### A stray decorator that would have broken updates on a newer Python

`_autoupdate_check` carried two stacked `@classmethod` decorators — a leftover
from a section header, present since the first commit. The bundled Python still
accepts that; chaining `classmethod` was removed in Python 3.13, so the day
Decky moves on, the update check would have raised `'classmethod' object is not
callable` at startup and stopped there.

## 0.3.4 — 2026-08-25

### Fixed

- **The active Steam account could no longer be identified, after Steam changed
  its files.** Steam stopped publishing a numeric `ActiveUser` in `registry.vdf`
  — it now publishes `AutoLoginUser`, holding the account *name* — and dropped
  `MostRecent` from `loginusers.vdf` in favour of `AutoLogin` and `Timestamp`.
  Both probes came back empty and everything fell back to a generic profile.
  The account is now resolved from `AutoLoginUser` matched by name, then
  `AutoLogin`, then the most recent `Timestamp`; the older keys are still tried
  first, so an older Steam behaves exactly as before.

## 0.3.3 — 2026-08-09

### Fixed

- **The in-plugin updater could not update anything on a normal install, and
  said it had.** Decky root-owns the plugin's top-level directory, so creating
  the temporary file the updater writes through failed with `Permission
  denied` — even though the files being replaced belong to the user. Writing
  in place is now used as a fallback when the temporary file cannot be created
  but the destination exists and is writable.

  Worse, the failure was reported as a success: `apply()` returns a dict, and
  `{"ok": False, "error": …}` is always truthy in Python, so the auto-updater
  logged "update installed" and restarted Decky anyway — on every boot, since
  the installed version never changed. It now reads the result and logs why it
  gave up.

## 0.3.2 — 2026-08-09

### Fixed

- **Controller navigation in rows of buttons.** `flow-children="horizontal"`
  is not a value the Steam client's focus engine accepts: it falls through to
  a default branch that logs `Unhandled flow-children` on every render and
  produces no focus flow at all, which can break controller navigation and
  even swallow state updates on rows that re-render often. Replaced with
  `row`. This was fixed in the repository on 2026-07-23 and never made it
  into a release until now.

## 0.3.1 — 2026-07-20

### Changed
- **Monochrome SVG icons across the QAM UI**, matching the rest of the
  Necrosiak plugin suite (Steamcord v1.16.1). Color emoji (save, controller,
  broadcast, clip, mic, key, send, refresh, GitHub, logout, tabs) were
  replaced with monochrome vector icons that inherit the surrounding text
  size and color.

### Fixed
- **In-plugin updates failed on root-owned installs.** The updater overwrote
  files with `shutil.copy2`, which ends with a `chmod` on the destination —
  something a non-root process cannot do on root-owned files even when they
  are world-writable. Files are now replaced via a temp file + atomic
  `os.replace`, which only needs write permission on the directory — and
  every replaced file becomes owned by the user, so a root-owned install
  heals itself as it updates.

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
