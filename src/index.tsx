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
  Navigation,
  ConfirmModal,
  showModal,
} from "@decky/ui";
import { definePlugin, call } from "@decky/api";
import { FaTwitch, FaYoutube } from "react-icons/fa";
import {
  BoneCastIcon, IcBroadcast, IcChat, IcController, IcFilm, IcGear, IcGithub, IcKey, IcSliders,
  IcLogout, IcMic, IcMicMute, IcRefresh, IcSave, IcSend,
} from "./components/Icons";
import { focusHalo, ActionCard, TWITCH, YOUTUBE, DANGER } from "./components/Styled";
import { t } from "./i18n";
import { clearClickableNotifications, notifyClickable } from "./clickableNotify";

const B = DialogButton as any;
const EyeIcon = () => <svg viewBox="0 0 24 24" width="13" height="13" fill="none"
  stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
  aria-hidden="true"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z" /><circle cx="12" cy="12" r="2.5" /></svg>;

// Onglets : même habillage que Steamcord (#43 là-bas : des boutons alignés ne
// disaient pas qu'ils étaient exclusifs). Coins arrondis en haut seulement,
// actif SOULIGNÉ d'un trait d'accent qui rejoint la règle sous la rangée,
// inactifs éteints. Le soulignement est un boxShadow interne : on le compose à
// la main avec l'anneau de focus au lieu de laisser focusHalo l'écraser. Texte
// blanc forcé, sinon le focus natif du DialogButton peint un fond clair dessous.
const TabBtn = ({ active, focused, onClick, onFocus, onBlur, children, color = TWITCH }: any) => {
  const shadow = [
    active ? `inset 0 -3px 0 ${color}` : "",
    focused ? `0 0 0 2px #fff, 0 0 8px 1px ${color}` : "",
  ].filter(Boolean).join(", ") || "none";
  return (
    <B noFocusRing
      onClick={onClick}
      onFocus={onFocus} onBlur={onBlur}
      onGamepadFocus={onFocus} onGamepadBlur={onBlur}
      style={{
        flex: "1 1 0", minWidth: 0, margin: 0, padding: "8px 0",
        fontSize: 13, minHeight: 40, boxSizing: "border-box",
        overflow: "visible", lineHeight: 1.2,
        borderRadius: "6px 6px 0 0",
        color: active || focused ? "#fff" : "rgba(255,255,255,0.62)",
        background: focused ? color + "d9"
          : active ? color + "47" : "rgba(255,255,255,0.04)",
        fontWeight: active ? 700 : 400,
        ...focusHalo(color, focused),
        boxShadow: shadow,
      }}
    >
      {children}
    </B>
  );
};

