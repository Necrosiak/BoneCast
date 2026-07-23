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
        const r: any = await call("stop_stream"); setStreaming(false);
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
    "idle" | "checking" | "available" | "uptodate" | "installing" | "failed">("idle");
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
      if (!(r === true || r?.ok)) { setUpdErr(r?.error || ""); setStatus("failed"); }
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

function Content() {
  const [tab, setTab] = useState<"live" | "chat" | "config">("live");
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
      {tab === "chat" && <ChatSection />}
      {tab === "config" && <ConfigSection />}
    </>
  );
}

export default definePlugin(() => ({
  name: "BoneCast",
  title: <div className={staticClasses.Title}>BoneCast</div>,
  icon: <FaTwitch />,
  content: <Content />,
}));
