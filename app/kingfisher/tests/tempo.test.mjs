// Tempo (V7, 25.10.2026): Menschen, Projekte und die Suche kommen mit dem Verzeichnis aus, nicht mit dem ganzen
// Gedächtnisgraphen, und zeigen dasselbe.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {brauchtGraph, graphUmfang, hatQuellen} from '../src/MemoryBrowseModel.ts';
import {contactDateFromGraph} from '../src/WorkspaceMemoryModel.ts';

const quelle = name => readFileSync(new URL(`../src/${name}`, import.meta.url), 'utf8');

test('Suchen, Menschen und Projekte brauchen nur das Verzeichnis, Entscheidungen den ganzen Graphen', () => {
  for (const tab of ['search', 'people', 'projects']) assert.equal(graphUmfang(tab), 'verzeichnis', tab);
  assert.equal(graphUmfang('decisions'), 'voll');
  for (const tab of ['areas', 'documents', 'organizations', 'places', 'topics', 'topic-files']) assert.equal(graphUmfang(tab), 'keiner', tab);
  assert.equal(graphUmfang('people', 'status'), 'keiner');
  assert.equal(brauchtGraph('people'), true);
  assert.equal(brauchtGraph('organizations'), false);
});

const person = {id: 'person:a', kind: 'person', label: 'Anna Keller <anna@x.example>', attributes: {}};
const quelleKnoten = (id, occurred_at, extra = {}) => ({id, kind: 'episode', label: id, attributes: {occurred_at, ...extra}});
const kante = (target, actual_contact = true) => ({id: 'e-' + target, source: 'person:a', target, relation: 'participated_in', scope: null,
  confidence: 1, state: 'observed', evidence_refs: [], actual_contact});
const voll = {generated_at: '2026-09-29T07:30:00+02:00', authority: 'projection', edges: [kante('episode:1'), kante('episode:2'), kante('episode:3', false)],
  nodes: [person, quelleKnoten('episode:1', '2026-09-20T10:00:00+02:00'), quelleKnoten('episode:2', '2026-12-01T10:00:00+01:00', {episode_kind: 'event'}),
    quelleKnoten('episode:3', '2026-09-28T10:00:00+02:00')]};

test('der letzte Kontakt ist im Verzeichnis derselbe wie aus dem ganzen Graphen', () => {
  const ausGraph = contactDateFromGraph(voll, 'person:a');
  assert.equal(ausGraph, new Date('2026-09-20T10:00:00+02:00').toLocaleDateString('de-DE'));
  // Das Verzeichnis bringt den Zeitpunkt mit (Sidecar `graph.verzeichnis`, dieselbe Regel) und hat keine Kanten.
  const verzeichnis = {...voll, nodes: [person], edges: [], verzeichnis: {hat_quellen: true, letzter_kontakt: {'person:a': '2026-09-20T10:00:00+02:00'}}};
  assert.equal(contactDateFromGraph(verzeichnis, 'person:a'), ausGraph);
  assert.equal(contactDateFromGraph(verzeichnis, 'person:b'), 'unbekannt');
  assert.equal(contactDateFromGraph(voll, 'person:b'), 'unbekannt');
  assert.equal(hatQuellen(verzeichnis), true);
  assert.equal(hatQuellen({...verzeichnis, verzeichnis: {hat_quellen: false, letzter_kontakt: {}}}), false);
  assert.equal(hatQuellen(voll), true);
  assert.equal(hatQuellen({...voll, nodes: [person]}), false);
});

test('die Gedächtnisseite holt das Verzeichnis und zeigt den Graphen erst, wenn er ganz da ist', () => {
  const seite = quelle('MemoryGraph.tsx');
  assert.match(seite, /\(art === "voll" \? api\.memoryGraph\(\) : api\.memoryVerzeichnis\(\)\)/);
  assert.match(seite, /const passend = graph !== null && \(umfang !== "voll" \|\| graphArt === "voll"\);/);
  // Ein später eintreffendes Verzeichnis ersetzt einen schon geladenen ganzen Graphen nicht.
  assert.match(seite, /artGeladen\.current === "voll" && art === "verzeichnis"\)\) return;/);
  assert.match(seite, /\) : graph && passend \? \(filter === "people"/);
  assert.match(seite, /hasSources=\{hatQuellen\(graph\)\}/);
  assert.match(quelle('MemorySearch.tsx'), /\|\| hatQuellen\(graph\)\)/);
  assert.match(quelle('api.ts'), /memoryVerzeichnis: \(\) => request<MemoryGraph>\("\/api\/v1\/memory\/verzeichnis"\)/);
});

test('Heute holt erst den Gruß und danach das volle Briefing, nicht beides zugleich', () => {
  const app = quelle('App.tsx');
  const morgen = app.slice(app.indexOf('function Morning('), app.indexOf('async function begin('));
  assert.match(morgen, /api\.morning\(false\)\.then\([\s\S]*?\.finally\(\(\) => \{ if \(active\) void refresh\.run\(true\); \}\);/);
  // Kein zweiter, gleichzeitiger Start der vollen Fassung.
  assert.equal(morgen.match(/refresh\.run\(true\)/g).length, 1);
});

test('während das volle Briefing kommt, hängt Heute keinen Text an, der die Seite springen ließe', () => {
  const app = quelle('App.tsx');
  assert.match(app, /<span className="today-stand" aria-busy=\{refreshing \|\| undefined\}>Stand \{stand\}\{refreshing \? <span className="visually-hidden"> · wird aktualisiert …<\/span> : null\}<\/span>/);
  assert.doesNotMatch(app, /refreshing \? " · wird aktualisiert …"/);
  assert.match(quelle('TodayOverview.css'), /\.today-stand\[aria-busy="true"\] \{ animation: today-atmen/);
});
