// Heute als die eine ruhige Seite (Paket U, H1 bis H8): ein gefüllter Knopf, Bilder nur im Kopf, leere Bereiche in
// einem Satz, die Vorbereitung am Termin, neue Post nur, wenn welche da ist, eine Uhr ohne Sekunden. Synthetische Daten.
import {test, after} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createServer} from 'vite';
import {fileURLToPath} from 'node:url';
import {naechsterTerminText} from '../src/heute.ts';

const quelle = (datei) => readFileSync(new URL(`../src/${datei}`, import.meta.url), 'utf8');
const server = await createServer({root: fileURLToPath(new URL('..', import.meta.url)), cacheDir: `/private/tmp/kingfisher-heute-ruhe-${process.pid}`, configFile: false,
  plugins: [{name: 'ruhe-hooks', enforce: 'pre', resolveId(id) { if (id === 'virtual:ruhe-hooks') return '\0' + id; },
    load(id) { if (id === '\0virtual:ruhe-hooks') return 'export const useState=v=>[typeof v==="function"?v():v,()=>{}];export const useRef=v=>({current:v});export const useEffect=()=>{};export const useMemo=f=>f();export const useCallback=f=>f;'; },
    transform(code, id) { if (id.endsWith('/TodayOverview.tsx')) return code.replace(/from (["'])react\1/, 'from "virtual:ruhe-hooks"'); }}],
  server: {middlewareMode: true, watch: null, ws: false, hmr: false}, appType: 'custom'});
after(() => server.close());
const {TodayOverview} = await server.ssrLoadModule('/src/TodayOverview.tsx');
const {ProfileSource} = await server.ssrLoadModule('/src/ProfileSource.tsx');

function nodes(n, p, out = []) { if (!n || typeof n !== 'object') return out; if (p(n)) out.push(n); [n.props?.children].flat(50).forEach(c => nodes(c, p, out)); return out; }
function text(n) { return n == null || typeof n === 'boolean' ? '' : typeof n === 'object' ? [n.props?.children].flat(50).map(text).join('') : String(n); }
const leer = {generated_at: '2026-09-29T05:30:00Z', timezone: 'Europe/Berlin', partial_failures: [], needs_you: [], later_today: [], happening_now: [], greeting: 'Guten Morgen.'};
const zeige = (briefing) => TodayOverview({briefing, onChange() {}, onTaskDone() {}, onOpenMail() {}, taskNotice: '', correctionSaved: false});
const morning = () => quelle('App.tsx').match(/function Morning\([\s\S]*?\n\}\n/)[0];

test('H2: Bilder nur im Seitenkopf, kein Eisvogel und keine Landschaft in Karten', () => {
  assert.equal((morning().match(/<img /g) ?? []).length, 1, 'genau ein Bild auf Heute: der Eisvogel im Kopf');
  assert.match(morning(), /<section className="hero">\s*<img className="hero-bird"/);
  for (const datei of ['TodayOverview.tsx', 'TodayTaskActions.tsx', 'TodaySourceStatus.tsx', 'PostfachStand.tsx', 'AudioBriefing.tsx'])
    assert.doesNotMatch(quelle(datei), /<img\b|ASSET\.media/, datei);
  assert.doesNotMatch(quelle('Einrichtung/HeuteLeer.tsx'), /<img\b/, 'auch der leere Heute-Zustand trägt kein Bild in der Karte');
});

test('H2/H3: höchstens ein gefüllter Knopf auf Heute, Zeilenaktionen leise, der Zähler ohne Signalfarbe', () => {
  for (const datei of ['TodayOverview.tsx', 'TodayTaskActions.tsx', 'TodaySourceStatus.tsx', 'PostfachStand.tsx', 'AudioBriefing.tsx'])
    assert.doesNotMatch(quelle(datei), /primary-action|tasks-add|play-toggle/, datei);
  assert.doesNotMatch(morning(), /primary-action|today-briefing-button/);
  const css = quelle('TodayOverview.css');
  const aktion = css.match(/\.today-action \{[^}]*\}/)[0];
  assert.match(aktion, /background: transparent/, 'Erledigen ist umrandet, nicht gefüllt');
  assert.doesNotMatch(css.match(/\.today-count \{[^}]*\}/)[0], /background|#ef792d/i, 'die Zahl ist kein orangefarbener Kreis');
  // Der eine gefüllte Knopf: Senden, in der Hauptaktionsfarbe statt in Orange (H5).
  assert.match(quelle('styles.css'), /\.command-bar \.send-button \{ background: var\(--calm-primary\);/);
  assert.doesNotMatch(quelle('styles.css'), /\.send-button \{[^}]*e76f2b/);
});

test('H8: leere Bereiche sagen es in einem Satz, ohne leere Karte für neue Post', () => {
  const baum = zeige(leer);
  const saetze = nodes(baum, n => n.props?.className === 'today-empty').map(text);
  assert.deepEqual(saetze, ['Nichts wartet auf dich.', 'Heute keine Termine.']);
  assert.equal(nodes(baum, n => n.type === 'h3' && n.props?.className === undefined && /Noch kein|Keine weiteren/.test(text(n))).length, 0);
  assert.equal(nodes(baum, n => n.props?.className?.includes?.('today-news')).length, 0, 'keine leere Gruppe „Neu eingegangen“');
  assert.equal(nodes(baum, n => n.props?.className === 'today-count').length, 0, 'kein Nullzähler');
  const mitNaechstem = zeige({...leer, naechster_termin: {title: 'Rheinauenblick', start: '2026-09-30T14:00:00+02:00', ganztags: false}});
  assert.equal(text(nodes(mitNaechstem, n => n.props?.className === 'today-empty')[1]), 'Heute keine Termine. Nächster: Mi., 30.9., 14:00 Rheinauenblick');
  const ohneKalender = zeige({...leer, partial_failures: [{section: 'calendar', message: 'Kalender ist nicht verbunden.'}]});
  assert.match(text(nodes(ohneKalender, n => n.props?.className === 'today-empty')[1]), /Termine fehlen, der Kalender ist nicht lesbar/, 'ein fehlender Kalender ist kein leerer Tag');
});

test('H1: die Vorbereitung steht am Termin, neue Post als ruhige Liste mit Quelle, höchstens drei', () => {
  const briefing = {...leer,
    later_today: [{id: 'c', time: '14:00', title: 'Rheinauenblick', detail: 'Mainz', source: 'calendar', source_ref: 'uid-1'}],
    needs_you: [{id: 'n', title: 'Termin vorbereiten', reason: 'Unterlagen mitnehmen', source: 'termin', source_ref: 'uid-1'}],
    happening_now: [
      {id: 'm', title: 'Honorar und Ablauf', detail: 'Frau Brandl', source: 'mail', source_ref: 'INBOX:1', occurred_at: '2026-09-28T10:00:00Z'},
      {id: 'w', title: 'Alles Gute!', detail: 'Quelle berichtet · Angabe', source: 'working_memory', source_ref: 'ep-1'},
      {id: 'p', title: 'Gedächtnisvorschläge', detail: '2 warten auf Bestätigung', source: 'proposals', source_ref: null},
    ]};
  const baum = zeige(briefing);
  const termin = nodes(baum, n => n.type === 'li' && /Rheinauenblick/.test(text(n)))[0];
  assert.match(text(termin), /Unterlagen mitnehmen/, 'der Grund der Vorbereitung steht am Termin');
  assert.equal(nodes(termin, n => n.type === 'a')[0].props.href, '/calendar?prepare=uid-1');
  assert.equal(nodes(baum, n => n.props?.className === 'today-attention-item').length, 0, 'die Vorbereitung steht nicht noch einmal unter „Braucht dich“');
  const liste = nodes(baum, n => n.props?.className === 'today-news-list')[0];
  assert.equal(nodes(liste, n => n.type === 'li').length, 3);
  assert.equal(nodes(liste, n => n.type === 'button' && /Nachricht öffnen/.test(text(n))).length, 1);
  const beleg = nodes(liste, n => n.type === ProfileSource)[0];
  assert.ok(beleg, 'die Quelle bleibt einen Klick entfernt');
  assert.equal(beleg.props.id, 'ep-1'); assert.equal(beleg.props.allowDismiss, true);
  assert.match(text(liste), /Quelldatum/, 'Quelldatum und Erfassung bleiben unterscheidbar');
});

test('Nachtrag 23.10.: ein großer Titel mit einer Zeile darunter, Ziele mindestens 44 px hoch', () => {
  const kopf = morning().match(/<div className="hero-copy">[\s\S]*?<\/div>/)[0];
  assert.doesNotMatch(kopf, /today-hero-label|DEIN TAG/, 'keine Überzeile über dem Titel');
  assert.equal((kopf.match(/<p\b/g) ?? []).length, 1, 'genau eine Zeile unter dem Titel');
  const css = quelle('TodayOverview.css');
  for (const regel of [/\.today-action \{[^}]*\}/, /\.today-text-link \{[^}]*\}/, /\.today-task-more > summary \{[^}]*\}/])
    assert.match(css.match(regel)[0], /min-height: 44px/, String(regel));
  assert.doesNotMatch(css + quelle('AudioBriefing.css'), /\.today-text-link \{[^}]*min-height: (?:[0-3]?\d|4[0-3])px/, 'kein Textknopf auf Heute kleiner als 44 px');
});

test('H5: der Platzhalter nennt, was geht, nicht was fehlt', () => {
  const app = quelle('App.tsx');
  assert.doesNotMatch(app, /Modell verbinden/);
  assert.match(app, /"Frag nach Menschen, Projekten, Terminen …"/);
  assert.match(quelle('CommandBar.tsx'), /: "Frag Kingfisher …"\)\}/);
});

test('H6: der Fuß ist eine Zeile Textlinks ohne Überschrift; der Postfachstand nur bei etwas zu tun', () => {
  const heute = quelle('TodayOverview.tsx');
  const fuss = heute.match(/export function TodayPersonal\(\) \{([\s\S]*?)\n\}/)[1];
  assert.doesNotMatch(fuss, /<h2|Für dich/);
  assert.doesNotMatch(heute, /Neu im Gedächtnis/, 'neue Quellen stehen offen in der Liste, nicht in einer Klappe');
  assert.match(quelle('PostfachStand.tsx'), /if \(ausstehend \|\| !mussHandeln\) return null;/);
});

test('H7: die Uhr der Seitenleiste zeigt Stunden und Minuten, ohne Sekunden', () => {
  const uhr = quelle('LiveClock.tsx');
  assert.doesNotMatch(uhr, /second:/);
  assert.match(uhr, /hour: "2-digit", minute: "2-digit", hour12: false/);
});

test('der nächste Termin wird kurz und in der Zone des Briefings genannt', () => {
  assert.equal(naechsterTerminText({title: 'Rheinauenblick', start: '2026-09-30T12:00:00Z', ganztags: false}, 'Europe/Berlin'), 'Mi., 30.9., 14:00 Rheinauenblick');
  assert.equal(naechsterTerminText({title: 'Geburtstag von Anna', start: '2026-10-01T00:00:00+02:00', ganztags: true}, 'Europe/Berlin'), 'Do., 1.10., Geburtstag von Anna');
  assert.equal(naechsterTerminText(null, 'Europe/Berlin'), null);
  assert.equal(naechsterTerminText({title: 'Kaputt', start: 'kein Datum', ganztags: false}, 'Europe/Berlin'), null);
});
