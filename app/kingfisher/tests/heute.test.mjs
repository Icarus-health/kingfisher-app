// Heute und Briefing (Fremdprobe 2, Befunde 10 und 11): kein Signalfarbenzähler bei null, eine Uhr.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { zaehlerText } from "../src/heute.ts";

const SRC = new URL("../src/", import.meta.url);

test("ein Zähler steht nur da, wenn es etwas zu zählen gibt", () => {
  assert.equal(zaehlerText(0), null);
  assert.equal(zaehlerText(Number.NaN), null);
  assert.equal(zaehlerText(1), "1");
  assert.equal(zaehlerText(12), "12");
});

test("die Kacheln zeigen ihre Zahl nur über zaehlerText, und Heute hat nur die Uhr der Seitenleiste", () => {
  const app = readFileSync(new URL("App.tsx", SRC), "utf8");
  const heute = readFileSync(new URL("TodayOverview.tsx", SRC), "utf8");
  assert.doesNotMatch(app, /<b[^>]*>\{(briefing\.\w+|fixtureNews)\.length\}<\/b>/);
  assert.doesNotMatch(heute, /today-count">\{attention\.length\}/);
  assert.doesNotMatch(app, /LiveClock/, "Heute hat keine zweite Uhr");
});

import { aktualisiertSatz, postfachAufHeute } from "../src/heute.ts";

test("nach „Aktualisieren“ steht, was dabei herauskam (Fremdprobe 2, Befund 18)", () => {
  assert.equal(aktualisiertSatz(null, ["a:1"], "14:43"), null, "beim ersten Laden kein Satz");
  assert.equal(aktualisiertSatz([], [], "14:43"), "Gerade abgerufen um 14:43: Der Posteingang ist leer.");
  assert.equal(aktualisiertSatz(["a:1"], ["a:1"], "14:43"), "Gerade abgerufen um 14:43, nichts Neues.");
  assert.equal(aktualisiertSatz(["a:1"], ["a:2", "a:1"], "14:43"), "Gerade abgerufen um 14:43: eine neue Nachricht.");
  assert.equal(aktualisiertSatz([], ["a:2", "a:1"], "14:43"), "Gerade abgerufen um 14:43: 2 neue Nachrichten.");
  const seite = readFileSync(new URL("Messages.tsx", SRC), "utf8");
  assert.match(seite, /onClick=\{\(\) => void load\(true\)\}/);
});

test("Heute zeigt den Stand eines Postfachs, der erklärt, warum keine Mails dastehen (Befund 17)", () => {
  for (const zustand of ["leer", "nicht_abgerufen", "pausiert", "fehler"]) assert.equal(postfachAufHeute(zustand), true, zustand);
  for (const zustand of ["liest", "aktuell"]) assert.equal(postfachAufHeute(zustand), false, zustand);
});
