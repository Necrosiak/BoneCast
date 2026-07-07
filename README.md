# BoneCast 🦴📡

Twitch for the Steam Gaming Mode — part of the Necrosiak plugin suite (alongside
[SkullKey](https://github.com/Necrosiak/SkullKey),
[Steamcord](https://github.com/Necrosiak/Steamcord) and BC250-Toolkit).

- **One Twitch login** (device code — gamepad friendly): fetches your stream key
  automatically, no manual copy-paste.
- **Editable stream title** — changeable even while live.
- **Automatic game category** — set from the running Steam game, updated on the fly
  (falls back to *Just Chatting* when no game / no Twitch category exists).
- **Transparent chat overlay** — read-only Twitch chat, drawn over the game in gaming
  mode (gamescope external-overlay plane), with native + BTTV/7TV/FFZ emotes.
- **Steamcord bridge** *(planned)*: when Steamcord is present, route Twitch audio into
  the Discord call.

> Streaming still requires an RTMP push under the hood (Twitch has no video-push API),
> but the key is fetched for you via OAuth — you never handle it.
