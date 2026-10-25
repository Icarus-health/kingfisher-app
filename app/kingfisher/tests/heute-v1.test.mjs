// V1 (25.10.2026): Aufgaben unter „Braucht dich“ in derselben Zeile wie die Aufgabenliste; andere Punkte im gleichen
// Zeilenmaß mit ihren Knöpfen. Nur synthetische Daten.
import {test, after} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createServer} from 'vite';
import {fileURLToPath} from 'node:url';

const quelle = (datei) => readFileSync(new URL(`../src/${datei}`, import.meta.url), 'utf8');
const MIT_HAKEN = ['/TodayOverview.tsx', '/TodayTaskRow.tsx', '/TaskRow.tsx'];
const server = await createServer({root: fileURLToPath(new URL('..', import.meta.url)), cacheDir: `/private/tmp/kingfisher-heute-v1-${process.pid}`, configFile: false,
  plugins: [{name: 'v1-hooks', enforce: 'pre', resolveId(id) { if (id === 'virtual:v1-hooks') return '\0' + id; },
    load(id) { if (id === '\0virtual:v1-hooks') return 'export const useState=v=>globalThis.__v1State(v);export const useRef=v=>({current:v});export const useEffect=()=>{};export const useMemo=f=>f();export const useCallback=f=>f;'; },
    transform(code, id) { if (MIT_HAKEN.some(p => id.endsWith(p))) return code.replace(/from (["'])react\1/, 'from "virtual:v1-hooks"'); }}],
  server: {middlewareMode: true, watch: null, ws: false, hmr: false}, appType: 'custom'});
after(() => server.close());
const {TodayOverview} = await server.ssrLoadModule('/src/TodayOverview.tsx');
const {TodayTaskRow, aufgabeAusPunkt} = await server.ssrLoadModule('/src/TodayTaskRow.tsx');
const {TaskRow} = await server.ssrLoadModule('/src/TaskRow.tsx');
const {api} = await server.ssrLoadModule('/src/api.ts');

function nodes(n, p, out = []) { if (!n || typeof n !== 'object') return out; if (p(n)) out.push(n); [n.props?.children].flat(50).forEach(c => nodes(c, p, out)); return out; }
function text(n) { return n == null || typeof n === 'boolean' ? '' : typeof n === 'object' ? [n.props?.children].flat(50).map(text).join('') : String(n); }
function render(fn, seeds = []) {
  let i = 0;
  globalThis.__v1State = v => { const slot = i++; return [slot in seeds ? seeds[slot] : (typeof v === 'function' ? v() : v), value => { seeds[slot] = typeof value === 'function' ? value(seeds[slot]) : value; }]; };
  try { return fn(); } finally { delete globalThis.__v1State; }
}
const aufgabe = {id: 't1', title: 'Flyer-Layout bei Frau Brandl nachfassen', status: 'open', created_at: '2026-09-20T08:00:00+02:00',
  due: '2026-09-26T17:00:00+02:00', notes: null, tags: [], project_id: 'p1', wartet_auf: null, wartet_seit: null, wartet_tage: null, overdue: true};
const punkt = {id: 'a1', title: aufgabe.title, detail: 'Projekt: Fachtag', priority: 'Hoch', source: 'aufgabe', source_ref: 't1', project_id: 'p1',
  reason: 'Seit drei Tagen überfällig.', task: aufgabe, project_name: 'Fachtag'};
const briefing = (needs_you) => ({generated_at: '2026-09-29T05:30:00Z', timezone: 'Europe/Berlin', partial_failures: [], later_today: [], happening_now: [],
  greeting: 'Guten Morgen.', needs_you});
const zeichne = (b, seeds, extra = {}) => render(() => TodayOverview({briefing: b, onChange() { extra.geladen = (extra.geladen ?? 0) + 1; }, onTaskDone() {}, onOpenMail() {},
  taskNotice: '', correctionSaved: false}), seeds);

test('eine Aufgabe unter „Braucht dich“ ist die Zeile der Aufgabenliste, ohne „Erledigen“ und „Details“', () => {
  const baum = zeichne(briefing([punkt]), []);
  const zeile = nodes(baum, n => n.type === TodayTaskRow);
  assert.equal(zeile.length, 1);
  assert.equal(nodes(baum, n => n.props?.className === 'today-attention-item').length, 0, 'keine zweite Darstellung daneben');
  assert.doesNotMatch(text(baum), /Erledigen|Details/);
  const row = render(() => TodayTaskRow(zeile[0].props));
  const liste = nodes(row, n => n.type === TaskRow)[0];
  assert.ok(liste, 'derselbe Baustein wie in der Liste');
  assert.equal(liste.props.compact, true);
  assert.equal(liste.props.ohneAktionen, true, 'Projekt und „Warte auf …“ stehen in der geöffneten Aufgabe');
  assert.equal(liste.props.task, aufgabe, 'die Aufgabe selbst, mit Fälligkeit');
  assert.equal(liste.props.projektName, 'Fachtag');
  assert.equal(typeof liste.props.onOpen, 'function', 'die ganze Zeile öffnet die Aufgabe');
});

test('die Zeile: Kreis mit 44-px-Ziel, Titel als Knopf über die ganze Zeile, eine leise Zeile, rechts die Fälligkeit, keine Zeilenaktionen', () => {
  const baum = render(() => TaskRow({task: aufgabe, view: 'mine', compact: true, ohneAktionen: true, projektName: 'Fachtag', hinweis: 'Verlauf ungeprüft',
    completing: false, onComplete() {}, onOpen() {}, onWait() {}, projects: [], onProjectChange() {}, onEdit: async () => false}));
  assert.equal(nodes(baum, n => n.props?.className === 'task-row-actions').length, 0);
  const kreis = nodes(baum, n => n.type === 'button' && n.props?.className === 'task-check')[0];
  assert.equal(kreis.props['aria-label'], `${aufgabe.title} erledigen`);
  assert.equal(kreis.props.disabled, false);
  assert.equal(text(nodes(baum, n => n.props?.className === 'task-title-link')[0]), aufgabe.title);
  const meta = nodes(baum, n => n.props?.className === 'task-meta')[0];
  assert.equal(text(meta), 'FachtagVerlauf ungeprüft', 'Projekt und Hinweis in einer leisen Zeile');
  assert.ok(nodes(baum, n => n.type === 'time' && n.props?.className === 'overdue').length === 1, 'überfällig rechts, rot');
  // Ohne die neuen Angaben bleibt die Liste, wie sie war: Zeilenaktionen da, Projekt aus der Projektliste.
  const inListe = render(() => TaskRow({task: aufgabe, view: 'mine', compact: true, completing: false, onComplete() {}, onOpen() {}, onWait() {},
    projects: [{id: 'p1', name: 'Aus der Liste', open: true}], onProjectChange() {}, onEdit: async () => false}));
  assert.equal(nodes(inListe, n => n.props?.className === 'task-row-actions').length, 1);
  assert.equal(text(nodes(inListe, n => n.props?.className === 'task-meta')[0]), 'Aus der Liste');
  const css = quelle('WorkspaceTasks.css');
  assert.match(css, /#root \.task-row \.task-check \{[^}]*width: 44px; height: 44px;/);
});

test('Erledigen wirkt sofort: der Kreis füllt sich, Heute sagt es und bietet „Rückgängig“', async () => {
  const aufrufe = [];
  const vorher = {completeTask: api.completeTask, reopenTask: api.reopenTask};
  api.completeTask = async id => { aufrufe.push(['erledigt', id]); return {...aufgabe, status: 'done'}; };
  api.reopenTask = async id => { aufrufe.push(['offen', id]); return aufgabe; };
  try {
    const zeileState = []; let fertig = null;
    const props = {item: punkt, onOpen() {}, onDone(a) { fertig = a; }};
    let row = render(() => TodayTaskRow(props), zeileState);
    nodes(row, n => n.type === TaskRow)[0].props.onComplete();
    await new Promise(r => setTimeout(r, 0));
    assert.deepEqual(aufrufe, [['erledigt', 't1']]);
    assert.deepEqual(fertig, {id: 't1', title: aufgabe.title});
    row = render(() => TodayTaskRow(props), zeileState);
    const liste = nodes(row, n => n.type === TaskRow)[0];
    assert.equal(liste.props.task.status, 'done', 'der Kreis zeigt den Haken');
    assert.equal(liste.props.completing, true, 'kein zweites Erledigen');

    const seiten = []; const extra = {};
    let baum = zeichne(briefing([punkt]), seiten, extra);
    nodes(baum, n => n.type === TodayTaskRow)[0].props.onDone({id: 't1', title: aufgabe.title});
    assert.equal(extra.geladen, 1, 'Heute lädt neu, die Aufgabe geht aus der Liste');
    baum = zeichne(briefing([]), seiten, extra);
    const satz = nodes(baum, n => n.props?.className === 'today-notice today-erledigt')[0];
    assert.equal(satz.props.role, 'status');
    assert.match(text(satz), /„Flyer-Layout bei Frau Brandl nachfassen“ erledigt\./);
    const zurueck = nodes(satz, n => n.type === 'button' && text(n) === 'Rückgängig')[0];
    await zurueck.props.onClick();
    assert.deepEqual(aufrufe.at(-1), ['offen', 't1']);
    baum = zeichne(briefing([]), seiten, extra);
    assert.match(text(nodes(baum, n => n.props?.className === 'today-notice today-erledigt')[0]), /ist wieder offen\./);
  } finally { Object.assign(api, vorher); }
});

test('ein nicht bestätigtes Erledigen sagt es an der Zeile', async () => {
  const vorher = api.completeTask;
  api.completeTask = async () => { throw new Error('offline'); };
  try {
    const state = []; let fertig = false;
    const props = {item: punkt, onOpen() {}, onDone() { fertig = true; }};
    nodes(render(() => TodayTaskRow(props), state), n => n.type === TaskRow)[0].props.onComplete();
    await new Promise(r => setTimeout(r, 0));
    const row = render(() => TodayTaskRow(props), state);
    assert.equal(fertig, false);
    assert.match(text(nodes(row, n => n.props?.role === 'alert')[0]), /nicht bestätigt/);
    assert.equal(nodes(row, n => n.type === TaskRow)[0].props.task.status, 'open');
  } finally { api.completeTask = vorher; }
});

test('die Zeile öffnet die Aufgabe im Seitenpaneel, mit Grund und Weg in die Aufgabenliste', () => {
  const seiten = [];
  let baum = zeichne(briefing([punkt]), seiten);
  nodes(baum, n => n.type === TodayTaskRow)[0].props.onOpen();
  baum = zeichne(briefing([punkt]), seiten);
  const paneel = nodes(baum, n => n.type?.name === 'DetailPanel')[0];
  assert.equal(paneel.props.title, 'Aufgabe');
  assert.match(text(paneel), /Seit drei Tagen überfällig\./);
  assert.equal(nodes(paneel, n => n.type?.name === 'TaskDetail')[0].props.taskId, 't1');
  assert.equal(nodes(paneel, n => n.type === 'a')[0].props.href, '/vorhaben?view=mine&task=t1&project=p1');
  paneel.props.onClose();
  baum = zeichne(briefing([punkt]), seiten);
  assert.equal(nodes(baum, n => n.type?.name === 'DetailPanel').length, 0);
});

test('Wartet-Punkte: dieselbe Zeile mit „Wartet auf …“; ohne mitgelieferte Aufgabe reichen Kennung und Titel', () => {
  const wartet = {id: 'w1', title: 'Rückmeldung Klinik', detail: '', source: 'wartet', source_ref: 't2',
    task: {...aufgabe, id: 't2', title: 'Rückmeldung Klinik', wartet_auf: 'Dr. Amann', project_id: null, due: null, overdue: false}};
  const liste = nodes(render(() => TodayTaskRow({item: wartet, onOpen() {}, onDone() {}})), n => n.type === TaskRow)[0];
  assert.equal(liste.props.view, 'waiting');
  const zeile = render(() => TaskRow(liste.props));
  assert.equal(text(nodes(zeile, n => n.props?.className === 'task-meta')[0]), 'Wartet auf Dr. Amann');
  const alt = aufgabeAusPunkt({id: 'a9', title: 'Alter Stand', source: 'aufgabe', source_ref: 't9'});
  assert.deepEqual([alt.id, alt.title, alt.status, alt.due], ['t9', 'Alter Stand', 'open', null]);
  assert.equal(aufgabeAusPunkt({...punkt, source_ref: 'anders'}).id, 'anders', 'eine fremde Aufgabe gilt nicht');
});

test('andere Punkte stehen im gleichen Zeilenmaß und behalten ihre Knöpfe', () => {
  const baum = zeichne(briefing([
    punkt,
    {id: 'z', title: 'Rechnung bis Freitag senden', detail: 'Vorschlag aus einer Mail', source: 'zusage', source_ref: 'c1', review_required: true},
    {id: 'k', title: 'Neue Akte „Fachtag Ernährung“?', detail: '', source: 'akte_vorschlag', source_ref: 'v1'},
    {id: 'n', title: 'Was kam bei „Rheinauenblick“ heraus?', detail: '', source: 'nachbereitung', source_ref: 'uid|1'},
  ]), []);
  const andere = nodes(baum, n => n.props?.className === 'today-attention-item');
  assert.equal(andere.length, 3);
  for (const zeile of andere) assert.equal(nodes(zeile, n => n.props?.className === 'today-item-symbol').length, 1, 'das Zeichen steht in der Spalte des Kreises');
  assert.equal(nodes(andere[0], n => n.type?.name === 'BriefingSuggestion').length, 1);
  assert.equal(nodes(andere[1], n => n.type?.name === 'AkteVorschlagKnoepfe').length, 1);
  assert.equal(nodes(andere[2], n => n.type === 'a')[0].props.href, '/calendar?nachbereiten=uid%7C1');
  const css = quelle('TodayOverview.css');
  const regel = css.match(/\.today-attention-item \{[^}]*\}/)[0];
  assert.match(regel, /grid-template-columns: 44px minmax\(0, 1fr\) auto/, 'dieselbe Spalte wie der Kreis');
  assert.match(regel, /min-height: var\(--g-zeile\)/, 'mindestens 52 px wie eine Zeile der Liste');
  assert.match(css, /\.today-attention-list > li \+ li::before \{ left: 56px; \}/, 'Trenner unter dem Text, nicht unter dem Kreis');
  assert.doesNotMatch(quelle('TodayOverview.tsx') + quelle('TodayTaskRow.tsx'), /today-task-more|Hier bearbeiten|Bearbeitung fortsetzen/);
});

test('schmal liegt das Aufgabenpaneel über der oberen Navigation, nicht darunter', () => {
  // Heute isoliert sich für die Landschaft und der Inhaltsbereich hat eine eigene Ebene; beides fällt, solange das
  // Paneel offen ist (im Browser bei 768 und 390 geprüft: „Schließen“ ist sichtbar und klickbar).
  const css = quelle('TodayOverview.css');
  const schmal = css.match(/@media \(max-width: 900px\) \{([\s\S]*?)\n\}/)[1];
  assert.match(schmal, /\n  \.today-page:has\(\.workspace-detail\) \{ isolation: auto; \}/);
  assert.match(schmal, /\n  #root \.today-page:has\(\.workspace-detail\) \.briefing-area \{ z-index: auto; \}/);
});
