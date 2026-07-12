# BoneCast 🦴📡

**Twitch in de Steam-spelmodus** — een [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader)-plug-in voor Steam Deck / Bazzite / SteamOS.

🌍 **Talen:** [English](../README.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Italiano](README.it.md) · [Português](README.pt.md) · **Nederlands** · [Polski](README.pl.md) · [Русский](README.ru.md)

> Onderdeel van de Necrosiak-pluginsuite, naast
> [SkullKey](https://github.com/Necrosiak/SkullKey),
> [Steamcord](https://github.com/Necrosiak/Steamcord) en BC250-Toolkit.
> De plugin-interface is vertaald in 9 talen en volgt automatisch de SteamOS-taal.

---

## Wat het doet

BoneCast zet alles wat je nodig hebt om te streamen naar **Twitch** rechtstreeks in het **Quick Access Menu** van Steam — geen desktop, geen toetsenbord, volledig gamepad-vriendelijk van inloggen tot live gaan.

- **Eén Twitch-login** *(apparaatcode — gamepad-vriendelijk)*: je voert een korte code in op `twitch.tv/activate`, en BoneCast haalt je **streamsleutel automatisch** op. Nooit meer handmatig kopiëren en plakken.
- **Ga live vanuit het QAM** — één knop start en stopt de RTMP-stream. Een **● LIVE**-badge is zichtbaar terwijl je uitzendt.
- **Bewerkbare streamtitel** — ingesteld vanuit de plug-in, aanpasbaar **zelfs tijdens de uitzending**.
- **Automatische spelcategorie** — uitgelezen van het draaiende Steam-spel (werkt ook voor niet-Steam-snelkoppelingen) en direct bijgewerkt. Valt terug op *Just Chatting* wanneer een spel geen bijpassende Twitch-categorie heeft.
- **Transparante chat-overlay** — de Twitch-chat (alleen-lezen) getekend **over het spel** in de spelmodus (gamescope external-overlay-laag), met native + **BTTV / 7TV / FFZ**-emotes. Positie, grootte en doorzichtigheid stel je live in vanuit het QAM, en de overlay blijft zelfs zichtbaar wanneer Big Picture de focus heeft.
- **🎬 Directe clips** — tijdens de uitzending clipt één knop de laatste ~30 seconden via de Twitch-API; de clip verschijnt zo'n 15 seconden later op je dashboard.
- **💬 Praat in je eigen chat** — stuur berichten naar je Twitch-chat rechtstreeks vanuit het QAM, zonder toetsenbord-op-desktop-acrobatiek.
- **⏸️ BRB-modus** — één tik vervangt het spelbeeld door een strak pauzescherm en dempt je microfoon; nog een tik brengt je terug. De stream valt nooit weg.
- **⏺️ Lokale opname** — sla je sessie op als MKV in `~/Video's/BoneCast/`, naast de livestream of **zonder überhaupt te streamen** (geen streamsleutel nodig).
- **Live microfoon dempen** — schakel je microfoon **op de stream** uit met één tik, zonder de uitzending te stoppen (en zonder je Discord-gesprek te dempen).
- **Streaminstellingen per account** — resolutie, fps, video-/audiobitrate, keyframe-interval en een **automatisch gedetecteerde encoder** (NVENC ▸ VAAPI ▸ software-x264). Alleen encoders die echt werken op jouw hardware worden aangeboden.
- **Discord-audiobrug** *(wanneer [Steamcord](https://github.com/Necrosiak/Steamcord) is geïnstalleerd)*: een optionele schakelaar mengt je **Discord-stem** in de stream, zodat je groep hoorbaar is voor de kijkers — terwijl jij hen gewoon blijft horen.

---

## Hoe het werkt

Twitch heeft geen video-push-API, dus live gaan betekent altijd een **RTMP-push** onder de motorkap. BoneCast regelt het voor je:

1. De **OAuth-apparaatcodeflow** logt je in bij Twitch en haalt je streamsleutel, titel en categorie op via de Helix-API — je raakt de sleutel nooit aan.
2. Het spelbeeld wordt vanuit **gamescope** vastgelegd in een `v4l2`-loopbackapparaat, en **ffmpeg** codeert het (hardware indien beschikbaar, anders software-`libx264`) en stuurt het naar `rtmp://…/<jouw-sleutel>`.
3. De **chat-overlay** is een transparant WebKit-oppervlak op de gamescope external-overlay-laag, dat Twitch-IRC anoniem leest en emotes weergeeft.

Alles wordt bediend vanuit het QAM en overleeft herstarts.

---

## 📸 Schermafbeeldingen

<p align="center">
  <img src="img/bonecast-golive.jpg" width="60%" alt="Go-live-paneel"/>
</p>

## Installatie

1. Installeer [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader).
2. Schakel de **ontwikkelaarsmodus** in via Decky's algemene instellingen, daarna Decky-instellingen → **Ontwikkelaar** → *Plug-in installeren via URL*:
   `https://github.com/Necrosiak/BoneCast/releases/latest/download/BoneCast.zip`
   (of pak `BoneCast.zip` van de [Releases](https://github.com/Necrosiak/BoneCast/releases)-pagina en installeer vanuit de ZIP).
3. Open het **Quick Access Menu → BoneCast**, log in bij Twitch en ga live.

BoneCast **werkt zichzelf automatisch bij** via GitHub Releases (uit te schakelen in het onderdeel *Updates* van de plug-in).

---

## 🐧 Compatibiliteit

BoneCast richt zich op **elke Linux-distributie** die Steam in de spelmodus /
Big Picture kan draaien: één build, runtime-detectie van alles wat extern is
(ffmpeg, libx264, v4l2loopback, GStreamer), en het exacte installatiecommando
voor jouw pakketbeheerder in het QAM wanneer er iets ontbreekt.
Pakketnotities per distributie: [OS-NOTES.md](OS-NOTES.md).

## 🐛 Bugs & ideeën — aarzel niet!

Een bug gevonden, gedraagt iets zich vreemd op jouw distributie, of mis je een
functie? **Open een [issue](https://github.com/Necrosiak/BoneCast/issues)** —
elk rapport bepaalt rechtstreeks wat er hierna wordt gebouwd. Vermeld indien
mogelijk:

- je distributie & versie (Bazzite 42, CachyOS, Ubuntu 24.04…) en je GPU (voor de encoder-detectie)
- de pluginversie en wat je aan het doen was (live gaan, overlay, OAuth…)
- wat je verwachtte versus wat er gebeurde
- logs: `~/homebrew/logs/BoneCast/`

Functieverzoeken en „het werkt!"-meldingen op ongebruikelijke opstellingen
zijn net zo waardevol.

## Credits

Gemaakt en onderhouden door **Necrosiak**. Onderdeel van de Necrosiak-pluginsuite voor de Steam-spelmodus.
