// Befund A5 der Persona-Prüfung: Heute sagte „8 Vorschläge sind zeitlich ungeklärt“ und zugleich „Nichts wartet auf
// dich“. Beide Sätze passen jetzt zusammen: Nichts *Neues* wartet, und bei älteren Vorschlägen ist unklar, ob sie noch
// gelten. Ohne solche Vorschläge bleibt es bei „Nichts wartet auf dich.“ Synthetische Daten.
import {test, after} from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'vite';
import {fileURLToPath} from 'node:url';
import {testCache} from './testcache.mjs';

const server = await createServer({root: fileURLToPath(new URL('..', import.meta.url)), cacheDir: testCache('heute-pruefen'), configFile: false,
  plugins: [{name: 'pruefen-hooks', enforce: 'pre', resolveId(id) { if (id === 'virtual:pruefen-hooks') return '\0' + id; },
    load(id) { if (id === '\0virtual:pruefen-hooks') return 'export const useState=v=>[typeof v==="function"?v():v,()=>{}];export const useRef=v=>({current:v});export const useEffect=()=>{};export const useMemo=f=>f();export const useCallback=f=>f;'; },
    transform(code, id) { if (id.endsWith('/TodayOverview.tsx')) return code.replace(/from (["'])react\1/, 'from "virtual:pruefen-hooks"'); }}],
  server: {middlewareMode: true, watch: null, ws: false, hmr: false}, appType: 'custom'});
after(() => server.close());
const {TodayOverview} = await server.ssrLoadModule('/src/TodayOverview.tsx');
const {TodaySourceStatus} = await server.ssrLoadModule('/src/TodaySourceStatus.tsx');

function nodes(n, p, out = []) { if (!n || typeof n !== 'object') return out; if (p(n)) out.push(n); [n.props?.children].flat(50).forEach(c => nodes(c, p, out)); return out; }
function text(n) { return n == null || typeof n === 'boolean' ? '' : typeof n === 'object' ? [n.props?.children].flat(50).map(text).join('') : String(n); }
const leer = {generated_at: '2026-10-27T06:20:00Z', timezone: 'Europe/Berlin', partial_failures: [], needs_you: [], later_today: [], happening_now: [], greeting: 'Guten Morgen.'};
const braucht = (briefing) => text(nodes(TodayOverview({briefing, onChange() {}, onTaskDone() {}, onOpenMail() {}, taskNotice: '', correctionSaved: false}),
  n => n.props?.className === 'today-empty')[0]);
const status = (briefing) => text(TodaySourceStatus({briefing, refreshing: false, refreshError: false, onRefresh() {}}));

test('A5: ohne ungeklärte Vorschläge bleibt „Nichts wartet auf dich.“ und die Zeile fehlt', () => {
  assert.equal(braucht(leer), 'Nichts wartet auf dich.');
  assert.equal(TodaySourceStatus({briefing: leer, refreshing: false, refreshError: false, onRefresh() {}}), null);
});

test('A5: mit ungeklärten Vorschlägen sagen beide Sätze dasselbe', () => {
  const acht = {...leer, historical_task_reviews: 8};
  assert.equal(braucht(acht), 'Nichts Neues wartet auf dich.');
  assert.equal(status(acht), 'Bei 8 Vorschlägen ist unklar, ob sie noch gelten. Prüfen →');
  assert.doesNotMatch(status(acht), /zeitlich ungeklärt/, 'kein Fachwort');
  assert.equal(status({...leer, historical_task_reviews: 1}), 'Bei einem Vorschlag ist unklar, ob er noch gilt. Prüfen →');
});
