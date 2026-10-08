import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";

const today = readFileSync(new URL("../src/MemoryQuestions.tsx", import.meta.url), "utf8");
const rows = readFileSync(new URL("../src/BefundeAnsicht.tsx", import.meta.url), "utf8");
const code = `${today}\n${rows}`;

test("Heute lädt offene Gedächtnisfragen nur im aktiven Bereich und zeigt eine begrenzte Auswahl", () => {
  assert.match(today, /api\.lintBefunde\("offen"\)/);
  assert.match(today, /if \(!active\) return/);
  assert.match(today, /slice\(0, 5\)/);
  assert.match(today, /onOpenAll/);
});

test("Heute priorisiert wichtige und verwaiste Punkte vor übrigen Befunden", () => {
  assert.match(today, /schwere === "wichtig"/);
  assert.match(today, /art === "waise"/);
  assert.match(today, /sachen\.length === 0/);
});

test("Quellen zeigen Originalzitat, unbekannte Quellenzeit und Erfassungszeit", () => {
  assert.match(rows, /beleg\.zitat/);
  assert.match(rows, /Quellenzeit unbekannt/);
  assert.match(rows, /beleg\.recorded_at/);
  assert.match(rows, /ProfileSource[\s\S]*readOnly/);
  assert.match(rows, /keine bestätigte Aussage/);
});

test("Entscheidungen übergeben den gespeicherten Stand und blockieren synchrone Doppelklicks", () => {
  assert.match(code, /entscheiden\(befund\.id, was, befund\.stand\)/);
  assert.match(code, /aktionLock\.current/);
});

test("Lade- und Entscheidungsfehler bleiben sichtbar und lassen einen erneuten Versuch zu", () => {
  assert.match(today, /role="alert"/);
  assert.match(today, /Erneut laden/);
  assert.match(rows, /Liste wird neu geladen/);
});
