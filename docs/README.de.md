# BoneCast 🦴📡

**Twitch im Steam-Spielmodus** — ein [Decky-Loader](https://github.com/SteamDeckHomebrew/decky-loader)-Plugin für Steam Deck / Bazzite / SteamOS.

🌍 **Sprachen:** [English](../README.md) · [Français](README.fr.md) · **Deutsch** · [Español](README.es.md) · [Italiano](README.it.md) · [Português](README.pt.md) · [Nederlands](README.nl.md) · [Polski](README.pl.md) · [Русский](README.ru.md)

> Teil der Necrosiak-Plugin-Suite, neben
> [SkullKey](https://github.com/Necrosiak/SkullKey),
> [Steamcord](https://github.com/Necrosiak/Steamcord) und BC250-Toolkit.
> Die Plugin-Oberfläche ist in 9 Sprachen übersetzt und folgt automatisch der SteamOS-Sprache.

---

## Was es kann

BoneCast bringt alles, was du zum Streamen auf **Twitch** brauchst, direkt ins **Quick Access Menu** von Steam — kein Desktop, keine Tastatur, komplett gamepad-tauglich vom Login bis zum Livegang.

- **Ein einziger Twitch-Login** *(Gerätecode — gamepad-freundlich)*: Du gibst einen kurzen Code auf `twitch.tv/activate` ein, und BoneCast holt deinen **Stream-Key automatisch**. Nie wieder manuelles Kopieren.
- **Live gehen direkt aus dem QAM** — ein Button startet und stoppt den RTMP-Stream. Ein **● LIVE**-Badge zeigt an, dass du sendest.
- **Bearbeitbarer Stream-Titel** — im Plugin gesetzt, änderbar **sogar während des Livestreams**.
- **Automatische Spielkategorie** — vom laufenden Steam-Spiel gelesen (funktioniert auch für Non-Steam-Verknüpfungen) und laufend aktualisiert. Fallback auf *Just Chatting*, wenn ein Spiel keine passende Twitch-Kategorie hat.
- **Transparentes Chat-Overlay** — der Twitch-Chat (nur lesend) wird im Spielmodus **über dem Spiel** gezeichnet (gamescope-External-Overlay-Ebene), mit nativen + **BTTV / 7TV / FFZ**-Emotes. Position, Größe und Deckkraft lassen sich live aus dem QAM einstellen, und es bleibt sogar sichtbar, wenn Big Picture den Fokus hat.
- **🎬 Sofort-Clips** — im Livestream clippt ein Button die letzten ~30 Sekunden über die Twitch-API; der Clip landet etwa 15 Sekunden später auf deinem Dashboard.
- **💬 Schreib in deinem eigenen Chat** — sende Nachrichten in deinen Twitch-Chat direkt aus dem QAM, ohne Tastatur-über-Desktop-Verrenkungen.
- **⏸️ BRB-Modus** — ein Tastendruck ersetzt das Spielbild durch einen sauberen Pausenbildschirm und schaltet dein Mikro stumm; ein weiterer bringt dich zurück. Der Stream bricht nie ab.
- **⏺️ Lokale Aufnahme** — speichere deine Session als MKV in `~/Videos/BoneCast/`, parallel zum Livestream oder **ganz ohne zu streamen** (kein Stream-Key im Spiel).
- **Live-Mikro-Stummschaltung** — schalte dein Mikrofon **im Stream** mit einem Tastendruck stumm, ohne die Übertragung zu stoppen (und ohne deinen Discord-Call stummzuschalten).
- **Stream-Einstellungen pro Konto** — Auflösung, fps, Video-/Audio-Bitrate, Keyframe-Intervall und ein **automatisch erkannter Encoder** (NVENC ▸ VAAPI ▸ Software-x264). Es werden nur Encoder angeboten, die auf deiner Hardware wirklich funktionieren.
- **Discord-Audio-Brücke** *(wenn [Steamcord](https://github.com/Necrosiak/Steamcord) installiert ist)*: Ein optionaler Schalter mischt deine **Discord-Stimme** in den Stream, sodass deine Gruppe von den Zuschauern gehört wird — während du sie weiterhin normal hörst.

---

## Wie es funktioniert

Twitch hat keine Video-Push-API, Livegehen bedeutet also immer einen **RTMP-Push** unter der Haube. BoneCast übernimmt das für dich:

1. Der **OAuth-Device-Flow** meldet dich bei Twitch an und holt Stream-Key, Titel und Kategorie über die Helix-API — du fasst den Key nie an.
2. Das Spielbild wird aus **gamescope** in ein `v4l2`-Loopback-Gerät aufgenommen, und **ffmpeg** kodiert es (Hardware wenn verfügbar, sonst Software-`libx264`) und schiebt es zu `rtmp://…/<dein-key>`.
3. Das **Chat-Overlay** ist eine transparente WebKit-Oberfläche auf der gamescope-External-Overlay-Ebene, die Twitch-IRC anonym liest und Emotes rendert.

Alles wird aus dem QAM gesteuert und überlebt Neustarts.

---

## 📸 Screenshots

<p align="center">
  <img src="img/bonecast-golive.jpg" width="60%" alt="Go-live-Panel"/>
</p>

## Installation

1. Installiere [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader).
2. Aktiviere den **Entwicklermodus** in Deckys allgemeinen Einstellungen, dann Decky-Einstellungen → **Entwickler** → *Plugin von URL installieren*:
   `https://github.com/Necrosiak/BoneCast/releases/latest/download/BoneCast.zip`
   (oder hol dir `BoneCast.zip` von der [Releases](https://github.com/Necrosiak/BoneCast/releases)-Seite und installiere aus dem ZIP).
3. Öffne das **Quick Access Menu → BoneCast**, melde dich bei Twitch an und geh live.

BoneCast **aktualisiert sich automatisch** über GitHub Releases (abschaltbar im Bereich *Updates* des Plugins).

---

## 🐧 Kompatibilität

BoneCast zielt auf **jede Linux-Distribution**, die Steam im Spielmodus /
Big Picture ausführen kann: ein Build, Laufzeiterkennung von allem Externen
(ffmpeg, libx264, v4l2loopback, GStreamer), und der exakte Installationsbefehl
für deinen Paketmanager wird im QAM angezeigt, wenn etwas fehlt.
Paket-Hinweise pro Distribution: [OS-NOTES.md](OS-NOTES.md).

## 🐛 Bugs & Ideen — nur her damit!

Einen Bug gefunden, etwas verhält sich auf deiner Distribution seltsam, oder
ein Feature fehlt? **Bitte eröffne ein
[Issue](https://github.com/Necrosiak/BoneCast/issues)** — jeder Bericht formt
direkt, was als Nächstes gebaut wird. Wenn möglich, gib an:

- deine Distribution & Version (Bazzite 42, CachyOS, Ubuntu 24.04…) und deine GPU (für die Encoder-Erkennung)
- die Plugin-Version und was du gerade gemacht hast (Livegang, Overlay, OAuth…)
- was du erwartet hast vs. was passiert ist
- Logs: `~/homebrew/logs/BoneCast/`

Feature-Wünsche und „es funktioniert!“-Berichte auf ungewöhnlichen Setups sind
genauso wertvoll.

## Credits

Erstellt und gepflegt von **Necrosiak**. Teil der Necrosiak-Plugin-Suite für den Steam-Spielmodus.
