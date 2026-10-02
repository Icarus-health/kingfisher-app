// Die eigene Frage als Quelle (Fremdprobe, Befund 15): vorne Alltagssprache, ein Satz, Knöpfe mit erkennbarer Wirkung;
// was nur Techniker brauchen, steht im Aufklapper „Für Techniker“. Im Browser: scripts/probe_seiten_ui.py.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const quelle = (datei) => readFileSync(new URL(`../src/${datei}`, import.meta.url), "utf8");
const FACHWORTE = ["keine bestätigte Aussage", "Einordnung", "Sortierergebnis", "Quelle ausschließen", "Angabe berichtigen", "Herkunft", "Wiederzulassung"];

test("unter der eigenen Frage steht vorne kein Fachwort; alles Technische liegt im Aufklapper", () => {
  const code = quelle("ProfileSource.tsx");
  const anfang = code.indexOf("const schlicht = ");
  const technik = code.indexOf('<details className="quelle-technik">', anfang);
  const ende = code.indexOf("</details>", technik);
  assert.ok(anfang > 0 && technik > anfang && ende > technik);
  const vorne = code.slice(anfang, technik);
  for (const wort of FACHWORTE) assert.ok(!vorne.includes(wort), `vorne: ${wort}`);
  const hinten = code.slice(technik, ende);
  assert.match(hinten, /<summary>Für Techniker<\/summary>/);
  for (const teil of ["keine bestätigte Aussage", "memory_status", "SourceCategories", "SourceBezuege", "{verwerfen}", "SourceProject", "Herkunft"]) {
    assert.ok(hinten.includes(teil), `hinten fehlt: ${teil}`);
  }
  // Knöpfe, deren Wirkung man am Namen erkennt, und je ein Satz.
  assert.match(vorne, /knopf="Wortlaut berichtigen"/);
  assert.match(vorne, />Nicht mehr verwenden</);
  assert.match(vorne, />Ja, nicht mehr verwenden</);
  assert.match(vorne, />Wieder verwenden</);
  for (const satz of vorne.matchAll(/<p[^>]*>([^<{]+)<\/p>/g)) assert.equal(satz[1].split(/[.!?](?:\s|$)/).filter(t => t.trim()).length, 1, satz[1]);
});

test("nur die eigene Frage im Gespräch bekommt die schlichte Ansicht", () => {
  // Die schlichte Ansicht steht nur unter der eigenen Frage; die Quellen einer Antwort stehen unter „Gestützt auf“.
  assert.match(quelle("App.tsx"), /message\.role !== "user" \? null : [^\n]*quiet eigeneFrage \/>/);
  assert.match(quelle("SourceCorrection.tsx"), /knopf = "Angabe berichtigen"/);
});
