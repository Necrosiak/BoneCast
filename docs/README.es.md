# BoneCast 🦴📡

**Twitch en el Modo Juego de Steam** — un complemento de [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) para Steam Deck / Bazzite / SteamOS.

🌍 **Idiomas:** [English](../README.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · **Español** · [Italiano](README.it.md) · [Português](README.pt.md) · [Nederlands](README.nl.md) · [Polski](README.pl.md) · [Русский](README.ru.md)

> Forma parte de la suite de complementos de Necrosiak, junto a
> [SkullKey](https://github.com/Necrosiak/SkullKey),
> [Steamcord](https://github.com/Necrosiak/Steamcord) y BC250-Toolkit.
> La interfaz está traducida a 9 idiomas y sigue automáticamente el idioma de SteamOS.

---

## Qué hace

BoneCast pone todo lo necesario para transmitir en **Twitch** directamente en el **Menú de Acceso Rápido** de Steam — sin escritorio, sin teclado, pensado para el mando desde el inicio de sesión hasta salir en directo.

- **Un solo inicio de sesión en Twitch** *(código de dispositivo — compatible con mando)*: introduces un código corto en `twitch.tv/activate` y BoneCast obtiene tu **clave de transmisión automáticamente**. Nunca más copiar y pegar.
- **Sal en directo desde el QAM** — un botón inicia y detiene la transmisión RTMP. Aparece una insignia **● EN DIRECTO** mientras transmites.
- **Título de transmisión editable** — se define desde el complemento y se puede cambiar **incluso en directo**.
- **Categoría de juego automática** — leída del juego de Steam en ejecución (también funciona con accesos directos ajenos a Steam) y actualizada al vuelo. Recurre a *Just Chatting* cuando un juego no tiene una categoría de Twitch equivalente.
- **Superposición de chat transparente** — el chat de Twitch en solo lectura dibujado **sobre el juego** en Modo Juego (plano external-overlay de gamescope), con emotes nativos + **BTTV / 7TV / FFZ**. Movible y personalizable.
- **Silenciar el micrófono en directo** — corta tu micrófono **en la transmisión** con un toque, sin detener la emisión (y sin silenciar tu llamada de Discord).
- **Ajustes de transmisión por cuenta** — resolución, fps, tasa de bits de vídeo/audio, intervalo de fotograma clave y un **codificador detectado automáticamente** (NVENC ▸ VAAPI ▸ x264 por software). Solo se ofrecen los codificadores que realmente funcionan en tu hardware.
- **Puente de audio de Discord** *(cuando [Steamcord](https://github.com/Necrosiak/Steamcord) está instalado)*: un interruptor opcional mezcla tu **voz de Discord** en la transmisión, para que tu grupo se oiga por los espectadores — mientras tú los sigues oyendo con normalidad.

---

## Cómo funciona

Twitch no tiene una API de envío de vídeo, así que salir en directo siempre implica un **envío RTMP** por debajo. BoneCast se encarga por ti:

1. El **flujo OAuth por código de dispositivo** te conecta a Twitch y obtiene tu clave de transmisión, título y categoría mediante la API Helix — nunca tocas la clave.
2. El fotograma del juego se captura desde **gamescope** a un dispositivo de bucle `v4l2`, y **ffmpeg** lo codifica (hardware si está disponible, software `libx264` en caso contrario) y lo envía a `rtmp://…/<tu-clave>`.
3. La **superposición de chat** es una superficie WebKit transparente promovida al plano external-overlay de gamescope, que lee el IRC de Twitch de forma anónima y muestra los emotes.

Todo se controla desde el QAM y sobrevive a los reinicios.

---

## Instalación

1. Instala [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader).
2. Descarga el último `BoneCast.zip` desde la página de [Releases](https://github.com/Necrosiak/BoneCast/releases), o instálalo desde la tienda de Decky cuando esté disponible.
3. Abre el **Menú de Acceso Rápido → BoneCast**, inicia sesión en Twitch y sal en directo.

BoneCast **se actualiza automáticamente** desde las Releases de GitHub (conmutable en la sección *Actualizaciones* del complemento).

---

## Créditos

Creado y mantenido por **Necrosiak**. Forma parte de la suite de complementos de Necrosiak para el Modo Juego de Steam.
