# BoneCast 🦴📡

**Twitch im Steam-Spielmodus** — ein [Decky-Loader](https://github.com/SteamDeckHomebrew/decky-loader)-Plugin für Steam Deck / Bazzite / SteamOS.

🌍 **Sprachen:** [English](../README.md) · [Français](README.fr.md) · **Deutsch** · [Español](README.es.md) · [Italiano](README.it.md) · [Português](README.pt.md) · [Nederlands](README.nl.md) · [Polski](README.pl.md) · [Русский](README.ru.md)

> Teil der Necrosiak-Plugin-Suite, neben
> [SkullKey](https://github.com/Necrosiak/SkullKey),
> [Steamcord](https://github.com/Necrosiak/Steamcord) und BC250-Toolkit.
> Die Plugin-Oberfläche ist in 9 Sprachen übersetzt und folgt automatisch deiner SteamOS-Sprache.

---

## Was es kann

BoneCast bringt alles, was du zum Streamen auf **Twitch** brauchst, direkt ins Steam-**Schnellzugriffsmenü** — ohne Desktop, ohne Tastatur, vom Login bis zum Livegang komplett gamepad-tauglich.

- **Ein einziger Twitch-Login** *(Gerätecode — gamepad-freundlich)*: Du gibst einen kurzen Code auf `twitch.tv/activate` ein, und BoneCast holt deinen **Stream-Schlüssel automatisch**. Nie wieder Kopieren und Einfügen.
- **Livegang aus dem QAM** — eine Taste startet und stoppt den RTMP-Stream. Ein **● LIVE**-Abzeichen erscheint während der Übertragung.
- **Bearbeitbarer Stream-Titel** — im Plugin festgelegt, **auch live** änderbar.
- **Automatische Spielkategorie** — aus dem laufenden Steam-Spiel gelesen (auch für Nicht-Steam-Verknüpfungen) und im Handumdrehen aktualisiert. Fällt auf *Just Chatting* zurück, wenn ein Spiel keine passende Twitch-Kategorie hat.
- **Transparentes Chat-Overlay** — schreibgeschützter Twitch-Chat **über dem Spiel** im Spielmodus (gamescope External-Overlay-Ebene), mit nativen + **BTTV / 7TV / FFZ**-Emotes. Verschiebbar und gestaltbar.
- **Mikrofon live stummschalten** — schalte dein Mikrofon **im Stream** mit einem Tipp stumm, ohne die Übertragung zu stoppen (und ohne deinen Discord-Anruf stummzuschalten).
- **Stream-Einstellungen pro Konto** — Auflösung, FPS, Video-/Audio-Bitrate, Keyframe-Intervall und ein **automatisch erkannter Encoder** (NVENC ▸ VAAPI ▸ Software-x264). Angeboten werden nur Encoder, die auf deiner Hardware wirklich funktionieren.
- **Discord-Audiobrücke** *(wenn [Steamcord](https://github.com/Necrosiak/Steamcord) installiert ist)*: ein optionaler Schalter mischt deine **Discord-Stimme** in den Stream, sodass deine Gruppe von den Zuschauern gehört wird — während du sie weiterhin normal hörst.

---

## Wie es funktioniert

Twitch hat keine Video-Push-API, daher bedeutet ein Livegang immer einen **RTMP-Push** im Hintergrund. BoneCast erledigt das für dich:

1. Der **OAuth-Gerätecode-Flow** meldet dich bei Twitch an und holt deinen Stream-Schlüssel, Titel und Kategorie über die Helix-API — du berührst den Schlüssel nie.
2. Das Spielbild wird von **gamescope** in ein `v4l2`-Loopback-Gerät aufgenommen, und **ffmpeg** kodiert es (Hardware wenn verfügbar, sonst Software-`libx264`) und pusht es zu `rtmp://…/<dein-Schlüssel>`.
3. Das **Chat-Overlay** ist eine transparente WebKit-Fläche auf der gamescope External-Overlay-Ebene, die den Twitch-IRC anonym liest und Emotes darstellt.

Alles wird aus dem QAM gesteuert und übersteht Neustarts.

---

## Installation

1. Installiere [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader).
2. Hol dir die neueste `BoneCast.zip` von der [Releases](https://github.com/Necrosiak/BoneCast/releases)-Seite oder installiere sie aus dem Decky-Store, sobald verfügbar.
3. Öffne das **Schnellzugriffsmenü → BoneCast**, melde dich bei Twitch an und geh live.

BoneCast **aktualisiert sich automatisch** über GitHub-Releases (im Abschnitt *Aktualisierungen* des Plugins umschaltbar).

---

## Danksagung

Erstellt und gepflegt von **Necrosiak**. Teil der Necrosiak-Plugin-Suite für den Steam-Spielmodus.
