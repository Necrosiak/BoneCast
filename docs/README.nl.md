# BoneCast 🦴📡

**Twitch in de Steam-spelmodus** — een [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader)-plug-in voor Steam Deck / Bazzite / SteamOS.

🌍 **Talen:** [English](../README.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Italiano](README.it.md) · [Português](README.pt.md) · **Nederlands** · [Polski](README.pl.md) · [Русский](README.ru.md)

> Onderdeel van de Necrosiak-plug-insuite, naast
> [SkullKey](https://github.com/Necrosiak/SkullKey),
> [Steamcord](https://github.com/Necrosiak/Steamcord) en BC250-Toolkit.
> De plug-ininterface is vertaald in 9 talen en volgt automatisch je SteamOS-taal.

---

## Wat het doet

BoneCast zet alles wat je nodig hebt om naar **Twitch** te streamen direct in het **Snelmenu** van Steam — geen bureaublad, geen toetsenbord, van inloggen tot livegaan volledig geschikt voor de controller.

- **Eén Twitch-login** *(apparaatcode — controllervriendelijk)*: je voert een korte code in op `twitch.tv/activate`, en BoneCast haalt je **streamsleutel automatisch** op. Nooit meer kopiëren en plakken.
- **Ga live vanuit het QAM** — één knop start en stopt de RTMP-stream. Een **● LIVE**-badge verschijnt tijdens het uitzenden.
- **Bewerkbare streamtitel** — ingesteld vanuit de plug-in, **ook tijdens het livegaan** te wijzigen.
- **Automatische spelcategorie** — gelezen uit het actieve Steam-spel (werkt ook voor niet-Steam-snelkoppelingen) en direct bijgewerkt. Valt terug op *Just Chatting* wanneer een spel geen bijpassende Twitch-categorie heeft.
- **Transparante chat-overlay** — alleen-lezen Twitch-chat getekend **over het spel** in de Spelmodus (gamescope external-overlay-vlak), met native + **BTTV / 7TV / FFZ**-emotes. Verplaatsbaar en aanpasbaar.
- **Microfoon live dempen** — dempt je microfoon **op de stream** met één tik, zonder de uitzending te stoppen (en zonder je Discord-gesprek te dempen).
- **Streaminstellingen per account** — resolutie, fps, video-/audiobitrate, keyframe-interval en een **automatisch gedetecteerde encoder** (NVENC ▸ VAAPI ▸ software-x264). Alleen encoders die echt werken op jouw hardware worden aangeboden.
- **Discord-audiobrug** *(wanneer [Steamcord](https://github.com/Necrosiak/Steamcord) is geïnstalleerd)*: een optionele schakelaar mengt je **Discord-stem** in de stream, zodat je groep door kijkers wordt gehoord — terwijl jij ze gewoon blijft horen.

---

## Hoe het werkt

Twitch heeft geen video-push-API, dus livegaan betekent altijd een **RTMP-push** op de achtergrond. BoneCast regelt dat voor je:

1. De **OAuth-apparaatcodeflow** logt je in bij Twitch en haalt je streamsleutel, titel en categorie op via de Helix-API — je raakt de sleutel nooit aan.
2. Het spelbeeld wordt vanuit **gamescope** vastgelegd naar een `v4l2`-loopbackapparaat, en **ffmpeg** codeert het (hardware indien beschikbaar, anders software-`libx264`) en pusht het naar `rtmp://…/<je-sleutel>`.
3. De **chat-overlay** is een transparant WebKit-oppervlak dat naar het gamescope external-overlay-vlak wordt gepromoveerd, dat de Twitch-IRC anoniem leest en emotes weergeeft.

Alles wordt vanuit het QAM aangestuurd en overleeft herstarts.

---

## Installatie

1. Installeer [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader).
2. Pak de nieuwste `BoneCast.zip` van de [Releases](https://github.com/Necrosiak/BoneCast/releases)-pagina, of installeer hem uit de Decky-store zodra beschikbaar.
3. Open het **Snelmenu → BoneCast**, log in bij Twitch en ga live.

BoneCast **werkt zichzelf automatisch bij** vanuit GitHub-Releases (in te schakelen in de sectie *Updates* van de plug-in).

---

## Met dank aan

Gemaakt en onderhouden door **Necrosiak**. Onderdeel van de Necrosiak-plug-insuite voor de Steam-spelmodus.
