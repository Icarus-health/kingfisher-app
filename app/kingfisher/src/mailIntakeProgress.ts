import type {MailIntakeAccount, MailIntakeStatus} from "./api";

const count = (value: number | null | undefined) => Number.isFinite(value) ? Math.max(0, value ?? 0) : 0;
const percentage = (value: number, total: number, unfinished: boolean) => total > 0
  ? Math.min(unfinished ? 99 : 100, Math.floor(100 * value / total)) : null;

// Totals describe enumerated work in each folder, never a difference between UIDs.
export function deriveIntakeProgress(account: MailIntakeAccount) {
  const sums = account.folders.reduce((result, folder) => ({
    counted: result.counted + count(folder.total),
    captured: result.captured + count(folder.captured),
    duplicates: result.duplicates + count(folder.duplicates),
    failed: result.failed + count(folder.failed),
    filtered: result.filtered + count(folder.filtered),
    pending: result.pending + count(folder.pending),
    livePending: result.livePending + count(folder.live_pending),
    liveFailed: result.liveFailed + count(folder.live_failed),
    liveFiltered: result.liveFiltered + count(folder.live_filtered),
    analyzed: result.analyzed + count(folder.analyzed),
    analysisFailed: result.analysisFailed + count(folder.analysis_failed),
    deferred: result.deferred + count(folder.deferred),
    excluded: result.excluded + count(folder.excluded),
    categorized: result.categorized + count(folder.categorized),
    categoriesPending: result.categoriesPending + count(folder.categories_pending),
    categoriesFailed: result.categoriesFailed + count(folder.categories_failed),
    categoriesDeferred: result.categoriesDeferred + count(folder.categories_deferred),
    categoriesUnverified: result.categoriesUnverified + count(folder.categories_unverified),
    categoriesFailedBy: Object.entries(folder.categories_failed_by ?? {}).reduce((reasons, [code, number]) => {
      if (typeof code === "string") reasons[code] = (reasons[code] ?? 0) + count(number);
      return reasons;
    }, {...result.categoriesFailedBy}),
  }), {counted: 0, captured: 0, duplicates: 0, failed: 0, filtered: 0, pending: 0, livePending: 0, liveFailed: 0, liveFiltered: 0,
    analyzed: 0, analysisFailed: 0, deferred: 0, excluded: 0, categorized: 0, categoriesPending: 0, categoriesFailed: 0,
    categoriesDeferred: 0, categoriesUnverified: 0, categoriesFailedBy: {} as Record<string, number>});
  const inventoryComplete = account.folders.length > 0 && account.folders.every(folder =>
    folder.inventory_complete && folder.total !== null && Number.isFinite(folder.total));
  const total = inventoryComplete ? sums.counted : null;
  const sources = sums.captured + sums.duplicates;
  // Exclusions are already captured sources later dismissed or withdrawn. Ausgefilterte (Newsletter) sind gelesen und
  // bewusst beiseitegelegt; ohne sie stünde ein Postfach mit einem Newsletter für immer auf „4 von 5“.
  const processed = sources + sums.filtered;
  const analysisSources = Math.max(0, sources - sums.excluded);
  const categoriesKnown = account.folders.length > 0 && account.folders.every(folder =>
    Number.isFinite(folder.categorized) && Number.isFinite(folder.categories_pending) && Number.isFinite(folder.categories_failed));
  const captureUnfinished = !inventoryComplete || sums.pending > 0 || sums.failed > 0 || processed < sums.counted;
  const analysisUnfinished = sums.deferred > 0 || sums.analysisFailed > 0 || sums.analyzed < analysisSources ||
    !categoriesKnown || sums.categoriesPending > 0 || sums.categoriesFailed > 0 || sums.categoriesDeferred > 0 ||
    sums.categoriesUnverified > 0 || sums.categorized < analysisSources;
  const retryAvailable = sums.failed > 0 || sums.liveFailed > 0 || sums.analysisFailed > 0 ||
    sums.categoriesFailed > 0 || sums.categoriesUnverified > 0 || Boolean(account.error);
  const complete = account.started && account.connected && !account.error && inventoryComplete &&
    !captureUnfinished && !analysisUnfinished && sums.livePending === 0;
  const stage = !account.connected ? "disconnected" : !account.started ? "ready" : account.paused ? "paused"
    : account.error ? "error" : !inventoryComplete ? "inventory" : account.history_waiting_for_analysis ? "waiting_analysis"
    : captureUnfinished || sums.livePending > 0 ? "capture"
    : analysisUnfinished ? "analysis" : "current";
  return {...sums, total, sources, analysisSources, categoriesKnown, processed, inventoryComplete, complete, stage, retryAvailable,
    capturePercent: total === null ? null : percentage(processed, total, captureUnfinished),
    analysisPercent: total === null || !categoriesKnown ? null
      : percentage(sums.analyzed + sums.categorized, 2 * analysisSources, analysisUnfinished),
    overallPercent: total === null ? null : percentage(processed + sums.analyzed + sums.categorized, total + 2 * analysisSources, !complete)};
}

