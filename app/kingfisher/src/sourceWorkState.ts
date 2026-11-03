import {ApiError, type api, type LocalSourceReference, type LocalSourceRun, type LocalSourceStart} from './api';

type Client = Pick<typeof api, 'localSourceStatus' | 'prepareLocalSource' | 'startLocalSource' | 'localSourceRun' | 'cancelLocalSource'>;
type Timer = {set: (callback: () => Promise<void>, delay: number) => number; clear: (id: number) => void};
export type SourceWorkState = {
  available: boolean; externalBusy: boolean;
  phase: 'idle' | 'preparing' | 'starting' | 'uncertain' | 'cancelling';
  error: 'source_changed' | 'prepare' | 'start_unknown' | 'poll' | 'cancel' | 'busy' | 'unavailable' | 'capacity' | 'expired' | null;
  pendingQuestion: string | null;
  run: LocalSourceRun | null;
};
export const emptySourceWorkState: SourceWorkState = {available: false, externalBusy: false, phase: 'idle', error: null, pendingQuestion: null, run: null};
const occupied = (run: LocalSourceRun | null) => !!run && (run.status === 'running' || run.execution_pending);
const same = (left: LocalSourceReference, right: LocalSourceReference) => left.id === right.id && left.fingerprint === right.fingerprint;
export const sourceWorkOccupied = (state: SourceWorkState) => state.phase !== 'idle' || occupied(state.run);
export const visibleSourceWorkRun = (state: SourceWorkState, source: LocalSourceReference) => state.run && same(state.run.source, source) ? state.run : null;
export const sourceWorkEnter = (event: {key: string; shiftKey?: boolean; isComposing?: boolean; keyCode?: number}) => event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229;
function withoutResult(run: LocalSourceRun): LocalSourceRun {
  const {text: _text, evidence: _evidence, coverage: _coverage, label: _label, verified: _verified, ...rest} = run;
  return rest;
}

type PendingAttempt = {payload: LocalSourceStart; expires: number};
// Unknown admissions survive closing a pane, for at most the controller's
// retention window. A full registry refuses new work instead of forgetting an
// unresolved confirmation and risking a duplicate. No results are stored here.
const pendingAttempts = new Map<string, PendingAttempt>();
const pendingKey = (source: LocalSourceReference) => JSON.stringify([source.id, source.fingerprint]);
function prunePending() {
  for (const [key, entry] of pendingAttempts) if (entry.expires <= Date.now()) pendingAttempts.delete(key);
}
function pendingFor(source: LocalSourceReference) {
  prunePending(); return pendingAttempts.get(pendingKey(source));
}
function forgetPending(entry: PendingAttempt) {
  const key = pendingKey({id: entry.payload.source_id, fingerprint: entry.payload.source_fingerprint});
  if (pendingAttempts.get(key) === entry) pendingAttempts.delete(key);
}

/** Owns one pane's bounded, in-memory review. A failed start is retried with
 * the identical confirmation; a second review must never duplicate unknown work. */
