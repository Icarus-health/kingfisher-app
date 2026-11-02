import assert from 'node:assert/strict';
import {after, test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {createServer} from 'vite';
import {testCache} from './testcache.mjs';
const server = await createServer({cacheDir: testCache('local-module-settings-ui.test'), root: fileURLToPath(new URL('..', import.meta.url)), plugins: [{name: 'module-settings-hooks', enforce: 'pre', resolveId(id) {if (id === 'virtual:module-settings-hooks') return '\0' + id;}, load(id) {if (id === '\0virtual:module-settings-hooks') return `export const useState=(...a)=>globalThis.__moduleSettingsDriver.state(...a);export const useRef=(...a)=>globalThis.__moduleSettingsDriver.ref(...a);export const useEffect=(...a)=>globalThis.__moduleSettingsDriver.effect(...a);`;}, transform(code, id) {if (id.endsWith('/src/LocalModuleSettings.tsx')) return code.replace(/from (["'])react\1/, 'from "virtual:module-settings-hooks"');}}], server: {middlewareMode: true, watch: null, ws: false, hmr: false}, appType: 'custom'});
after(() => server.close());
const {LocalModuleSettings} = await server.ssrLoadModule('/src/LocalModuleSettings.tsx');
const {Technik} = await server.ssrLoadModule('/src/Einstellungen/Technik.tsx');
const {TECHNIK, zielAus} = await server.ssrLoadModule('/src/Einstellungen/gliederung.ts');
function nodes(node, predicate, out = []) {if (!node || typeof node !== 'object') return out; if (predicate(node)) out.push(node); for (const child of [node.props?.children].flat(10)) nodes(child, predicate, out); return out;}
function words(node) {return node == null ? '' : typeof node === 'object' ? [node.props?.children].flat(10).map(words).join(' ') : String(node);}
const button = (tree, label) => nodes(tree, n => n.type === 'button' && words(n) === label)[0];
function driver() {
  const states = [], refs = [], effects = [], pending = []; let s = 0, r = 0, e = 0;
  const d = {state(initial) {const i = s++; if (!(i in states)) states[i] = typeof initial === 'function' ? initial() : initial; return [states[i], next => states[i] = typeof next === 'function' ? next(states[i]) : next];}, ref(initial) {return refs[r++] ??= {current: initial};}, effect(fn, deps) {const i = e++; if (!effects[i] || deps.some((v, j) => v !== effects[i].deps[j])) {effects[i]?.cleanup?.(); effects[i] = {deps}; pending.push(() => effects[i].cleanup = fn());}}, render() {s = r = e = 0; globalThis.__moduleSettingsDriver = d; return LocalModuleSettings();}, effects() {pending.splice(0).forEach(fn => fn());}, close() {effects.forEach(x => x.cleanup?.()); delete globalThis.__moduleSettingsDriver;}};
  return d;
}
function environment(bridge = true) {
  const old = {window: globalThis.window, fetch: globalThis.fetch}, win = new EventTarget(), messages = [], timers = new Map(); let next = 0, reads = 0;
  if (bridge) win.webkit = {messageHandlers: {kingfisher: {postMessage: value => messages.push(value)}}};
  win.setTimeout = fn => {timers.set(++next, fn); return next;}; win.clearTimeout = id => timers.delete(id);
  globalThis.window = win; globalThis.fetch = () => {reads++; throw new Error('No provider or API work is allowed');};
  return {win, messages, timers, get reads() {return reads;}, event(status, generation = messages.at(-1).generation) {win.dispatchEvent(new CustomEvent('kingfisher:local-modules', {detail: {generation, status}}));}, timeout() {const entry = timers.entries().next().value; assert.ok(entry); timers.delete(entry[0]); entry[1]();}, restore() {globalThis.window = old.window; globalThis.fetch = old.fetch;}};
}
test('Lokale Werkzeuge is reachable under the existing lazy Für Techniker section', () => {
  const env = environment();
  try {const target = zielAus('#technik-werkzeuge'); assert.deepEqual(target, {bereich: 'technik', technik: 'werkzeuge'}); assert.equal(TECHNIK.filter(x => x.id === 'werkzeuge').length, 1); const tree = Technik({integrationen: {overview: null}, ziel: target, zuBereich() {}}); const section = nodes(tree, n => n.props?.id === 'werkzeuge')[0]; assert.equal(section.props.titel, 'Lokale Werkzeuge'); assert.ok(nodes(section, n => n.type === LocalModuleSettings).length); assert.equal(env.messages.length, 0); assert.equal(env.reads, 0);} finally {env.restore();}
});
test('mount probes status only and an absent or silent old wrapper clearly requests an app update', () => {
  for (const bridge of [false, true]) {
    const env = environment(bridge), d = driver();
    try {d.render(); assert.equal(env.messages.length, 0); d.effects(); assert.equal(env.reads, 0); if (bridge) {assert.deepEqual(Object.keys(env.messages[0]).sort(), ['aktion', 'generation']); assert.equal(env.messages[0].aktion, 'lokaleWerkzeugeStatus'); env.timeout();} const tree = d.render(); assert.match(words(tree), /Mac-App aktualisieren/); assert.equal(button(tree, 'Einrichten'), undefined); assert.equal(env.messages.filter(x => x.aktion === 'lokaleWerkzeugeEinrichten').length, 0);} finally {d.close(); env.restore();}
  }
});
test('the compact card names the download scope and only its explicit button starts setup', () => {
  const env = environment(), d = driver();
  try {d.render(); d.effects(); env.event('unavailable'); let tree = d.render(); assert.match(words(tree), /öffentliche Laufzeitdateien/); assert.match(words(tree), /ausgewählte Quelle/); assert.match(words(tree), /Qwen 3.5/); assert.match(words(tree), /Nur Lesen/); assert.equal(button(tree, 'Einrichten').props.disabled, false); button(tree, 'Einrichten').props.onClick(); button(tree, 'Einrichten').props.onClick(); tree = d.render(); assert.equal(env.messages.filter(x => x.aktion === 'lokaleWerkzeugeEinrichten').length, 1); assert.equal(button(tree, 'Einrichten').props.disabled, true); env.event('downloading'); assert.match(words(d.render()), /Laufzeit wird geladen/); assert.equal(env.reads, 0); env.event('cancelled');} finally {d.close(); env.restore();}
});
test('an unknown attempt keeps setup disabled, focuses reconciliation and cancellation never claims immediate stop', () => {
  const env = environment(), d = driver(); let focused = 0;
  try {d.render(); d.effects(); env.event('unavailable'); let tree = d.render(); button(tree, 'Einrichten').props.onClick(); env.timeout(); tree = d.render(); button(tree, 'Status erneut prüfen').props.ref.current = {focus() {focused++;}}; d.effects(); assert.ok(focused); assert.equal(button(tree, 'Einrichten').props.disabled, true); assert.match(words(tree), /noch unklar/); button(tree, 'Abbrechen').props.onClick(); tree = d.render(); assert.match(words(tree), /kann noch auslaufen/); assert.equal(button(tree, 'Abbrechen').props.disabled, true); env.event('cancelled'); tree = d.render(); assert.match(words(tree), /abgebrochen/); assert.equal(button(tree, 'Einrichten').props.disabled, false);} finally {d.close(); env.restore();}
});
test('cleanup cancels only an initiated generation and removes the event listener', () => {
  const env = environment(), d = driver(); d.render(); d.effects(); const generation = env.messages[0].generation; d.close(); assert.equal(env.messages.length, 1); env.event('downloading', generation); assert.equal(env.messages.length, 1); env.restore();
  const active = environment(), running = driver(); running.render(); running.effects(); active.event('unavailable'); button(running.render(), 'Einrichten').props.onClick(); const attempt = active.messages.at(-1).generation; running.close(); assert.deepEqual(active.messages.at(-1), {aktion: 'lokaleWerkzeugeAbbrechen', generation: attempt});
  const next = driver(); next.render(); next.effects(); assert.equal(active.messages.at(-1).aktion, 'lokaleWerkzeugeStatus'); assert.equal(active.messages.at(-1).generation, attempt); active.event('cancelled'); next.close(); active.restore();
});