// Reads, actions and visibility transitions share one queue and ignore stale results.
export function watchMailIntake({read, onStatus, onError, visible = true}: {
  read: (signal: AbortSignal) => Promise<MailIntakeStatus>;
  onStatus: (status: MailIntakeStatus) => void;
  onError: (kind: "status" | "action", error: unknown) => void;
  visible?: boolean;
}) {
  let stopped = false;
  let shown = visible;
  let generation = 0;
  let actionBusy = false;
  let actionController: AbortController | undefined;
  let request: {controller: AbortController; done: Promise<void>} | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  function schedule() {
    clearTimeout(timer);
    if (!stopped && shown && !actionBusy && !request) timer = setTimeout(refresh, 3000);
  }
  function refresh(): Promise<void> {
    if (stopped || !shown || actionBusy || request) return Promise.resolve();
    clearTimeout(timer);
    const version = generation;
    const current = {controller: new AbortController(), done: Promise.resolve()};
    request = current;
    current.done = (async () => {
      try {
        const next = await read(current.controller.signal);
        if (!stopped && shown && version === generation) onStatus(next);
      } catch (error) {
        if (!stopped && shown && version === generation && !current.controller.signal.aborted) onError("status", error);
      } finally {
        if (request === current) request = undefined;
        schedule();
      }
    })();
    return current.done;
  }
  function setVisible(next: boolean) {
    if (shown === next || stopped) return;
    shown = next;
    generation++;
    clearTimeout(timer);
    if (!shown) request?.controller.abort();
    else void refresh();
  }
  async function execute<T>(action: (signal: AbortSignal) => Promise<T>, publish?: (value: T) => void): Promise<T | undefined> {
    if (stopped || actionBusy) return;
    actionBusy = true;
    clearTimeout(timer);
    generation++;
    request?.controller.abort();
    await request?.done;
    if (stopped) {actionBusy = false; return;}
    const controller = new AbortController();
    actionController = controller;
    try {
      const next = await action(controller.signal);
      if (stopped || controller.signal.aborted) return;
      publish?.(next);
      return next;
    } catch (error) {
      if (!stopped && !controller.signal.aborted) onError("action", error);
    } finally {
      actionBusy = false;
      if (actionController === controller) actionController = undefined;
      schedule();
    }
  }
  async function run(action: (signal: AbortSignal) => Promise<MailIntakeStatus>) {
    return (await execute(action, onStatus)) !== undefined;
  }
  function inspect<T>(readPreview: (signal: AbortSignal) => Promise<T>) {
    return execute(readPreview);
  }
  function stop() {
    stopped = true;
    generation++;
    clearTimeout(timer);
    request?.controller.abort();
    actionController?.abort();
  }
  void refresh();
  return {refresh, setVisible, run, inspect, stop};
}
