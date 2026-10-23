// Die Aufgabenseite zeigt Aufgaben, nicht Bedienelemente (Paket U2): keine leeren Gruppen und Nullzähler, ein
// gefüllter Knopf, kein Such- oder Aktualisieren-Knopf (Suche beim Tippen, Liste lädt selbst nach), „Zur Prüfung“ nur mit
// Inhalt, Zeilenaktionen bei Zeiger oder Tastaturfokus, Bearbeiten mit Titel oben und einem „Speichern“.
import {createServer} from 'vite';
import {test, after} from 'node:test';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {visibleTaskGroups} from '../src/taskWorkspaceModel.ts';
import {TaskPager} from '../src/taskPager.ts';

const root = fileURLToPath(new URL('..', import.meta.url));
const css = readFileSync(root + '/src/WorkspaceTasks.css', 'utf8');
const server = await createServer({cacheDir: `/private/tmp/kingfisher-ui-test-cache-${process.pid}-aufgaben-ruhig`, root, configFile: false,
  plugins: [{name: 'u2-hooks', enforce: 'pre',
    resolveId(id) { if (id === 'virtual:u2-hooks') return '\0' + id; },
    load(id) { if (id === '\0virtual:u2-hooks') return 'export const useState=(...a)=>globalThis.__u2.state(...a);export const useRef=(...a)=>globalThis.__u2.ref(...a);export const useEffect=(...a)=>globalThis.__u2.effect(...a);export const useMemo=f=>f();'; },
    transform(code, id) {
      if (id.endsWith('/src/App.tsx')) return code.replace('from "react"', 'from "virtual:u2-hooks"') + '\nexport {Tasks};';
      if (id.endsWith('/src/TaskRow.tsx')) return code.replace('from "react"', 'from "virtual:u2-hooks"');
    }}],
  server: {middlewareMode: true, watch: null, ws: false, hmr: false}, appType: 'custom'});
after(() => server.close());

function nodes(n, predicate, out = []) { if (!n || typeof n !== 'object') return out; if (predicate(n)) out.push(n); for (const c of [n.props?.children].flat(20)) nodes(c, predicate, out); return out; }
function text(n) { return !n ? '' : typeof n === 'object' ? [n.props?.children].flat(20).map(text).join('') : String(n); }
const tick = async () => { for (let i = 0; i < 4; i++) await new Promise(setImmediate); };

function driver(render) {
  const values = [], refs = [], effects = [], pending = [];
  let si = 0, ri = 0, ei = 0;
  const d = {
    state(initial) { const i = si++; if (!(i in values)) values[i] = typeof initial === 'function' ? initial() : initial; return [values[i], v => { values[i] = typeof v === 'function' ? v(values[i]) : v; }]; },
    ref(initial) { const i = ri++; return refs[i] ??= {current: initial}; },
    effect(fn, deps) { const i = ei++; if (!effects[i] || !deps || deps.some((v, j) => v !== effects[i].deps[j])) { const old = effects[i]; effects[i] = {deps: deps ?? []}; pending.push(() => { old?.cleanup?.(); effects[i].cleanup = fn(); }); } },
    render() { si = ri = ei = 0; globalThis.__u2 = d; return render(); },
    run() { pending.splice(0).forEach(fn => fn()); },
  };
  return d;
}

const task = (id, title, due = null, extra = {}) => ({id, title, due, status: 'open', overdue: false, project_id: null, wartet_auf: null, notes: null, ...extra});

