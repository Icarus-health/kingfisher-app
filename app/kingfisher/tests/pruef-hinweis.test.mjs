import {test} from "node:test";
import assert from "node:assert/strict";
import {nebensatz, pruefRolleOhneModell, pruefungFuss, pruefungSchalterSatz, verworfenPruefmodell} from "../src/pruefHinweis.ts";

test("Ein Nebensatz steht nur bei einfach und dünn, und nur mit Anlass", () => {
  assert.equal(nebensatz({verlaesslichkeit: "gut", hinweis: "nur eine Quelle, von 2024"}), "");
  assert.equal(nebensatz({verlaesslichkeit: "einfach", hinweis: "nur eine Quelle, von 2024"}), "nur eine Quelle, von 2024");
  assert.equal(nebensatz({verlaesslichkeit: "duenn", hinweis: "nur über Betreff oder Absender belegt"}), "nur über Betreff oder Absender belegt");
  assert.equal(nebensatz({verlaesslichkeit: "einfach", hinweis: ""}), "");
  assert.equal(nebensatz({}), "", "ältere Antworten ohne Einstufung zeigen nichts");
});

test("Vom Prüfmodell verworfene Sätze werden gezählt, nicht versteckt", () => {
  assert.equal(verworfenPruefmodell(0), "");
  assert.equal(verworfenPruefmodell(undefined), "");
  assert.equal(verworfenPruefmodell(1), "1 Satz verworfen (Prüfmodell)");
  assert.equal(verworfenPruefmodell(3), "3 Sätze verworfen (Prüfmodell)");
});

test("Der Fuß sagt, ob das Prüfmodell lief", () => {
  assert.match(pruefungFuss("an"), /dazu von einem Prüfmodell/);
  assert.match(pruefungFuss("aus"), /ausgeschaltet/);
  assert.match(pruefungFuss("kein_modell"), /nicht eingerichtet/);
  assert.match(pruefungFuss(undefined), /nicht eingerichtet/);
});

test("Der Schalter sagt in einem Satz, was er tut, und wenn kein Modell da ist", () => {
  assert.match(pruefungSchalterSatz({schalter: "an", zustand: "kein_modell", modell: null}), /Noch kein Prüfmodell/);
  assert.match(pruefungSchalterSatz({schalter: "an", zustand: "an", modell: "tev1:4b"}), /\(tev1:4b\) prüft jeden Satz/);
  assert.match(pruefungSchalterSatz({schalter: "aus", zustand: "aus", modell: "tev1:4b"}), /^Aus:/);
});

test("Die Modellkarte nennt die fehlende Prüfung", () => {
  assert.match(pruefRolleOhneModell({rolle: "pruefung", wirksam: {modell: null}}), /nur ohne Modell geprüft/);
  assert.equal(pruefRolleOhneModell({rolle: "pruefung", wirksam: {modell: "tev1:4b"}}), "");
  assert.equal(pruefRolleOhneModell({rolle: "antwort", wirksam: {modell: null}}), "");
});
