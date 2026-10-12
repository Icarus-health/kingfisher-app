/** Nur aus der bewussten Connect-Aktion, niemals aus Poll/Effect/Neustart aufrufen. */
export function requestMacCalendarPermission(state: { enabled: boolean; authorize: boolean; generation: number },
  window: unknown = globalThis): boolean {
  if (state.enabled !== true || state.authorize !== true || !Number.isSafeInteger(state.generation) || state.generation < 0) return false;
  try {
    const bridge = (window as { webkit?: { messageHandlers?: { kingfisher?: { postMessage: (body: unknown) => void } } } })?.webkit?.messageHandlers?.kingfisher;
    if (!bridge || typeof bridge.postMessage !== "function") return false;
    bridge.postMessage({ aktion: "kalenderFreigeben", generation: state.generation });
    return true;
  } catch { return false; }
}
