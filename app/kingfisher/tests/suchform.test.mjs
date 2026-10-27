// Suche nach Namen (Persona-Prüfung, Befund A7): „Müller“ findet „Mueller“ und umgekehrt, ebenso ä/ae, ö/oe, ß/ss.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { passtSuche } from "../src/suchform.ts";

test("Umlaute in beiden Richtungen, ß und ss, Grundform ohne Punkte", () => {
  for (const [text, suche] of [["Thomas Müller", "Mueller"], ["Katrin Mueller", "Müller"], ["Jörg Weiß", "weiss"],
    ["Jörg Weiss", "Weiß"], ["Universität Gießen", "universitaet giessen"], ["Björn Schäfer", "Schafer"],
    ["Dr. Jürgen Müller-Lüdenscheidt", "luedenscheidt"], ["Ölbaum GmbH", "oelbaum"]]) {
    assert.ok(passtSuche(text, suche), `${suche} → ${text}`);
  }
  assert.ok(!passtSuche("Thomas Müller", "Meier"));
  assert.ok(!passtSuche("Katrin Mueller", "Muller"), "„Muller“ ist keine Schreibweise von „Mueller“");
  assert.ok(passtSuche("Thomas Müller", ""));
});

test("Gedächtnissuche und Verzeichnis der Menschen nutzen dieselbe Regel", () => {
  const modell = readFileSync(new URL("../src/MemoryBrowseModel.ts", import.meta.url), "utf8");
  assert.match(modell, /&& passtSuche\(node\.label, query\)\);/);
  const verzeichnis = readFileSync(new URL("../src/MemoryDirectory.tsx", import.meta.url), "utf8");
  assert.match(verzeichnis, /sorted\.filter\(node => passtSuche\(node\.label, query\)\)/);
});