// Rangée d'onglets = UN arrêt de nav vertical (gauche/droite circule entre les
// onglets), fermée par une règle que le soulignement de l'actif vient couper.
const TabRow = ({ children }: any) => (
  <Focusable flow-children="row"
    style={{
      display: "flex", gap: 4, marginBottom: 6, width: "100%", boxSizing: "border-box",
      borderBottom: "1px solid rgba(255,255,255,0.14)",
    }}>
    {children}
  </Focusable>
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
  const refresh = () =>
    call<[], any>("get_config").then((c: any) => {
      setLoggedIn(!!c?.logged_in); setLogin(c?.login || "");
      setKeySet(!!c?.key_set);
      if (typeof c?.title === "string") setTitle(c.title);
      if (typeof c?.game_name === "string") setGameName(c.game_name);
    }).catch(() => {});

  useEffect(() => { refresh(); }, []);

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
      <StreamControls platform="twitch" color={TWITCH} ready={keySet} clip
        beforeStart={async () => {
          // Catégorie Twitch auto = jeu en cours (Steam OU raccourci non-Steam).
          try {
            const gn = (Router as any)?.MainRunningApp?.display_name;
            if (gn) { setGameName(gn); await call<[string], any>("set_game", gn); }
          } catch { /* pas de jeu détecté → on garde la catégorie précédente */ }
        }} />
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

// ── Contrôles du live, un exemplaire PAR plateforme ──────────────────────────
// Twitch et YouTube ont chacun le leur (réglages compris). Le backend n'accepte
// qu'un live à la fois : si l'autre plateforme est à l'antenne, on l'affiche et
// le bouton reste bloqué au lieu d'échouer.
function StreamControls({ platform, color, ready, beforeStart, clip }: {
  platform: "twitch" | "youtube"; color: string; ready: boolean;
  beforeStart?: () => Promise<void>; clip?: boolean;
}) {
  const [live, setLive] = useState<string | null>(null);  // plateforme à l'antenne
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [micActive, setMicActive] = useState(false);
  const [micMuted, setMicMuted] = useState(false);
  const [stMic, setStMic] = useState(false);
  const [brb, setBrb] = useState(false);
  const [brbBusy, setBrbBusy] = useState(false);
  const [clipBusy, setClipBusy] = useState(false);
  const [resumeLeft, setResumeLeft] = useState(0);   // > 0 : reconnexion auto en cours

  // Un enregistrement local appartient à l'onglet qui l'a lancé ; on le montre
  // des deux côtés pour pouvoir l'arrêter, comme un live.
  const mine = live === platform || live === "record";
  const other = live && !mine ? live : null;
  const recOnly = live === "record";

  const apply = (r: any) => {
    // Reconnexion auto (coupure réseau…) : le live compte toujours comme le
    // nôtre, le bouton reste « Arrêter » (arrêter = abandonner la reprise).
    const p = r?.streaming ? (r?.platform || null) : (r?.resuming || null);
    setResumeLeft(!r?.streaming && r?.resuming ? (r?.resume_left || 0) : 0);
    setLive((prev) => {
      if (prev && (prev === platform || prev === "record") && !p) setMsg(t("live_stopped"));
      return p;
    });
    setMicActive(!!r?.mic); setMicMuted(!!r?.mic_muted); setBrb(!!r?.brb);
  };

  useEffect(() => {
    call<[], any>("get_config").then((c: any) => {
      const st = platform === "youtube" ? c?.youtube?.stream : c?.stream;
      setStMic(!!st?.mic);
    }).catch(() => {});
    const poll = () => call<[], any>("get_stream_status").then(apply).catch(() => {});
    poll();
    const id = setInterval(poll, 2000);
    return () => clearInterval(id);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const errText = (r: any) =>
    r?.error === "busy" ? t("err_busy", { p: platformName(r?.platform) })
    : r?.error === "no_key" ? t("err_no_key")
    : r?.error === "no_yt_key" ? t("err_no_yt_key")
    : r?.error === "yt_api" ? ytReason(r?.hint, t("err_live_failed"))
    : r?.error === "no_ffmpeg" ? "⚠️ " + (r?.hint || t("hint_no_ffmpeg"))
    : r?.error === "no_x264" ? "⚠️ " + (r?.hint || t("hint_no_x264"))
    : r?.error === "no_gst" ? "⚠️ " + (r?.hint || t("hint_no_gst"))
    : "⚠️ " + (r?.hint || r?.error || t("err_live_failed"));

  const toggleLive = async () => {
    setBusy(true); setMsg("");
    try {
      if (mine) {
        const r: any = await call("stop_stream");
        setLive(null); setLiveSource("bonecast", false);
        setMicActive(false); setMicMuted(false); setBrb(false);
        if (r?.record_path) setMsg(t("recorded_to") + r.record_path);
      } else {
        if (beforeStart) await beforeStart();
        const r: any = await call<[boolean, string], any>("start_stream", false, platform);
        if (r?.ok) { setLive(platform); setMicActive(stMic); setMicMuted(false); }
        else setMsg(errText(r));
      }
    } finally { setBusy(false); }
  };

  // Enregistrement local SANS passer en live (mkv dans Vidéos/BoneCast).
  const startRecordOnly = async () => {
    setBusy(true); setMsg("");
    try {
      const r: any = await call<[boolean, string], any>("start_stream", true, platform);
      if (r?.ok) { setLive("record"); setMicActive(stMic); }
      else setMsg(r?.error === "busy" ? errText(r)
        : "⚠️ " + (r?.hint || r?.error || t("err_record_failed")));
    } finally { setBusy(false); }
  };

  // BRB : écran pause à l'antenne (le live continue, micro auto-coupé).
  const toggleBrb = async () => {
    setBrbBusy(true);
    try {
      const r: any = await call(brb ? "brb_stop" : "brb_start");
      if (r?.ok) setBrb(!brb);
    } finally { setBrbBusy(false); }
  };

  // Clip des ~30 dernières secondes (Twitch seulement, ~15 s pour le publier).
  const doClip = async () => {
    setClipBusy(true);
    try {
      const r: any = await call("create_clip");
      setMsg(r?.ok ? t("clip_created")
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

  if (other) {
    return (
      <PanelSectionRow>
        <div style={{ fontSize: 12, color: "#fff", textAlign: "center", opacity: 0.85 }}>
          {t("busy_other", { p: platformName(other) })}
        </div>
      </PanelSectionRow>
    );
  }

  return (
    <>
      <PanelSectionRow>
        <ActionCard color={mine ? DANGER : color} active big
          disabled={busy || (!mine && !ready)} onClick={toggleLive}>
          {busy ? "…" : <><IcBroadcast /> {mine ? (recOnly ? t("stop_record") : t("stop_live")) : t("go_live")}</>}
        </ActionCard>
      </PanelSectionRow>
      {mine && resumeLeft > 0 && (
        <PanelSectionRow>
          <div style={{ fontSize: 12, color: "#fff", textAlign: "center", opacity: 0.85 }}>
            {t("reconnecting", { s: resumeLeft })}
          </div>
        </PanelSectionRow>
      )}
      {!live && (
        <PanelSectionRow>
          <ActionCard color={color} disabled={busy} onClick={startRecordOnly}>
            {t("record_only_btn")}
          </ActionCard>
        </PanelSectionRow>
      )}
      {mine && (
        <PanelSectionRow>
          <div style={{ fontSize: 12, fontWeight: 800, color: DANGER, textAlign: "center" }}>
            {recOnly ? t("status_rec")
             : brb ? t("status_brb")
             : platform === "youtube" ? t("status_live_yt") : t("status_live")}
          </div>
        </PanelSectionRow>
      )}
      {mine && (
        <PanelSectionRow>
          <Focusable flow-children="row" style={{ display: "flex", gap: 6, width: "100%" }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <ActionCard color={brb ? DANGER : color} active={brb}
                disabled={brbBusy} onClick={toggleBrb}>
                {brb ? t("brb_back") : t("brb_pause")}
              </ActionCard>
            </div>
            {clip && !recOnly && (
              <div style={{ flex: 1, minWidth: 0 }}>
                <ActionCard color={color} disabled={clipBusy} onClick={doClip}>
                  {clipBusy ? "…" : <><IcFilm /> {t("clip_btn")}</>}
                </ActionCard>
              </div>
            )}
          </Focusable>
        </PanelSectionRow>
      )}
      {mine && micActive && (
        <PanelSectionRow>
          <ActionCard color={micMuted ? DANGER : color} active={micMuted} onClick={toggleMicMute}>
            {micMuted ? <><IcMicMute /> {t("mic_muted_btn")}</> : <><IcMic /> {t("mic_mute_btn")}</>}
          </ActionCard>
        </PanelSectionRow>
      )}
      {msg && <PanelSectionRow><div style={{ fontSize: 11, color: "#fff", wordBreak: "break-word" }}>{msg}</div></PanelSectionRow>}
    </>
  );
}

// Codes d'erreur bruts de l'API YouTube (champ `reason`) → phrase utile.
// Tout nouvel utilisateur tombe sur liveStreamingNotEnabled (24 h d'attente
// chez YouTube la 1re fois) : un code nu ne lui dit pas quoi faire.
const YT_REASONS: Record<string, string> = {
  liveStreamingNotEnabled: "yt_err_not_enabled",
  livePermissionBlocked: "yt_err_blocked",
  accessNotConfigured: "yt_err_api_off",
  quotaExceeded: "yt_err_quota",
  rateLimitExceeded: "yt_err_quota",
  userRequestsExceedRateLimit: "yt_err_quota",
  insufficientPermissions: "yt_err_auth",
  authError: "yt_err_auth",
  not_logged_in: "yt_err_auth",
};
const ytReason = (reason?: string, fallback?: string) => {
  const key = reason ? YT_REASONS[reason] : undefined;
  return key ? "⚠️ " + t(key) : "⚠️ YouTube : " + (reason || fallback || "");
};

const platformName = (p?: string) =>
  p === "youtube" ? "YouTube" : p === "record" ? t("recording_name") : "Twitch";

// ── Onglet YOUTUBE : connexion Google (ou clé manuelle) + titre + live ──────
function YouTubeSection() {
  const [yt, setYt] = useState<any>({});
  const [titleInput, setTitleInput] = useState("");
  const [keyInput, setKeyInput] = useState("");
  const [authing, setAuthing] = useState(false);
  const [authBusy, setAuthBusy] = useState(false);
  const [authCode, setAuthCode] = useState("");
  const [authUrl, setAuthUrl] = useState("");
  const [msg, setMsg] = useState("");

  const refresh = () =>
    call<[], any>("get_config").then((c: any) => setYt(c?.youtube || {})).catch(() => {});
  useEffect(() => { refresh(); }, []);

  // Poll tant qu'on attend l'autorisation Google (device flow).
  useEffect(() => {
    if (!authing) return;
    const id = setInterval(async () => {
      try {
        const r: any = await call("yt_auth_poll");
        if (r?.status === "ok") {
          setAuthing(false); setAuthCode(""); setMsg(t("auth_connected")); refresh();
        } else if (["expired", "denied", "error"].includes(r?.status)) {
          setAuthing(false); setAuthCode("");
          setMsg(r.status === "expired" ? t("auth_expired")
               : r.status === "denied" ? t("auth_denied") : t("auth_error"));
        }
      } catch { /* on continue à poller */ }
    }, 5000);
    return () => clearInterval(id);
  }, [authing]); // eslint-disable-line react-hooks/exhaustive-deps

  const startAuth = async () => {
    setAuthBusy(true); setMsg("");
    try {
      const r: any = await call("yt_auth_start");
      if (r?.ok) {
        setAuthCode(r.user_code || "");
        setAuthUrl((r.verification_uri || "google.com/device").replace(/^https?:\/\/(www\.)?/, ""));
        setAuthing(true);
      } else setMsg("⚠️ " + (r?.error || t("err_generic")));
    } finally { setAuthBusy(false); }
  };
  const save = (patch: any) =>
    call<[any], any>("yt_set_settings", patch).then(() => refresh()).catch(() => {});

  const loggedIn = !!yt.logged_in;
  const ready = loggedIn || !!yt.key_set;

  return (
    <PanelSection title={t("yt_title")}>
      {loggedIn ? (
        <PanelSectionRow>
          <div style={{ fontSize: 13, color: YOUTUBE, fontWeight: 700 }}>
            <FaYoutube style={{ verticalAlign: "-0.125em" }} /> {yt.channel || t("connected")}
          </div>
        </PanelSectionRow>
      ) : yt.login_available && (
        <>
          <PanelSectionRow>
            <ActionCard color={YOUTUBE} active disabled={authBusy || authing} onClick={startAuth}>
              <FaYoutube style={{ verticalAlign: "-0.125em" }} /> {authing ? t("login_waiting") : authBusy ? "…" : t("yt_login_button")}
            </ActionCard>
          </PanelSectionRow>
          {authCode && (
            <PanelSectionRow>
              <div style={{ fontSize: 12, color: "#fff", lineHeight: 1.6, border: `1px solid ${YOUTUBE}`, borderRadius: 8, padding: 10, textAlign: "center" }}>
                {t("go_to")} <span style={{ color: YOUTUBE, fontWeight: 700 }}>{authUrl}</span> {t("and_enter")}
                <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: 4, marginTop: 4 }}>{authCode}</div>
              </div>
            </PanelSectionRow>
          )}
        </>
      )}
      {loggedIn && (
        <>
          <PanelSectionRow>
            <TextField label={t("title_label")} value={titleInput}
              placeholder={yt.title || t("title_placeholder")}
              onChange={(e: any) => setTitleInput(e?.target?.value ?? "")} />
          </PanelSectionRow>
          <PanelSectionRow>
            <ActionCard color={YOUTUBE} disabled={!titleInput}
              onClick={() => { save({ title: titleInput }); setTitleInput(""); }}>
              <IcSave /> {t("save_title")}
            </ActionCard>
          </PanelSectionRow>
          <PanelSectionRow>
            <Dropdown strDefaultLabel={t("yt_privacy")} selectedOption={yt.privacy || "public"}
              rgOptions={[
                { data: "public", label: t("yt_public") },
                { data: "unlisted", label: t("yt_unlisted") },
                { data: "private", label: t("yt_private") },
              ]} onChange={(e: any) => save({ privacy: e.data })} />
          </PanelSectionRow>
          {/* Latence du live (#1) : prise en compte au prochain lancement. */}
          <PanelSectionRow>
            <Dropdown strDefaultLabel={t("yt_latency")} selectedOption={yt.latency || "normal"}
              rgOptions={[
                { data: "normal", label: t("yt_latency_normal") },
                { data: "low", label: t("yt_latency_low") },
                { data: "ultraLow", label: t("yt_latency_ultra") },
              ]} onChange={(e: any) => save({ latency: e.data })} />
          </PanelSectionRow>
          <PanelSectionRow>
            <div style={{ fontSize: 11, opacity: 0.75, color: "#fff" }}>
              <IcController /> {t("yt_category_note")}
            </div>
          </PanelSectionRow>
        </>
      )}
      {!loggedIn && (
        <>
          <PanelSectionRow>
            <div style={{ fontSize: 11, opacity: 0.75, color: "#fff" }}>
              <IcKey /> {yt.login_available ? t("yt_or_key") : t("yt_key_intro")}
            </div>
          </PanelSectionRow>
          <PanelSectionRow>
            <TextField label={t("yt_key_label")} value={keyInput} bIsPassword
              placeholder={yt.key_set ? t("yt_key_saved") : ""}
              onChange={(e: any) => setKeyInput(e?.target?.value ?? "")} />
          </PanelSectionRow>
          <PanelSectionRow>
            <Focusable flow-children="row" style={{ display: "flex", gap: 6, width: "100%" }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <ActionCard color={YOUTUBE} disabled={!keyInput.trim()}
                  onClick={() => { save({ key: keyInput }); setKeyInput(""); }}>
                  <IcSave /> {t("yt_key_save")}
                </ActionCard>
              </div>
              {yt.key_set && (
                <div style={{ flex: 1, minWidth: 0 }}>
                  <ActionCard color={DANGER} onClick={() => save({ key: "" })}>
                    {t("yt_key_clear")}
                  </ActionCard>
                </div>
              )}
            </Focusable>
          </PanelSectionRow>
          <PanelSectionRow>
            <div style={{ fontSize: 10, opacity: 0.6, color: "#fff" }}>{t("yt_key_help")}</div>
          </PanelSectionRow>
        </>
      )}
      <StreamControls platform="youtube" color={YOUTUBE} ready={ready} />
      {msg && <PanelSectionRow><div style={{ fontSize: 11, color: "#fff" }}>{msg}</div></PanelSectionRow>}
    </PanelSection>
  );
}

// ── Onglet CHAT : overlay + écrire dans son chat ─────────────────────────────
function ChatSection({ platform }: { platform: "twitch" | "youtube" }) {
  const yt = platform === "youtube";
  // Connecté à Twitch sans le droit de lire les followers (login antérieur) →
  // l'overlay ne peut pas afficher les nouveaux follows : on le dit.
  const [followsMissing, setFollowsMissing] = useState(false);
  useEffect(() => {
    if (yt) return;
    call<[], any>("get_config")
      .then((c: any) => setFollowsMissing(!!c?.logged_in && c?.follows_scope === false))
      .catch(() => {});
  }, [yt]);
  const color = yt ? YOUTUBE : TWITCH;
  const [canSend, setCanSend] = useState(!yt);
  const [otherOverlay, setOtherOverlay] = useState<string | null>(null);
  const [channelInput, setChannelInput] = useState("");
  const [channelSet, setChannelSet] = useState("");
  const [overlayOn, setOverlayOn] = useState(false);
  const [ov, setOv] = useState<any>({ opacity: 62, fontSize: 13, width: 360, height: 460, pos: "tr", badges: true, thirdParty: true });
  const [chatInput, setChatInput] = useState("");
  const [chatMsg, setChatMsg] = useState("");
  const [chatBusy, setChatBusy] = useState(false);

  const refresh = () =>
    call<[], any>("get_config").then((c: any) => {
      const src = yt ? c?.youtube : c;
      setChannelSet((yt ? src?.chat_source : src?.channel) || "");
      setOverlayOn(!!src?.overlay_on);
      if (src?.overlay) setOv((p: any) => ({ ...p, ...src.overlay }));
      if (yt) setCanSend(!!src?.can_send);
      const pf = c?.overlay_platform;
      setOtherOverlay(pf && pf !== platform ? pf : null);
    }).catch(() => {});
  useEffect(() => { refresh(); }, []);

  const pushOv = (patch: any) =>
    setOv((prev: any) => { const next = { ...prev, ...patch }; call("set_overlay_settings", next, platform).catch(() => {}); return next; });
  const toggleOverlay = async (v: boolean) => {
    setOverlayOn(v); setChatMsg("");
    try {
      const r: any = v ? await call<[string], any>("start_overlay", platform) : await call("stop_overlay");
      if (r?.error === "busy") setChatMsg(t("overlay_busy", { p: platformName(r?.platform) }));
    } catch { /* noop */ }
    refresh();
  };

  // Message dans SON chat Twitch (Helix — nécessite le scope user:write:chat).
  const sendChat = async () => {
    if (!chatInput.trim()) return;
    setChatBusy(true); setChatMsg("");
    try {
      const r: any = await call<[string], any>(yt ? "yt_send_chat" : "send_chat", chatInput);
      if (r?.ok) { setChatInput(""); setChatMsg(t("sent")); }
      else setChatMsg(r?.error === "missing_scope"
        ? t("reconnect_scopes")
        : r?.error === "not_live" ? t("yt_chat_not_live")
        : yt && r?.error && r.error !== "empty" ? ytReason(r.error)
        : "⚠️ " + (r?.error || t("err_send_failed")));
    } finally { setChatBusy(false); }
  };

  return (
    <>
      {canSend && <PanelSection title={t("chat_write_title")}>
      {followsMissing && (
        <PanelSectionRow>
          <div style={{ fontSize: 11, opacity: 0.75, color: "#fff", lineHeight: 1.5 }}>
            {t("follows_reconnect")}
          </div>
        </PanelSectionRow>
      )}
        <PanelSectionRow>
          <TextField label={t("message_label")} value={chatInput}
            placeholder={t("chat_placeholder")}
            onChange={(e: any) => setChatInput(e?.target?.value ?? "")} />
        </PanelSectionRow>
        <PanelSectionRow>
          <ActionCard color={color} disabled={chatBusy || !chatInput.trim()} onClick={sendChat}>
            {chatBusy ? "…" : <><IcSend /> {t("send")}</>}
          </ActionCard>
        </PanelSectionRow>
        {chatMsg && <PanelSectionRow><div style={{ fontSize: 11, color: "#fff" }}>{chatMsg}</div></PanelSectionRow>}
      </PanelSection>}
      <PanelSection title={t("overlay_title")}>
        <PanelSectionRow>
          <div style={{ fontSize: 11, opacity: 0.75, color: "#fff" }}>
            {yt ? (channelSet ? t("yt_channel_current", { ch: channelSet }) : t("yt_channel_none"))
              : channelSet ? t("channel_current", { ch: channelSet }) : t("channel_none")}
          </div>
        </PanelSectionRow>
        <PanelSectionRow>
          <TextField label={t("channel_other_label")} value={channelInput}
            placeholder={channelSet || (yt ? t("yt_channel_placeholder") : t("channel_placeholder"))}
            onChange={(e: any) => setChannelInput(e?.target?.value ?? "")} />
        </PanelSectionRow>
        <PanelSectionRow>
          <ActionCard color={color} disabled={!channelInput}
            onClick={() => (yt ? call<[any], any>("yt_set_settings", { chat_channel: channelInput })
              : call<[string], any>("set_channel", channelInput))
              .then(() => { setChannelInput(""); refresh(); }).catch(() => {})}>
            <IcSave /> {t("channel_use")}
          </ActionCard>
        </PanelSectionRow>
        {otherOverlay && (
          <PanelSectionRow>
            <div style={{ fontSize: 11, color: "#ffcc8a" }}>
              {t("overlay_busy", { p: platformName(otherOverlay) })}
            </div>
          </PanelSectionRow>
        )}
        {!canSend && chatMsg && <PanelSectionRow><div style={{ fontSize: 11, color: "#fff" }}>{chatMsg}</div></PanelSectionRow>}
        <PanelSectionRow>
          <ToggleField label={t("overlay_show")}
            description={channelSet ? t("overlay_desc") : t("overlay_need_channel")}
            checked={overlayOn} onChange={toggleOverlay} disabled={!channelSet || !!otherOverlay} bottomSeparator="none" />
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
            {!yt && <PanelSectionRow>
              <ToggleField label={t("show_badges")} checked={!!ov.badges}
                onChange={(v: boolean) => pushOv({ badges: v })} bottomSeparator="none" />
            </PanelSectionRow>}
            {!yt && <PanelSectionRow>
              <ToggleField label={t("third_party_emotes")} checked={!!ov.thirdParty}
                onChange={(v: boolean) => pushOv({ thirdParty: v })} bottomSeparator="none" />
            </PanelSectionRow>}
          </>
        )}
      </PanelSection>
    </>
  );
}

// ── Onglet CONFIG : réglages stream + mises à jour + à propos + déconnexion ──
function RecordLocation() {
  const [loc, setLoc] = useState<any>(null);
  const load = () => call<[], any>("get_record_locations").then(setLoc).catch(() => {});
  useEffect(() => { load(); }, []);
  if (!loc?.options) return null;
  const label = (o: any) => {
    const where = o.internal ? t("record_internal") : o.name;
    return o.free_gb != null ? `${where} — ${t("record_free", { gb: o.free_gb })}` : where;
  };
  return (
    <>
      <PanelSectionRow>
        <Dropdown strDefaultLabel={t("record_location")} selectedOption={loc.selected}
          rgOptions={loc.options.map((o: any) => ({ data: o.id, label: label(o) }))}
          onChange={(e: any) => call<[string], any>("set_record_drive", e.data).then(load).catch(() => {})} />
      </PanelSectionRow>
      <PanelSectionRow>
        <div style={{ fontSize: 11, opacity: 0.75, color: "#fff", lineHeight: 1.5 }}>
          {loc.missing ? t("record_missing", { d: loc.missing }) : t("record_location_desc")}
        </div>
      </PanelSectionRow>
    </>
  );
}

// Délai pendant lequel un live coupé (réseau, Arrêter par erreur, redémarrage)
// peut reprendre au même endroit. Réglage commun aux deux plateformes.
function ResumeWindow() {
  const [sec, setSec] = useState<number | null>(null);
  useEffect(() => {
    call<[], any>("get_resume_window").then((r: any) => setSec(r?.seconds ?? 15)).catch(() => {});
  }, []);
  if (sec === null) return null;
  return (
    <PanelSectionRow>
      <Dropdown strDefaultLabel={t("resume_window")} selectedOption={sec}
        rgOptions={[
          { data: 0, label: t("resume_off") },
          ...[15, 30, 60, 120].map((v) => ({ data: v, label: v < 60 ? `${v} s` : `${v / 60} min` })),
        ]}
        onChange={(e: any) => call<[number], any>("set_resume_window", e.data)
          .then((r: any) => r?.ok && setSec(r.seconds)).catch(() => {})} />
      <div style={{ fontSize: 10, opacity: 0.6, color: "#fff", marginTop: 4 }}>
        {t("resume_desc")}
      </div>
    </PanelSectionRow>
  );
}

function StreamSettings({ platform }: { platform: "twitch" | "youtube" }) {
  const [encoders, setEncoders] = useState<string[]>(["software"]);
  const [steamcord, setSteamcord] = useState(false);
  const [st, setSt] = useState<any>({ resolution: "720p", fps: 30, bitrate: 4500,
    audio_bitrate: 160, keyframe: 2, encoder: "auto", mic: false, record: false });

  useEffect(() => {
    call<[], any>("get_config").then((c: any) => {
      const cur = platform === "youtube" ? c?.youtube?.stream : c?.stream;
      if (cur) setSt((p: any) => ({ ...p, ...cur }));
      setSteamcord(!!c?.steamcord);
    }).catch(() => {});
    call<[], any>("get_encoders").then((e: any) => {
      if (Array.isArray(e?.available)) setEncoders(e.available);
    }).catch(() => {});
  }, []);

  // Applique un réglage et le persiste côté backend (par compte).
  const pushSt = (patch: any) =>
    setSt((prev: any) => { const next = { ...prev, ...patch };
      call("set_stream_settings", next, platform).catch(() => {}); return next; });

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
      {/* Effort x264 : seulement quand l'encodage se fait au processeur. */}
      {(st.encoder === "software" || (st.encoder === "auto"
        && !encoders.includes("nvenc") && !encoders.includes("vaapi"))) && (
        <PanelSectionRow>
          <Dropdown strDefaultLabel={t("effort")} selectedOption={st.effort || "balanced"}
            rgOptions={[
              { data: "light", label: t("effort_light") },
              { data: "balanced", label: t("effort_balanced") },
              { data: "quality", label: t("effort_quality") },
            ]} onChange={(e: any) => pushSt({ effort: e.data })} />
        </PanelSectionRow>
      )}
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
      {/* Où vont les enregistrements : stockage interne, carte SD, disque externe (#1). */}
      <RecordLocation />
      <ResumeWindow />
      {/* Écran pause perso : image déposée à la main depuis le mode Bureau. */}
      <PanelSectionRow>
        <div style={{ fontSize: 11, opacity: 0.75, color: "#fff", lineHeight: 1.5 }}>
          {t("brb_custom_hint")}
        </div>
      </PanelSectionRow>
    </PanelSection>
  );
}

// Auto-update basé sur les releases GitHub (comme le reste de la suite).
function UpdaterSection() {
  const [auto, setAuto] = useState(true);
  const [status, setStatus] = useState<
    "idle" | "checking" | "available" | "uptodate" | "updated" | "installing" | "failed" | "needsrestart">("idle");
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
            // Finir sur « À jour (x) » ne se distinguait pas d'un clic resté
            // sans effet (Steamcord #52, 24/09) : un état à part dit que ça a
            // marché, et quoi faire.
          setCurrent(latest);
          setStatus("updated");
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
    : status === "updated" ? t("upd_done", { v: current })
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
      {status === "updated" ? (
        <PanelSectionRow>
          <div style={{ fontSize: 11, color: "#23a55a", lineHeight: 1.35 }}>{t("upd_done_note", { v: current })}</div>
        </PanelSectionRow>
      ) : null}
      {status === "failed" && updErr ? (
        <PanelSectionRow>
          <div style={{ fontSize: 11, opacity: 0.8, wordBreak: "break-word" }}>{updErr}</div>
        </PanelSectionRow>
      ) : null}
    </PanelSection>
  );
}

// Comptes connectés : une ligne par plateforme (icône, nom, « Se déconnecter »).
// Rangés dans ⚙ plutôt que dans Live : pas de déconnexion par erreur en direct.
function AccountRow({ icon, color, name, onLogout }: any) {
  return (
    <PanelSectionRow>
      <ActionCard color={DANGER} center={false} onClick={onLogout}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, width: "100%", minWidth: 0 }}>
          <span style={{ color, display: "flex", flexShrink: 0 }}>{icon}</span>
          <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis",
            whiteSpace: "nowrap", textAlign: "left", fontWeight: 600 }}>{name}</span>
          <span style={{ display: "flex", alignItems: "center", gap: 4, flexShrink: 0,
            fontSize: 12, opacity: 0.8 }}>
            <IcLogout /> {t("logout_short")}
          </span>
        </div>
      </ActionCard>
    </PanelSectionRow>
  );
}

