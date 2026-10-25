// Viel Bestand (V6, 25.10.2026): Was bei 8.000 Mails, 600 Kontakten und 300 Aufgaben auffiel, bleibt behoben.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {brauchtGraph} from '../src/MemoryBrowseModel.ts';
import {heuteKopfZeile} from '../src/taskWorkspaceModel.ts';

const quelle = name => readFileSync(new URL(`../src/${name}`, import.meta.url), 'utf8');

test('nur Suchen, Menschen, Projekte und Entscheidungen laden den ganzen Gedächtnisgraphen', () => {
  for (const tab of ['search', 'people', 'projects', 'decisions']) assert.equal(brauchtGraph(tab), true, tab);
  for (const tab of ['areas', 'documents', 'organizations', 'places', 'topics', 'topic-files']) assert.equal(brauchtGraph(tab), false, tab);
  assert.equal(brauchtGraph('people', 'status'), false);
  assert.equal(brauchtGraph('search', 'support'), false);
  const seite = quelle('MemoryGraph.tsx');
  // Der Graph wird nur angefragt, wenn die Ansicht ihn braucht, und das Laden der Seite hängt nur dann an ihm.
  assert.match(seite, /if \(!graphNoetig \|\| graphAngefragt\.current\) return;/);
  assert.match(seite, /data-memory-loading=\{graphNoetig && !graph && !error\}/);
  // Ein Fehler des Graphen sperrt Organisationen, Orte und Themen nicht.
  assert.match(seite, /: error && graphNoetig \? \(/);
});

test('die Zeile über den Aufgaben nennt keine Seitengröße als Zahl', () => {
  const seite1 = {seite: 1, weitere: true};
  assert.equal(heuteKopfZeile(50, 50, seite1), 'Mehr als 50 Aufgaben brauchen dich heute.');
  assert.equal(heuteKopfZeile(12, 50, seite1), '12 Aufgaben brauchen dich heute.');
  assert.equal(heuteKopfZeile(1, 1, {seite: 1, weitere: false}), 'Eine Aufgabe braucht dich heute.');
  assert.equal(heuteKopfZeile(7, 7, {seite: 1, weitere: false}), '7 Aufgaben brauchen dich heute.');
  assert.equal(heuteKopfZeile(0, 50, seite1), undefined);
  assert.equal(heuteKopfZeile(50, 50, {seite: 2, weitere: true}), undefined);
  assert.match(quelle('App.tsx'), /heuteKopfZeile\(heuteDran, listTasks\?\.length \?\? 0, \{seite: taskPage\.page, weitere: taskPage\.canNext\}\)/);
});

test('ein gekürzter Betreff in der Mailliste steht ganz im Titel', () => {
  assert.match(quelle('Messages.tsx'), /<span className="mail-subject" title=\{betreff \|\| undefined\}>/);
});

test('lange Wörter in Fundstellen der Suche brechen um, statt über den Rand zu ragen', () => {
  assert.match(quelle('MemoryWorkspace.css'), /#root \.memory-search-results blockquote \{ overflow-wrap: anywhere; \}/);
});
