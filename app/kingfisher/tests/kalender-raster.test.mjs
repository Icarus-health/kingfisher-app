// Der Kalendermonat als Raster mit einem Tab-Halt, und eine saubere Überschriftenfolge (Persona-Prüfung, Paket B, B5).
// Vorher: rund 45 Tab-Stopps ohne Pfeiltasten, Termine als 6 × 6 px große Punkte zum Antippen; Nachrichten mit zwei h1,
// Aufgaben und Gedächtnis ohne Überschrift unter dem Titel.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { monatsWochen, tabTag, tagBeschriftung, tagNachTaste, tagSchluessel } from "../src/calendarGrid.ts";

const quelle = name => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");
const ohneKommentare = css => css.replace(/\/\*[\s\S]*?\*\//g, "");
const t = (j, m, d) => new Date(j, m - 1, d);
const k = d => tagSchluessel(d);

test("der Monat in Wochen, Montag zuerst, mit leeren Feldern davor und danach", () => {
  const oktober = monatsWochen(2026, 9);
  assert.ok(oktober.every(w => w.length === 7));
  assert.deepEqual(oktober[0].slice(0, 4).map(d => d && d.getDate()), [null, null, null, 1], "der 1. Oktober 2026 ist ein Donnerstag");
  assert.equal(oktober.flat().filter(Boolean).length, 31);
  assert.equal(oktober.at(-1).filter(Boolean).at(-1).getDate(), 31);
  assert.equal(monatsWochen(2027, 1).length, 4, "Februar 2027 beginnt am Montag: genau vier Wochen");
});

test("Pfeiltasten wandern von Tag zu Tag, Pos1 und Ende zur Woche, Bild auf und ab einen Monat", () => {
  const di = t(2026, 10, 27);
  assert.equal(k(tagNachTaste("ArrowRight", di)), "2026-10-28");
  assert.equal(k(tagNachTaste("ArrowLeft", di)), "2026-10-26");
  assert.equal(k(tagNachTaste("ArrowDown", di)), "2026-11-03", "über den Monatsrand hinaus");
  assert.equal(k(tagNachTaste("ArrowUp", di)), "2026-10-20");
  assert.equal(k(tagNachTaste("Home", di)), "2026-10-26", "Montag");
  assert.equal(k(tagNachTaste("End", di)), "2026-11-01", "Sonntag");
  assert.equal(k(tagNachTaste("PageDown", t(2026, 1, 31))), "2026-02-28", "auf den letzten Tag des kürzeren Monats");
  assert.equal(k(tagNachTaste("PageUp", t(2026, 3, 31))), "2026-02-28");
  assert.equal(tagNachTaste("a", di), null);
  assert.equal(tagNachTaste("Tab", di), null, "Tab verlässt das Raster");
});

test("jeder Tag ist beschriftet: Wochentag, Datum, Zahl der Termine, heute", () => {
  const heute = t(2026, 10, 27);
  assert.equal(tagBeschriftung(t(2026, 10, 27), 2, heute), "Dienstag, 27. Oktober, 2 Termine, heute");
  assert.equal(tagBeschriftung(t(2026, 10, 28), 1, heute), "Mittwoch, 28. Oktober, 1 Termin");
  assert.equal(tagBeschriftung(t(2026, 10, 29), 0, heute), "Donnerstag, 29. Oktober, keine Termine");
  assert.equal(k(tabTag(2026, 9, t(2026, 10, 27))), "2026-10-27", "der gewählte Tag trägt den Tab-Halt");
  assert.equal(k(tabTag(2026, 10, t(2026, 10, 27))), "2026-11-01", "in einem anderen Monat der erste");
});

test("die Seite: ein Raster mit Zeilen, Spaltenköpfen und Zellen; ein Tab-Halt; Termine im Tag ohne eigenen", () => {
  const kal = quelle("CalendarPage.tsx");
  assert.match(kal, /role="grid" aria-label=\{name\} aria-readonly="true" onKeyDown=\{event => rasterTaste\(event, small\)\}/);
  assert.match(kal, /className="month-reihe" role="row"/);
  assert.match(kal, /role="columnheader" aria-label=\{d\}/);
  assert.match(kal, /role="gridcell" aria-selected=\{gewaehlt\}/);
  assert.match(kal, /tabIndex=\{schluessel === haltTag \? 0 : -1\}/);
  assert.match(kal, /aria-label=\{tagBeschriftung\(day, events\.length, today\)\} aria-current=\{dateKey\(day\) === dateKey\(today\) \? "date" : undefined\}/);
  assert.match(kal, /<button type="button" tabIndex=\{-1\} className="calendar-month-event"/);
  assert.match(kal, /className="calendar-month-more" type="button" tabIndex=\{-1\}/);
  assert.match(kal, /const neu = tagNachTaste\(event\.key, focus\);/);
  // Enter öffnet die Termine des Tages und führt zum ersten.
  assert.match(kal, /setAgendaOpen\(true\);\s*window\.setTimeout\(\(\) => document\.querySelector<HTMLButtonElement>\("\.calendar-page \.calendar-agenda \.calendar-entry"\)\?\.focus\(\), 0\);/);
  assert.match(kal, /document\.querySelector<HTMLButtonElement>\(`\.calendar-page \[data-tag="\$\{tagSchluessel\(focus\)\}"\]`\)\?\.focus\(\);/);
});

test("Ziele mindestens 24 px; die Punkte am Handy sind nur Zeichen; die Woche ist eine Zeile über alle sieben Spalten", () => {
  const css = ohneKommentare(quelle("CalendarPage.css"));
  assert.match(css, /\.calendar-month-event \{[^}]*min-height:24px;/);
  assert.match(css, /\.calendar-month-more \{[^}]*min-height:24px;/);
  assert.match(css, /\.month-grid > \.month-reihe \{ display:grid; grid-column:1 \/ -1; grid-template-columns:subgrid; \}/);
  const schmal = css.slice(css.indexOf("@media(max-width:700px)"));
  assert.match(schmal, /\.calendar-month-events > button \{ pointer-events:none; \}/);
  assert.match(schmal, /\.month-grid:not\(\.mini-month\) \.month-day \{ min-height:var\(--g-kal-monatstag-schmal\);/);
});

test("Überschriften: ein h1 je Seite, die Mail darunter, Listen mit ihrem Namen, Gruppen eine Stufe tiefer", () => {
  assert.doesNotMatch(quelle("MailReader.tsx"), /<h1/, "der Betreff ist kein zweites h1 neben „Nachrichten“");
  assert.match(quelle("MailReader.tsx"), /<h2>\{detail\.subject \|\| "\(Ohne Betreff\)"\}<\/h2>/);
  assert.doesNotMatch(quelle("MemorySearch.tsx"), /<h1/);
  const gruppe = quelle("grundlage/Gruppe.tsx");
  assert.match(gruppe, /const Ueberschrift = stufe === 4 \? "h4" : stufe === 3 \? "h3" : "h2";/);
  const app = quelle("App.tsx");
  assert.match(app, /<h2 className="visually-hidden" id="aufgaben-liste-titel">\{heading\}<\/h2>/);
  assert.match(app, /titel=\{group\.label\} stufe=\{3\}/);
  assert.match(app, /<h2 className="visually-hidden">Entscheidungen<\/h2>/);
  assert.match(quelle("ZurueckgenommenGruppe.tsx"), /titel="Zurückgenommen" stufe=\{3\}/);
  assert.match(quelle("MemoryDirectory.tsx"), /<Gruppe titel=\{<><span className="visually-hidden">\{title\}: <\/span>/);
  assert.match(quelle("MemoryGraph.tsx"), /<h2 className="visually-hidden">Bereiche<\/h2><MemoryAreas \/>/);
});
