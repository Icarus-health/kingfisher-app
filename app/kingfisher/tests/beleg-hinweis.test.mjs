import {test} from "node:test";
import assert from "node:assert/strict";
import {belegHinweise, istGekennzeichnet} from "../src/belegHinweis.ts";

const ueberholt = {text: "überholt durch [1]: 15. Oktober 2026 → 12. November 2026", durch: 1, grund: "frist", alt: "", neu: ""};
const person = {art: "andere_person", text: "Andere Person gleichen Namens (Alex Winter, anna@beispiel.test)"};
const zeitraum = {art: "ausserhalb_zeitraum", text: "Außerhalb des gefragten Zeitraums (der letzten Woche): Quelle vom 12.03.2025"};

test("Ein Beleg ohne Kennzeichnung hat keinen Hinweis", () => {
  assert.deepEqual(belegHinweise({}), []);
  assert.deepEqual(belegHinweise({kennzeichen: []}), []);
  assert.equal(istGekennzeichnet({}), false);
});

test("Namensvetter und Zeitraum erscheinen als Hinweis mit Adresse und Datum", () => {
  assert.deepEqual(belegHinweise({kennzeichen: [person]}), [person.text]);
  assert.deepEqual(belegHinweise({kennzeichen: [zeitraum]}), [zeitraum.text]);
  assert.match(belegHinweise({kennzeichen: [person]})[0], /anna@beispiel\.test/);
  assert.match(belegHinweise({kennzeichen: [zeitraum]})[0], /12\.03\.2025/);
  assert.equal(istGekennzeichnet({kennzeichen: [zeitraum]}), true);
});

test("Überholt steht vor den Kennzeichen, nichts doppelt", () => {
  assert.deepEqual(belegHinweise({ueberholt, kennzeichen: [zeitraum, person, person]}), [ueberholt.text, zeitraum.text, person.text]);
});
