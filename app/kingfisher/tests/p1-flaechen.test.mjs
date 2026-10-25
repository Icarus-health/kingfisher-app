// Flächenpaket P1 (Heute und Gespräche, 23.10.2026): große ruhige Flächen, wenig Text, ein gefüllter Knopf je Ansicht,
// Quelldatum und Erfassung in einer leisen Zeile unterscheidbar. Quelltext- und Modelltests mit synthetischen Daten.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {eingangZeile} from '../src/heute.ts';

const quelle = (datei) => readFileSync(new URL(`../src/${datei}`, import.meta.url), 'utf8');
const ohneKommentare = (css) => css.replace(/\/\*[\s\S]*?\*\//g, '');
const regel = (css, selektor) => {
  const treffer = ohneKommentare(css).split('}').map(teil => teil.trim()).find(teil => teil.split('{')[0].trim() === selektor);
  assert.ok(treffer, `Regel ${selektor} fehlt`);
  return treffer.split('{')[1];
};
const JETZT = '2026-09-29T05:31:00Z';

test('Neu eingegangen: eine Zeile mit Art, Quelldatum und, an einem anderen Tag, der Erfassung', () => {
  assert.deepEqual(eingangZeile({source: 'working_memory', detail: 'Quelle berichtet · Zusage', occurred_at: '2026-09-26T07:40:00Z',
    recorded_at: '2026-09-29T05:30:00Z'}, 'Europe/Berlin', JETZT),
  {zeile: 'Zusage · 26. Sept. · erfasst heute, 07:30', titel: 'Quelldatum: 26.09.2026, 09:40 · Erfasst: 29.09.2026, 07:30'});
  // „Angabe“ sagt nichts, „Quelle berichtet“ steht schon in der Überschrift.
  assert.equal(eingangZeile({source: 'working_memory', detail: 'Quelle berichtet · Zusage, Angabe', occurred_at: '2026-06-08T15:45:00Z',
    recorded_at: '2026-09-29T05:30:00Z'}, 'Europe/Berlin', JETZT).zeile, 'Zusage · 8. Juni · erfasst heute, 07:30');
  // Am selben Tag erfasst: das Datum genügt in der Zeile, der Hinweis nennt beide Zeitpunkte.
  const mail = eingangZeile({source: 'mail', detail: 'Eva Brandl', occurred_at: '2026-09-29T04:10:00Z', recorded_at: '2026-09-29T05:30:00Z'}, 'Europe/Berlin', JETZT);
  assert.equal(mail.zeile, 'Eva Brandl · heute, 06:10');
  assert.equal(mail.titel, 'Quelldatum: 29.09.2026, 06:10 · Erfasst: 29.09.2026, 07:30');
  // Ohne Quelldatum wird nichts erfunden; ein anderes Jahr steht dabei.
  assert.equal(eingangZeile({source: 'mail', detail: 'Eva Brandl', occurred_at: null, recorded_at: '2025-09-29T05:30:00Z'}, 'Europe/Berlin', JETZT).zeile,
    'Eva Brandl · Datum unbekannt · erfasst 29. Sept. 2025');
  assert.deepEqual(eingangZeile({source: 'proposals', detail: '2 warten auf Bestätigung'}, 'Europe/Berlin', JETZT), {zeile: '2 warten auf Bestätigung'});
});

test('Heute: der Fuß und die Tageslage sind Zeilen einer Fläche, kein Dreieck und keine Linkreihe', () => {
  const heute = quelle('TodayOverview.tsx');
  assert.doesNotMatch(heute, /<details className="today-activity/, 'Tageslage ohne Klappdreieck');
  assert.match(heute, /<button className="g-zeile today-activity-zeile" type="button" aria-expanded=\{activityOpen\}/);
  const fuss = heute.match(/export function TodayPersonal\(\) \{([\s\S]*?)\n\}/)[1];
  // Der Baustein `Zeile` als Verweis (V4): eine ganze Zeile mit Pfeil je Bereich.
  assert.equal((fuss.match(/<Zeile href="\/(?:development|world|wellbeing|review)" titel="[^"]+" \/>/g) ?? []).length, 4, 'vier ganze Zeilen');
  assert.doesNotMatch(fuss, /today-text-link/);
});

test('Heute: die Landschaft läuft in den Grund aus, die Statuszeile steht nicht im Bild, schmal ein heller Schleier', () => {
  const css = quelle('TodayOverview.css');
  const bild = regel(css, '.today-landscape');
  // Beide Schreibweisen: die ungepräfixte gilt in Chromium, die gepräfixte in WebKit (Safari, Tauri unter macOS).
  assert.match(bild, /(?<!-)mask-image: linear-gradient\(to bottom, #000 0%, #000 \d+%, transparent \d+%\)/);
  assert.match(bild, /-webkit-mask-image: linear-gradient\(to bottom, #000 0%, #000 \d+%, transparent \d+%\)/);
  assert.doesNotMatch(ohneKommentare(css), /briefing-area \{[^}]*margin-top: -/, 'nichts zieht den Inhalt ins Bild');
  const schmal = ohneKommentare(css).match(/@media \(max-width: 900px\) \{([\s\S]*?)\n\}/)[1];
  assert.match(schmal, /linear-gradient\(180deg, rgba\(245,246,248,\.7\d\)/, 'der Gruß bleibt auf dem Bild lesbar');
  assert.doesNotMatch(quelle('NordicWorkspace.css'), /\.today-(?:page|landscape|source-status|activity|personal)\b/, 'Heute hat eine Quelle für seine Stile');
});

test('Gespräch: gefüllt ist Senden mit Text oder die Freigabe; Vorschläge sind nicht gefüllt, leeres Senden grau', () => {
  const senden = quelle('CommandBar.css');
  assert.match(regel(senden, '.shell .command-bar .send-button:disabled'), /background: var\(--g-segment-grund\)/);
  const chat = quelle('Workspace.css');
  assert.match(regel(chat, '.shell .workspace-chat .memory-candidate:not(.action-approval) .memory-confirm'), /background: var\(--g-flaeche\); box-shadow: var\(--g-schatten\)/);
  assert.match(regel(chat, '.shell .workspace-chat .memory-candidate:not(.action-approval) .memory-reject'), /background: transparent/);
  // Die Freigabekarte bleibt vollständig: Vorschau, Bestätigungswort, Freigeben, Ablehnen, Ergebnis, Fehlergrund.
  const karte = quelle('ActionApprovalCard.tsx');
  for (const teil of ['action.dry_run', 'action.confirmation_phrase', 'Freigeben und ausführen', 'Ablehnen', 'labels[action.state]',
    'Freigabe nicht bestätigt. Bitte den Gesprächsstand neu laden und das Ergebnis prüfen.'])
    assert.ok(karte.includes(teil), teil);
});

test('Gespräch: wer spricht, bleibt für Vorleseprogramme da; Ziele des Rückkanals 44 px', () => {
  const app = quelle('App.tsx');
  assert.match(app, /<span className="message-wer">\{message\.role === "user" \? "Du" : "Kingfisher"\}<\/span>/);
  assert.match(regel(quelle('Workspace.css'), '.shell main.workspace-chat .message > .message-wer'), /clip-path: inset\(50%\)/);
  for (const [datei, selektor] of [['Rueckmeldung.css', '.stimmt-nicht-link'], ['Rueckmeldung.css', '.stimmt-nicht-arten button'],
    ['Workspace.css', '.workspace-chat .beleg-quellen .quiet-source-toggle'], ['Workspace.css', '.workspace-chat .conversation-new']])
    assert.match(regel(quelle(datei), selektor), /(?:min-height|height): 44px/, selektor);
});
