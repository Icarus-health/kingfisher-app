import {test} from "node:test";
import assert from "node:assert/strict";
import {ergebnisText, saetzeText, uebernehmbar, vorgabeWahl, vorgeschlagenText} from "../src/uebernehmen.ts";

const satz = (nr, mehr = {}) => ({nr, text: `Satz ${nr}.`, hinweise: [], steht_schon: false, vorgabe: true, ...mehr});

test("Übernehmen gibt es nur unter einer fertigen Antwort in Sätzen", () => {
  const mitSaetzen = {role: "assistant", status: "complete", metadata: {context: {satzantwort: {saetze: [{text: "a"}]}}}};
  assert.equal(uebernehmbar(mitSaetzen), true);
  assert.equal(uebernehmbar({...mitSaetzen, role: "user"}), false);
  assert.equal(uebernehmbar({...mitSaetzen, status: "error"}), false);
  assert.equal(uebernehmbar({role: "assistant", status: "complete"}), false, "Zitatmodus ohne Sätze");
  assert.equal(uebernehmbar({role: "assistant", status: "complete", metadata: {context: {satzantwort: {saetze: []}}}}), false);
  assert.equal(uebernehmbar({role: "assistant", status: "complete", metadata: {context: {clarification_choices: [1], satzantwort: {saetze: [{}]}}}}), false, "Rückfrage");
  assert.equal(uebernehmbar({role: "assistant", status: "complete", metadata: {context: {clarification_date: true, satzantwort: {saetze: [{}]}}}}), false, "Rückfrage nach Datum");
});

test("Vorgabe: alle Sätze ohne Hinweis, ohne Dopplung und ohne früheren Vorschlag", () => {
  const saetze = [satz(1), satz(2, {vorgabe: false, hinweise: ["überholt"]}), satz(3, {vorgabe: false, steht_schon: true}), satz(4)];
  assert.deepEqual(vorgabeWahl(saetze), [1, 4]);
  assert.deepEqual(vorgabeWahl(saetze, [{statement: "Satz 4."}]), [1], "ein Satz mit Vorschlag wird nicht noch einmal vorgewählt");
  assert.deepEqual(vorgabeWahl([]), []);
});

test("Texte: Zählung, Ergebnis je Satz und Satz über den Vorschlägen", () => {
  assert.equal(saetzeText(1), "1 Satz");
  assert.equal(saetzeText(3), "3 Sätze");
  assert.equal(ergebnisText({status: "steht_schon"}), "Steht schon in der Akte.");
  assert.equal(ergebnisText({status: "liegt_vor"}), "Liegt schon zur Entscheidung vor.");
  assert.equal(ergebnisText({status: "fehler", grund: "Der Beleg gilt nicht mehr."}), "Der Beleg gilt nicht mehr.");
  assert.equal(ergebnisText({status: "fehler"}), "Das ließ sich nicht vorschlagen.");
  assert.equal(vorgeschlagenText([{status: "vorgeschlagen"}, {status: "steht_schon"}]), "Vorgeschlagen.");
  assert.equal(vorgeschlagenText([{status: "steht_schon"}, {status: "steht_schon"}]), "Steht schon in der Akte.");
  assert.equal(vorgeschlagenText([{status: "liegt_vor"}]), "Liegt schon zur Entscheidung vor.");
  assert.equal(vorgeschlagenText([{status: "fehler"}]), "Nichts vorgeschlagen.");
  assert.equal(vorgeschlagenText([]), "Nichts vorgeschlagen.");
});
