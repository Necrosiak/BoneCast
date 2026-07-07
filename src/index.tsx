import { useEffect, useState } from "react";
import {
  staticClasses,
  PanelSection,
  PanelSectionRow,
  TextField,
  ToggleField,
  SliderField,
  Dropdown,
  DialogButton,
  Router,
} from "@decky/ui";
import { definePlugin, call } from "@decky/api";
import { FaTwitch } from "react-icons/fa";
import { focusHalo, TWITCH, DANGER } from "./components/Styled";

const B = DialogButton as any;

// ── Section streaming : login OAuth + titre + catégorie auto ──────────────────
function StreamSection() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [login, setLogin] = useState("");
  const [keySet, setKeySet] = useState(false);
  const [title, setTitle] = useState("");
  const [titleInput, setTitleInput] = useState("");
  const [gameName, setGameName] = useState("");
  // device flow
  const [authing, setAuthing] = useState(false);
  const [authBusy, setAuthBusy] = useState(false);
  const [authCode, setAuthCode] = useState("");
  const [authMsg, setAuthMsg] = useState("");
  // streaming (live Twitch)
  const [streaming, setStreaming] = useState(false);
  const [streamBusy, setStreamBusy] = useState(false);
  const [streamMsg, setStreamMsg] = useState("");
  // mute micro à la volée (n'affecte que le stream, pas le vocal Discord)
  const [micActive, setMicActive] = useState(false);
  const [micMuted, setMicMuted] = useState(false);
  // réglages du stream + encodeurs détectés
  const [encoders, setEncoders] = useState<string[]>(["software"]);
  const [steamcord, setSteamcord] = useState(false);
  const [st, setSt] = useState<any>({ resolution: "720p", fps: 30, bitrate: 4500,
    audio_bitrate: 160, keyframe: 2, encoder: "auto", mic: false });
  // focus states
  const [loginFocus, setLoginFocus] = useState(false);
  const [logoutFocus, setLogoutFocus] = useState(false);
  const [titleFocus, setTitleFocus] = useState(false);
  const [liveFocus, setLiveFocus] = useState(false);
  const [micFocus, setMicFocus] = useState(false);

  const refresh = () =>
    call<[], any>("get_config").then((c: any) => {
      setLoggedIn(!!c?.logged_in); setLogin(c?.login || "");
      setKeySet(!!c?.key_set);
      setStreaming(!!c?.streaming);
      if (typeof c?.title === "string") setTitle(c.title);
      if (typeof c?.game_name === "string") setGameName(c.game_name);
      if (c?.stream) setSt((p: any) => ({ ...p, ...c.stream }));
      setSteamcord(!!c?.steamcord);
    }).catch(() => {});

  useEffect(() => { refresh(); }, []);

  // Détecte les encodeurs dispo (matériel VAAPI + logiciel) une fois au montage.
  useEffect(() => {
    call<[], any>("get_encoders").then((e: any) => {
      if (Array.isArray(e?.available)) setEncoders(e.available);
    }).catch(() => {});
  }, []);

  // Applique un réglage et le persiste côté backend (par compte).
  const pushSt = (patch: any) =>
    setSt((prev: any) => { const next = { ...prev, ...patch };
      call("set_stream_settings", next).catch(() => {}); return next; });

  // Tant qu'on est en live, surveille que ffmpeg n'a pas planté (reflète l'arrêt).
  useEffect(() => {
    if (!streaming) return;
    const id = setInterval(async () => {
      try {
        const r: any = await call("get_stream_status");
        if (!r?.streaming) {
          setStreaming(false); setStreamMsg("⏹️ Live arrêté");
          setMicActive(false); setMicMuted(false);
        } else {
          setMicActive(!!r?.mic); setMicMuted(!!r?.mic_muted);
        }
      } catch { /* on continue */ }
    }, 4000);
    return () => clearInterval(id);
  }, [streaming]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleLive = async () => {
    setStreamBusy(true); setStreamMsg("");
    try {
      if (streaming) {
        await call("stop_stream"); setStreaming(false);
        setMicActive(false); setMicMuted(false);
      } else {
        // Catégorie Twitch auto = jeu en cours (Steam OU raccourci non-Steam).
        try {
          const gn = (Router as any)?.MainRunningApp?.display_name;
          if (gn) { setGameName(gn); await call<[string], any>("set_game", gn); }
        } catch { /* pas de jeu détecté → on garde la catégorie précédente */ }
        const r: any = await call("start_stream");
        if (r?.ok) {
          setStreaming(true); setStreamMsg("");
          setMicActive(!!st.mic); setMicMuted(false);
        }
        else setStreamMsg(
          r?.error === "no_key" ? "⚠️ Clé introuvable — reconnecte-toi à Twitch"
          : r?.error === "no_loopback" ? "⚠️ /dev/video42 absent (v4l2loopback non chargé)"
          : "⚠️ " + (r?.error || "échec du live"));
      }
    } finally { setStreamBusy(false); }
  };

  // Coupe/rétablit le micro sur le stream (n'affecte pas le vocal Discord).
  const toggleMicMute = async () => {
    const next = !micMuted;
    setMicMuted(next);                        // optimiste
    try {
      const r: any = await call<[boolean], any>("set_mic_mute", next);
      if (typeof r?.muted === "boolean") setMicMuted(r.muted);
    } catch { setMicMuted(!next); }           // rollback si échec
  };

  // Poll le backend tant qu'on attend l'autorisation Twitch (device flow).
  useEffect(() => {
    if (!authing) return;
    const id = setInterval(async () => {
      try {
        const r: any = await call("auth_poll");
        if (r?.status === "ok") {
          setAuthing(false); setAuthCode(""); setAuthMsg("✓ Connecté");
          refresh();
        } else if (["expired", "denied", "error"].includes(r?.status)) {
          setAuthing(false); setAuthCode("");
          setAuthMsg(r.status === "expired" ? "⏱️ Code expiré, réessaie"
                   : r.status === "denied" ? "❌ Autorisation refusée" : "⚠️ Erreur");
        }
      } catch { /* on continue à poller */ }
    }, 5000);
    return () => clearInterval(id);
  }, [authing]); // eslint-disable-line react-hooks/exhaustive-deps

  const startAuth = async () => {
    setAuthBusy(true); setAuthMsg("");
    try {
      const r: any = await call("auth_start");
      if (r?.ok) { setAuthCode(r.user_code || ""); setAuthing(true); }
      else setAuthMsg("⚠️ " + (r?.error || "erreur"));
    } finally { setAuthBusy(false); }
  };
  const saveTitle = () =>
    call<[string], any>("set_title", titleInput)
      .then(() => { setTitle(titleInput); setTitleInput(""); refresh(); }).catch(() => {});
  const doLogout = () => call("logout").then(refresh).catch(() => {});

  return (
    <PanelSection title="📡 Twitch">
      {loggedIn ? (
        <>
          <PanelSectionRow>
            <div style={{ display: "flex", alignItems: "center", gap: 8, width: "100%" }}>
              <span style={{ color: TWITCH, fontWeight: 700, fontSize: 13 }}>
                🟣 {login ? "@" + login : "Connecté"}
              </span>
              <B style={{ marginLeft: "auto", minWidth: 0, padding: "4px 10px", borderRadius: 6, color: "#fff", ...focusHalo(DANGER, logoutFocus) }}
                onFocus={() => setLogoutFocus(true)} onBlur={() => setLogoutFocus(false)}
                onGamepadFocus={() => setLogoutFocus(true)} onGamepadBlur={() => setLogoutFocus(false)}
                onClick={doLogout}>Déconnexion</B>
            </div>
          </PanelSectionRow>
          <PanelSectionRow>
            <TextField label="Titre du stream" value={titleInput}
              placeholder={title || "Titre de ton live (modifiable en direct)"}
              onChange={(e: any) => setTitleInput(e?.target?.value ?? "")} />
          </PanelSectionRow>
          <PanelSectionRow>
            <B disabled={!titleInput} style={{ width: "100%", borderRadius: 6, color: "#fff", ...focusHalo(TWITCH, titleFocus) }}
              onFocus={() => setTitleFocus(true)} onBlur={() => setTitleFocus(false)}
              onGamepadFocus={() => setTitleFocus(true)} onGamepadBlur={() => setTitleFocus(false)}
              onClick={saveTitle}>💾 Enregistrer le titre</B>
          </PanelSectionRow>
          <PanelSectionRow>
            <div style={{ fontSize: 11, opacity: 0.75, color: "#fff" }}>
              🎮 Catégorie auto = jeu en cours{gameName ? ` : ${gameName}` : " (détecté au passage en live)"}
            </div>
          </PanelSectionRow>
          <PanelSectionRow>
            <B disabled={streamBusy || !keySet}
              style={{ width: "100%", borderRadius: 6, color: "#fff", fontWeight: 700,
                background: streaming ? DANGER : TWITCH,
                ...focusHalo(streaming ? DANGER : TWITCH, liveFocus) }}
              onFocus={() => setLiveFocus(true)} onBlur={() => setLiveFocus(false)}
              onGamepadFocus={() => setLiveFocus(true)} onGamepadBlur={() => setLiveFocus(false)}
              onClick={toggleLive}>
              {streamBusy ? "…" : streaming ? "⏹️ Arrêter le live" : "🔴 Passer en live"}
            </B>
          </PanelSectionRow>
          {streaming && (
            <PanelSectionRow>
              <div style={{ fontSize: 12, fontWeight: 800, color: DANGER, textAlign: "center" }}>
                ● EN DIRECT sur Twitch
              </div>
            </PanelSectionRow>
          )}
          {streaming && micActive && (
            <PanelSectionRow>
              <B style={{ width: "100%", borderRadius: 6, color: "#fff", fontWeight: 700,
                background: micMuted ? DANGER : "transparent",
                ...focusHalo(micMuted ? DANGER : TWITCH, micFocus) }}
                onFocus={() => setMicFocus(true)} onBlur={() => setMicFocus(false)}
                onGamepadFocus={() => setMicFocus(true)} onGamepadBlur={() => setMicFocus(false)}
                onClick={toggleMicMute}>
                {micMuted ? "🔇 Micro coupé (cliquer pour rétablir)" : "🎙️ Couper le micro"}
              </B>
            </PanelSectionRow>
          )}
          {streamMsg && <PanelSectionRow><div style={{ fontSize: 11, color: "#fff" }}>{streamMsg}</div></PanelSectionRow>}
          {!keySet && (
            <PanelSectionRow>
              <div style={{ fontSize: 11, opacity: 0.6, color: "#fff" }}>
                🔑 Récupération de la clé de stream…
              </div>
            </PanelSectionRow>
          )}
          <PanelSectionRow>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#fff", opacity: 0.85, marginTop: 4 }}>
              ⚙️ Réglages du stream
            </div>
          </PanelSectionRow>
              <PanelSectionRow>
                <Dropdown strDefaultLabel="Résolution" selectedOption={st.resolution}
                  rgOptions={[
                    { data: "720p", label: "720p (1280×720)" },
                    { data: "800p", label: "800p (1280×800)" },
                    { data: "1080p", label: "1080p (1920×1080)" },
                    { data: "source", label: "Source (sans mise à l'échelle)" },
                  ]} onChange={(e: any) => pushSt({ resolution: e.data })} />
              </PanelSectionRow>
              <PanelSectionRow>
                <Dropdown strDefaultLabel="Images/s" selectedOption={st.fps}
                  rgOptions={[{ data: 30, label: "30 fps" }, { data: 60, label: "60 fps" }]}
                  onChange={(e: any) => pushSt({ fps: e.data })} />
              </PanelSectionRow>
              <PanelSectionRow>
                <SliderField label={`Débit vidéo ${st.bitrate} kbps`} value={st.bitrate}
                  min={1500} max={8000} step={250} showValue={false}
                  onChange={(v: number) => pushSt({ bitrate: v })} bottomSeparator="none" />
              </PanelSectionRow>
              <PanelSectionRow>
                <SliderField label={`Débit audio ${st.audio_bitrate} kbps`} value={st.audio_bitrate}
                  min={96} max={320} step={16} showValue={false}
                  onChange={(v: number) => pushSt({ audio_bitrate: v })} bottomSeparator="none" />
              </PanelSectionRow>
              <PanelSectionRow>
                <SliderField label={`Intervalle keyframe ${st.keyframe}s`} value={st.keyframe}
                  min={1} max={5} step={1} showValue={false}
                  onChange={(v: number) => pushSt({ keyframe: v })} bottomSeparator="none" />
              </PanelSectionRow>
              <PanelSectionRow>
                <Dropdown strDefaultLabel="Encodeur" selectedOption={st.encoder}
                  rgOptions={[
                    { data: "auto", label: "Auto (recommandé)" },
                    { data: "software", label: "Logiciel — x264 (universel)" },
                    ...(encoders.includes("nvenc")
                      ? [{ data: "nvenc", label: "Matériel — NVENC (Nvidia)" }] : []),
                    ...(encoders.includes("vaapi")
                      ? [{ data: "vaapi", label: "Matériel — VAAPI (AMD/Intel)" }] : []),
                  ]} onChange={(e: any) => pushSt({ encoder: e.data })} />
              </PanelSectionRow>
              <PanelSectionRow>
                <div style={{ fontSize: 10, opacity: 0.6, color: "#fff" }}>
                  {encoders.includes("nvenc")
                    ? "GPU Nvidia détecté : encodage matériel NVENC disponible."
                    : encoders.includes("vaapi")
                    ? "GPU compatible : encodage matériel VAAPI disponible."
                    : "Pas d'encodage matériel sur ce GPU → logiciel (x264)."}
                </div>
              </PanelSectionRow>
              <PanelSectionRow>
                <ToggleField label="🎙️ Ajouter le micro" checked={!!st.mic}
                  description="Mixe ton micro par défaut avec le son du jeu"
                  onChange={(v: boolean) => pushSt({ mic: v })} bottomSeparator="none" />
              </PanelSectionRow>
              {steamcord && (
                <PanelSectionRow>
                  <ToggleField label="💬 Ajouter le son Discord au stream"
                    checked={!!st.discord_audio}
                    description="Mixe la voix de ta conversation Discord (Steamcord) dans le live"
                    onChange={(v: boolean) => pushSt({ discord_audio: v })} bottomSeparator="none" />
                </PanelSectionRow>
              )}
        </>
      ) : (
        <>
          <PanelSectionRow>
            <div style={{ fontSize: 11, opacity: 0.75, color: "#fff", marginBottom: 4 }}>
              Connecte ton compte Twitch : clé récupérée automatiquement + titre & catégorie éditables.
            </div>
          </PanelSectionRow>
          <PanelSectionRow>
            <B disabled={authBusy || authing}
              style={{ width: "100%", borderRadius: 6, color: "#fff", background: TWITCH, ...focusHalo(TWITCH, loginFocus) }}
              onFocus={() => setLoginFocus(true)} onBlur={() => setLoginFocus(false)}
              onGamepadFocus={() => setLoginFocus(true)} onGamepadBlur={() => setLoginFocus(false)}
              onClick={startAuth}>
              🟣 {authing ? "En attente d'autorisation…" : authBusy ? "…" : "Se connecter à Twitch"}
            </B>
          </PanelSectionRow>
          {authCode && (
            <PanelSectionRow>
              <div style={{ fontSize: 12, color: "#fff", lineHeight: 1.6, border: `1px solid ${TWITCH}`, borderRadius: 8, padding: 10, textAlign: "center" }}>
                Va sur <span style={{ color: TWITCH, fontWeight: 700 }}>twitch.tv/activate</span> et entre :
                <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: 4, marginTop: 4 }}>{authCode}</div>
              </div>
            </PanelSectionRow>
          )}
          {authMsg && <PanelSectionRow><div style={{ fontSize: 11, color: "#fff" }}>{authMsg}</div></PanelSectionRow>}
        </>
      )}
    </PanelSection>
  );
}