async function withTasks(run, {tasks = [], total = tasks.length} = {}) {
  const oldWindow = globalThis.window, oldDocument = globalThis.document;
  const timers = [], listeners = {}, calls = [];
  globalThis.window = {location: {search: '', href: 'http://synthetic/vorhaben', pathname: '/vorhaben'}, history: {state: null, replaceState() {}},
    setInterval() { return 1; }, clearInterval() {}, setTimeout(fn) { timers.push(fn); return timers.length; }, clearTimeout(id) { timers[id - 1] = null; },
    addEventListener(type, fn) { listeners[type] = fn; }, removeEventListener() {}};
  globalThis.document = {visibilityState: 'visible', addEventListener(type, fn) { listeners['doc:' + type] = fn; }, removeEventListener() {}};
  const {Tasks} = await server.ssrLoadModule('/src/App.tsx');
  const {api} = await server.ssrLoadModule('/src/api.ts');
  const saved = {tasks: api.tasks, projects: api.projects};
  api.tasks = async (view, projectId, options) => { calls.push({view, projectId, ...options}); return {tasks: options?.q ? tasks.filter(t => t.title.includes(options.q)) : tasks, total, next_cursor: null, limit: 50}; };
  api.projects = async () => [];
  const d = driver(() => Tasks({recentConversation: null}));
  try {
    d.render(); d.run(); await tick();
    await run({d, timers, listeners, calls});
  } finally { Object.assign(api, saved); globalThis.window = oldWindow; globalThis.document = oldDocument; }
}

test('nur Gruppen mit Aufgaben: keine leere Gruppe, kein Nullzähler', () => {
  const now = new Date('2026-09-29T07:31:00');
  const groups = visibleTaskGroups([{id: 'a', due: '2026-10-02T17:00:00'}, {id: 'b', due: null}], now);
  assert.deepEqual(groups.map(g => g.label), ['Demnächst', 'Ohne Termin']);
  assert.ok(groups.every(g => g.items.length > 0));
  assert.deepEqual(visibleTaskGroups([], now), []);
});

test('stilles Nachladen lässt die Liste stehen und bleibt auf der aktuellen Seite; scheitert es, bleibt die Liste', async () => {
  const states = [], cursors = [];
  let fail = false;
  const pager = new TaskPager(async (_, cursor) => { cursors.push(cursor); if (fail) throw new Error('offline'); return {tasks: [{id: cursor ?? 'first'}], total: 2, next_cursor: cursor ? null : 'next'}; }, s => states.push(s));
  await pager.select({view: 'mine', projectId: '', q: ''}); await pager.next();
  const before = states.length;
  await pager.reload();
  assert.equal(cursors.at(-1), 'next', 'reload stays on the current page');
  assert.ok(states.slice(before).every(s => s.tasks !== null && !s.loading), 'no empty loading state while reloading');
  assert.equal(states.at(-1).tasks[0].id, 'next');
  fail = true; const count = states.length;
  await pager.reload();
  assert.equal(states.length, count, 'a failed quiet reload keeps the visible list without a new error state');
  fail = false; await pager.previous();
  assert.equal(states.at(-1).tasks[0].id, 'first', 'navigation still works after a failed quiet reload');
});

test('Liste: Aufgaben statt Bedienung, ein gefüllter Knopf, keine leeren Gruppen, keine Seitenzahl bei einer Seite', async () => {
  await withTasks(async ({d}) => {
    const tree = d.render();
    const groups = nodes(tree, n => n.type === 'section' && n.props.className === 'workspace-task-group');
    assert.deepEqual(groups.map(g => g.props['aria-label']), ['Demnächst'], 'only groups with tasks');
    assert.doesNotMatch(text(tree), /Keine Aufgaben auf dieser Seite|Seite 1|Aufgaben ·/);
    const buttons = nodes(tree, n => n.type === 'button');
    for (const name of ['Suchen', 'Liste aktualisieren', 'Neues Projekt', 'Suche löschen']) assert.equal(buttons.filter(b => text(b) === name).length, 0, `no „${name}“ button in the list`);
    const filled = buttons.filter(b => /(^|\s)(primary-action|tasks-add)(\s|$)/.test(b.props.className ?? ''));
    assert.equal(filled.length, 1, 'exactly one filled button per view');
    assert.equal(text(filled[0]), 'Aufgabe');
    assert.equal(nodes(tree, n => n.type === 'button' && text(n).startsWith('Zur Prüfung')).length, 0, 'no review tab without anything to review');
    const rows = nodes(tree, n => n.type?.name === 'TaskRow');
    assert.equal(rows.length, 2); assert.ok(rows.every(r => r.props.compact && r.props.onOpen));
  }, {tasks: [task('t1', 'Drei Referenzen an Dr. Amann schicken', '2030-10-02T17:00:00'), task('t2', 'Abo Klinikküche entscheiden', '2030-10-15T12:00:00')]});
});

