# BoneCast 🦴📡

**Twitch en el Modo Juego de Steam** — un complemento de [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) para Steam Deck / Bazzite / SteamOS.

🌍 **Idiomas:** [English](../README.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · **Español** · [Italiano](README.it.md) · [Português](README.pt.md) · [Nederlands](README.nl.md) · [Polski](README.pl.md) · [Русский](README.ru.md)

> Forma parte de la suite de plugins de Necrosiak, junto a
> [SkullKey](https://github.com/Necrosiak/SkullKey),
> [Steamcord](https://github.com/Necrosiak/Steamcord) y BC250-Toolkit.
> La interfaz del plugin está traducida a 9 idiomas y sigue automáticamente el idioma de SteamOS.

---

## Qué hace

BoneCast pone todo lo necesario para transmitir en **Twitch** directamente en el **Menú de acceso rápido** de Steam — sin escritorio, sin teclado, pensado para el mando desde el inicio de sesión hasta salir en directo.

- **Un único inicio de sesión en Twitch** *(código de dispositivo — apto para mando)*: introduces un código corto en `twitch.tv/activate` y BoneCast obtiene tu **clave de transmisión automáticamente**. Nunca más copiar y pegar.
- **Sal en directo desde el QAM** — un botón inicia y detiene el flujo RTMP. Una insignia **● EN DIRECTO** se muestra mientras transmites.
- **Título del directo editable** — se define desde el plugin y se puede cambiar **incluso en directo**.
- **Categoría de juego automática** — leída del juego de Steam en ejecución (también funciona con accesos directos no-Steam) y actualizada al vuelo. Si un juego no tiene categoría de Twitch equivalente, se usa *Just Chatting*.
- **Overlay de chat transparente** — el chat de Twitch en solo lectura dibujado **sobre el juego** en Modo Juego (plano external-overlay de gamescope), con emotes nativos + **BTTV / 7TV / FFZ**. La posición, el tamaño y la opacidad se ajustan en vivo desde el QAM, y sigue visible incluso con Big Picture en primer plano.
- **🎬 Clips instantáneos** — en directo, un botón recorta los últimos ~30 segundos mediante la API de Twitch; el clip aparece en tu panel unos 15 segundos después.
- **💬 Habla en tu propio chat** — envía mensajes a tu chat de Twitch directamente desde el QAM, sin malabares de teclado sobre el escritorio.
- **⏸️ Modo BRB** — un toque sustituye la imagen del juego por una pantalla de pausa limpia y silencia tu micrófono; otro toque te trae de vuelta. La transmisión nunca se corta.
- **⏺️ Grabación local** — guarda tu sesión como MKV en `~/Vídeos/BoneCast/`, en paralelo al directo o **sin transmitir nada** (sin clave de transmisión de por medio).
- **Silenciar el micro en directo** — corta tu micrófono **en la transmisión** con un toque, sin detener el directo (y sin silenciar tu llamada de Discord).
- **Ajustes de transmisión por cuenta** — resolución, fps, tasa de bits de vídeo/audio, intervalo de fotogramas clave y un **codificador autodetectado** (NVENC ▸ VAAPI ▸ x264 por software). Solo se ofrecen los codificadores que realmente funcionan en tu hardware.
- **Puente de audio de Discord** *(si [Steamcord](https://github.com/Necrosiak/Steamcord) está instalado)*: un interruptor opcional mezcla tu **voz de Discord** en la transmisión, para que tu grupo sea escuchado por los espectadores — mientras tú los sigues oyendo con normalidad.

---

## Cómo funciona

Twitch no tiene API de envío de vídeo, así que salir en directo siempre implica un **push RTMP** por debajo. BoneCast se encarga por ti:

1. El **flujo OAuth por código de dispositivo** te conecta a Twitch y obtiene tu clave de transmisión, tu título y tu categoría mediante la API Helix — nunca tocas la clave.
2. La imagen del juego se captura desde **gamescope** hacia un dispositivo de bucle `v4l2`, y **ffmpeg** la codifica (por hardware si está disponible, con `libx264` por software si no) y la envía a `rtmp://…/<tu-clave>`.
3. El **overlay de chat** es una superficie WebKit transparente promovida al plano external-overlay de gamescope, que lee el IRC de Twitch de forma anónima y muestra los emotes.

Todo se controla desde el QAM y sobrevive a los reinicios.

---

## 📸 Capturas de pantalla

<p align="center">
  <img src="img/bonecast-golive.jpg" width="60%" alt="Panel de salir en directo"/>
</p>

## Instalación

1. Instala [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader).
2. Activa el **Modo desarrollador** en los ajustes generales de Decky, luego ajustes de Decky → **Desarrollador** → *Instalar plugin desde URL*:
   `https://github.com/Necrosiak/BoneCast/releases/latest/download/BoneCast.zip`
   (o descarga `BoneCast.zip` desde la página de [Releases](https://github.com/Necrosiak/BoneCast/releases) e instálalo desde el ZIP).
3. Abre el **Menú de acceso rápido → BoneCast**, inicia sesión en Twitch y sal en directo.

BoneCast **se actualiza automáticamente** desde las Releases de GitHub (desactivable en la sección *Actualizaciones* del plugin).

---

## 🐧 Compatibilidad

BoneCast apunta a **todas las distribuciones Linux** capaces de ejecutar Steam
en Modo Juego / Big Picture: una sola build, detección en tiempo de ejecución
de todo lo externo (ffmpeg, libx264, v4l2loopback, GStreamer), y el comando de
instalación exacto para tu gestor de paquetes mostrado en el QAM cuando falta
algo. Notas de paquetes por distribución: [OS-NOTES.md](OS-NOTES.md).

## 🐛 Errores e ideas — ¡no lo dudes!

¿Has encontrado un error, algo se comporta raro en tu distribución o falta una
función? **Abre un [issue](https://github.com/Necrosiak/BoneCast/issues)** —
cada informe orienta directamente lo que se construirá después. Si puedes,
incluye:

- tu distribución y versión (Bazzite 42, CachyOS, Ubuntu 24.04…) y tu GPU (para las sondas de codificador)
- la versión del plugin y qué estabas haciendo (salir en directo, overlay, OAuth…)
- qué esperabas frente a qué ocurrió
- los registros: `~/homebrew/logs/BoneCast/`

Las peticiones de funciones y los informes de «¡funciona!» en configuraciones
poco comunes son igual de valiosos.

## Créditos

Creado y mantenido por **Necrosiak**. Forma parte de la suite de plugins de Necrosiak para el Modo Juego de Steam.
