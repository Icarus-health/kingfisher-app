import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createLocalModuleSetup, localModulesPost, localModuleEvent, localModuleCanStart} from '../src/localModuleSetup.ts';
function fixture(options = {}) {
  const requests = [], timers = new Map(); let timer = 0, state;
  const setup = createLocalModuleSetup({post: message => {requests.push(message); return options.delivered !== false;}, changed: value => {state = value;}, timers: {set: fn => {timers.set(++timer, fn); return timer;}, clear: id => timers.delete(id)}});
  return {setup, requests, timers, get state() {return state;}, event(status, extra = {}) {setup.event({generation: state.generation, status, ...extra});}, timeout() {const entry = timers.entries().next().value; assert.ok(entry); timers.delete(entry[0]); entry[1]();}, close(clear = true) {if (clear && state?.pending) this.event('cancelled'); setup.dispose();}};
}
test('a status probe never initializes anything and a silent old wrapper offers an app update', () => {
  const f = fixture(); assert.deepEqual(f.requests, []); f.setup.probe(); assert.equal(f.requests.length, 1); assert.equal(f.requests[0].aktion, 'lokaleWerkzeugeStatus'); assert.equal(f.state.phase, 'checking'); f.timeout(); assert.equal(f.state.phase, 'unsupported'); assert.equal(localModuleCanStart(f.state), false); f.setup.start(); assert.equal(f.requests.length, 1); f.close();
  const absent = fixture({delivered: false}); absent.setup.probe(); assert.equal(absent.state.phase, 'unsupported'); assert.equal(absent.timers.size, 0); absent.close();
});
test('an acknowledged slow status is unknown rather than an unsupported wrapper', () => {
  const f = fixture(); f.setup.probe(); f.event('checking'); f.timeout();
  assert.equal(f.state.phase, 'unknown'); assert.equal(f.state.pending, false);
  assert.equal(localModuleCanStart(f.state), false);
  f.setup.cancel(); f.setup.start();
  assert.deepEqual(f.requests.map(x => x.aktion), ['lokaleWerkzeugeStatus']);
  f.event('ready'); assert.equal(f.state.phase, 'ready'); f.close();
});
test('only an explicit click after a supported idle status starts one fixed setup generation', () => {
  const f = fixture(); f.setup.probe(); f.event('unavailable'); assert.equal(localModuleCanStart(f.state), true); const probe = f.state.generation; f.setup.start(); f.setup.start(); assert.equal(f.requests.length, 2); assert.equal(f.requests[1].aktion, 'lokaleWerkzeugeEinrichten'); assert.ok(f.state.generation > probe); assert.equal(f.state.pending, true); assert.equal(localModuleCanStart(f.state), false); for (const request of f.requests) assert.deepEqual(Object.keys(request).sort(), ['aktion', 'generation']); f.close();
});
test('closed events reject unknown fields and unsafe or stale generations without changing the visible state', () => {
  const f = fixture(); f.setup.probe(); const original = {...f.state};
  for (const value of [null, [], {generation: -1, status: 'ready'}, {generation: .5, status: 'ready'}, {generation: Number.MAX_SAFE_INTEGER + 1, status: 'ready'}, {generation: f.state.generation, status: 'other'}, {generation: f.state.generation, status: 'ready', path: '/private'}, {generation: f.state.generation - 1, status: 'ready'}]) {f.setup.event(value); assert.deepEqual(f.state, original);}
  const extra = {generation: f.state.generation, status: 'ready'}; Object.defineProperty(extra, 'hidden', {value: 'no'}); assert.equal(localModuleEvent(extra), null); f.event('ready'); assert.equal(f.state.phase, 'ready'); assert.equal(localModuleCanStart(f.state), false); f.close();
});
test('cancel targets only the active generation and late progress cannot undo cancellation or a terminal result', () => {
  const f = fixture(); f.setup.probe(); f.event('unavailable'); f.setup.start(); f.event('downloading'); const generation = f.state.generation; f.setup.cancel(); f.setup.cancel(); assert.equal(f.requests.at(-1).aktion, 'lokaleWerkzeugeAbbrechen'); assert.equal(f.requests.at(-1).generation, generation); assert.equal(f.requests.filter(x => x.aktion === 'lokaleWerkzeugeAbbrechen').length, 1); assert.equal(f.state.pending, true); f.event('installing'); assert.equal(f.state.phase, 'cancelling'); f.timeout(); assert.equal(f.state.phase, 'unknown'); f.setup.start(); assert.equal(f.requests.filter(x => x.aktion === 'lokaleWerkzeugeEinrichten').length, 1); f.event('cancelled'); assert.equal(f.state.pending, false); f.event('ready'); assert.equal(f.state.phase, 'cancelled'); f.close();
});
test('an unconfirmed setup survives close/reopen with status-only reconciliation and the same generation', () => {
  const first = fixture(); first.setup.probe(); first.event('unavailable'); first.setup.start(); const generation = first.state.generation; first.timeout(); assert.equal(first.state.phase, 'unknown'); first.close(false); assert.deepEqual(first.requests.at(-1), {aktion: 'lokaleWerkzeugeAbbrechen', generation});
  const next = fixture(); next.setup.probe(); assert.deepEqual(next.requests, [{aktion: 'lokaleWerkzeugeStatus', generation}]); assert.equal(next.state.pending, true); next.setup.start(); assert.equal(next.requests.length, 1); next.event('failed'); assert.equal(localModuleCanStart(next.state), true); next.setup.start(); assert.equal(next.requests.at(-1).aktion, 'lokaleWerkzeugeEinrichten'); assert.ok(next.state.generation > generation); next.close();
});
test('a late prior status and stale timeout cannot overwrite a new setup or restart it after unmount', () => {
  const f = fixture(); f.setup.probe(); const oldGeneration = f.state.generation, oldTimer = [...f.timers.values()][0]; f.event('unavailable'); f.setup.start(); f.event('verifying'); f.setup.event({generation: oldGeneration, status: 'ready'}); oldTimer(); assert.equal(f.state.phase, 'verifying'); f.event('downloading'); assert.equal(f.state.phase, 'verifying'); const snapshot = {...f.state}; f.close(false); f.event('ready'); assert.deepEqual(f.state, snapshot);
  const cleanup = fixture(); cleanup.setup.probe(); cleanup.event('cancelled'); cleanup.close();
});
test('native posting uses only the allowed action and safe generation, never caller extra fields', () => {
  const requests = [], environment = {webkit: {messageHandlers: {kingfisher: {postMessage: value => requests.push(value)}}}};
  assert.equal(localModulesPost({aktion: 'lokaleWerkzeugeStatus', generation: 0, secret: 'never'}, environment), true); assert.deepEqual(requests, [{aktion: 'lokaleWerkzeugeStatus', generation: 0}]);
  for (const request of [{aktion: 'other', generation: 1}, {aktion: 'lokaleWerkzeugeEinrichten', generation: -1}, {aktion: 'lokaleWerkzeugeStatus', generation: Infinity}]) assert.equal(localModulesPost(request, environment), false);
  assert.equal(localModulesPost({aktion: 'lokaleWerkzeugeStatus', generation: 1}, {}), false); assert.equal(requests.length, 1);
});
test('a second mounted card reconciles the one unknown setup instead of admitting another generation', () => {
  const first = fixture(), second = fixture(); first.setup.probe(); first.event('unavailable'); second.setup.probe(); second.event('unavailable'); first.setup.start(); const generation = first.state.generation; second.setup.start(); assert.equal(second.requests.filter(x => x.aktion === 'lokaleWerkzeugeEinrichten').length, 0); assert.deepEqual(second.requests.at(-1), {aktion: 'lokaleWerkzeugeStatus', generation}); assert.equal(second.state.pending, true); second.event('cancelled'); second.close(); first.event('cancelled'); first.close();
});
