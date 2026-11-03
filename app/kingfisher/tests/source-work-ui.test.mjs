import assert from 'node:assert/strict';
import {after, test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
import {testCache} from './testcache.mjs';
const server = await createServer({cacheDir: testCache('source-work-ui.test'), root: fileURLToPath(new URL('..', import.meta.url)), plugins: [{name: 'source-work-hooks', enforce: 'pre', resolveId(id) {if (id === 'virtual:source-work-hooks') return '\0' + id;}, load(id) {if (id === '\0virtual:source-work-hooks') return `export const useState=(...a)=>globalThis.__sourceWorkDriver.state(...a);export const useRef=(...a)=>globalThis.__sourceWorkDriver.ref(...a);export const useEffect=(...a)=>globalThis.__sourceWorkDriver.effect(...a);export const useId=()=>globalThis.__sourceWorkDriver.id();`;}, transform(code, id) {if (id.endsWith('/src/SourceWork.tsx') || id.endsWith('/src/ProfileSource.tsx')) return code.replace(/from (["'])react\1/, 'from "virtual:source-work-hooks"');}}], server: {middlewareMode: true, watch: null, ws: false, hmr: false}, appType: 'custom'});
after(() => server.close());
const {SourceWork} = await server.ssrLoadModule('/src/SourceWork.tsx');
const {ProfileSource} = await server.ssrLoadModule('/src/ProfileSource.tsx');
const {api} = await server.ssrLoadModule('/src/api.ts');
const fp = 'a'.repeat(64), nextFp = 'b'.repeat(64), source = {id: 'selected', fingerprint: fp};
const run = {id: '1'.repeat(32), source, model: 'kingfisher-qwen3.5:9b-8k', status: 'running', execution_pending: true};
function nodes(node, predicate, out = []) {if (!node || typeof node !== 'object') return out; if (predicate(node)) out.push(node); for (const child of [node.props?.children].flat(10)) nodes(child, predicate, out); return out;}
function words(node) {return node == null ? '' : typeof node === 'object' ? [node.props?.children].flat(10).map(words).join(' ') : String(node);}
const button = (tree, label) => nodes(tree, n => n.type === 'button' && words(n).includes(label))[0];
const flush = () => new Promise(setImmediate);
function driver(Component, props) {
  const states = [], refs = [], effects = [], pending = []; let s = 0, r = 0, e = 0;
  const d = {state(initial) {const i = s++; if (!(i in states)) states[i] = typeof initial === 'function' ? initial() : initial; return [states[i], next => states[i] = typeof next === 'function' ? next(states[i]) : next];}, ref(initial) {return refs[r++] ??= {current: initial};}, effect(fn, deps) {const i = e++; if (!effects[i] || deps.some((v, j) => v !== effects[i].deps[j])) {effects[i]?.cleanup?.(); effects[i] = {deps}; pending.push(() => effects[i].cleanup = fn());}}, id() {return 'source-work-field';}, render(next = {}) {props = {...props, ...next}; s = r = e = 0; globalThis.__sourceWorkDriver = d; return Component(props);}, effects() {pending.splice(0).forEach(fn => fn());}, close() {effects.forEach(x => x.cleanup?.()); delete globalThis.__sourceWorkDriver;}};
  return d;
}
function environment(overrides = {}) {
  const old = {...api}, oldWindow = globalThis.window; let timer = 0; const scheduled = new Map(), calls = [];
  globalThis.window = {setInterval: () => 0, clearInterval: () => {}, setTimeout: fn => {scheduled.set(++timer, fn); return timer;}, clearTimeout: id => scheduled.delete(id)};
  Object.assign(api, {localSourceStatus: async () => {calls.push('status'); return {status: 'configured', model: run.model, runtime: {status: 'idle', busy: false, model: run.model}};}, prepareLocalSource: async (id, question) => {calls.push(['prepare', id, question]); return {source, review_binding: 'r'.repeat(43), model: run.model, expires_in: 120, limits: {seconds: 120, tool_calls: 8, model_calls: 3}};}, startLocalSource: async body => {calls.push(['start', body]); return run;}, cancelLocalSource: async () => ({...run, status: 'cancelled', execution_pending: false}), localSourceRun: async () => run, profileSource: async () => ({title: 'Selected original', body: 'Original', source_fingerprint: fp, source_current: true, state: 'new'}), ...overrides});
  return {calls, scheduled, async tick() {const entry = scheduled.entries().next().value; assert.ok(entry); scheduled.delete(entry[0]); entry[1](); await flush();}, restore() {Object.assign(api, old); globalThis.window = oldWindow;}};
}
async function opened(d) {d.render(); d.effects(); await flush(); let tree = d.render(); button(tree, 'Lokal mit KI prüfen').props.onClick(); tree = d.render(); d.effects(); return tree;}
test('the action appears only beside an eligible current episode, never an own question or read-only view', async () => {
  for (const props of [{}, {readOnly: true}, {originalOnly: true}, {eigeneFrage: true}, {kind: 'note'}]) {
    const env = environment(), d = driver(ProfileSource, {kind: 'episode', id: 'selected', embedded: true, ...props});
    try {d.render(); d.effects(); await flush(); const tree = d.render(); assert.equal(nodes(tree, n => n.type === SourceWork).length, Object.keys(props).length ? 0 : 1); assert.equal(env.calls.length, 0, 'the source wrapper itself never starts or probes a model');} finally {d.close(); env.restore();}
  }
  for (const record of [{source_fingerprint: undefined}, {source_current: false}, {state: 'ignored'}]) {
    const env = environment({profileSource: async () => ({title: 'Selected original', body: 'Original', source_fingerprint: fp, source_current: true, state: 'new', ...record})}), d = driver(ProfileSource, {kind: 'episode', id: 'selected', embedded: true});
    try {d.render(); d.effects(); await flush(); assert.equal(nodes(d.render(), n => n.type === SourceWork).length, 0);} finally {d.close(); env.restore();}
  }
});
test('opening and typing never start work; Enter submits once and composition or Shift+Enter do not submit', async () => {
  const env = environment(), d = driver(SourceWork, {id: 'selected', fingerprint: fp, title: 'Selected original'});
  try {let tree = await opened(d); assert.deepEqual(env.calls, ['status']); const textarea = nodes(tree, n => n.type === 'textarea')[0]; assert.ok(nodes(tree, n => n.type === 'label' && n.props.htmlFor === textarea.props.id).length); assert.match(words(tree), /Selected original/); assert.match(words(tree), /Qwen 3.5/);
    textarea.props.onChange({target: {value: 'keep\nquestion'}}); tree = d.render(); let prevented = 0;
    const key = extra => ({key: 'Enter', shiftKey: false, nativeEvent: {isComposing: false, keyCode: 13}, preventDefault() {prevented++;}, ...extra});
    const field = nodes(tree, n => n.type === 'textarea')[0]; field.props.onKeyDown(key({shiftKey: true})); field.props.onCompositionStart(); field.props.onKeyDown(key()); field.props.onCompositionEnd(); field.props.onKeyDown(key({nativeEvent: {isComposing: false, keyCode: 229}})); assert.deepEqual(env.calls, ['status']);
    field.props.onKeyDown(key()); field.props.onKeyDown(key()); await flush(); tree = d.render(); assert.equal(env.calls.filter(x => x[0] === 'start').length, 1); assert.equal(prevented, 2); assert.equal(nodes(tree, n => n.type === 'textarea')[0].props.value, 'keep\nquestion'); assert.equal(button(tree, 'Lokal prüfen').props.disabled, true);
  } finally {d.close(); env.restore();}
});
test('prepare errors keep the question, focus it and show an adjacent announced error', async () => {
  const env = environment({prepareLocalSource: async () => {throw new TypeError('private raw diagnostics');}}), d = driver(SourceWork, {id: 'selected', fingerprint: fp, title: 'Selected original'}); let focused = 0;
  try {let tree = await opened(d); nodes(tree, n => n.type === 'textarea')[0].props.onChange({target: {value: 'retained private draft'}}); tree = d.render(); nodes(tree, n => n.type === 'textarea')[0].props.ref.current = {focus() {focused++;}}; nodes(tree, n => n.type === 'form')[0].props.onSubmit({preventDefault() {}}); await flush(); tree = d.render(); d.effects(); assert.equal(nodes(tree, n => n.type === 'textarea')[0].props.value, 'retained private draft'); assert.equal(nodes(tree, n => n.props?.role === 'alert').length, 1); assert.ok(focused); assert.doesNotMatch(words(tree), /private raw diagnostics/); assert.equal(button(tree, 'Lokal prüfen').props.disabled, false);
  } finally {d.close(); env.restore();}
});
test('results are explicitly unverified, partial and escaped; fingerprint changes hide old prose before effects', async () => {
  const env = environment({localSourceRun: async () => ({...run, status: 'completed', execution_pending: false, label: 'DRAFT', verified: false, text: '<img src=x onerror=alert(1)>', evidence: [{...source, title: 'Selected original', start: 0, end: 4, quote: '<b>x'}], coverage: {source_characters: 100, opened_characters: 4, complete_text_opened: false}})}), d = driver(SourceWork, {id: 'selected', fingerprint: fp, title: 'Selected original'});
  try {let tree = await opened(d); nodes(tree, n => n.type === 'textarea')[0].props.onChange({target: {value: 'question'}}); tree = d.render(); nodes(tree, n => n.type === 'form')[0].props.onSubmit({preventDefault() {}}); await flush(); await env.tick(); tree = d.render(); const html = renderToStaticMarkup(tree); assert.match(html, /Entwurf/); assert.match(html, /ungeprüft/); assert.match(html, /Teil der Quelle/); assert.match(html, /Originalbelege/); assert.ok(html.includes('&lt;img')); assert.ok(html.includes('&lt;b&gt;x')); assert.ok(!html.includes('<img')); assert.ok(!html.includes('<b>x'));
    tree = d.render({fingerprint: nextFp}); assert.doesNotMatch(words(tree), /onerror|Originalbelege/); assert.equal(nodes(tree, n => n.type === 'textarea')[0].props.value, 'question');
  } finally {d.close(); env.restore();}
});
test('navigation never pairs a new source ID with the previous displayed original before effects', async () => {
  const env = environment(), d = driver(ProfileSource, {kind: 'episode', id: 'selected', embedded: true});
  try {d.render(); d.effects(); await flush(); assert.equal(nodes(d.render(), n => n.type === SourceWork).length, 1); const next = d.render({id: 'next-source'}); assert.equal(nodes(next, n => n.type === SourceWork).length, 0); assert.doesNotMatch(words(next), /Selected original/);} finally {d.close(); env.restore();}
});
test('a failed same-source refresh retains the saved original read-only and withdraws its work action', async () => {
  let refresh, reads = 0; const oldDocument = globalThis.document;
  const env = environment({profileSource: async () => {if (++reads > 1) throw new Error('withdrawn'); return {title: 'Selected original', body: 'Withdrawn private text', source_fingerprint: fp, source_current: true, state: 'new'};}}), d = driver(ProfileSource, {kind: 'episode', id: 'selected', embedded: true});
  globalThis.window.setInterval = fn => {refresh = fn; return 1;}; globalThis.document = {hidden: false};
  try {d.render(); d.effects(); await flush(); assert.match(words(d.render()), /Withdrawn private text/); refresh(); await flush(); const tree = d.render(); assert.equal(nodes(tree, n => n.type === SourceWork).length, 0); assert.match(words(tree), /Withdrawn private text/); assert.match(words(tree), /Zuletzt geladener Stand/); assert.equal(nodes(tree, n => n.type === 'button' && /ausschließen|verwerfen|zulassen|berichtigen/.test(words(n))).length, 0); for (const child of nodes(tree, n => ['SourceCategories', 'SourceBezuege'].includes(n.type?.name))) assert.equal(child.props.readOnly, true);} finally {d.close(); env.restore(); globalThis.document = oldDocument;}
});