export class SourceWorkSession {
  private state: SourceWorkState = {...emptySourceWorkState};
  private alive = true;
  private actionBusy = false;
  private polling = false;
  private version = 0;
  private statusVersion = 0;
  private timer: number | undefined;
  private attempt: PendingAttempt | null = null;
  constructor(private client: Client, private current: () => LocalSourceReference,
    private changed: (state: SourceWorkState) => void,
    private timers: Timer = {set: (callback, delay) => window.setTimeout(() => {void callback();}, delay), clear: id => window.clearTimeout(id)}) {}
  private update(change: Partial<SourceWorkState>) {
    this.state = {...this.state, ...change};
    if (this.alive) this.changed(this.state);
  }
  private restorePending() {
    const pending = pendingFor(this.current());
    if (!pending) return false;
    this.attempt = pending;
    this.update({phase: 'uncertain', pendingQuestion: pending.payload.question, error: 'start_unknown'});
    return true;
  }
  async open() {
    if (this.state.phase === 'idle' && !occupied(this.state.run)) this.restorePending();
    const version = ++this.statusVersion;
    try {
      const status = await this.client.localSourceStatus();
      if (!this.alive || version !== this.statusVersion) return;
      this.update({available: status.status === 'configured', externalBusy: status.runtime?.busy === true, error: this.attempt ? 'start_unknown' : null});
    } catch (error) {
      if (!this.alive || version !== this.statusVersion) return;
      this.update({available: this.state.available && !(error instanceof ApiError && error.status === 404), error: this.state.available ? 'unavailable' : null});
    }
  }
  async start(question: string) {
    if (!this.alive || this.actionBusy || sourceWorkOccupied(this.state) || !this.state.available || !question.trim() || question.length > 1200) return;
    if (this.restorePending()) return;
    if (this.state.externalBusy) {this.update({error: 'busy'}); return;}
    this.actionBusy = true; this.clearTimer(); const version = ++this.version;
    const source = {...this.current()};
    this.update({phase: 'preparing', run: null, error: null});
    try {
      const review = await this.client.prepareLocalSource(source.id, question);
      if (!this.alive) return;
      if (version !== this.version || !same(source, this.current()) || !same(source, review.source)) {
        this.update({phase: 'idle', error: 'source_changed'}); return;
      }
      if (this.restorePending()) return;
      if (pendingAttempts.size >= 16) {this.update({phase: 'idle', error: 'capacity'}); return;}
      const bytes = new Uint8Array(16); globalThis.crypto.getRandomValues(bytes);
      const payload: LocalSourceStart = {source_id: source.id, question, source_fingerprint: source.fingerprint, review_binding: review.review_binding, consent: true,
        idempotency_key: Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')};
      this.attempt = {payload, expires: Date.now() + 300000};
      pendingAttempts.set(pendingKey(source), this.attempt);
      this.update({pendingQuestion: question});
      await this.sendAttempt();
    } catch {
      if (this.alive) this.update({phase: 'idle', error: 'prepare'});
    } finally {this.actionBusy = false; this.schedule();}
  }
  async retryStart() {
    if (!this.alive || this.actionBusy || !this.attempt || this.state.phase !== 'uncertain') return;
    if (this.attempt.expires <= Date.now()) {
      forgetPending(this.attempt); this.attempt = null;
      this.update({phase: 'idle', error: 'expired', pendingQuestion: null}); return;
    }
    if (!same(this.current(), {id: this.attempt.payload.source_id, fingerprint: this.attempt.payload.source_fingerprint})) {
      this.update({error: 'source_changed'}); return;
    }
    this.actionBusy = true;
    try {await this.sendAttempt();} finally {this.actionBusy = false; this.schedule();}
  }
  private async sendAttempt() {
    const pending = this.attempt!, attempt = pending.payload;
    this.update({phase: 'starting', error: null});
    try {
      const run = await this.client.startLocalSource(attempt);
      if (!run || !/^[a-f0-9]{32}$/.test(run.id) || !same(run.source, {id: attempt.source_id, fingerprint: attempt.source_fingerprint})) throw new Error('Unconfirmed start');
      forgetPending(pending); this.attempt = null;
      if (!this.alive) {if (occupied(run)) void this.client.cancelLocalSource(run.id).catch(() => undefined); return;}
      this.update({phase: 'idle', pendingQuestion: null, run: same(run.source, this.current()) ? run : {...withoutResult(run), status: 'stale'}, externalBusy: false});
      if (!same(run.source, this.current()) && occupied(run)) {
        // Release the action guard only for revocation of the known old run.
        this.actionBusy = false; await this.cancel(); this.actionBusy = true;
      }
    } catch {
      // HTTP failures can follow an admitted request (for example during an
      // update). They too retain the exact key instead of preparing new work.
      if (this.alive) this.update({phase: 'uncertain', error: 'start_unknown'});
    }
  }
  sourceChanged() {
    if (this.attempt && !same(this.current(), {id: this.attempt.payload.source_id, fingerprint: this.attempt.payload.source_fingerprint})) this.update({error: 'source_changed'});
    const run = this.state.run;
    if (run && !same(run.source, this.current())) {
      this.update({run: {...withoutResult(run), status: 'stale'}, error: 'source_changed'});
      if (occupied(run)) void this.cancel(); else this.clearTimer();
    }
  }
  async cancel() {
    const run = this.state.run;
    if (!this.alive || this.actionBusy || !occupied(run)) return;
    this.actionBusy = true; this.clearTimer(); const version = ++this.version;
    this.update({phase: 'cancelling', run: {...withoutResult(run!), status: 'cancelled', execution_pending: true}, error: null});
    try {
      const result = await this.client.cancelLocalSource(run!.id);
      if (this.alive && version === this.version) this.update({run: withoutResult(result), phase: 'idle'});
    } catch {
      if (this.alive && version === this.version) this.update({phase: 'idle', error: 'cancel'});
    } finally {this.actionBusy = false; this.schedule();}
  }
  private clearTimer() {
    if (this.timer !== undefined) this.timers.clear(this.timer);
    this.timer = undefined;
  }
  private schedule() {
    this.clearTimer();
    if (!this.alive || this.actionBusy || this.polling || !this.state.run || !(occupied(this.state.run) || this.state.run.status === 'completed')) return;
    this.timer = this.timers.set(() => this.poll(), occupied(this.state.run) ? 1500 : 5000);
  }
  private async poll() {
    if (!this.alive || this.polling || this.actionBusy || !this.state.run) return;
    this.clearTimer(); this.polling = true;
    const version = this.version, id = this.state.run.id;
    try {
      const result = await this.client.localSourceRun(id);
      if (!this.alive || version !== this.version || this.state.run?.id !== id) return;
      const current = same(result.source, this.current());
      this.update({run: current ? result : {...withoutResult(result), status: 'stale'}, error: current ? null : 'source_changed'});
      if (!current && occupied(result)) void this.cancel();
    } catch (error) {
      if (this.alive && version === this.version && this.state.run?.id === id) {
        if (error instanceof ApiError && error.status === 404) this.update({run: null, error: 'expired'});
        else this.update({run: withoutResult(this.state.run), error: 'poll'});
      }
    } finally {this.polling = false; this.schedule();}
  }
  dispose() {
    if (!this.alive) return;
    this.alive = false; this.clearTimer(); this.version++; this.statusVersion++;
    if (occupied(this.state.run)) void this.client.cancelLocalSource(this.state.run!.id).catch(() => undefined);
    this.state = {...emptySourceWorkState}; this.attempt = null;
    // An already sent start must still return so its known active run can be
    // revoked. Private questions never enter browser storage or logs.
  }
}
