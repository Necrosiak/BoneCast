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
  Focusable,
  Router,
} from "@decky/ui";
import { definePlugin, call } from "@decky/api";
import { FaTwitch } from "react-icons/fa";
import {
  IcBroadcast, IcChat, IcController, IcFilm, IcGithub, IcKey,
  IcLogout, IcMic, IcMicMute, IcRefresh, IcSave, IcSend,
} from "./components/Icons";
import { focusHalo, ActionCard, TWITCH, DANGER } from "./components/Styled";
import { t } from "./i18n";

const B = DialogButton as any;
const EyeIcon = () => <svg viewBox="0 0 24 24" width="13" height="13" fill="none"
  stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
  aria-hidden="true"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z" /><circle cx="12" cy="12" r="2.5" /></svg>;

// Onglet de navigation (même idiome que Steamcord : texte blanc forcé + fond
// piloté nous-mêmes, sinon le focus natif du DialogButton peint un fond clair
// sous notre texte blanc = illisible).
const TabBtn = ({ active, focused, onClick, onFocus, onBlur, children }: any) => (
  <B
    onClick={onClick}
    onFocus={onFocus} onBlur={onBlur}
    onGamepadFocus={onFocus} onGamepadBlur={onBlur}
    style={{
      flex: "1 1 0", minWidth: 0, margin: 0, padding: "4px 0",
      fontSize: 12, minHeight: 0, boxSizing: "border-box",
      color: "#fff",
      background: focused
        ? "rgba(145,70,255,0.85)"
        : active ? "rgba(145,70,255,0.35)" : "rgba(255,255,255,0.06)",
      fontWeight: active ? 700 : 400,
      ...focusHalo(TWITCH, focused),
    }}
  >
    {children}
  </B>
);