test('ganz leer: ein Satz, keine Gruppe; „Zur Prüfung“ erscheint erst mit Inhalt und mit Zahl', async () => {
  await withTasks(async ({d}) => {
    let tree = d.render();
    assert.equal(nodes(tree, n => n.type === 'section' && n.props.className === 'workspace-task-group').length, 0);
    const empty = nodes(tree, n => n.props?.className === 'task-empty');
    assert.equal(empty.length, 1); assert.equal(text(empty[0]), 'Keine offenen Aufgaben für dich.');
    nodes(tree, n => n.type?.name === 'TaskSuggestions')[0].props.onTotal(3); tree = d.render();
    const tab = nodes(tree, n => n.type === 'button' && text(n).startsWith('Zur Prüfung'));
    assert.equal(tab.length, 1); assert.equal(text(tab[0]), 'Zur Prüfung · 3');
    nodes(tree, n => n.type?.name === 'TaskSuggestions')[0].props.onTotal(0); tree = d.render();
    // Reiter in einer Zeile, die waagrecht rollt statt umzubrechen; der gewählte Reiter rollt in den Blick.
    assert.match(css, /\.shell main\.workspace-tasks \.task-tabs \{flex-wrap:nowrap;overflow-x:auto;/);
    assert.match(css, /\.shell main\.workspace-tasks \.task-tabs button \{flex:0 0 auto;white-space:nowrap;\}/);
    assert.match(readFileSync(root + '/src/App.tsx', 'utf8'), /querySelector<HTMLElement>\('\[aria-pressed="true"\]'\)\?\.scrollIntoView\?\.\(\{block: "nearest", inline: "nearest"\}\)/);
    assert.equal(nodes(tree, n => n.type === 'button' && text(n).startsWith('Zur Prüfung')).length, 0);
  });
});

test('die Suche filtert beim Tippen, ohne Knopf; das Fenster im Blick lädt die Liste still nach', async () => {
  await withTasks(async ({d, timers, listeners, calls}) => {
    let tree = d.render();
    const input = nodes(tree, n => n.type === 'input' && n.props.type === 'search')[0];
    assert.ok(input); assert.equal(input.props['aria-label'], 'Aufgaben durchsuchen');
    input.props.onChange({target: {value: 'Amann'}}); d.render(); d.run();
    timers.filter(Boolean).forEach(fn => fn()); d.render(); d.run(); await tick();
    assert.equal(calls.at(-1).q, 'Amann', 'typing alone searches');
    tree = d.render();
    assert.equal(nodes(tree, n => n.type?.name === 'TaskRow').length, 1);
    const before = calls.length;
    listeners.focus(); await tick();
    assert.equal(calls.length, before, 'no reload right after a load');
    const now = Date.now; Date.now = () => now() + 60000;
    try { listeners.focus(); await tick(); } finally { Date.now = now; }
    assert.equal(calls.length, before + 1, 'focus reloads the list without a button');
    assert.equal(calls.at(-1).q, 'Amann');
  }, {tasks: [task('t1', 'Drei Referenzen an Dr. Amann schicken', '2030-10-02T17:00:00'), task('t2', 'Abo Klinikküche entscheiden')]});
});

async function rowTree(props) {
  const {TaskRow} = await server.ssrLoadModule('/src/TaskRow.tsx');
  const d = driver(() => TaskRow({view: 'mine', completing: false, onComplete() {}, onWait() {}, projects: [{id: 'p', name: 'Rheinauenblick', open: true}], onProjectChange() {}, onEdit: async () => true, ...props}));
  return d.render();
}

test('Listenzeile: Projekt nur wenn gesetzt, Aktionen per Tastatur erreichbar und nur bei Zeiger oder Fokus sichtbar', async () => {
  let tree = await rowTree({task: task('t', 'Unterlagen vorbereiten', '2030-09-30T10:00:00', {project_id: 'p'}), compact: true, onOpen() {}});
  assert.match(text(tree), /Rheinauenblick/);
  const actions = nodes(tree, n => n.props?.className === 'task-row-actions');
  assert.equal(actions.length, 1, 'actions stay in the DOM, so Tab reaches them');
  assert.equal(nodes(actions[0], n => n.type === 'select').length, 1);
  assert.equal(nodes(actions[0], n => n.type === 'button' && text(n) === 'Warte auf …').length, 1);
  assert.equal(nodes(tree, n => n.type === 'button' && text(n) === 'Bearbeiten').length, 0, 'the title opens editing; no duplicate button');
  assert.equal(nodes(tree, n => n.props?.className === 'task-title-link').length, 1);
  tree = await rowTree({task: task('t', 'Fachartikel gliedern'), compact: true, onOpen() {}});
  const copy = nodes(tree, n => n.props?.className === 'task-copy')[0];
  assert.equal(nodes(copy, n => n.type === 'small').length, 0, 'no project, no date: nothing extra under the title');
  assert.equal(nodes(tree, n => n.type === 'time').length, 0, 'no „Ohne Termin“ in the row');
  // Sichtbar bei Zeiger oder Tastaturfokus, ohne Zeiger oder schmal ausgeblendet (dort öffnet der Titel alles).
  assert.match(css, /\(hover:hover\) and \(min-width:901px\)\{[^}]*\.task-row\.compact > \.task-row-actions \{opacity:0;/);
  assert.match(css, /\.task-row\.compact:is\(:hover,:focus-within,\.task-row-open\) > \.task-row-actions \{opacity:1;\}/);
  assert.match(css, /\(hover:none\), \(max-width:900px\)\{(?:\n[^\n]*){0,3}\n \.shell main\.workspace-tasks \.task-row\.compact > \.task-row-actions \{display:none;\}/);
});

test('Bearbeiten: Titel zuerst, kein „optional“, „Wiedervorlage löschen“ nur wenn gesetzt, ein gefüllter Knopf „Speichern“', async () => {
  let tree = await rowTree({task: task('t', 'Flyer-Layout nachfassen', '2030-09-26T17:00:00'), startEditing: true});
  const form = nodes(tree, n => n.type === 'form')[0];
  assert.ok(form);
  assert.equal(nodes(form, n => n.type === 'input')[0].props.value, 'Flyer-Layout nachfassen', 'title first');
  assert.doesNotMatch(text(form), /optional|unabhängig/);
  assert.equal(nodes(form, n => n.type === 'button' && text(n) === 'Wiedervorlage löschen').length, 0);
  const filled = nodes(form, n => n.type === 'button' && /primary-action/.test(n.props.className ?? ''));
  assert.deepEqual(filled.map(text), ['Speichern']);
  assert.equal(nodes(tree, n => n.type === 'select').length, 1, 'project stays changeable in the open task');
  tree = await rowTree({task: task('t', 'Referenzen schicken', null, {remind_at: '2030-10-01T07:00:00Z'}), startEditing: true});
  assert.equal(nodes(tree, n => n.type === 'button' && text(n) === 'Wiedervorlage löschen').length, 1);
  tree = await rowTree({task: task('t', 'Referenzen schicken'), startEditing: true, compact: true, onOpen() {}});
  assert.equal(nodes(tree, n => n.type === 'form').length, 0, 'the list row never edits in place');
});
