import assert from 'node:assert/strict';
import {after, test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {createServer} from 'vite';
import {testCache} from './testcache.mjs';
const server = await createServer({cacheDir: testCache('source-work.test'), root: fileURLToPath(new URL('..', import.meta.url)), server: {middlewareMode: true, watch: null, ws: false, hmr: false}, appType: 'custom'});
after(() => server.close());
const {SourceWorkSession, sourceWorkEnter, sourceWorkOccupied, visibleSourceWorkRun} = await server.ssrLoadModule('/src/sourceWorkState.ts');
const {ApiError, api} = await server.ssrLoadModule('/src/api.ts');
const fp = 'a'.repeat(64), nextFp = 'b'.repeat(64);
const source = {id: 'selected', fingerprint: fp};
const review = {review_binding: 'r'.repeat(43), source, model: 'kingfisher-qwen3.5:9b-8k', expires_in: 120, limits: {seconds: 120, tool_calls: 8, model_calls: 3}};
const run = {id: '1'.repeat(32), source, model: review.model, status: 'running', execution_pending: true};
const done = {...run, status: 'completed', execution_pending: false, label: 'DRAFT', verified: false, text: '<script>synthetic</script>', evidence: [{...source, start: 0, end: 4, quote: '<b>x', title: 'Selected'}], coverage: {source_characters: 100, opened_characters: 4, complete_text_opened: false}};
const deferred = () => {let resolve, reject; const promise = new Promise((yes, no) => {resolve = yes; reject = no;}); return {promise, resolve, reject};};
const flush = () => new Promise(setImmediate);
function fixture(overrides = {}) {
  let current = {...source}, snapshot;
  const calls = [], scheduled = new Map(); let timerId = 0;
  const client = {
    localSourceStatus: async () => {calls.push(['status']); return {status: 'configured', model: review.model, runtime: {status: 'idle', busy: false, model: review.model}};},
    prepareLocalSource: async (id, question) => {calls.push(['prepare', id, question]); return review;},
    startLocalSource: async body => {calls.push(['start', body]); return run;},
    localSourceRun: async id => {calls.push(['poll', id]); return run;},
    cancelLocalSource: async id => {calls.push(['cancel', id]); return {...run, status: 'cancelled', execution_pending: false};},
    ...overrides,
  };
  const session = new SourceWorkSession(client, () => current, value => {snapshot = value;}, {set: fn => {scheduled.set(++timerId, fn); return timerId;}, clear: id => scheduled.delete(id)});
  return {session, client, calls, scheduled, setSource(value) {current = value;}, get state() {return snapshot;}, async open() {await session.open();}, async tick() {const entry = scheduled.entries().next().value; assert.ok(entry, 'a bounded next poll is scheduled'); scheduled.delete(entry[0]); await entry[1](); await flush();}, close() {session.dispose();}};
}
test('opening reads occupancy only and an absent module has no action', async () => {
  const f = fixture(); assert.equal(f.calls.length, 0); await f.open(); assert.deepEqual(f.calls, [['status']]); assert.equal(f.state.available, true); f.close();
  for (const response of [{status: 'not_installed', model: review.model}, new ApiError(404)]) {const f = fixture({localSourceStatus: async () => {if (response instanceof Error) throw response; return response;}}); await f.open(); assert.equal(f.state.available, false); assert.equal(f.state.error, null); f.close();}
});
test('one explicit start binds exact reviewed question and displayed fingerprint; repeated clicks cannot create another job', async () => {
  const gate = deferred(); const f = fixture({prepareLocalSource: async () => gate.promise}); await f.open();
  const first = f.session.start('  Selected question\nsecond line  '); await f.session.start('different duplicate'); assert.equal(f.state.phase, 'preparing'); gate.resolve(review); await first;
  const starts = f.calls.filter(x => x[0] === 'start'); assert.equal(starts.length, 1);
  assert.deepEqual({...starts[0][1], idempotency_key: 'opaque'}, {source_id: 'selected', question: '  Selected question\nsecond line  ', source_fingerprint: fp, review_binding: 'r'.repeat(43), consent: true, idempotency_key: 'opaque'});
  assert.match(starts[0][1].idempotency_key, /^[A-Za-z0-9_-]{8,80}$/); assert.equal(sourceWorkOccupied(f.state), true); await f.session.start('another'); assert.equal(f.calls.filter(x => x[0] === 'start').length, 1); f.close();
});
test('a changed displayed source during prepare never starts and retains a recoverable form', async () => {
  for (const responseChanges of [false, true]) {const gate = deferred(); const f = fixture({prepareLocalSource: async () => gate.promise}); await f.open(); const request = f.session.start('keep my question'); if (!responseChanges) f.setSource({...source, fingerprint: nextFp}); gate.resolve(responseChanges ? {...review, source: {...source, fingerprint: nextFp}} : review); await request; assert.equal(f.calls.filter(x => x[0] === 'start').length, 0); assert.equal(f.state.error, 'source_changed'); assert.equal(sourceWorkOccupied(f.state), false); f.close();}
});
test('a lost start response locks new work and explicit retry reuses the exact review and idempotency key', async () => {
  const sent = []; let count = 0; const f = fixture({startLocalSource: async body => {sent.push(body); if (++count === 1) throw new TypeError('lost network'); return run;}}); await f.open(); await f.session.start('original question'); assert.equal(f.state.phase, 'uncertain'); assert.equal(sourceWorkOccupied(f.state), true); await f.session.start('edited question'); assert.equal(sent.length, 1, 'a changed question cannot become another job while the first start is unknown'); await f.session.retryStart(); assert.equal(sent.length, 2); assert.deepEqual(sent[1], sent[0]); assert.equal(f.calls.filter(x => x[0] === 'prepare').length, 1); assert.equal(f.state.run.id, run.id); f.close();
});
test('a stale start response after navigation is withheld and late active work after unmount is cancelled', async () => {
  const gate = deferred(); const f = fixture({startLocalSource: async () => gate.promise}); await f.open(); const request = f.session.start('question'); await flush(); f.setSource({...source, fingerprint: nextFp}); f.session.sourceChanged(); gate.resolve(done); await request; assert.equal(visibleSourceWorkRun(f.state, {...source, fingerprint: nextFp}), null); assert.equal(f.calls.filter(x => x[0] === 'cancel').length, 0); f.close();
  const pending = deferred(); const g = fixture({startLocalSource: async () => pending.promise}); await g.open(); const start = g.session.start('question'); await flush(); g.close(); pending.resolve(run); await start; assert.deepEqual(g.calls.filter(x => x[0] === 'cancel'), [['cancel', run.id]]);
});
test('cancel hides prose immediately and keeps admission blocked until physical execution exits', async () => {
  const cancellation = deferred(); const f = fixture({cancelLocalSource: async id => {f.calls.push(['cancel', id]); return cancellation.promise;}, localSourceRun: async () => ({...run, status: 'cancelled', execution_pending: false})}); await f.open(); await f.session.start('question'); const request = f.session.cancel(); assert.equal(sourceWorkOccupied(f.state), true); assert.equal(visibleSourceWorkRun(f.state, source)?.text, undefined); await f.session.start('duplicate'); assert.equal(f.calls.filter(x => x[0] === 'start').length, 1); cancellation.resolve({...run, status: 'cancelled', execution_pending: true}); await request; assert.equal(sourceWorkOccupied(f.state), true); await f.tick(); assert.equal(sourceWorkOccupied(f.state), false); assert.equal(f.state.run.status, 'cancelled'); f.close();
});
test('serialized polling rejects a late pre-cancel result and does not overlap slow polls', async () => {
  const gate = deferred(); let polls = 0; const f = fixture({localSourceRun: async () => {polls++; return gate.promise;}, cancelLocalSource: async () => ({...run, status: 'cancelled', execution_pending: true})}); await f.open(); await f.session.start('question'); const tick = f.tick(); await flush(); assert.equal(polls, 1); assert.equal(f.scheduled.size, 0); await f.session.cancel(); gate.resolve(done); await tick; assert.equal(f.state.run.status, 'cancelled'); assert.equal(visibleSourceWorkRun(f.state, source)?.text, undefined); f.close();
});
test('a completed draft disappears before effects on fingerprint change and while a later freshness poll fails', async () => {
  let count = 0; const f = fixture({localSourceRun: async () => {if (++count === 1) return done; throw new TypeError('offline');}}); await f.open(); await f.session.start('question'); await f.tick(); assert.equal(visibleSourceWorkRun(f.state, source).text, '<script>synthetic</script>'); assert.equal(visibleSourceWorkRun(f.state, {...source, fingerprint: nextFp}), null); await f.tick(); assert.equal(visibleSourceWorkRun(f.state, source)?.text, undefined); assert.equal(f.state.error, 'poll'); assert.equal(f.scheduled.size, 1, 'ordinary offline failure keeps one serialized retry'); assert.equal(f.calls.filter(x => x[0] === 'start').length, 1); f.close();
});
test('terminal failure with execution_pending keeps start blocked and source withdrawal cancels only active work', async () => {
  const f = fixture({localSourceRun: async () => ({...run, status: 'failed', execution_pending: true, error: 'Failed', message: 'fixed'})}); await f.open(); await f.session.start('question'); await f.tick(); assert.equal(sourceWorkOccupied(f.state), true); f.setSource({...source, fingerprint: nextFp}); f.session.sourceChanged(); await flush(); assert.equal(f.calls.filter(x => x[0] === 'cancel').length, 1); f.close();
  const g = fixture({localSourceRun: async () => done}); await g.open(); await g.session.start('question'); await g.tick(); g.close(); assert.equal(g.calls.filter(x => x[0] === 'cancel').length, 0);
});
test('keyboard Enter submits while Shift+Enter and composition keep editing', () => {
  assert.equal(sourceWorkEnter({key: 'Enter', shiftKey: false, isComposing: false, keyCode: 13}), true);
  for (const event of [{key: 'Enter', shiftKey: true}, {key: 'Enter', isComposing: true}, {key: 'Enter', keyCode: 229}, {key: 'a'}]) assert.equal(sourceWorkEnter(event), false);
});
test('the UI API sends only the closed local-module contract and never a model or provider address', async () => {
  const original = globalThis.fetch, requests = []; globalThis.fetch = async (path, init) => {requests.push([path, init]); return {ok: true, json: async () => run};};
  try {await api.prepareLocalSource('selected', 'question'); await api.startLocalSource({source_id: 'selected', question: 'question', source_fingerprint: fp, review_binding: review.review_binding, consent: true, idempotency_key: 'opaque-key'}); await api.localSourceRun(run.id); await api.cancelLocalSource(run.id); assert.equal(requests[0][0], '/api/v1/modules/local-source/prepare'); assert.deepEqual(JSON.parse(requests[0][1].body), {source_id: 'selected', question: 'question'}); assert.deepEqual(Object.keys(JSON.parse(requests[1][1].body)).sort(), ['consent','idempotency_key','question','review_binding','source_fingerprint','source_id']); assert.equal(requests[2][0], `/api/v1/modules/local-source/runs/${run.id}`); assert.equal(requests[3][0], `/api/v1/modules/local-source/runs/${run.id}/cancel`);} finally {globalThis.fetch = original;}
});
test('closing and reopening an unknown start restores its exact payload and never reconciles automatically', async () => {
  const sent = []; const first = fixture({startLocalSource: async body => {sent.push(body); throw new TypeError('lost');}}); await first.open(); await first.session.start('private retained question'); first.close();
  const next = fixture({startLocalSource: async body => {sent.push(body); return run;}}); await next.open(); assert.equal(next.state.phase, 'uncertain'); assert.equal(next.state.pendingQuestion, 'private retained question'); assert.deepEqual(next.calls, [['status']]); assert.equal(sent.length, 1);
  await next.session.start('different private question'); assert.equal(sent.length, 1); await next.session.retryStart(); assert.equal(sent.length, 2); assert.deepEqual(sent[1], sent[0]); assert.equal(next.calls.filter(x => x[0] === 'prepare').length, 0); next.close();
});
test('pending attempts are bounded and expire; a changed source never inherits the old confirmation', async () => {
  const oldNow = Date.now; let now = oldNow(); Date.now = () => now;
  const sessions = []; let starts = 0;
  try {
    for (let i = 0; i < 17; i++) {const id = `bounded-${i}`; const f = fixture({prepareLocalSource: async () => ({...review, source: {id, fingerprint: fp}}), startLocalSource: async () => {starts++; throw new TypeError('lost');}}); sessions.push(f); f.setSource({id, fingerprint: fp}); await f.open(); await f.session.start('question'); f.close();}
    assert.equal(starts, 16); assert.equal(sessions[16].state.error, 'capacity');
    const changed = fixture(); changed.setSource({id: 'bounded-0', fingerprint: nextFp}); await changed.open(); assert.equal(changed.state.phase, 'idle'); assert.equal(changed.state.pendingQuestion, null); assert.equal(visibleSourceWorkRun(changed.state, {id: 'bounded-0', fingerprint: nextFp}), null); changed.close();
    now += 300001;
    const expired = fixture({prepareLocalSource: async () => ({...review, source: {id: 'bounded-0', fingerprint: fp}}), startLocalSource: async () => {starts++; throw new TypeError('lost');}}); expired.setSource({id: 'bounded-0', fingerprint: fp}); await expired.open(); assert.equal(expired.state.phase, 'idle'); await expired.session.start('new explicit question'); assert.equal(starts, 17); expired.close();
  } finally {Date.now = oldNow;}
});
for (const completed of [false, true]) test(`a definitive missing ${completed ? 'completed' : 'active'} run ends polling without another job`, async () => {
    let polls = 0;
    const f = fixture({localSourceRun: async () => {if (completed && ++polls === 1) return done; throw new ApiError(404);}});
    await f.open(); await f.session.start('preserved explicit question');
    if (completed) {await f.tick(); assert.equal(visibleSourceWorkRun(f.state, source).text, '<script>synthetic</script>');}
    await f.tick();
    assert.equal(f.state.run, null); assert.equal(f.state.error, 'expired'); assert.equal(f.scheduled.size, 0); assert.equal(sourceWorkOccupied(f.state), false);
    assert.equal(f.calls.filter(x => x[0] === 'prepare').length, 1); assert.equal(f.calls.filter(x => x[0] === 'start').length, 1); f.close();
});
