// Flächenpaket P2 (Aufgaben und Persönliche Entwicklung, Grundlage vom 23.10.2026): Quelltext- und Stilzusicherungen.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {dueLabel} from '../src/taskWorkspaceModel.ts';

const src = name => readFileSync(new URL(`../src/${name}`, import.meta.url), 'utf8');
const BEREICH = ['WorkspaceTasks.css', 'DecisionControls.css', 'ProjectOverview.css', 'ProjectControls.css', 'DetailPanel.css'];

test('die Spalte bleibt im Fenster: die Segmentleiste rollt auch schmal, statt hinter dem Rand zu verschwinden', () => {
  const css = src('WorkspaceTasks.css');
  // Eine feste Höchstbreite allein würde die Leiste bei 390 px breiter als das Fenster machen (Abschnitte unerreichbar).
  assert.match(css, /#root main\.aufgaben > :not\(\.g-kopfleiste, \.workspace-detail\) \{ max-width: min\(960px, 100%\); \}/);
  // Ist das Detailpaneel offen und das Fenster breit, rückt die Liste zur Seite.
  assert.match(css, /@media \(min-width: 1180px\) \{\n  #root main\.aufgaben:has\(> \.workspace-detail\) \{ padding-right: /);
});

test('keine lokalen Farben im Bereich: nur Werte der Grundlage (--g-*) und von CalmUI (--calm-*)', () => {
  for (const name of BEREICH) {
    // Der gemeinsame Textknopf `.text-action` steht unverändert aus dem Bestand in DecisionControls.css.
    const css = src(name).split('\n').filter(zeile => !zeile.startsWith('.text-action')).join('\n');
    assert.doesNotMatch(css, /#[0-9a-fA-F]{3,8}\b/, `${name} setzt eine eigene Farbe`);
    assert.doesNotMatch(css, /\bInter\b/, `${name} setzt eine eigene Schrift`);
  }
});

test('Bausteine statt eigener Köpfe: Aufgaben und Entwicklung mit Seitenkopf, Segmenten, Gruppen und Leer', () => {
  const app = src('App.tsx');
  const tasks = app.slice(app.indexOf('function Tasks('), app.indexOf('export function App('));
  assert.match(tasks, /<Seitenkopf className="tasks-heading" titel="Aufgaben"/);
  assert.match(tasks, /<Segmente className="aufgaben-segmente" label="Aufgabenansichten"/);
  assert.doesNotMatch(tasks, /task-tabs|className="eyebrow"/, 'no old tab bar, no overline');
  assert.match(tasks, /<Gruppe className="workspace-task-group"/);
  assert.match(tasks, /<Leer className="task-empty"/);
  const dev = src('DevelopmentPage.tsx');
  assert.match(dev, /<Seitenkopf className="tasks-heading" titel="Persönliche Entwicklung"/);
  for (const ziel of ['/vorhaben', '/wellbeing', '/review']) assert.match(dev, new RegExp(`<Zeile href="${ziel}"`), `${ziel} stays reachable`);
  assert.doesNotMatch(dev, /Zurück zu Heute|eyebrow/, 'Heute steht in der Seitenleiste');
});

test('ein gefüllter Knopf: Entscheidungen und Ziele füllen ihren Knopf nur, solange kein Formular offen ist', () => {
  const decisions = src('DecisionControls.tsx');
  assert.match(decisions, /\{!creating \? <button className=\{kopf \? "secondary-action" : "primary-action"\}/);
  const goals = src('GoalControls.tsx');
  assert.match(goals, /const formularOffen = Boolean\(editing \|\| closing \|\| nextStepGoal\);/);
  assert.match(goals, /className=\{formularOffen \? "secondary-action" : "primary-action"\}/);
  // Die Gewohnheit ist der zweite Knopf der Ansicht: getönt.
  assert.match(src('HabitControls.tsx'), /<button className="secondary-action" disabled=\{busy \|\| !label\.trim\(\)\}>Gewohnheit festhalten/);
});

test('Zusagen bleiben: Vorschläge werden erst mit Bestätigung zur Aufgabe, nichts geht nach draußen, Warten bleibt lokal', () => {
  assert.match(src('TaskSuggestions.tsx'), /In deinen Quellen erkannt\. Erst deine Bestätigung macht daraus eine Aufgabe\./);
  assert.match(src('TaskSuggestions.tsx'), /Quelldatum: [\s\S]*Erfasst: /, 'source date and capture time stay distinguishable');
  assert.match(src('AufgabenPostVorschlaege.tsx'), /fussnote="Nicht sicher genug, um es selbst abzulegen\. Nichts geht nach draußen\."/);
  assert.match(src('TaskRow.tsx'), /<small>Nur lokal vermerken; keine Nachricht senden\.<\/small>/);
  assert.match(src('GoalControls.tsx'), /Der Widerruf bleibt nachvollziehbar\. Er bedeutet nicht, dass das Ziel erreicht wurde\./);
});

test('Quelle und Verlauf der Aufgabe sind ruhige Aufklapper mit Zustand für Vorleser', () => {
  for (const [datei, titel] of [['TaskSource.tsx', 'Quelle'], ['TaskHistory.tsx', 'Verlauf']]) {
    assert.match(src(datei), new RegExp(`<button type="button" className="task-aufklapper" aria-expanded=\\{open\\} onClick=\\{\\(\\) => setOpen\\(value => !value\\)\\}>${titel}</button>`));
  }
  assert.match(src('WorkspaceTasks.css'), /#root \.task-aufklapper\[aria-expanded="true"\]::after \{ transform: /);
});

test('Fälligkeit, wie man sie sagt: Heute, Morgen, Gestern, sonst Tag und Monat (Jahr nur, wenn es ein anderes ist)', () => {
  const jetzt = new Date(2026, 8, 29, 7, 31);
  assert.equal(dueLabel(new Date(2026, 8, 29, 17).toISOString(), jetzt), 'Heute');
  assert.equal(dueLabel(new Date(2026, 8, 30, 10).toISOString(), jetzt), 'Morgen');
  assert.equal(dueLabel(new Date(2026, 8, 28, 10).toISOString(), jetzt), 'Gestern');
  assert.equal(dueLabel(new Date(2026, 9, 2, 17).toISOString(), jetzt), '2. Okt.');
  assert.equal(dueLabel(new Date(2027, 0, 4, 17).toISOString(), jetzt), '4. Jan. 2027');
  assert.equal(dueLabel(null, jetzt), 'Ohne Termin');
  assert.equal(dueLabel('kein Datum', jetzt), 'Termin nicht lesbar');
});
