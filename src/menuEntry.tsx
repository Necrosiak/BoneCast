import { BoneCastIcon } from "./components/Icons";
import { registerSteamMenu } from "./steamMenu";

// The BoneCast entry in Steam's main menu can be turned off; the Quick Access
// panel stays available either way (same option as Steamcord #86).
const ENABLED_KEY = "BONECAST_MENU_ENTRY";
let unregister: (() => void) | undefined;

const register = () => registerSteamMenu({ id: "bonecast", label: "BoneCast", route: "/bonecast", icon: <BoneCastIcon />, order: 30 });

export function menuEntryEnabled(): boolean {
  try { return localStorage.getItem(ENABLED_KEY) !== "0"; } catch { return true; }
}

export function setMenuEntryEnabled(on: boolean) {
  try { localStorage.setItem(ENABLED_KEY, on ? "1" : "0"); } catch {}
  if (on && !unregister) unregister = register();
  else if (!on && unregister) { unregister(); unregister = undefined; }
}

export function patchMenu(): () => void {
  if (menuEntryEnabled() && !unregister) unregister = register();
  return () => { unregister?.(); unregister = undefined; };
}
