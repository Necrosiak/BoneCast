# BoneCast 🦴📡

**Twitch nella Modalità Gioco di Steam** — un plugin [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) per Steam Deck / Bazzite / SteamOS.

🌍 **Lingue:** [English](../README.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Español](README.es.md) · **Italiano** · [Português](README.pt.md) · [Nederlands](README.nl.md) · [Polski](README.pl.md) · [Русский](README.ru.md)

> Fa parte della suite di plugin Necrosiak, insieme a
> [SkullKey](https://github.com/Necrosiak/SkullKey),
> [Steamcord](https://github.com/Necrosiak/Steamcord) e BC250-Toolkit.
> L'interfaccia è tradotta in 9 lingue e segue automaticamente la lingua di SteamOS.

---

## Cosa fa

BoneCast mette tutto il necessario per trasmettere su **Twitch** direttamente nel **Menu di Accesso Rapido** di Steam — senza desktop, senza tastiera, pensato per il controller dal login fino alla diretta.

- **Un solo accesso a Twitch** *(codice dispositivo — compatibile con il controller)*: inserisci un codice breve su `twitch.tv/activate` e BoneCast recupera la tua **chiave di streaming automaticamente**. Mai più copia e incolla.
- **Vai in diretta dal QAM** — un pulsante avvia e ferma lo stream RTMP. Un distintivo **● IN DIRETTA** appare durante la trasmissione.
- **Titolo dello stream modificabile** — impostato dal plugin, modificabile **anche in diretta**.
- **Categoria di gioco automatica** — letta dal gioco Steam in esecuzione (funziona anche con i collegamenti non-Steam) e aggiornata al volo. Ripiega su *Just Chatting* quando un gioco non ha una categoria Twitch corrispondente.
- **Overlay chat trasparente** — la chat Twitch in sola lettura disegnata **sopra il gioco** in Modalità Gioco (piano external-overlay di gamescope), con emote native + **BTTV / 7TV / FFZ**. Spostabile e personalizzabile.
- **Muto microfono in diretta** — silenzia il microfono **sullo stream** con un tocco, senza fermare la trasmissione (e senza silenziare la tua chiamata Discord).
- **Impostazioni di streaming per account** — risoluzione, fps, bitrate video/audio, intervallo dei fotogrammi chiave e un **encoder rilevato automaticamente** (NVENC ▸ VAAPI ▸ x264 software). Vengono offerti solo gli encoder che funzionano davvero sul tuo hardware.
- **Ponte audio Discord** *(quando [Steamcord](https://github.com/Necrosiak/Steamcord) è installato)*: un interruttore opzionale miscela la tua **voce Discord** nello stream, così il tuo gruppo viene sentito dagli spettatori — mentre tu continui a sentirli normalmente.

---

## Come funziona

Twitch non ha un'API di push video, quindi andare in diretta comporta sempre un **push RTMP** dietro le quinte. BoneCast se ne occupa per te:

1. Il **flusso OAuth a codice dispositivo** ti collega a Twitch e recupera la tua chiave di streaming, il titolo e la categoria tramite l'API Helix — non tocchi mai la chiave.
2. Il fotogramma del gioco viene catturato da **gamescope** in un dispositivo di loopback `v4l2`, e **ffmpeg** lo codifica (hardware se disponibile, software `libx264` altrimenti) e lo invia a `rtmp://…/<la-tua-chiave>`.
3. L'**overlay chat** è una superficie WebKit trasparente promossa sul piano external-overlay di gamescope, che legge l'IRC di Twitch in modo anonimo e mostra le emote.

Tutto è pilotato dal QAM e sopravvive ai riavvii.

---

## Installazione

1. Installa [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader).
2. Scarica l'ultimo `BoneCast.zip` dalla pagina [Releases](https://github.com/Necrosiak/BoneCast/releases), oppure installalo dallo store Decky una volta disponibile.
3. Apri il **Menu di Accesso Rapido → BoneCast**, accedi a Twitch e vai in diretta.

BoneCast **si aggiorna automaticamente** dalle Release di GitHub (attivabile nella sezione *Aggiornamenti* del plugin).

---

## Crediti

Creato e mantenuto da **Necrosiak**. Fa parte della suite di plugin Necrosiak per la Modalità Gioco di Steam.