// ── Section overlay chat ──────────────────────────────────────────────────────
function OverlaySection() {
  const [channelInput, setChannelInput] = useState("");
  const [channelSet, setChannelSet] = useState("");
  const [chFocus, setChFocus] = useState(false);
  const [overlayOn, setOverlayOn] = useState(false);
  const [ov, setOv] = useState<any>({ opacity: 62, fontSize: 13, width: 360, height: 460, pos: "tr", badges: true, thirdParty: true });

  const refresh = () =>
    call<[], any>("get_config").then((c: any) => {
      if (typeof c?.channel === "string") setChannelSet(c.channel);
      setOverlayOn(!!c?.overlay_on);
      if (c?.overlay) setOv((p: any) => ({ ...p, ...c.overlay }));
    }).catch(() => {});
  useEffect(() => { refresh(); }, []);

  const pushOv = (patch: any) =>
    setOv((prev: any) => { const next = { ...prev, ...patch }; call("set_overlay_settings", next).catch(() => {}); return next; });
  const toggleOverlay = async (v: boolean) => {
    setOverlayOn(v);
    try { await call(v ? "start_overlay" : "stop_overlay"); } catch { /* noop */ }
    refresh();
  };

  return (
    <PanelSection title="💬 Overlay chat">
      <PanelSectionRow>
        <div style={{ fontSize: 11, opacity: 0.75, color: "#fff" }}>
          {channelSet ? `Chaîne : ${channelSet} (auto depuis ton compte)` : "Connecte-toi à Twitch, ou saisis une chaîne ci-dessous."}
        </div>
      </PanelSectionRow>
      <PanelSectionRow>
        <TextField label="Regarder une autre chaîne (optionnel)" value={channelInput}
          placeholder={channelSet || "ton_pseudo_twitch"}
          onChange={(e: any) => setChannelInput(e?.target?.value ?? "")} />
      </PanelSectionRow>
      <PanelSectionRow>
        <B disabled={!channelInput}
          style={{ width: "100%", borderRadius: 6, color: "#fff", ...focusHalo(TWITCH, chFocus) }}
          onFocus={() => setChFocus(true)} onBlur={() => setChFocus(false)}
          onGamepadFocus={() => setChFocus(true)} onGamepadBlur={() => setChFocus(false)}
          onClick={() => call<[string], any>("set_channel", channelInput)
            .then(() => { setChannelInput(""); refresh(); }).catch(() => {})}>
          💾 Utiliser cette chaîne
        </B>
      </PanelSectionRow>
      <PanelSectionRow>
        <ToggleField label="Afficher l'overlay chat"
          description={channelSet ? "Fenêtre transparente par-dessus le jeu (mode jeu) ou le bureau" : "Renseigne d'abord ta chaîne"}
          checked={overlayOn} onChange={toggleOverlay} disabled={!channelSet} bottomSeparator="none" />
      </PanelSectionRow>
      {overlayOn && (
        <>
          <PanelSectionRow>
            <SliderField label={`Opacité ${ov.opacity}%`} value={ov.opacity}
              min={10} max={95} step={5} showValue={false}
              onChange={(v: number) => pushOv({ opacity: v })} bottomSeparator="none" />
          </PanelSectionRow>
          <PanelSectionRow>
            <SliderField label={`Taille du texte ${ov.fontSize}px`} value={ov.fontSize}
              min={10} max={22} step={1} showValue={false}
              onChange={(v: number) => pushOv({ fontSize: v })} bottomSeparator="none" />
          </PanelSectionRow>
          <PanelSectionRow>
            <SliderField label={`Largeur ${ov.width}px`} value={ov.width}
              min={240} max={640} step={10} showValue={false}
              onChange={(v: number) => pushOv({ width: v })} bottomSeparator="none" />
          </PanelSectionRow>
          <PanelSectionRow>
            <SliderField label={`Hauteur ${ov.height}px`} value={ov.height}
              min={200} max={900} step={20} showValue={false}
              onChange={(v: number) => pushOv({ height: v })} bottomSeparator="none" />
          </PanelSectionRow>
          <PanelSectionRow>
            <Dropdown rgOptions={[
              { data: "tl", label: "↖ Haut-gauche" }, { data: "tr", label: "↗ Haut-droite" },
              { data: "bl", label: "↙ Bas-gauche" }, { data: "br", label: "↘ Bas-droite" },
            ]} selectedOption={ov.pos} onChange={(e: any) => pushOv({ pos: e.data })}
              strDefaultLabel="Position" />
          </PanelSectionRow>
          <PanelSectionRow>
            <ToggleField label="Afficher les badges" checked={!!ov.badges}
              onChange={(v: boolean) => pushOv({ badges: v })} bottomSeparator="none" />
          </PanelSectionRow>
          <PanelSectionRow>
            <ToggleField label="Emotes BTTV / 7TV / FFZ" checked={!!ov.thirdParty}
              onChange={(v: boolean) => pushOv({ thirdParty: v })} bottomSeparator="none" />
          </PanelSectionRow>
        </>
      )}
    </PanelSection>
  );
}

function Content() {
  return (
    <>
      <StreamSection />
      <OverlaySection />
    </>
  );
}

export default definePlugin(() => ({
  name: "BoneCast",
  title: <div className={staticClasses.Title}>BoneCast</div>,
  icon: <FaTwitch />,
  content: <Content />,
}));
