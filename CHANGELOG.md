# Changelog

## 0.5.1 — 2026-09-30

Requested and tested by [dreemur-e](https://github.com/dreemur-e) in
[#1](https://github.com/Necrosiak/BoneCast/issues/1).

### Fix: stopping a stream or recording could restart Gaming Mode

Stopping could make gamescope crash, which closes the game and restarts the
Steam session. This comes from a bug in gamescope itself: it can crash if a
screen capture disconnects while it is drawing a frame for it. BoneCast used to
cut the capture off abruptly; it now pauses it first, lets gamescope finish the
frame, and only then disconnects. Every stop in testing since has been clean,
including a 23-minute recording and a Twitch live.

### Save recordings to an SD card or an external drive

A new **Save recordings to** choice in Settings lists the internal storage and
every SD card or external drive that is plugged in, with its free space.
Recordings go into a `BoneCast` folder on that drive. If the drive isn't there
when you record, BoneCast saves to the internal storage instead.

### YouTube stream latency

When you're logged in to YouTube, pick the latency of your live: **Normal**
(about 20 s, best quality), **Low** (about 10 s) or **Ultra-low** (about 5 s,
without captions or 1440p and above). It applies to the next live.

### Animated pause screen

Besides an image, the `BoneCast-BRB` folder now takes a looping video:
`brb.mp4`, `brb.webm`, `brb.mkv`, `brb.mov` or `brb.gif`. Its sound is not
used. Animated `.webp` files can't be decoded, so convert them to `.gif` or
`.mp4`.

### Settings tab

- Your Twitch and YouTube accounts now sit together in an **Accounts**
  section, one line each, with *Log out* next to them. Logging out of YouTube
  is no longer in the Live tab, so it can't be tapped by mistake during a
  live.

## 0.5.0 — 2026-09-29

### Log in with YouTube

Requested in [#1](https://github.com/Necrosiak/BoneCast/issues/1).

- **YouTube login**, like Twitch: tap *Log in*, enter the code on
  `google.com/device`, and BoneCast creates the live for you. No stream key
  to copy. Google shows an "unverified app" warning on the way; that's
  expected, tap *Continue*. The stream key still works if you'd rather not
  log in.
- **Title and visibility** (public, unlisted, private) from the QAM. The
  title can be changed **while live**.
- **Write in your own YouTube chat** from the Chat tab.
- **Clear YouTube errors.** Instead of a raw code, BoneCast now says what to
  do, for example when live streaming isn't enabled on your channel yet
  (YouTube takes up to 24 hours the first time).
- **BoneCast reopens on the platform you used last**, Twitch or YouTube, so
  there's one less tap during a live.

### Chat overlay

- **Live events show as highlighted cards**: subs, resubs, gifted subs,
  raids and bits on Twitch; Super Chats, Super Stickers, new members and
  gifted memberships on YouTube.
- **Unlisted YouTube lives** now show in the chat overlay. The overlay used to
  look for the live on your channel page, where only public lives appear.
- **YouTube chat arrives faster**: every 2 seconds instead of up to 10.

### Your own pause screen

- Put an image named `brb.png` (or `.jpg` / `.webp`) in the `BoneCast-BRB`
  folder of your home folder, from Desktop Mode. BoneCast shows it when you
  press Pause, and picks up a new image the next time you press it. 16:9
  works best; other sizes get black bars. No image, or one that can't be
  read, gives the usual pause screen.

### Fix

- Starting two lives within a second or two (Twitch then YouTube, or a double
  tap) could start two encoders at once. Starts now wait for each other, so
  the second one is refused as it should be. Same for the chat overlay.

## 0.4.1 — 2026-09-29

### Going live works on a stock Steam Deck

Reported in [#1](https://github.com/Necrosiak/BoneCast/issues/1).

- **No more virtual camera.** BoneCast used to pass the game image to the
  encoder through a virtual video device (`/dev/video42`), which needs the
  `v4l2loopback` kernel module. SteamOS doesn't load it, and loading it needs
  `sudo`, so on a stock Steam Deck neither Twitch nor YouTube could go live.
  The capture now hands its frames straight to ffmpeg through a pipe: nothing to
  install, no `sudo`, on any Linux.
- **A steady 30 frames per second.** gamescope sends no image while the screen
  doesn't change (a paused menu, a loading screen). The stream then got no video
  at all, and stopping it could hang for seconds and leave an unreadable
  recording. BoneCast now repeats the last image, so the stream never starves
  and stops in a fraction of a second.
- **The pause screen (BRB)** is drawn by the capture itself, with no second
  encoder. It looks the same and switches instantly both ways.
- **Setup hints are in English**, and BoneCast no longer suggests
  `sudo pacman` on SteamOS, whose system is read-only.

### Fix

- Stopping a BoneCast stream also killed Steamcord's screen capture, which has
  the same file name. BoneCast now only stops its own.

## 0.4.0 — 2026-09-28

### YouTube, next to Twitch

BoneCast now has two platforms, each in its own tab with its own settings:
**Twitch** (Live, Watch, Chat, Settings) and **YouTube** (Live, Chat,
Settings). Updates and About live under the ⚙ tab.

- **Go live on YouTube** with your stream key from YouTube Studio. Everything
  from the Twitch side comes along: pause screen (BRB), live mic mute, local
  recording, Discord audio, and **its own stream settings** — resolution,
  bitrate, encoder and so on are no longer shared with Twitch.
- **YouTube chat overlay** over the game, with no account and no API quota:
  type your channel (`@handle`), and it waits for your live to start, then
  connects on its own. Channel owner, moderators and members are coloured,
  Super Chats show their amount.
- **One at a time:** a Twitch live and a YouTube live never run together, and
  neither do the two chat overlays. The other tab says what is running
  instead of offering a button that would fail.
- Logging in with your YouTube account (stream key and title set
  automatically, writing in your chat) is prepared and comes in the next
  update.

### Tabs and icon

- Tabs now look like Steamcord's: rounded tops, the active one underlined in
  its platform's colour, inactive ones dimmed.
- New plugin icon — a bone and a broadcast signal — instead of the Twitch logo.

### Fix

- When the stream process stopped on its own (network drop, rejected key),
  nothing tidied up after it, and starting a live could report a failure even
  though the stream was running: the method meant to watch for this was called
  but had never been written. It now exists and cleans up like a normal stop.


## 0.3.9 — 2026-09-27

### A successful update now says so

After installing an update, the button went back to "Up to date", exactly like
a click that did nothing. It now reads "Updated to vX ✓", with a note to close
and reopen the Quick Access menu to load the new version. Same fix as
[Steamcord #52](https://github.com/Necrosiak/Steamcord/issues/52), reported by
[@bastiHST90](https://github.com/bastiHST90).

## 0.3.8 — 2026-09-22

### Updates that installed but never loaded

Installing an update wrote the new files and stopped there: the plugin reload
that should follow could never happen, so the update only took effect at the
next boot — with nothing said about it either way. Two measured reasons: Decky's
loader is a PyInstaller bundle, so every plugin backend inherits its library path
and `systemctl` cannot even start from one; and restarting a system service is
refused to a plugin that does not run as root. Nothing read the result.

The update button now asks the loader — which does run as root — to reload this
plugin alone, and reports the new version when it is done. Automatic updates say
the update takes effect the next time Steam starts, instead of claiming a reload
that never came.

Found through [Steamcord #52](https://github.com/Necrosiak/Steamcord/issues/52),
reported by [@bastiHST90](https://github.com/bastiHST90); the same defect was in
this plugin.

### Unload

The microphone state was only restored after the audio bridge had been torn
down — an await that never resumes during an unload, so it was skipped whenever
the bridge lingered. It now happens first.

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
