import { call } from "@decky/api";
import { BoneCastIcon } from "./components/Icons";
import { registerSteamMenu } from "./steamMenu";

// The BoneCast entry in Steam's main menu can be turned off; the Quick Access
// panel stays available either way (same option as Steamcord #86).
const ENABLED_KEY = "BONECAST_MENU_ENTRY";
let unregister: (() => void) | undefined;

const register = () => registerSteamMenu({ id: "bonecast", label: "BoneCast", route: "/bonecast", icon: <BoneCastIcon />, order: 30 });

const loadBackend = () => call<[], "on" | "off" | null>("get_menu_entry");
const saveBackend = (on: boolean) => call<[boolean], unknown>("set_menu_entry", on);

export function menuEntryEnabled(): boolean {
  try { return localStorage.getItem(ENABLED_KEY) !== "0"; } catch { return true; }
}

const apply = (on: boolean) => {
  if (on && !unregister) unregister = register();
  else if (!on && unregister) { unregister(); unregister = undefined; }
};

const storeLocal = (on: boolean) => {
  try { localStorage.setItem(ENABLED_KEY, on ? "1" : "0"); } catch {}
};

export function setMenuEntryEnabled(on: boolean) {
  storeLocal(on);
  // The backend copy is what counts at the next start (Steamcord #86):
  // Steam's localStorage can come back with an older value after a restart.
  saveBackend(on).catch(() => {});
  apply(on);
}

let started = 0;

export function patchMenu(): () => void {
  const run = ++started;
  loadBackend()
    .then((menu) => {
      if (run !== started) return;
      if (menu === "on" || menu === "off") {
        storeLocal(menu === "on");
        apply(menu === "on");
      } else {
        // First start with this version: keep the local choice and save it.
        const on = menuEntryEnabled();
        saveBackend(on).catch(() => {});
        apply(on);
      }
    })
    .catch(() => { if (run === started) apply(menuEntryEnabled()); });
  return () => { started++; unregister?.(); unregister = undefined; };
}
