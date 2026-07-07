# BoneCast 🦴📡

**Twitch en Mode Jeu Steam** — un plugin [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) pour Steam Deck / Bazzite / SteamOS.

🌍 **Langues :** [English](../README.md) · **Français** · [Deutsch](README.de.md) · [Español](README.es.md) · [Italiano](README.it.md) · [Português](README.pt.md) · [Nederlands](README.nl.md) · [Polski](README.pl.md) · [Русский](README.ru.md)

> Fait partie de la suite de plugins Necrosiak, aux côtés de
> [SkullKey](https://github.com/Necrosiak/SkullKey),
> [Steamcord](https://github.com/Necrosiak/Steamcord) et BC250-Toolkit.
> L'interface est traduite en 9 langues et suit automatiquement la langue de SteamOS.

---

## Ce que ça fait

BoneCast met tout ce qu'il faut pour streamer sur **Twitch** directement dans le **Menu d'accès rapide** de Steam — sans bureau, sans clavier, pensé pour la manette du login jusqu'au passage en live.

- **Une seule connexion Twitch** *(code d'appareil — compatible manette)* : tu saisis un code court sur `twitch.tv/activate`, et BoneCast récupère ta **clé de stream automatiquement**. Plus jamais de copier-coller.
- **Passe en live depuis le QAM** — un bouton démarre et arrête le flux RTMP. Un badge **● EN DIRECT** s'affiche pendant la diffusion.
- **Titre du stream modifiable** — défini depuis le plugin, changeable **même en direct**.
- **Catégorie de jeu automatique** — lue depuis le jeu Steam en cours (fonctionne aussi pour les raccourcis non-Steam) et mise à jour à la volée. Repli sur *Just Chatting* quand un jeu n'a pas de catégorie Twitch correspondante.
- **Overlay de chat transparent** — le chat Twitch en lecture seule dessiné **par-dessus le jeu** en Mode Jeu (plan external-overlay de gamescope), avec les émotes natives + **BTTV / 7TV / FFZ**. Déplaçable et stylisable.
- **Coupure micro en direct** — coupe ton micro **sur le stream** d'un seul appui, sans arrêter la diffusion (et sans couper ton vocal Discord).
- **Réglages de stream par compte** — résolution, fps, débit vidéo/audio, intervalle d'image-clé, et un **encodeur auto-détecté** (NVENC ▸ VAAPI ▸ x264 logiciel). Seuls les encodeurs qui marchent réellement sur ton matériel sont proposés.
- **Pont audio Discord** *(si [Steamcord](https://github.com/Necrosiak/Steamcord) est installé)* : une case optionnelle mixe ta **voix Discord** dans le stream, pour que ton groupe soit entendu des spectateurs — tout en continuant à les entendre normalement.

---

## Comment ça marche

Twitch n'a pas d'API de push vidéo, donc passer en live implique toujours un **push RTMP** en coulisses. BoneCast s'en occupe pour toi :

1. Le **flux OAuth par code d'appareil** te connecte à Twitch et récupère ta clé de stream, ton titre et ta catégorie via l'API Helix — tu ne touches jamais à la clé.
2. L'image du jeu est capturée depuis **gamescope** vers un périphérique de bouclage `v4l2`, puis **ffmpeg** l'encode (matériel si disponible, logiciel `libx264` sinon) et la pousse vers `rtmp://…/<ta-clé>`.
3. L'**overlay de chat** est une surface WebKit transparente promue sur le plan external-overlay de gamescope, qui lit l'IRC Twitch de façon anonyme et affiche les émotes.

Tout se pilote depuis le QAM et survit aux redémarrages.

---

## Installation

1. Installe [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader).
2. Récupère le dernier `BoneCast.zip` depuis la page des [Releases](https://github.com/Necrosiak/BoneCast/releases), ou installe-le depuis le store Decky une fois disponible.
3. Ouvre le **Menu d'accès rapide → BoneCast**, connecte-toi à Twitch, et passe en live.

BoneCast **se met à jour automatiquement** depuis les Releases GitHub (activable dans la section *Mises à jour* du plugin).

---

## Crédits

Créé et maintenu par **Necrosiak**. Fait partie de la suite de plugins Necrosiak pour le Mode Jeu Steam.
