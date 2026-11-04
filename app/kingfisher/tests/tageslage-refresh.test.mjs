import assert from 'node:assert/strict';
import {after, test} from 'node:test';
import {createServer} from 'vite';
import {fileURLToPath} from 'node:url';

// Only artificial snapshots and in-process rendering; no browser, provider or personal data.
const server = await createServer({root: fileURLToPath(new URL('..', import.meta.url)), configFile: false,
  cacheDir: `/private/tmp/kf-tageslage-refresh-${process.pid}`,
  plugins: [{name: 'daily-hooks', enforce: 'pre', resolveId(id) {if (id === 'virtual:daily-hooks') return '\0' + id;},
    load(id) {if (id === '\0virtual:daily-hooks') return 'export const useState=(...a)=>globalThis.__dailyDriver.state(...a);export const useRef=(...a)=>globalThis.__dailyDriver.ref(...a);export const useEffect=(...a)=>globalThis.__dailyDriver.effect(...a);export const useCallback=(...a)=>globalThis.__dailyDriver.callback(...a);';},
    transform(code, id) {if (id.endsWith('/TagesLage.tsx')) return code.replace('from "react"', 'from "virtual:daily-hooks"');}}],
  server: {middlewareMode: true, watch: null, ws: false, hmr: false}, appType: 'custom'});
after(() => server.close());
const {TagesLage} = await server.ssrLoadModule('/src/TagesLage.tsx');
const {api} = await server.ssrLoadModule('/src/api.ts');
const flush = () => new Promise(resolve => setImmediate(resolve));
const deferred = () => {let resolve, reject; const promise = new Promise((a, b) => {resolve = a; reject = b;}); return {promise, resolve, reject};};
const nodes = (node, check, found = []) => {if (node && typeof node === 'object') {if (check(node)) found.push(node); for (const child of [node.props?.children].flat(10)) nodes(child, check, found);} return found;};
const text = node => node == null || typeof node === 'boolean' ? '' : typeof node === 'object' ? [node.props?.children].flat(10).map(text).join('') : String(node);
const snapshot = (message = 'Belege bis Freitag prüfen.', extra = {}) => ({jetzt: '2026-11-04T09:00:00+01:00', termine: [], fehler: {},
  tageslage: {einleitung: 'Das zählt heute.', verlauf: [], zeilen: message ? [{art: 'fristen', text: message, aktionen: []}] : []}, ...extra});

async function withView(run) {
  const original = {window: globalThis.window, document: globalThis.document, driver: globalThis.__dailyDriver,
    read: api.tagBriefing, unsubscribe: api.weltAbbestellen};
  const intervals = new Map(), timeouts = new Map(); let timer = 0;
  globalThis.window = {setInterval(fn) {intervals.set(++timer, fn); return timer;}, clearInterval(id) {intervals.delete(id);},
    setTimeout(fn) {timeouts.set(++timer, fn); return timer;}, clearTimeout(id) {timeouts.delete(id);}};
  globalThis.document = {hidden: false};
  const values = [], refs = [], effects = [], callbacks = [], pending = [];
  let s = 0, r = 0, e = 0, c = 0, closed = false, lateWrites = 0;
  const same = (a, b) => a && b && a.length === b.length && a.every((v, i) => Object.is(v, b[i]));
  const view = {
    state(initial) {const i = s++; if (!(i in values)) values[i] = typeof initial === 'function' ? initial() : initial;
      return [values[i], next => {if (closed) lateWrites++; values[i] = typeof next === 'function' ? next(values[i]) : next;}];},
    ref(initial) {return refs[r++] ??= {current: initial};},
    callback(fn, deps) {const i = c++; if (!same(callbacks[i]?.deps, deps)) callbacks[i] = {fn, deps}; return callbacks[i].fn;},
    effect(fn, deps) {const i = e++; if (!same(effects[i]?.deps, deps)) {effects[i]?.cleanup?.(); effects[i] = {deps}; pending.push(() => effects[i].cleanup = fn());}},
    render() {s = r = e = c = 0; globalThis.__dailyDriver = view; return TagesLage({});},
    async mount() {view.render(); pending.splice(0).forEach(fn => fn()); await flush();},
    tick() {for (const fn of intervals.values()) fn();},
    close() {if (!closed) {effects.forEach(effect => effect.cleanup?.()); closed = true;}},
    get lateWrites() {return lateWrites;}, timeouts,
  };
  try {await run(view);} finally {view.close(); api.tagBriefing = original.read; api.weltAbbestellen = original.unsubscribe;
    globalThis.window = original.window; globalThis.document = original.document; globalThis.__dailyDriver = original.driver;}
}