// ── Onglet LIVE : login OAuth + titre + go live + BRB/clip/micro ─────────────
function LiveSection() {
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
  const [stMic, setStMic] = useState(false);   // réglage « micro dans le stream »

  const [brb, setBrb] = useState(false);
  const [brbBusy, setBrbBusy] = useState(false);
  const [clipBusy, setClipBusy] = useState(false);
  const [recOnly, setRecOnly] = useState(false);

  const refresh = () =>
    call<[], any>("get_config").then((c: any) => {
      setLoggedIn(!!c?.logged_in); setLogin(c?.login || "");
      setKeySet(!!c?.key_set);
      setStreaming(!!c?.streaming);
      if (typeof c?.title === "string") setTitle(c.title);
      if (typeof c?.game_name === "string") setGameName(c.game_name);
      setStMic(!!c?.stream?.mic);
    }).catch(() => {});

  useEffect(() => { refresh(); }, []);

  // Tant qu'on est en live, surveille que ffmpeg n'a pas planté (reflète l'arrêt).
  useEffect(() => {
    if (!streaming) return;
    const id = setInterval(async () => {
      try {
        const r: any = await call("get_stream_status");
        if (!r?.streaming) {
          setStreaming(false); setStreamMsg(t("live_stopped"));
          setMicActive(false); setMicMuted(false); setBrb(false); setRecOnly(false);
        } else {
          setMicActive(!!r?.mic); setMicMuted(!!r?.mic_muted);
          setBrb(!!r?.brb); setRecOnly(!!r?.record_only);
        }
      } catch { /* on continue */ }
    }, 4000);
    return () => clearInterval(id);
  }, [streaming]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleLive = async () => {
    setStreamBusy(true); setStreamMsg("");
    try {
      if (streaming) {
        const r: any = await call("stop_stream"); setStreaming(false); setLiveSource("bonecast", false);
        setMicActive(false); setMicMuted(false); setBrb(false); setRecOnly(false);
        if (r?.record_path) setStreamMsg(t("recorded_to") + r.record_path);
      } else {
        // Catégorie Twitch auto = jeu en cours (Steam OU raccourci non-Steam).
        try {
          const gn = (Router as any)?.MainRunningApp?.display_name;
          if (gn) { setGameName(gn); await call<[string], any>("set_game", gn); }
        } catch { /* pas de jeu détecté → on garde la catégorie précédente */ }
        const r: any = await call("start_stream");
        if (r?.ok) {
          setStreaming(true); setStreamMsg("");
          setMicActive(stMic); setMicMuted(false);
        }
        else setStreamMsg(
          r?.error === "no_key" ? t("err_no_key")
          // stand-alone : le backend fournit la commande exacte pour CET OS
          : r?.error === "no_loopback" ? "⚠️ " + (r?.hint || t("hint_no_loopback"))
          : r?.error === "no_ffmpeg" ? "⚠️ " + (r?.hint || t("hint_no_ffmpeg"))
          : r?.error === "no_x264" ? "⚠️ " + (r?.hint || t("hint_no_x264"))
          : r?.error === "no_gst" ? "⚠️ " + (r?.hint || t("hint_no_gst"))
          : "⚠️ " + (r?.hint || r?.error || t("err_live_failed")));
      }
    } finally { setStreamBusy(false); }
  };

  // Enregistrement local SANS passer en live (mkv dans Vidéos/BoneCast).
  const startRecordOnly = async () => {
    setStreamBusy(true); setStreamMsg("");
    try {
      const r: any = await call<[boolean], any>("start_stream", true);
      if (r?.ok) { setStreaming(true); setRecOnly(true); setMicActive(stMic); }
      else setStreamMsg("⚠️ " + (r?.hint || r?.error || t("err_record_failed")));
    } finally { setStreamBusy(false); }
  };

  // BRB : écran pause à l'antenne (le live continue, micro auto-coupé).
  const toggleBrb = async () => {
    setBrbBusy(true);
    try {
      const r: any = await call(brb ? "brb_stop" : "brb_start");
      if (r?.ok) setBrb(!brb);
    } finally { setBrbBusy(false); }
  };

  // Clip des ~30 dernières secondes (Twitch met ~15 s à le publier).
  const doClip = async () => {
    setClipBusy(true);
    try {
      const r: any = await call("create_clip");
      setStreamMsg(r?.ok ? t("clip_created")
        : r?.error === "missing_scope" ? t("reconnect_scopes")
        : r?.error === "not_live" ? t("clip_not_live")
        : "⚠️ " + (r?.error || t("err_clip_failed")));
    } finally { setClipBusy(false); }
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
          setAuthing(false); setAuthCode(""); setAuthMsg(t("auth_connected"));
          refresh();
        } else if (["expired", "denied", "error"].includes(r?.status)) {
          setAuthing(false); setAuthCode("");
          setAuthMsg(r.status === "expired" ? t("auth_expired")
                   : r.status === "denied" ? t("auth_denied") : t("auth_error"));
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
      else setAuthMsg("⚠️ " + (r?.error || t("err_generic")));
    } finally { setAuthBusy(false); }
  };
  const saveTitle = () =>
    call<[string], any>("set_title", titleInput)
      .then(() => { setTitle(titleInput); setTitleInput(""); refresh(); }).catch(() => {});

  if (!loggedIn) {
    return (
      <PanelSection title={t("twitch_title")}>
        <PanelSectionRow>
          <div style={{ fontSize: 11, opacity: 0.75, color: "#fff", marginBottom: 4 }}>
            {t("login_intro")}
          </div>
        </PanelSectionRow>
        <PanelSectionRow>
          <ActionCard color={TWITCH} active disabled={authBusy || authing} onClick={startAuth}>
            <FaTwitch style={{ verticalAlign: "-0.125em" }} /> {authing ? t("login_waiting") : authBusy ? "…" : t("login_button")}
          </ActionCard>
        </PanelSectionRow>
        {authCode && (
          <PanelSectionRow>
            <div style={{ fontSize: 12, color: "#fff", lineHeight: 1.6, border: `1px solid ${TWITCH}`, borderRadius: 8, padding: 10, textAlign: "center" }}>
              {t("go_to")} <span style={{ color: TWITCH, fontWeight: 700 }}>twitch.tv/activate</span> {t("and_enter")}
              <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: 4, marginTop: 4 }}>{authCode}</div>
            </div>
          </PanelSectionRow>
        )}
        {authMsg && <PanelSectionRow><div style={{ fontSize: 11, color: "#fff" }}>{authMsg}</div></PanelSectionRow>}
      </PanelSection>
    );
  }

  return (
    <PanelSection title={t("live_title")}>
      <PanelSectionRow>
        <div style={{ fontSize: 13, color: TWITCH, fontWeight: 700 }}>
          <FaTwitch style={{ verticalAlign: "-0.125em" }} /> {login ? "@" + login : t("connected")}
        </div>
      </PanelSectionRow>
      <PanelSectionRow>
        <TextField label={t("title_label")} value={titleInput}
          placeholder={title || t("title_placeholder")}
          onChange={(e: any) => setTitleInput(e?.target?.value ?? "")} />
      </PanelSectionRow>
      <PanelSectionRow>
        <ActionCard color={TWITCH} disabled={!titleInput} onClick={saveTitle}>
          <IcSave /> {t("save_title")}
        </ActionCard>
      </PanelSectionRow>
      <PanelSectionRow>
        <div style={{ fontSize: 11, opacity: 0.75, color: "#fff" }}>
          <IcController /> {t("category_auto")}{gameName ? ` : ${gameName}` : " " + t("category_detect")}
        </div>
      </PanelSectionRow>
      <PanelSectionRow>
        <ActionCard color={streaming ? DANGER : TWITCH} active big
          disabled={streamBusy || !keySet} onClick={toggleLive}>
          {streamBusy ? "…" : <><IcBroadcast /> {streaming ? t("stop_live") : t("go_live")}</>}
        </ActionCard>
      </PanelSectionRow>
      {!streaming && (
        <PanelSectionRow>
          <ActionCard color={TWITCH} disabled={streamBusy} onClick={startRecordOnly}>
            {t("record_only_btn")}
          </ActionCard>
        </PanelSectionRow>
      )}
      {streaming && (
        <PanelSectionRow>
          <div style={{ fontSize: 12, fontWeight: 800, color: DANGER, textAlign: "center" }}>
            {recOnly ? t("status_rec")
             : brb ? t("status_brb")
             : t("status_live")}
          </div>
        </PanelSectionRow>
      )}
      {streaming && (
        <PanelSectionRow>
          <Focusable flow-children="row" style={{ display: "flex", gap: 6, width: "100%" }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <ActionCard color={brb ? DANGER : TWITCH} active={brb}
                disabled={brbBusy} onClick={toggleBrb}>
                {brb ? t("brb_back") : t("brb_pause")}
              </ActionCard>
            </div>
            {!recOnly && (
              <div style={{ flex: 1, minWidth: 0 }}>
                <ActionCard color={TWITCH} disabled={clipBusy} onClick={doClip}>
                  {clipBusy ? "…" : <><IcFilm /> {t("clip_btn")}</>}
                </ActionCard>
              </div>
            )}
          </Focusable>
        </PanelSectionRow>
      )}
      {streaming && micActive && (
        <PanelSectionRow>
          <ActionCard color={micMuted ? DANGER : TWITCH} active={micMuted} onClick={toggleMicMute}>
            {micMuted ? <><IcMicMute /> {t("mic_muted_btn")}</> : <><IcMic /> {t("mic_mute_btn")}</>}
          </ActionCard>
        </PanelSectionRow>
      )}
      {streamMsg && <PanelSectionRow><div style={{ fontSize: 11, color: "#fff", wordBreak: "break-word" }}>{streamMsg}</div></PanelSectionRow>}
      {!keySet && (
        <PanelSectionRow>
          <div style={{ fontSize: 11, opacity: 0.6, color: "#fff" }}>
            <IcKey /> {t("key_fetching")}
          </div>
        </PanelSectionRow>
      )}
    </PanelSection>
  );
}

