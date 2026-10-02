import type { GoogleSession } from "./api";

export const GOOGLE_SIGN_IN_LIMIT_MS = 10 * 60 * 1000;

// One request at a time; disposed or terminal flows cannot publish late responses.
export function watchGoogleSignIn({read, onSession, onError, onTimeout}: {
  read: () => Promise<GoogleSession>;
  onSession: (session: GoogleSession) => void;
  onError: () => void;
  onTimeout: () => void;
}) {
  let stopped = false;
  let inFlight = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const deadline = setTimeout(() => { stop(); onTimeout(); }, GOOGLE_SIGN_IN_LIMIT_MS);
  function stop() {
    stopped = true;
    clearTimeout(timer);
    clearTimeout(deadline);
  }
  async function refresh() {
    if (stopped || inFlight) return;
    clearTimeout(timer);
    inFlight = true;
    try {
      const next = await read();
      if (stopped) return;
      if (next.status !== "waiting" && next.status !== "processing") stop();
      onSession(next);
    } catch {
      if (!stopped) onError();
    } finally {
      inFlight = false;
      if (!stopped) timer = setTimeout(refresh, 2500);
    }
  }
  void refresh();
  return {refresh, stop};
}
