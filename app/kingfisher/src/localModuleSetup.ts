export type LocalModuleNativeStatus = 'checking' | 'downloading' | 'installing' | 'verifying' | 'ready' | 'cancelled' | 'failed' | 'unavailable';
export type LocalModuleMessage = {aktion: 'lokaleWerkzeugeStatus' | 'lokaleWerkzeugeEinrichten' | 'lokaleWerkzeugeAbbrechen'; generation: number};
export type LocalModuleSetupState = {phase: LocalModuleNativeStatus | 'unsupported' | 'unknown' | 'cancelling'; generation: number; pending: boolean};
type Timers = {set: (callback: () => void, delay: number) => number; clear: (id: number) => void};
const statuses = new Set(['checking', 'downloading', 'installing', 'verifying', 'ready', 'cancelled', 'failed', 'unavailable']);
const actions = new Set(['lokaleWerkzeugeStatus', 'lokaleWerkzeugeEinrichten', 'lokaleWerkzeugeAbbrechen']);
const safeGeneration = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
const stage = {checking: 0, downloading: 1, installing: 2, verifying: 3};
// One unresolved setup identity survives pane teardown; no paths, credentials,
// questions or installed-state claim are retained, and no browser storage is used.
let pendingGeneration: number | null = null;
let generationSequence = Date.now();
function nextGeneration() {
  if (generationSequence >= Number.MAX_SAFE_INTEGER) throw new Error('Generation exhausted');
  return ++generationSequence;
}
export const emptyLocalModuleSetup: LocalModuleSetupState = {phase: 'checking', generation: 0, pending: false};
export const localModuleCanStart = (state: LocalModuleSetupState) => !state.pending && ['unavailable', 'cancelled', 'failed'].includes(state.phase);
export function localModuleEvent(value: unknown): {generation: number; status: LocalModuleNativeStatus} | null {
  try {
    if (!value || typeof value !== 'object' || Array.isArray(value) || Reflect.ownKeys(value).length !== 2) return null;
    const event = value as Record<string, unknown>;
    if (!Object.hasOwn(event, 'generation') || !Object.hasOwn(event, 'status') || !safeGeneration(event.generation) || typeof event.status !== 'string' || !statuses.has(event.status)) return null;
    return {generation: event.generation, status: event.status as LocalModuleNativeStatus};
  } catch {return null;}
}
export function localModulesPost(message: LocalModuleMessage, environment: unknown = globalThis): boolean {
  try {
    if (!safeGeneration(message.generation) || !actions.has(message.aktion)) return false;
    const bridge = (environment as {webkit?: {messageHandlers?: {kingfisher?: {postMessage?: (message: LocalModuleMessage) => void}}}})?.webkit?.messageHandlers?.kingfisher;
    if (typeof bridge?.postMessage !== 'function') return false;
    bridge.postMessage({aktion: message.aktion, generation: message.generation});
    return true;
  } catch {return false;}
}
export function createLocalModuleSetup({post, changed, timers = {set: (callback, delay) => window.setTimeout(callback, delay), clear: id => window.clearTimeout(id)}}: {
  post: (message: LocalModuleMessage) => boolean; changed: (state: LocalModuleSetupState) => void; timers?: Timers;
}) {
  let state: LocalModuleSetupState = {...emptyLocalModuleSetup, generation: pendingGeneration ?? nextGeneration(), pending: pendingGeneration !== null};
  let alive = true, settled = false, cancelRequested = false, acknowledged = false, timerVersion = 0, timer: number | undefined;
  const update = (patch: Partial<LocalModuleSetupState>) => {state = {...state, ...patch}; if (alive) changed({...state});};
  const clearTimer = () => {timerVersion++; if (timer !== undefined) timers.clear(timer); timer = undefined;};
  function wait() {
    clearTimer(); const version = timerVersion, generation = state.generation;
    timer = timers.set(() => {
      if (!alive || version !== timerVersion || generation !== state.generation) return;
      timer = undefined; update({phase: state.pending || acknowledged ? 'unknown' : 'unsupported'});
    }, state.pending || acknowledged ? 30000 : 3000);
  }
  function send(aktion: LocalModuleMessage['aktion']) {
    try {return post({aktion, generation: state.generation});} catch {return false;}
  }
  return {
    probe() {
      if (!alive) return;
      if (!state.pending && pendingGeneration !== null) {state = {...state, generation: pendingGeneration, pending: true}; settled = false; cancelRequested = false;}
      if (!state.pending) {state.generation = nextGeneration(); settled = false; cancelRequested = false; acknowledged = false;}
      update({phase: 'checking'}); wait();
      if (!send('lokaleWerkzeugeStatus')) {clearTimer(); update({phase: state.pending ? 'unknown' : 'unsupported'});}
    },
    start() {
      if (!alive || !localModuleCanStart(state)) return;
      if (pendingGeneration !== null) {
        settled = false; cancelRequested = false;
        update({generation: pendingGeneration, pending: true, phase: 'unknown'}); this.probe(); return;
      }
      settled = false; cancelRequested = false; pendingGeneration = nextGeneration();
      update({generation: pendingGeneration, pending: true, phase: 'checking'}); wait();
      if (!send('lokaleWerkzeugeEinrichten')) {clearTimer(); update({phase: 'unknown'});}
    },
    cancel() {
      if (!alive || !state.pending || cancelRequested && state.phase === 'cancelling') return;
      cancelRequested = true; update({phase: 'cancelling'}); wait();
      if (!send('lokaleWerkzeugeAbbrechen')) {clearTimer(); update({phase: 'unknown'});}
    },
    event(value: unknown) {
      const event = localModuleEvent(value);
      if (!alive || settled || !event || event.generation !== state.generation) return;
      acknowledged = true;
      if (event.status in stage) {
        if (cancelRequested) return;
        if (state.phase in stage && stage[event.status as keyof typeof stage] < stage[state.phase as keyof typeof stage]) return;
        if (event.status !== 'checking') pendingGeneration = state.generation;
        update({phase: event.status, pending: state.pending || event.status !== 'checking'}); wait();
      } else {
        clearTimer(); settled = true;
        if (pendingGeneration === state.generation) pendingGeneration = null;
        update({phase: event.status, pending: false});
      }
    },
    dispose() {
      if (!alive) return;
      alive = false; clearTimer();
      if (state.pending) send('lokaleWerkzeugeAbbrechen');
    },
  };
}
export type LocalModuleSetupSession = ReturnType<typeof createLocalModuleSetup>;