// ── Onglet CHAT : overlay + écrire dans son chat ─────────────────────────────
function ChatSection() {
  const [channelInput, setChannelInput] = useState("");
  const [channelSet, setChannelSet] = useState("");
  const [overlayOn, setOverlayOn] = useState(false);
  const [ov, setOv] = useState<any>({ opacity: 62, fontSize: 13, width: 360, height: 460, pos: "tr", badges: true, thirdParty: true });
  const [chatInput, setChatInput] = useState("");
  const [chatMsg, setChatMsg] = useState("");
  const [chatBusy, setChatBusy] = useState(false);

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

  // Message dans SON chat Twitch (Helix — nécessite le scope user:write:chat).
  const sendChat = async () => {
    if (!chatInput.trim()) return;
    setChatBusy(true); setChatMsg("");
    try {
      const r: any = await call<[string], any>("send_chat", chatInput);
      if (r?.ok) { setChatInput(""); setChatMsg(t("sent")); }
      else setChatMsg(r?.error === "missing_scope"
        ? t("reconnect_scopes")
        : "⚠️ " + (r?.error || t("err_send_failed")));
    } finally { setChatBusy(false); }
  };

  return (
    <>
      <PanelSection title={t("chat_write_title")}>
        <PanelSectionRow>
          <TextField label={t("message_label")} value={chatInput}
            placeholder={t("chat_placeholder")}
            onChange={(e: any) => setChatInput(e?.target?.value ?? "")} />
        </PanelSectionRow>
        <PanelSectionRow>
          <ActionCard color={TWITCH} disabled={chatBusy || !chatInput.trim()} onClick={sendChat}>
            {chatBusy ? "…" : <><IcSend /> {t("send")}</>}
          </ActionCard>
        </PanelSectionRow>
        {chatMsg && <PanelSectionRow><div style={{ fontSize: 11, color: "#fff" }}>{chatMsg}</div></PanelSectionRow>}
      </PanelSection>
      <PanelSection title={t("overlay_title")}>
        <PanelSectionRow>
          <div style={{ fontSize: 11, opacity: 0.75, color: "#fff" }}>
            {channelSet ? t("channel_current", { ch: channelSet }) : t("channel_none")}
          </div>
        </PanelSectionRow>
        <PanelSectionRow>
          <TextField label={t("channel_other_label")} value={channelInput}
            placeholder={channelSet || t("channel_placeholder")}
            onChange={(e: any) => setChannelInput(e?.target?.value ?? "")} />
        </PanelSectionRow>
        <PanelSectionRow>
          <ActionCard color={TWITCH} disabled={!channelInput}
            onClick={() => call<[string], any>("set_channel", channelInput)
              .then(() => { setChannelInput(""); refresh(); }).catch(() => {})}>
            <IcSave /> {t("channel_use")}
          </ActionCard>
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField label={t("overlay_show")}
            description={channelSet ? t("overlay_desc") : t("overlay_need_channel")}
            checked={overlayOn} onChange={toggleOverlay} disabled={!channelSet} bottomSeparator="none" />
        </PanelSectionRow>
        {overlayOn && (
          <>
            <PanelSectionRow>
              <SliderField label={t("opacity", { v: ov.opacity })} value={ov.opacity}
                min={10} max={95} step={5} showValue={false}
                onChange={(v: number) => pushOv({ opacity: v })} bottomSeparator="none" />
            </PanelSectionRow>
            <PanelSectionRow>
              <SliderField label={t("font_size", { v: ov.fontSize })} value={ov.fontSize}
                min={10} max={22} step={1} showValue={false}
                onChange={(v: number) => pushOv({ fontSize: v })} bottomSeparator="none" />
            </PanelSectionRow>
            <PanelSectionRow>
              <SliderField label={t("width", { v: ov.width })} value={ov.width}
                min={240} max={640} step={10} showValue={false}
                onChange={(v: number) => pushOv({ width: v })} bottomSeparator="none" />
            </PanelSectionRow>
            <PanelSectionRow>
              <SliderField label={t("height", { v: ov.height })} value={ov.height}
                min={200} max={900} step={20} showValue={false}
                onChange={(v: number) => pushOv({ height: v })} bottomSeparator="none" />
            </PanelSectionRow>
            <PanelSectionRow>
              <Dropdown rgOptions={[
                { data: "tl", label: t("pos_tl") }, { data: "tr", label: t("pos_tr") },
                { data: "bl", label: t("pos_bl") }, { data: "br", label: t("pos_br") },
              ]} selectedOption={ov.pos} onChange={(e: any) => pushOv({ pos: e.data })}
                strDefaultLabel={t("position")} />
            </PanelSectionRow>
            <PanelSectionRow>
              <ToggleField label={t("show_badges")} checked={!!ov.badges}
                onChange={(v: boolean) => pushOv({ badges: v })} bottomSeparator="none" />
            </PanelSectionRow>
            <PanelSectionRow>
              <ToggleField label={t("third_party_emotes")} checked={!!ov.thirdParty}
                onChange={(v: boolean) => pushOv({ thirdParty: v })} bottomSeparator="none" />
            </PanelSectionRow>
          </>
        )}
      </PanelSection>
    </>
  );
}

