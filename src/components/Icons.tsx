// Icônes SVG monochromes : remplacent les emojis couleur pour coller à l'UI
// SteamOS (même passe que Steamcord v1.16.1). Bootstrap Icons via react-icons
// (déjà en dép, tree-shaké) : 1em / currentColor → hérite taille et couleur.
import {
  BsArrowRepeat, BsBoxArrowRight, BsBroadcast, BsChatDots, BsController,
  BsFilm, BsGear, BsGithub, BsKey, BsMic, BsMicMute, BsSave, BsSend, BsSliders,
} from "react-icons/bs";

type IcProps = { size?: number | string; color?: string; style?: any };

const mk = (C: any) => (p: IcProps = {}) => (
  <C size={p.size} color={p.color}
     style={{ verticalAlign: "-0.125em", flexShrink: 0, ...(p.style || {}) }} />
);

export const IcBroadcast = mk(BsBroadcast);
export const IcChat = mk(BsChatDots);
export const IcController = mk(BsController);
export const IcFilm = mk(BsFilm);
export const IcGear = mk(BsGear);
export const IcSliders = mk(BsSliders);
export const IcGithub = mk(BsGithub);
export const IcKey = mk(BsKey);
export const IcLogout = mk(BsBoxArrowRight);
export const IcMic = mk(BsMic);
export const IcMicMute = mk(BsMicMute);
export const IcRefresh = mk(BsArrowRepeat);
export const IcSave = mk(BsSave);
export const IcSend = mk(BsSend);

// Icône du plugin (barre du QAM) : un os + un signal de diffusion, le nom
// BoneCast en dessin. Fond transparent, tracé en currentColor → blanc comme les
// icônes voisines ; plus le logo Twitch depuis que YouTube est là aussi. Le
// viewBox est serré sur le dessin : en 0 0 24 24, les marges la rendaient
// nettement plus petite que ses voisines, qui remplissent leur cadre.
export const BoneCastIcon = () => (
  <svg viewBox="3.1 3.1 17.8 18.8" width="1em" height="1em" fill="none" stroke="currentColor"
    strokeWidth="2.3" strokeLinecap="round" aria-hidden="true">
    <line x1="7" y1="18" x2="17" y2="18" />
    <g fill="currentColor" stroke="none">
      <circle cx="5.6" cy="16.6" r="2" /><circle cx="5.6" cy="19.4" r="2" />
      <circle cx="18.4" cy="16.6" r="2" /><circle cx="18.4" cy="19.4" r="2" />
      <circle cx="12" cy="8.5" r="1.6" />
    </g>
    <path d="M8.6 5.1a4.8 4.8 0 0 0 0 6.8" /><path d="M15.4 5.1a4.8 4.8 0 0 1 0 6.8" />
  </svg>
);