test('failed refresh keeps the last briefing visibly stale and retry replaces it', () => withView(async view => {
  const calls = []; let fail = false;
  api.tagBriefing = async silent => {calls.push(silent); if (fail) throw Error('offline'); return snapshot(calls.length === 1 ? 'Alte Frist.' : 'Aktuelle Frist.');};
  await view.mount(); assert.match(text(view.render()), /Alte Frist/);
  fail = true; view.tick(); await flush();
  let tree = view.render();
  assert.match(text(tree), /letzte[rn]? (geladene[rn]? )?Stand/i);
  assert.match(text(tree), /Alte Frist/, 'saved overview stays readable');
  const retry = nodes(tree, n => n.type === 'button' && /Erneut/.test(text(n)))[0];
  assert.ok(retry, 'retry is available next to the stale warning');
  fail = false; retry.props.onClick(); await flush(); tree = view.render();
  assert.match(text(tree), /Aktuelle Frist/); assert.doesNotMatch(text(tree), /Alte Frist|Aktualisierung fehlgeschlagen/);
  assert.deepEqual(calls, [false, true, true], 'refresh and retry do not move the last-look marker');
}));

test('an empty old briefing cannot reassure after the refresh fails', () => withView(async view => {
  let fail = false;
  api.tagBriefing = async () => {if (fail) throw Error('offline'); return snapshot('', {tageslage: {einleitung: 'Heute liegt nichts an.', verlauf: [], zeilen: []}});};
  await view.mount(); fail = true; view.tick(); await flush();
  const tree = view.render();
  assert.match(text(tree), /nicht vollständig erfasst/);
  assert.doesNotMatch(text(tree), /Heute liegt nichts an/);
}));

test('initial failure offers a real retry without requiring page navigation', () => withView(async view => {
  let fail = true; api.tagBriefing = async () => {if (fail) throw Error('offline'); return snapshot();};
  await view.mount();
  const retry = nodes(view.render(), n => n.type === 'button' && /Erneut/.test(text(n)))[0];
  assert.ok(retry); fail = false; retry.props.onClick(); await flush();
  assert.match(text(view.render()), /Belege bis Freitag/);
}));

test('a late older response cannot restore a source after explicit unsubscribe refresh', () => withView(async view => {
  const oldRead = deferred(), freshRead = deferred(); let reads = 0;
  const subscribed = snapshot('Abonnierte Meldung.', {tageslage: {einleitung: 'Das zählt heute.', verlauf: [], zeilen: [
    {art: 'welt', text: 'Abonnierte Meldung.', aktionen: [{art: 'welt_quelle', ref: 'synthetic-world-source', beschriftung: 'Quelle abbestellen'}]}]}});
  api.tagBriefing = async () => {reads++; return reads === 1 ? subscribed : reads === 2 ? oldRead.promise : freshRead.promise;};
  api.weltAbbestellen = async () => ({});
  await view.mount(); view.tick();
  nodes(view.render(), n => n.type === 'button' && text(n) === 'Quelle abbestellen')[0].props.onClick(); await flush();
  freshRead.resolve(snapshot('Aktueller Stand ohne abbestellte Quelle.')); await flush();
  oldRead.resolve(subscribed); await flush(); await flush();
  const tree = view.render(); assert.match(text(tree), /Aktueller Stand ohne/); assert.doesNotMatch(text(tree), /Abonnierte Meldung/);
}));

test('response after leaving cannot schedule background retries or change unmounted state', () => withView(async view => {
  const pending = deferred(); api.tagBriefing = () => pending.promise;
  await view.mount(); view.close();
  pending.resolve(snapshot('Fahrzeit.', {termine: [{uid: 'synthetic-trip', wegezeit: {status: 'wird_berechnet'}}]})); await flush();
  assert.equal(view.timeouts.size, 0); assert.equal(view.lateWrites, 0);
}));

test('automatic ticks do not pile up while a briefing read is still pending', () => withView(async view => {
  const pending = deferred(); let reads = 0;
  api.tagBriefing = () => {reads++; return pending.promise;};
  await view.mount(); view.tick(); view.tick(); view.tick();
  assert.equal(reads, 1);
  pending.resolve(snapshot()); await flush();
  globalThis.document.hidden = true; view.tick(); assert.equal(reads, 1);
  globalThis.document.hidden = false; view.tick(); await flush(); assert.equal(reads, 2);
}));

test('an older failure does not mark a successful newer snapshot stale', () => withView(async view => {
  const oldRead = deferred(); let reads = 0;
  const subscribed = snapshot('Meldung.', {tageslage: {einleitung: 'Das zählt heute.', verlauf: [], zeilen: [
    {art: 'welt', text: 'Meldung.', aktionen: [{art: 'welt_quelle', ref: 'synthetic-source', beschriftung: 'Abbestellen'}]}]}});
  api.tagBriefing = async () => {reads++; return reads === 1 ? subscribed : reads === 2 ? oldRead.promise : snapshot('Neu bestätigt.');};
  api.weltAbbestellen = async () => ({});
  await view.mount(); view.tick();
  nodes(view.render(), n => n.type === 'button' && text(n) === 'Abbestellen')[0].props.onClick(); await flush();
  oldRead.reject(Error('old request offline')); await flush();
  assert.match(text(view.render()), /Neu bestätigt/); assert.doesNotMatch(text(view.render()), /Aktualisierung fehlgeschlagen/);
}));