// ── Onglet CONFIG : réglages stream + mises à jour + à propos + déconnexion ──
function StreamSettings() {
  const [encoders, setEncoders] = useState<string[]>(["software"]);
  const [steamcord, setSteamcord] = useState(false);
  const [st, setSt] = useState<any>({ resolution: "720p", fps: 30, bitrate: 4500,
    audio_bitrate: 160, keyframe: 2, encoder: "auto", mic: false, record: false });

  useEffect(() => {
    call<[], any>("get_config").then((c: any) => {
      if (c?.stream) setSt((p: any) => ({ ...p, ...c.stream }));
      setSteamcord(!!c?.steamcord);
    }).catch(() => {});
    call<[], any>("get_encoders").then((e: any) => {
      if (Array.isArray(e?.available)) setEncoders(e.available);
    }).catch(() => {});
  }, []);

  // Applique un réglage et le persiste côté backend (par compte).
  const pushSt = (patch: any) =>
    setSt((prev: any) => { const next = { ...prev, ...patch };
      call("set_stream_settings", next).catch(() => {}); return next; });

  return (
    <PanelSection title={t("quality_title")}>
      <PanelSectionRow>
        <Dropdown strDefaultLabel={t("resolution")} selectedOption={st.resolution}
          rgOptions={[
            { data: "720p", label: "720p (1280×720)" },
            { data: "800p", label: "800p (1280×800)" },
            { data: "1080p", label: "1080p (1920×1080)" },
            { data: "source", label: t("res_source") },
          ]} onChange={(e: any) => pushSt({ resolution: e.data })} />
      </PanelSectionRow>
      <PanelSectionRow>
        <Dropdown strDefaultLabel={t("fps_label")} selectedOption={st.fps}
          rgOptions={[{ data: 30, label: "30 fps" }, { data: 60, label: "60 fps" }]}
          onChange={(e: any) => pushSt({ fps: e.data })} />
      </PanelSectionRow>
      <PanelSectionRow>
        <SliderField label={t("video_bitrate", { v: st.bitrate })} value={st.bitrate}
          min={1500} max={8000} step={250} showValue={false}
          onChange={(v: number) => pushSt({ bitrate: v })} bottomSeparator="none" />
      </PanelSectionRow>
      <PanelSectionRow>
        <SliderField label={t("audio_bitrate", { v: st.audio_bitrate })} value={st.audio_bitrate}
          min={96} max={320} step={16} showValue={false}
          onChange={(v: number) => pushSt({ audio_bitrate: v })} bottomSeparator="none" />
      </PanelSectionRow>
      <PanelSectionRow>
        <SliderField label={t("keyframe_interval", { v: st.keyframe })} value={st.keyframe}
          min={1} max={5} step={1} showValue={false}
          onChange={(v: number) => pushSt({ keyframe: v })} bottomSeparator="none" />
      </PanelSectionRow>
      <PanelSectionRow>
        <Dropdown strDefaultLabel={t("encoder")} selectedOption={st.encoder}
          rgOptions={[
            { data: "auto", label: t("enc_auto") },
            { data: "software", label: t("enc_software") },
            ...(encoders.includes("nvenc")
              ? [{ data: "nvenc", label: t("enc_nvenc") }] : []),
            ...(encoders.includes("vaapi")
              ? [{ data: "vaapi", label: t("enc_vaapi") }] : []),
          ]} onChange={(e: any) => pushSt({ encoder: e.data })} />
      </PanelSectionRow>
      <PanelSectionRow>
        <div style={{ fontSize: 10, opacity: 0.6, color: "#fff" }}>
          {encoders.includes("nvenc")
            ? t("gpu_nvenc")
            : encoders.includes("vaapi")
            ? t("gpu_vaapi")
            : t("gpu_software")}
        </div>
      </PanelSectionRow>
      <PanelSectionRow>
        <ToggleField label={t("mic_add")} checked={!!st.mic}
          description={t("mic_add_desc")}
          onChange={(v: boolean) => pushSt({ mic: v })} bottomSeparator="none" />
      </PanelSectionRow>
      {steamcord && (
        <PanelSectionRow>
          <ToggleField label={t("discord_audio")}
            checked={!!st.discord_audio}
            description={t("discord_audio_desc")}
            onChange={(v: boolean) => pushSt({ discord_audio: v })} bottomSeparator="none" />
        </PanelSectionRow>
      )}
      <PanelSectionRow>
        <ToggleField label={t("record_toggle")}
          checked={!!st.record}
          description={t("record_desc")}
          onChange={(v: boolean) => pushSt({ record: v })} bottomSeparator="none" />
      </PanelSectionRow>
    </PanelSection>
  );
}

