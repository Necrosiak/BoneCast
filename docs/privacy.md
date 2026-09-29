---
title: BoneCast privacy policy
---

# BoneCast privacy policy

*Last updated: September 29, 2026*

BoneCast is a free, open-source plugin that runs entirely on your own
device. It has no servers of its own, no accounts of its own, no analytics
and no advertising.

## What BoneCast accesses

When you log in to **Twitch** or **YouTube** from BoneCast, you authorize it
on the platform's own sign-in page. BoneCast then receives an access token
and uses it only to do what you ask from the plugin:

- **YouTube**: read your channel name, create and end your live broadcasts,
  set their title, visibility and category, get the stream key for them, and
  post the messages you write to your own live chat.
- **Twitch**: read your stream key, set your stream title and category,
  create clips, post the messages you write to your own chat, and list the
  channels you follow that are live.

To show chat over your game, BoneCast also reads the public chat of the
channel you choose, the same way a viewer does.

## Where your data stays

- Access tokens and settings are stored **only on your device**, in your
  home folder. They are never sent anywhere except to Twitch or Google when
  BoneCast talks to their APIs on your behalf.
- BoneCast does not collect, sell or share any personal data, and does not
  send anything to its developer.
- Your video and audio go only to the platform you stream to, and to a local
  recording file if you turn recording on.

BoneCast's use of information received from Google APIs adheres to the
[Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy),
including the Limited Use requirements. BoneCast uses YouTube API Services;
see the [YouTube Terms of Service](https://www.youtube.com/t/terms) and the
[Google Privacy Policy](https://policies.google.com/privacy).

## Removing access

- Log out from BoneCast's YouTube or Twitch tab: this deletes the stored
  token from your device.
- You can also revoke access at any time from your Google account
  ([myaccount.google.com/permissions](https://myaccount.google.com/permissions))
  or from Twitch (Settings → Connections).
- Uninstalling BoneCast and deleting `~/.config/bonecast-*.json` and
  `~/.local/share/bonecast/` removes everything it stored.

## Contact

Questions: open an issue on
[github.com/Necrosiak/BoneCast](https://github.com/Necrosiak/BoneCast/issues).
