// Icônes SVG monochromes : remplacent les emojis couleur pour coller à l'UI
// SteamOS (même passe que Steamcord v1.16.1). Bootstrap Icons via react-icons
// (déjà en dép, tree-shaké) : 1em / currentColor → hérite taille et couleur.
import {
  BsArrowRepeat, BsBoxArrowRight, BsBroadcast, BsChatDots, BsController,
  BsFilm, BsGithub, BsKey, BsMic, BsMicMute, BsSave, BsSend,
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
export const IcGithub = mk(BsGithub);
export const IcKey = mk(BsKey);
export const IcLogout = mk(BsBoxArrowRight);
export const IcMic = mk(BsMic);
export const IcMicMute = mk(BsMicMute);
export const IcRefresh = mk(BsArrowRepeat);
export const IcSave = mk(BsSave);
export const IcSend = mk(BsSend);