// Auto-update basé sur les releases GitHub (comme le reste de la suite).
function UpdaterSection() {
  const [auto, setAuto] = useState(true);
  const [status, setStatus] = useState<
    "idle" | "checking" | "available" | "uptodate" | "installing" | "failed" | "needsrestart">("idle");
  const [updErr, setUpdErr] = useState("");
  const [latest, setLatest] = useState("");
  const [current, setCurrent] = useState("");
  const [url, setUrl] = useState("");

  useEffect(() => {
    call<[], boolean>("get_autoupdate").then((v) => setAuto(!!v)).catch(() => {});
    call<[], string>("get_version").then((v) => setCurrent(v || "")).catch(() => {});
  }, []);

  const doCheck = async () => {
    setStatus("checking");
    try {
      const info: any = await call<[], any>("check_update");
      setCurrent(info?.current || "");
      if (info?.update_available) {
        setLatest(info.latest); setUrl(info.url); setStatus("available");
      } else setStatus("uptodate");
    } catch { setStatus("idle"); }
  };
  const doInstall = async () => {
    setStatus("installing");                    // le backend décompresse + recharge
    // Échec → {ok:false, error} : on l'affiche au lieu de rester sur « Installation… ».
    try {
      const r: any = await call<[string], any>("apply_update", url);
      if (!(r === true || r?.ok)) { setUpdErr(r?.error || ""); setStatus("failed"); return; }
      // Les fichiers sont écrits — mais rien n'est chargé pour autant : le
      // backend ne peut pas redémarrer plugin_loader (mesuré le 22/09 : les
      // bibliothèques du bundle PyInstaller du loader, léguées à nos backends,
      // empêchent `systemctl` de démarrer ; et sans elles, polkit refuse
      // l'unité système à un plugin non root). Le loader, LUI, est root : sa route interne
      // loader/reload_plugin arrête le backend, le réimporte depuis les
      // fichiers neufs et fait recharger dist/index.js au frontend. Ce n'est
      // PAS utilities/install_plugin, la route du Store, qui se perd sur un
      // 404 deckbrew et laisse une modale figée (13/09).
      const backend: any = (window as any).DeckyBackend;
      if (backend?.call) {
        try {
          await backend.call("loader/reload_plugin", "BoneCast");
            // Le panneau à l'écran n'est PAS remonté par le rechargement : Steam
            // garde l'arbre React déjà monté, et il restait donc figé sur
            // « Installation… » — vu à l'écran le 22/09, alors même que le
            // plugin venait d'être réimporté des deux côtés. C'est très
            // exactement le « je clique et il ne se passe rien » de #52, donc on
            // finit le parcours nous-mêmes. Le nouveau code sert dès la
            // prochaine ouverture du menu.
          setCurrent(latest);
          setStatus("uptodate");
          return;
        } catch { /* Decky trop ancien : route absente */ }
      }
      setStatus("needsrestart");
    } catch { setStatus("failed"); }
  };
  const onToggle = (v: boolean) => {
    setAuto(v); call<[boolean], boolean>("set_autoupdate", v).catch(() => {});
  };

  const label =
    status === "checking" ? t("upd_checking")
    : status === "installing" ? t("upd_installing")
    : status === "available" ? t("upd_install", { v: latest })
    : status === "uptodate" ? t("upd_uptodate", { v: current })
    : status === "failed" ? t("upd_failed")
    : status === "needsrestart" ? t("upd_needs_restart")
    : t("upd_check");

  return (
    <PanelSection title={t("updates_title")}>
      <PanelSectionRow>
        <ToggleField label={t("upd_auto")} checked={auto}
          description={t("upd_auto_desc")}
          onChange={onToggle} bottomSeparator="none" />
      </PanelSectionRow>
      <PanelSectionRow>
        <ActionCard color={TWITCH} onClick={status === "available" ? doInstall : doCheck}>
          <IcRefresh /> {label}
        </ActionCard>
      </PanelSectionRow>
      {status === "failed" && updErr ? (
        <PanelSectionRow>
          <div style={{ fontSize: 11, opacity: 0.8, wordBreak: "break-word" }}>{updErr}</div>
        </PanelSectionRow>
      ) : null}
    </PanelSection>
  );
}

// À propos + déconnexion Twitch (bas de l'onglet Config, comme Steamcord).
function AboutSection() {
  const [version, setVersion] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);
  const [login, setLogin] = useState("");
  useEffect(() => {
    call<[], string>("get_version").then((v) => setVersion(v || "")).catch(() => {});
    call<[], any>("get_config").then((c: any) => {
      setLoggedIn(!!c?.logged_in); setLogin(c?.login || "");
    }).catch(() => {});
  }, []);
  const open = (url: string) => { try { (window as any).SteamClient?.URL?.ExecuteSteamURL?.("steam://openurl/" + url); } catch {} };
  const doLogout = () => call("logout").then(() => setLoggedIn(false)).catch(() => {});
  return (
    <PanelSection title={t("about_title")}>
      <PanelSectionRow>
        <div style={{ fontSize: 11, color: "#aaa", lineHeight: 1.6 }}>
          <div><b style={{ color: "#fff" }}>BoneCast</b>{version ? ` v${version}` : ""} 🦴📡</div>
          <div>{t("by")} <span style={{ color: TWITCH }}>Necrosiak</span></div>
        </div>
      </PanelSectionRow>
      <PanelSectionRow>
        <ActionCard color={TWITCH} onClick={() => open("https://github.com/Necrosiak/BoneCast")}>
          <IcGithub /> GitHub
        </ActionCard>
      </PanelSectionRow>
      {loggedIn && (
        <PanelSectionRow>
          <ActionCard color={DANGER} onClick={doLogout}>
            <IcLogout /> {t("logout")}{login ? ` (@${login})` : ""}
          </ActionCard>
        </PanelSectionRow>
      )}
    </PanelSection>
  );
}

function ConfigSection() {
  return (
    <>
      <StreamSettings />
      <UpdaterSection />
      <AboutSection />
    </>
  );
}

