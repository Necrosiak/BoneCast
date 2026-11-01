// The route navigates back before the modal opens: its unmount must not cancel
// the opening. The plugin owns this timer and cancels it only on unload.
export function deferredView(open: () => void) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  return {
    schedule() {
      if (timer !== undefined) return;
      timer = setTimeout(() => { timer = undefined; open(); }, 100);
    },
    cancel() { if (timer !== undefined) clearTimeout(timer); timer = undefined; },
  };
}