function AccountsSection() {
  const [tw, setTw] = useState<any>(null);
  const [yt, setYt] = useState<any>(null);
  const load = () => call<[], any>("get_config").then((c: any) => {
    setTw(c?.logged_in ? { name: c?.login ? `@${c.login}` : "Twitch" } : null);
    setYt(c?.youtube?.logged_in ? { name: c?.youtube?.channel || "YouTube" } : null);
  }).catch(() => {});
  useEffect(() => { load(); }, []);
  if (!tw && !yt) return null;
  return (
    <PanelSection title={t("accounts_title")}>
      {tw && <AccountRow icon={<FaTwitch />} color={TWITCH} name={tw.name}
        onLogout={() => call("logout").then(load).catch(() => {})} />}
      {yt && <AccountRow icon={<FaYoutube />} color={YOUTUBE} name={yt.name}
        onLogout={() => call("yt_logout").then(load).catch(() => {})} />}
    </PanelSection>
  );
}

// À propos (bas de l'onglet Config, comme Steamcord).
function AboutSection() {
  const [version, setVersion] = useState("");
  useEffect(() => {
    call<[], string>("get_version").then((v) => setVersion(v || "")).catch(() => {});
  }, []);
  const open = (url: string) => { try { (window as any).SteamClient?.URL?.ExecuteSteamURL?.("steam://openurl/" + url); } catch {} };
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
    </PanelSection>
  );
}