// ── Onglet VISIONNAGE : lives Twitch au-dessus du jeu ───────────────────────
function WatchSection() {
  const [watch, setWatch] = useState<any>({ streams: [], layout: "corner_br", scale: 1,
    opacity: 0.5, max_fps: 30, audio: "", volume: 1 });
  const [input, setInput] = useState("");
  const [watching, setWatching] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [followed, setFollowed] = useState<any[]>([]);
  const [followedBusy, setFollowedBusy] = useState(true);
  const [followedError, setFollowedError] = useState("");

  const refreshFollowed = async () => {
    setFollowedBusy(true); setFollowedError("");
    try {
      const r: any = await call("get_followed_live");
      if (r?.ok) setFollowed(Array.isArray(r.streams) ? r.streams : []);
      else setFollowedError(r?.error === "missing_follow_scope" ? t("watch_followed_reconnect")
        : r?.error === "not_logged_in" ? t("watch_followed_login") : t("watch_followed_failed"));
    } catch { setFollowedError(t("watch_followed_failed")); }
    finally { setFollowedBusy(false); }
  };

  useEffect(() => {
    call<[], any>("get_config").then((c: any) => {
      if (c?.watch) setWatch((old: any) => ({ ...old, ...c.watch }));
      setInput(Array.isArray(c?.watch?.streams) ? c.watch.streams.join(", ") : "");
      setWatching(!!c?.watching);
    }).catch(() => {});
    refreshFollowed();
  }, []);

  const streamList = (value: string) => [...new Set(value.split(/[\s,]+/)
    .map((v) => v.trim().replace(/^@/, "").toLowerCase())
    .filter((v) => /^[a-z0-9_]{1,25}$/.test(v)))].slice(0, 4);
  const push = (patch: any) => setWatch((old: any) => {
    const next = { ...old, ...patch };
    call("set_watch_settings", next).catch(() => {});
    return next;
  });
  const saveStreams = async () => {
    const streams = streamList(input);
    const had = Array.isArray(watch.streams) && watch.streams.length > 0;
    const audio = streams.includes(watch.audio) ? watch.audio : !had && streams.length ? streams[0] : "";
    const next = { ...watch, streams, audio };
    setWatch(next);
    const r: any = await call("set_watch_settings", next);
    if (!r?.ok) setMsg("⚠️ " + (r?.error || t("watch_save_failed")));
    else setMsg(next.streams.length ? "" : t("watch_need_stream"));
    return r;
  };
  const playFollowed = async (login: string) => {
    const selected = streamList(input);
    const next = selected.includes(login)
      ? selected.filter((value) => value !== login)
      : selected.length < 4 ? [...selected, login] : selected;
    setInput(next.join(", "));
    // Premier live lancé : son activé d'office (le user s'attend à l'entendre,
    // la liste « Son » est tout en bas du QAM). Ensuite on respecte son choix.
    const audio = next.includes(watch.audio) ? watch.audio
      : !selected.length && next.length ? next[0] : "";
    const nextWatch = { ...watch, streams: next, audio };
    setWatch(nextWatch);
    setBusy(true); setMsg("");
    try {
      const saved: any = await call("set_watch_settings", nextWatch);
      if (!saved?.ok) { setMsg("⚠️ " + (saved?.error || t("watch_save_failed"))); return; }
      if (!next.length && watching) {
        await call("stop_watch"); setWatching(false); return;
      }
      if (next.length && !watching) {
        const started: any = await call("start_watch");
        if (started?.ok) setWatching(true);
        else setMsg("⚠️ " + (started?.error || t("watch_start_failed")));
      }
    } finally { setBusy(false); }
  };
  const toggle = async () => {
    setBusy(true); setMsg("");
    try {
      if (watching) {
        await call("stop_watch"); setWatching(false);
      } else {
        const saved: any = await saveStreams();
        if (!saved?.ok) return;
        const r: any = await call("start_watch");
        if (r?.ok) setWatching(true);
        else setMsg(r?.error === "no_watch_stream" ? t("watch_need_stream")
          : "⚠️ " + (r?.error || t("watch_start_failed")));
      }
    } finally { setBusy(false); }
  };
  const count = Array.isArray(watch.streams) ? watch.streams.length : 0;
  // Un son qui pointe vers une chaîne retirée vaut « muet » : le helper ne
  // joue que le son d'un flux affiché.
  const audioOn = count > 0 && !!watch.audio && watch.streams.includes(watch.audio);
  const layouts: any = {
    1: [["corner_br", t("watch_corner")], ["corner_tr", t("watch_corner_top")],
        ["corner_bl", t("watch_corner_left")], ["corner_tl", t("watch_corner_top_left")],
        ["side_right", t("watch_side")], ["side_left", t("watch_side_left")], ["full", t("watch_full")]],
    2: [["side_by_side", t("watch_side_by_side")], ["stacked", t("watch_stacked")],
        ["stacked_left", t("watch_stacked_left")], ["pip", t("watch_pip")]],
    3: [["one_plus_two", "1 + 2"], ["row", t("watch_row")], ["column", t("watch_column")], ["column_left", t("watch_column_left")]],
    4: [["grid", t("watch_grid")], ["one_plus_three", "1 + 3"], ["row", t("watch_row")]],
  };
  return (
    <PanelSection title={t("watch_title")}>
      <PanelSectionRow><div style={{ fontSize: 11, opacity: 0.75 }}>
        {t("watch_intro")}
      </div></PanelSectionRow>
      <PanelSectionRow><div style={{ display: "flex", alignItems: "center", gap: 8, width: "100%" }}>
        <div style={{ flex: 1, fontSize: 13, fontWeight: 700 }}>{t("watch_followed_title")}</div>
        <ActionCard color={TWITCH} disabled={followedBusy} onClick={refreshFollowed}>
          <IcRefresh /> {followedBusy ? "…" : t("watch_followed_refresh")}
        </ActionCard>
      </div></PanelSectionRow>
      {followedError && <PanelSectionRow><div style={{ fontSize: 11, color: "#ffcc8a" }}>{followedError}</div></PanelSectionRow>}
      {!followedBusy && !followedError && followed.length === 0 && <PanelSectionRow><div style={{ fontSize: 11, opacity: 0.7 }}>
        {t("watch_followed_empty")}
      </div></PanelSectionRow>}
      {followed.map((live: any) => {
        const selected = streamList(input).includes(live.login);
        const full = !selected && streamList(input).length >= 4;
        const detail = [live.game, live.title].filter(Boolean).join(" — ");
        const thumbnail = String(live.thumbnail || "").replace("{width}", "160").replace("{height}", "90");
        const viewers = new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(Number(live.viewers) || 0);
        return <PanelSectionRow key={live.login}>
          <ActionCard color={TWITCH} active={selected} disabled={full} center={false}
            onClick={() => playFollowed(live.login)}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0, width: "100%", textAlign: "left" }}>
              <div style={{ width: 82, height: 46, flex: "0 0 auto", position: "relative", overflow: "hidden", borderRadius: 3, background: "rgba(0,0,0,0.35)" }}>
                {thumbnail && <img src={thumbnail} alt="" style={{ display: "block", width: "100%", height: "100%", objectFit: "cover" }} />}
                <span style={{ position: "absolute", left: 4, bottom: 3, padding: "1px 3px", borderRadius: 2, background: "#e91916", color: "#fff", fontSize: 8, fontWeight: 800, letterSpacing: 0.3 }}>LIVE</span>
              </div>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 4, minWidth: 0, fontWeight: 700 }}>
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{live.name}</span>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 2, opacity: 0.65, fontWeight: 400, fontSize: 10, whiteSpace: "nowrap" }}><EyeIcon /> {viewers}</span>
                </div>
                <div style={{ fontSize: 10, opacity: 0.65, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>@{live.login}{detail ? " · " + detail : ""}</div>
              </div>
            </div>
          </ActionCard>
        </PanelSectionRow>;
      })}
      <PanelSectionRow>
        <TextField label={t("watch_channels")} value={input}
          placeholder="channel1, channel2" onChange={(e: any) => setInput(e?.target?.value ?? "")}
          onBlur={() => { saveStreams(); }} />
      </PanelSectionRow>
      <PanelSectionRow>
        <ActionCard color={TWITCH} disabled={busy} onClick={toggle}>
          <IcBroadcast /> {busy ? "…" : watching ? t("watch_stop") : t("watch_start")}
        </ActionCard>
      </PanelSectionRow>
      {msg && <PanelSectionRow><div style={{ fontSize: 11, color: "#ffb4b4" }}>{msg}</div></PanelSectionRow>}
      {count > 0 && <>
        <PanelSectionRow>
          <Dropdown strDefaultLabel={t("watch_layout")} selectedOption={watch.layout}
            rgOptions={(layouts[count] || layouts[1]).map(([data, label]: any) => ({ data, label }))}
            onChange={(e: any) => push({ layout: e.data })} />
        </PanelSectionRow>
        <PanelSectionRow>
          <SliderField label={t("watch_scale", { v: Math.round(watch.scale * 100) })}
            value={watch.scale * 100} min={40} max={160} step={5} showValue={false}
            onChange={(v: number) => push({ scale: v / 100 })} bottomSeparator="none" />
        </PanelSectionRow>
        <PanelSectionRow>
          <SliderField label={t("watch_opacity", { v: Math.round(watch.opacity * 100) })}
            value={watch.opacity * 100} min={15} max={100} step={5} showValue={false}
            onChange={(v: number) => push({ opacity: v / 100 })} bottomSeparator="none" />
        </PanelSectionRow>
        <PanelSectionRow>
          <Dropdown strDefaultLabel={t("watch_fps")} selectedOption={watch.max_fps}
            rgOptions={[{ data: 30, label: "30 fps" }, { data: 60, label: "60 fps" }]}
            onChange={(e: any) => push({ max_fps: e.data })} />
        </PanelSectionRow>
        <PanelSectionRow>
          <Dropdown strDefaultLabel={t("watch_audio")} selectedOption={audioOn ? watch.audio : ""}
            rgOptions={[{ data: "", label: t("watch_audio_off") },
              ...watch.streams.map((s: string) => ({ data: s, label: t("watch_audio_of", { v: s }) }))]}
            onChange={(e: any) => push({ audio: e.data })} />
        </PanelSectionRow>
        {audioOn && <PanelSectionRow>
          <SliderField label={t("watch_volume", { v: Math.round(watch.volume * 100) })}
            value={watch.volume * 100} min={0} max={150} step={5} showValue={false}
            onChange={(v: number) => push({ volume: v / 100 })} bottomSeparator="none" />
        </PanelSectionRow>}
      </>}
    </PanelSection>
  );
}

