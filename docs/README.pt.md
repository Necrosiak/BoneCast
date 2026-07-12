# BoneCast 🦴📡

**Twitch no Modo Jogo do Steam** — um plugin do [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) para Steam Deck / Bazzite / SteamOS.

🌍 **Idiomas:** [English](../README.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Italiano](README.it.md) · **Português** · [Nederlands](README.nl.md) · [Polski](README.pl.md) · [Русский](README.ru.md)

> Faz parte da suíte de plugins Necrosiak, ao lado de
> [SkullKey](https://github.com/Necrosiak/SkullKey),
> [Steamcord](https://github.com/Necrosiak/Steamcord) e BC250-Toolkit.
> A interface do plugin está traduzida em 9 idiomas e segue automaticamente o idioma do SteamOS.

---

## O que ele faz

O BoneCast coloca tudo o que você precisa para transmitir na **Twitch** diretamente no **Menu de acesso rápido** do Steam — sem desktop, sem teclado, pensado para o controle do login até entrar ao vivo.

- **Um único login na Twitch** *(código de dispositivo — amigável ao controle)*: você digita um código curto em `twitch.tv/activate` e o BoneCast obtém sua **chave de transmissão automaticamente**. Nunca mais copiar e colar.
- **Entre ao vivo pelo QAM** — um botão inicia e para o fluxo RTMP. Um selo **● AO VIVO** aparece enquanto você transmite.
- **Título da transmissão editável** — definido no plugin, alterável **mesmo ao vivo**.
- **Categoria de jogo automática** — lida do jogo Steam em execução (funciona também com atalhos não-Steam) e atualizada em tempo real. Se um jogo não tiver categoria correspondente na Twitch, usa-se *Just Chatting*.
- **Overlay de chat transparente** — o chat da Twitch em somente leitura desenhado **por cima do jogo** no Modo Jogo (plano external-overlay do gamescope), com emotes nativos + **BTTV / 7TV / FFZ**. Posição, tamanho e opacidade se ajustam ao vivo pelo QAM, e ele continua visível mesmo com o Big Picture em foco.
- **🎬 Clipes instantâneos** — ao vivo, um botão recorta os últimos ~30 segundos pela API da Twitch; o clipe chega ao seu painel cerca de 15 segundos depois.
- **💬 Fale no seu próprio chat** — envie mensagens para o seu chat da Twitch direto do QAM, sem malabarismo de teclado sobre o desktop.
- **⏸️ Modo BRB** — um toque substitui a imagem do jogo por uma tela de pausa limpa e silencia seu microfone; outro toque traz você de volta. A transmissão nunca cai.
- **⏺️ Gravação local** — salve sua sessão como MKV em `~/Vídeos/BoneCast/`, em paralelo à transmissão ao vivo ou **sem transmitir nada** (nenhuma chave de transmissão envolvida).
- **Mudo do microfone ao vivo** — corte seu microfone **na transmissão** com um toque, sem parar a transmissão (e sem silenciar sua chamada do Discord).
- **Configurações de transmissão por conta** — resolução, fps, taxa de bits de vídeo/áudio, intervalo de quadros-chave e um **codificador autodetectado** (NVENC ▸ VAAPI ▸ x264 por software). Só são oferecidos os codificadores que realmente funcionam no seu hardware.
- **Ponte de áudio do Discord** *(quando o [Steamcord](https://github.com/Necrosiak/Steamcord) está instalado)*: uma opção mistura sua **voz do Discord** na transmissão, para que seu grupo seja ouvido pelos espectadores — enquanto você continua a ouvi-los normalmente.

---

## Como funciona

A Twitch não tem API de envio de vídeo, então entrar ao vivo sempre significa um **push RTMP** por baixo dos panos. O BoneCast cuida disso para você:

1. O **fluxo OAuth por código de dispositivo** conecta você à Twitch e obtém sua chave de transmissão, título e categoria pela API Helix — você nunca toca na chave.
2. A imagem do jogo é capturada do **gamescope** para um dispositivo de loopback `v4l2`, e o **ffmpeg** a codifica (por hardware quando disponível, com `libx264` por software caso contrário) e a envia para `rtmp://…/<sua-chave>`.
3. O **overlay de chat** é uma superfície WebKit transparente promovida ao plano external-overlay do gamescope, que lê o IRC da Twitch anonimamente e renderiza os emotes.

Tudo é controlado pelo QAM e sobrevive a reinicializações.

---

## 📸 Capturas de tela

<p align="center">
  <img src="img/bonecast-golive.jpg" width="60%" alt="Painel de entrar ao vivo"/>
</p>

## Instalação

1. Instale o [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader).
2. Ative o **Modo desenvolvedor** nas configurações gerais do Decky, depois configurações do Decky → **Desenvolvedor** → *Instalar plugin de URL*:
   `https://github.com/Necrosiak/BoneCast/releases/latest/download/BoneCast.zip`
   (ou baixe o `BoneCast.zip` na página de [Releases](https://github.com/Necrosiak/BoneCast/releases) e instale a partir do ZIP).
3. Abra o **Menu de acesso rápido → BoneCast**, faça login na Twitch e entre ao vivo.

O BoneCast **se atualiza automaticamente** pelas Releases do GitHub (desativável na seção *Atualizações* do plugin).

---

## 🐧 Compatibilidade

O BoneCast mira **todas as distribuições Linux** capazes de rodar o Steam no
Modo Jogo / Big Picture: uma única build, detecção em tempo de execução de
tudo o que é externo (ffmpeg, libx264, v4l2loopback, GStreamer), e o comando
de instalação exato para o seu gerenciador de pacotes exibido no QAM quando
algo falta. Notas de pacotes por distribuição: [OS-NOTES.md](OS-NOTES.md).

## 🐛 Bugs e ideias — não hesite!

Encontrou um bug, algo se comporta mal na sua distribuição ou falta um
recurso? **Abra uma [issue](https://github.com/Necrosiak/BoneCast/issues)** —
cada relato orienta diretamente o que será construído em seguida. Se puder,
inclua:

- sua distribuição e versão (Bazzite 42, CachyOS, Ubuntu 24.04…) e sua GPU (para as sondas de codificador)
- a versão do plugin e o que você estava fazendo (entrar ao vivo, overlay, OAuth…)
- o que você esperava vs. o que aconteceu
- os logs: `~/homebrew/logs/BoneCast/`

Pedidos de recursos e relatos de «funciona!» em configurações incomuns são
igualmente valiosos.

## Créditos

Criado e mantido por **Necrosiak**. Faz parte da suíte de plugins Necrosiak para o Modo Jogo do Steam.