function ConfigSection() {
  return (
    <>
      <UpdaterSection />
      <AccountsSection />
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

const LAST_PLATFORM_KEY = "bonecast_last_platform";

function Content() {
  // Deux plateformes indépendantes : chacune a ses sous-onglets et SES réglages.
  // Seuls les mises à jour et l'« À propos » sont communs (onglet Config).
  // #1 (dreemur-e) : on rouvre sur la dernière plateforme choisie (Twitch ou
  // YouTube) au lieu de toujours Twitch → moins de boutons en plein live.
  // L'onglet ⚙ n'est pas retenu : on y passe, on n'y reste pas.
  const [platform, setPlatform] = useState<"twitch" | "youtube" | "config">(() => {
    try { return localStorage.getItem(LAST_PLATFORM_KEY) === "youtube" ? "youtube" : "twitch"; }
    catch { return "twitch"; }
  });
  const [tab, setTab] = useState<"live" | "watch" | "chat" | "settings">("live");
  const [focus, setFocus] = useState<string | null>(null);
  const tb = (id: string, active: boolean, onClick: () => void, label: any, color?: string) => (
    <TabBtn active={active} focused={focus === id} color={color}
      onClick={onClick}
      onFocus={() => setFocus(id)}
      onBlur={() => setFocus((f: any) => (f === id ? null : f))}>
      {label}
    </TabBtn>
  );
  const pick = (p: "twitch" | "youtube" | "config") => {
    setPlatform(p); setTab("live");
    if (p !== "config") { try { localStorage.setItem(LAST_PLATFORM_KEY, p); } catch {} }
  };
  const accent = platform === "youtube" ? YOUTUBE : TWITCH;
  return (
    <>
      <PanelSection>
        <PanelSectionRow>
          <div style={{ width: "100%" }}>
            <TabRow>
              {tb("p_twitch", platform === "twitch", () => pick("twitch"),
                <><FaTwitch style={{ verticalAlign: "-0.125em" }} /> Twitch</>)}
              {tb("p_youtube", platform === "youtube", () => pick("youtube"),
                <><FaYoutube style={{ verticalAlign: "-0.125em" }} /> YouTube</>, YOUTUBE)}
              {tb("p_config", platform === "config", () => pick("config"), <IcGear />, "#8e9297")}
            </TabRow>
            {platform !== "config" && (
              <TabRow>
                {tb("t_live", tab === "live", () => setTab("live"),
                  <><IcBroadcast /> {t("tab_live")}</>, accent)}
                {platform === "twitch" && tb("t_watch", tab === "watch", () => setTab("watch"),
                  <><IcBroadcast /> {t("tab_watch")}</>)}
                {tb("t_chat", tab === "chat", () => setTab("chat"),
                  <><IcChat /> {t("tab_chat")}</>, accent)}
                {tb("t_settings", tab === "settings", () => setTab("settings"),
                  <><IcSliders /> {t("tab_settings")}</>, accent)}
              </TabRow>
            )}
          </div>
        </PanelSectionRow>
      </PanelSection>
      {platform === "twitch" && tab === "live" && <LiveSection />}
      {platform === "twitch" && tab === "watch" && <WatchSection />}
      {platform === "twitch" && tab === "chat" && <ChatSection key="tw-chat" platform="twitch" />}
      {platform === "twitch" && tab === "settings" && <StreamSettings key="tw" platform="twitch" />}
      {platform === "youtube" && tab === "live" && <YouTubeSection />}
      {platform === "youtube" && tab === "chat" && <ChatSection key="yt-chat" platform="youtube" />}
      {platform === "youtube" && tab === "settings" && <StreamSettings key="yt" platform="youtube" />}
      {platform === "config" && <ConfigSection />}
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

function notify(data: { title?: string; body: string; duration?: number; clickKey?: string; onClick?: () => void; urgent?: boolean }): boolean {
  // Une alerte de live perdu doit sortir même si le mode streamer est forcé :
  // sinon l'utilisateur ne sait jamais qu'il n'est plus à l'antenne.
  if (!data.urgent && streamerActive()) {
    setTimeout(() => notify(data), STREAMER_RETRY_MS);
    return true;
  }
  try {
    if (data.clickKey && data.onClick && notifyClickable("bonecast", data.clickKey,
      data.title || "BoneCast", data.body, data.onClick)) return true;
    const App = (window as any).App;
    const steamid = App?.GetCurrentUser?.()?.strSteamID || App?.m_CurrentUser?.strSteamID || "";
    // steamid OBLIGATOIRE : sans lui l'entrée est malformée et fait planter le
    // panneau de notifs Steam → mieux vaut ne rien notifier.
    const notifications = (window as any).SteamClient?.ClientNotifications;
    const display = notifications?.DisplayClientNotification;
    if (!steamid || typeof display !== "function") return false;
    display.call(notifications,
      1,
      JSON.stringify({ title: data.title || "BoneCast", body: data.body, state: "active", steamid }),
      () => {},
    );
    return true;
  } catch (e) { console.error("[BoneCast] notify failed", e); return false; }
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
      const body = notice.reload
        ? `Update ${notice.version} installed — it becomes active the next time Steam starts.`
        : `Update ${notice.version} could not be installed automatically. `
          + "Install it from Decky → Developer → Install plugin from URL.";
      notify({
        title: "BoneCast",
        // Deux avis distincts : la maj n'a pas pu s'écrire (il faut la poser à
        // la main), ou elle est écrite mais pas chargée — le backend n'a pas le
        // droit de redémarrer le loader, donc elle prendra effet au prochain
        // démarrage de Steam. Annoncer le second comme un échec serait faux.
        body,
        clickKey: `update:${notice.version}:${notice.reload ? "installed" : "failed"}`,
        onClick: () => {
          Navigation.CloseSideMenus();
          showModal(<ConfirmModal
            strTitle="BoneCast update"
            strDescription={body}
            bAlertDialog={!!notice.reload}
            strOKButtonText={notice.reload ? "OK" : "Open release"}
            onOK={notice.reload ? undefined : () => {
              const url = `https://github.com/Necrosiak/BoneCast/releases/tag/v${encodeURIComponent(notice.version)}`;
              (window as any).SteamClient?.URL?.ExecuteSteamURL?.("steam://openurl/" + url);
            }}
          />);
        },
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
  let alertInFlight = false;
  let lastShownAlertId = 0;
  const pollLive = async () => {
    try {
      const st: any = await call("get_stream_status");
      setLiveSource("bonecast", !!st?.streaming);
    } catch {}
    if (alertInFlight) return;
    alertInFlight = true;
    try {
      const alert: any = await call("get_stream_alert");
      if (!alert?.id) return;
      if (lastShownAlertId === alert.id || notify({
        title: "BoneCast",
        body: t("stream_stopped_alert", { p: platformName(alert.platform) }),
        urgent: true,
      })) {
        lastShownAlertId = alert.id;
        await call("ack_stream_alert", alert.id);
      }
    } catch (e) { console.error("[BoneCast] stream alert failed", e); }
    finally { alertInFlight = false; }
  };
  pollLive();
  const liveTimer = setInterval(pollLive, 5000);
  return {
    name: "BoneCast",
    title: <div className={staticClasses.Title}>BoneCast</div>,
    icon: <BoneCastIcon />,
    content: <Content />,
    onDismount() {
      clearInterval(liveTimer);
      setLiveSource("bonecast", false);
      clearClickableNotifications("bonecast");
    },
  };
});
