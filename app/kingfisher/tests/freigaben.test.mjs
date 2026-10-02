// Fremdprobe 3, Befund 4: Im Schritt „Freigaben“ heißt der Knopf „Weiter“, sobald man etwas angefasst hat, und wer das
// Wetter ohne Ort einschalten wollte, liest in einem Satz, warum es aus ist.
import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {FREIGABEN_START, WETTER_OHNE_ORT, freigabenErledigt, freigabenWeiter, wetterHinweis} from "../src/Einrichtung/freigaben.ts";

const aus = {meetings: false, wetter: false, fahrzeiten: false};
const gelesen = (an = aus) => freigabenWeiter(FREIGABEN_START, {art: "gelesen", an});

test("Unberührt und alles aus: „Überspringen“", () => {
  assert.equal(freigabenErledigt(FREIGABEN_START), false);
  assert.equal(freigabenErledigt(gelesen()), false);
  assert.equal(wetterHinweis(gelesen()), null);
});

test("Was schon an ist, zählt als erledigt", () => {
  assert.equal(freigabenErledigt(gelesen({...aus, fahrzeiten: true})), true);
});

test("Wer das Wetter einschaltet, bekommt „Weiter“, auch wenn noch kein Ort gewählt ist", () => {
  const stand = freigabenWeiter(gelesen(), {art: "wetter_wunsch", an: true});
  assert.equal(freigabenErledigt(stand), true);
  assert.equal(wetterHinweis(stand), WETTER_OHNE_ORT);
  // Ein Ort ist gewählt und gespeichert: an, der Satz verschwindet.
  const mitOrt = freigabenWeiter(stand, {art: "geaendert", id: "wetter", an: true});
  assert.equal(mitOrt.an.wetter, true);
  assert.equal(wetterHinweis(mitOrt), null);
  // Das Neulesen nach dem Zuklappen hält den Wunsch fest, solange der Ort fehlt.
  assert.equal(wetterHinweis(freigabenWeiter(stand, {art: "gelesen", an: aus})), WETTER_OHNE_ORT);
});

test("Wieder ausgeschaltet: kein Satz, aber angefasst bleibt angefasst", () => {
  const stand = freigabenWeiter(freigabenWeiter(gelesen(), {art: "wetter_wunsch", an: true}), {art: "wetter_wunsch", an: false});
  assert.equal(wetterHinweis(stand), null);
  assert.equal(freigabenErledigt(stand), true);
});

test("Eine Änderung an Meetings oder Fahrzeiten macht den Schritt erledigt, auch wenn danach alles aus ist", () => {
  assert.equal(freigabenErledigt(freigabenWeiter(gelesen(), {art: "geaendert", id: "meetings"})), true);
  assert.equal(freigabenErledigt(freigabenWeiter(gelesen(), {art: "geaendert", id: "fahrzeiten", an: false})), true);
});

test("Der Schritt hört auf alle drei Einstellungen und zeigt den Satz zum Wetter", () => {
  const code = readFileSync(new URL("../src/Einrichtung/FreigabenSchritt.tsx", import.meta.url), "utf8");
  assert.match(code, /<TranscriptSettings beiAenderung=/);
  assert.match(code, /<Wetter beiAenderung=[^\n]+\n\s+beiWunsch=\{an => melden\(\{art: "wetter_wunsch", an\}\)\} \/>/);
  assert.match(code, /hinweis: wetterHinweis\(stand\)/);
  assert.match(code, /<SchrittFuss erledigt=\{freigabenErledigt\(stand\)\}/);
  // Das Wetter meldet jedes Umlegen des Schalters, bevor es entscheidet, ob es speichert oder nach dem Ort fragt.
  const wetter = readFileSync(new URL("../src/WeltSettings.tsx", import.meta.url), "utf8");
  assert.match(wetter, /if \(!stand\) return;\n\s+beiWunsch\?\.\(an\);/);
});