function Content() {
  const [tab, setTab] = useState<"live" | "watch" | "chat" | "config">("live");
  const [focus, setFocus] = useState<string | null>(null);
  return (
    <>
      <PanelSection>
        <PanelSectionRow>
          {/* Rangée d'onglets = UN arrêt de nav vertical, gauche/droite circule
              entre les onglets (même idiome que Steamcord). */}
          <Focusable flow-children="row"
            style={{ display: "flex", gap: 4, width: "100%", boxSizing: "border-box" }}>
            <TabBtn active={tab === "live"} focused={focus === "live"}
              onClick={() => setTab("live")}
              onFocus={() => setFocus("live")}
              onBlur={() => setFocus((f: any) => (f === "live" ? null : f))}>
              <IcBroadcast /> {t("tab_live")}
            </TabBtn>
            <TabBtn active={tab === "watch"} focused={focus === "watch"}
              onClick={() => setTab("watch")}
              onFocus={() => setFocus("watch")}
              onBlur={() => setFocus((f: any) => (f === "watch" ? null : f))}>
              <IcBroadcast /> {t("tab_watch")}
            </TabBtn>
            <TabBtn active={tab === "chat"} focused={focus === "chat"}
              onClick={() => setTab("chat")}
              onFocus={() => setFocus("chat")}
              onBlur={() => setFocus((f: any) => (f === "chat" ? null : f))}>
              <IcChat /> {t("tab_chat")}
            </TabBtn>
            <TabBtn active={tab === "config"} focused={focus === "config"}
              onClick={() => setTab("config")}
              onFocus={() => setFocus("config")}
              onBlur={() => setFocus((f: any) => (f === "config" ? null : f))}>
              {t("tab_config")}
            </TabBtn>
          </Focusable>
        </PanelSectionRow>
      </PanelSection>
      {tab === "live" && <LiveSection />}
      {tab === "watch" && <WatchSection />}
      {tab === "chat" && <ChatSection />}
      {tab === "config" && <ConfigSection />}
    </>
  );
}

