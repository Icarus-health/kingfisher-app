// Geburtstag und Wiederkehrendes in der Akte (M4, docs/49-kreis-und-privat.md): Vorschlag ist kein Fakt.
import assert from "node:assert/strict";
import { test } from "node:test";
import { wkAntwort, wkSatz, wkSichtbar, wkTitel } from "../src/wiederkehrendes.ts";

const eintrag = (aenderung = {}) => ({
  id: "v-1", art: "vorschlag", praedikat: "geburtstag", wert: "09-30", aussage: "Gabriele Hartmann hat am 30. September Geburtstag.",
  begruendung: "Dein Glückwunsch vom 30.09.2025.", beleg: { episode_id: "e-1", zitat: "alles Gute zum Geburtstag!" }, ...aenderung,
});

test("ohne Vorschlag und ohne Aussage keine Karte", () => {
  assert.equal(wkSichtbar(null), false);
  assert.equal(wkSichtbar({ sache: "person:a:x", offen: [], angenommen: [] }), false);
  assert.equal(wkSichtbar({ sache: "person:a:x", offen: [eintrag()], angenommen: [] }), true);
});

test("ein Vorschlag heißt Vorschlag, eine angenommene Aussage steht fest", () => {
  assert.equal(wkSatz(eintrag()), "Vorschlag: Gabriele Hartmann hat am 30. September Geburtstag.");
  assert.equal(wkSatz(eintrag({ art: "aussage" })), "Steht fest: Gabriele Hartmann hat am 30. September Geburtstag.");
});

test("Titel nach Inhalt, Antwort in einem Satz", () => {
  assert.equal(wkTitel({ sache: "person:a:x", offen: [eintrag()], angenommen: [] }), "Geburtstag");
  assert.equal(wkTitel({ sache: "organisation:x", offen: [eintrag({ praedikat: "wiederkehrend" })], angenommen: [] }), "Wiederkehrend");
  assert.match(wkAntwort(eintrag(), true), /inneren Kreis/);
  assert.equal(wkAntwort(eintrag(), false), "Verworfen. Kingfisher schlägt das nicht noch einmal vor.");
});
