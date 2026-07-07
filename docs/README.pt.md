# BoneCast 🦴📡

**Twitch no Modo Jogo do Steam** — um plugin do [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) para Steam Deck / Bazzite / SteamOS.

🌍 **Idiomas:** [English](../README.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Italiano](README.it.md) · **Português** · [Nederlands](README.nl.md) · [Polski](README.pl.md) · [Русский](README.ru.md)

> Faz parte da suíte de plugins da Necrosiak, ao lado de
> [SkullKey](https://github.com/Necrosiak/SkullKey),
> [Steamcord](https://github.com/Necrosiak/Steamcord) e BC250-Toolkit.
> A interface está traduzida em 9 idiomas e segue automaticamente o idioma do SteamOS.

---

## O que faz

O BoneCast coloca tudo o que você precisa para transmitir na **Twitch** diretamente no **Menu de Acesso Rápido** do Steam — sem desktop, sem teclado, pensado para o controle desde o login até entrar ao vivo.

- **Um único login na Twitch** *(código de dispositivo — compatível com controle)*: você digita um código curto em `twitch.tv/activate` e o BoneCast obtém a sua **chave de transmissão automaticamente**. Nunca mais copiar e colar.
- **Entre ao vivo pelo QAM** — um botão inicia e para a transmissão RTMP. Um selo **● AO VIVO** aparece durante a transmissão.
- **Título de transmissão editável** — definido pelo plugin e alterável **mesmo ao vivo**.
- **Categoria de jogo automática** — lida do jogo Steam em execução (também funciona com atalhos não-Steam) e atualizada na hora. Recorre a *Just Chatting* quando um jogo não tem uma categoria correspondente na Twitch.
- **Sobreposição de chat transparente** — o chat da Twitch em somente leitura desenhado **sobre o jogo** no Modo Jogo (plano external-overlay do gamescope), com emotes nativos + **BTTV / 7TV / FFZ**. Móvel e personalizável.
- **Silenciar o microfone ao vivo** — corte o seu microfone **na transmissão** com um toque, sem parar a emissão (e sem silenciar a sua chamada do Discord).
- **Configurações de transmissão por conta** — resolução, fps, taxa de bits de vídeo/áudio, intervalo de quadro-chave e um **codificador detectado automaticamente** (NVENC ▸ VAAPI ▸ x264 por software). Só são oferecidos os codificadores que realmente funcionam no seu hardware.
- **Ponte de áudio do Discord** *(quando o [Steamcord](https://github.com/Necrosiak/Steamcord) está instalado)*: um interruptor opcional mistura a sua **voz do Discord** na transmissão, para que o seu grupo seja ouvido pelos espectadores — enquanto você continua a ouvi-los normalmente.

---

## Como funciona

A Twitch não tem uma API de envio de vídeo, então entrar ao vivo sempre envolve um **envio RTMP** nos bastidores. O BoneCast cuida disso por você:

1. O **fluxo OAuth por código de dispositivo** conecta você à Twitch e obtém a sua chave de transmissão, título e categoria pela API Helix — você nunca toca na chave.
2. O quadro do jogo é capturado do **gamescope** para um dispositivo de loopback `v4l2`, e o **ffmpeg** o codifica (hardware quando disponível, software `libx264` caso contrário) e o envia para `rtmp://…/<sua-chave>`.
3. A **sobreposição de chat** é uma superfície WebKit transparente promovida ao plano external-overlay do gamescope, que lê o IRC da Twitch anonimamente e renderiza os emotes.

Tudo é controlado pelo QAM e sobrevive a reinicializações.

---

## Instalação

1. Instale o [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader).
2. Baixe o `BoneCast.zip` mais recente na página de [Releases](https://github.com/Necrosiak/BoneCast/releases), ou instale-o pela loja do Decky quando estiver disponível.
3. Abra o **Menu de Acesso Rápido → BoneCast**, faça login na Twitch e entre ao vivo.

O BoneCast **atualiza-se automaticamente** a partir das Releases do GitHub (alternável na seção *Atualizações* do plugin).

---

## Créditos

Criado e mantido por **Necrosiak**. Faz parte da suíte de plugins da Necrosiak para o Modo Jogo do Steam.