// Notif native Steam (DisplayClientNotification, type 1 = popup + son). Le
// toaster Decky crée des entrées SANS notification_type qui ne s'affichent pas
// et font PLANTER le panneau de notifs Steam sur ce build — c'est le constat
// déjà fait dans Steamcord, SkullKey et le Toolkit, où ce helper existe depuis
// longtemps ; BoneCast était le seul à ne pas l'avoir.
// Mode streamer — contrat PARTAGÉ avec Steamcord, SkullKey et BC250 Toolkit
// (tous dans le même contexte JS de Steam) : window.__necroStreamer.sources =
// { source: bool }, réglage localStorage « necro_streamer_mode » (auto | always
// | off, réglable dans Steamcord), événement « necro-streamer-change ».
// Pendant un live ou un enregistrement, un toast Steam s'imprime dans la vidéo
// capturée : on le retient jusqu'à la fin.
function setLiveSource(name: string, live: boolean) {
  const w = window as any;
  const g = (w.__necroStreamer ||= { sources: {} });
  if (!!g.sources[name] === live) return;
  g.sources[name] = live;
  window.dispatchEvent(new Event("necro-streamer-change"));
}
function streamerActive(): boolean {
  let mode = "auto";
  try { mode = localStorage.getItem("necro_streamer_mode") || "auto"; } catch {}
  if (mode === "off") return false;
  if (mode === "always") return true;
  return Object.values((window as any).__necroStreamer?.sources || {}).some(Boolean);
}
const STREAMER_RETRY_MS = 15000;

function notify(data: { title?: string; body: string; duration?: number }) {
  if (streamerActive()) { setTimeout(() => notify(data), STREAMER_RETRY_MS); return; }
  try {
    const App = (window as any).App;
    const steamid = App?.GetCurrentUser?.()?.strSteamID || App?.m_CurrentUser?.strSteamID || "";
    // steamid OBLIGATOIRE : sans lui l'entrée est malformée et fait planter le
    // panneau de notifs Steam → mieux vaut ne rien notifier.
    if (!steamid) return;
    (window as any).SteamClient?.ClientNotifications?.DisplayClientNotification?.(
      1,
      JSON.stringify({ title: data.title || "BoneCast", body: data.body, state: "active", steamid }),
      () => {},
    );
  } catch (e) { console.error("[BoneCast] notify failed", e); }
}

// ── Auto-update : le frontend ne fait que PRÉVENIR ───────────────────────────
// C'est le backend qui installe (il en a le droit : le dossier du plugin est à
// root, mais les fichiers dedans nous appartiennent). Lui seul ne peut pas
// notifier — d'où ce relais.
//
// ⛔ Surtout NE PAS appeler `DeckyBackend.call('utilities/install_plugin', …)` :
// c'est la route du Store Decky. Elle décompresse, puis déclare l'install à
// plugins.deckbrew.xyz, qui ne connaît pas nos plugins → 404 → la suite ne
// s'exécute pas : fichiers écrits, plugin jamais rechargé, et une modale
// « Mise à jour en cours » figée en travers de l'interface Steam. Mesuré le
// 13/09 sur BC250-Toolkit.
const UPDATE_POLL_MS = 5000;
const UPDATE_POLL_TRIES = 36; // 3 min, le temps qu'un démarrage à froid finisse

async function reportFailedUpdate() {
  for (let i = 0; i < UPDATE_POLL_TRIES; i++) {
    let notice: any = null;
    try {
      notice = await call<[], any>("take_pending_update");
    } catch {
      // Backend pas encore joignable : ce n'est pas un échec, on repasse.
    }
    if (notice?.version) {
      notify({
        title: "BoneCast",
        // Deux avis distincts : la maj n'a pas pu s'écrire (il faut la poser à
        // la main), ou elle est écrite mais pas chargée — le backend n'a pas le
        // droit de redémarrer le loader, donc elle prendra effet au prochain
        // démarrage de Steam. Annoncer le second comme un échec serait faux.
        body: notice.reload
          ? `Update ${notice.version} installed — it becomes active the next time Steam starts.`
          : `Update ${notice.version} could not be installed automatically. `
            + "Install it from Decky → Developer → Install plugin from URL.",
      });
      return;
    }
    await new Promise((r) => setTimeout(r, UPDATE_POLL_MS));
  }
}

export default definePlugin(() => {
  reportFailedUpdate();
  // Mode streamer : un stream OU un enregistrement BoneCast est une source de
  // live — le toast finirait aussi dans le fichier enregistré.
  const pollLive = () => call<[], any>("get_stream_status")
    .then((st: any) => setLiveSource("bonecast", !!st?.streaming)).catch(() => {});
  pollLive();
  const liveTimer = setInterval(pollLive, 5000);
  return {
    name: "BoneCast",
    title: <div className={staticClasses.Title}>BoneCast</div>,
    icon: <FaTwitch />,
    content: <Content />,
    onDismount() { clearInterval(liveTimer); setLiveSource("bonecast", false); },
  };
});
