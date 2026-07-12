# BoneCast 🦴📡

**Twitch nella Modalità Gioco di Steam** — un plugin [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) per Steam Deck / Bazzite / SteamOS.

🌍 **Lingue:** [English](../README.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Español](README.es.md) · **Italiano** · [Português](README.pt.md) · [Nederlands](README.nl.md) · [Polski](README.pl.md) · [Русский](README.ru.md)

> Fa parte della suite di plugin Necrosiak, insieme a
> [SkullKey](https://github.com/Necrosiak/SkullKey),
> [Steamcord](https://github.com/Necrosiak/Steamcord) e BC250-Toolkit.
> L'interfaccia del plugin è tradotta in 9 lingue e segue automaticamente la lingua di SteamOS.

---

## Cosa fa

BoneCast mette tutto il necessario per trasmettere su **Twitch** direttamente nel **Menu di accesso rapido** di Steam — niente desktop, niente tastiera, pensato per il controller dal login fino alla diretta.

- **Un solo accesso a Twitch** *(codice dispositivo — adatto al controller)*: inserisci un codice breve su `twitch.tv/activate` e BoneCast recupera la tua **chiave di trasmissione automaticamente**. Mai più copia-incolla.
- **Vai in diretta dal QAM** — un pulsante avvia e ferma il flusso RTMP. Un badge **● IN DIRETTA** compare mentre trasmetti.
- **Titolo della diretta modificabile** — impostato dal plugin, modificabile **anche in diretta**.
- **Categoria di gioco automatica** — letta dal gioco Steam in esecuzione (funziona anche con i collegamenti non-Steam) e aggiornata al volo. Se un gioco non ha una categoria Twitch corrispondente, si passa a *Just Chatting*.
- **Overlay della chat trasparente** — la chat di Twitch in sola lettura disegnata **sopra il gioco** in Modalità Gioco (piano external-overlay di gamescope), con emote native + **BTTV / 7TV / FFZ**. Posizione, dimensione e opacità si regolano in tempo reale dal QAM, e resta visibile anche con Big Picture in primo piano.
- **🎬 Clip istantanee** — in diretta, un pulsante ritaglia gli ultimi ~30 secondi tramite l'API di Twitch; la clip arriva sulla tua dashboard circa 15 secondi dopo.
- **💬 Parla nella tua chat** — invia messaggi nella tua chat di Twitch direttamente dal QAM, senza acrobazie con tastiera e desktop.
- **⏸️ Modalità BRB** — un tocco sostituisce l'immagine del gioco con una schermata di pausa pulita e silenzia il microfono; un altro tocco ti riporta in gioco. La trasmissione non si interrompe mai.
- **⏺️ Registrazione locale** — salva la tua sessione come MKV in `~/Video/BoneCast/`, in parallelo alla diretta oppure **senza trasmettere affatto** (nessuna chiave di trasmissione coinvolta).
- **Muto del microfono in diretta** — taglia il microfono **sulla trasmissione** con un tocco, senza fermare la diretta (e senza silenziare la tua chiamata Discord).
- **Impostazioni di trasmissione per account** — risoluzione, fps, bitrate video/audio, intervallo dei keyframe e un **encoder rilevato automaticamente** (NVENC ▸ VAAPI ▸ x264 software). Vengono proposti solo gli encoder che funzionano davvero sul tuo hardware.
- **Ponte audio Discord** *(se [Steamcord](https://github.com/Necrosiak/Steamcord) è installato)*: un interruttore opzionale mixa la tua **voce Discord** nella trasmissione, così il tuo gruppo viene sentito dagli spettatori — mentre tu continui a sentirli normalmente.

---

## Come funziona

Twitch non ha un'API di push video, quindi andare in diretta significa sempre un **push RTMP** dietro le quinte. BoneCast se ne occupa per te:

1. Il **flusso OAuth con codice dispositivo** ti connette a Twitch e recupera chiave di trasmissione, titolo e categoria tramite l'API Helix — non tocchi mai la chiave.
2. L'immagine del gioco viene catturata da **gamescope** verso un dispositivo di loopback `v4l2`, e **ffmpeg** la codifica (hardware quando disponibile, `libx264` software altrimenti) e la invia a `rtmp://…/<la-tua-chiave>`.
3. L'**overlay della chat** è una superficie WebKit trasparente promossa sul piano external-overlay di gamescope, che legge l'IRC di Twitch in forma anonima e mostra le emote.

Tutto si controlla dal QAM e sopravvive ai riavvii.

---

## 📸 Screenshot

<p align="center">
  <img src="img/bonecast-golive.jpg" width="60%" alt="Pannello per andare in diretta"/>
</p>

## Installazione

1. Installa [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader).
2. Attiva la **Modalità sviluppatore** nelle impostazioni generali di Decky, poi impostazioni Decky → **Sviluppatore** → *Installa plugin da URL*:
   `https://github.com/Necrosiak/BoneCast/releases/latest/download/BoneCast.zip`
   (oppure scarica `BoneCast.zip` dalla pagina delle [Releases](https://github.com/Necrosiak/BoneCast/releases) e installalo dallo ZIP).
3. Apri il **Menu di accesso rapido → BoneCast**, accedi a Twitch e vai in diretta.

BoneCast **si aggiorna automaticamente** dalle Releases di GitHub (disattivabile nella sezione *Aggiornamenti* del plugin).

---

## 🐧 Compatibilità

BoneCast punta a **tutte le distribuzioni Linux** in grado di eseguire Steam in
Modalità Gioco / Big Picture: una sola build, rilevamento a runtime di tutto
ciò che è esterno (ffmpeg, libx264, v4l2loopback, GStreamer), e il comando di
installazione esatto per il tuo gestore di pacchetti mostrato nel QAM quando
manca qualcosa. Note sui pacchetti per distribuzione: [OS-NOTES.md](OS-NOTES.md).

## 🐛 Bug e idee — non esitare!

Hai trovato un bug, qualcosa si comporta male sulla tua distribuzione o manca
una funzione? **Apri una [issue](https://github.com/Necrosiak/BoneCast/issues)**
— ogni segnalazione orienta direttamente ciò che verrà costruito dopo. Se
puoi, includi:

- la tua distribuzione e versione (Bazzite 42, CachyOS, Ubuntu 24.04…) e la tua GPU (per le sonde dell'encoder)
- la versione del plugin e cosa stavi facendo (andare in diretta, overlay, OAuth…)
- cosa ti aspettavi rispetto a cosa è successo
- i log: `~/homebrew/logs/BoneCast/`

Le richieste di funzionalità e i report «funziona!» su configurazioni insolite
sono altrettanto preziosi.

## Crediti

Creato e mantenuto da **Necrosiak**. Fa parte della suite di plugin Necrosiak per la Modalità Gioco di Steam.
