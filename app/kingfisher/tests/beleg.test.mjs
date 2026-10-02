// Worauf sich eine Antwort stützt (Fremdprobe 2, Befunde 12 bis 14): sichtbar unter jeder Antwort, „ohne Beleg“ deutlich,
// kein „Stimmt nicht?“ unter Hinweisen des Programms, die linke Spalte widerspricht keiner belegten Antwort.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { OHNE_BELEG, belegStand, kontextLeerSatz } from "../src/beleg.ts";
import { GEMELDET, meldbar, systemhinweis } from "../src/rueckmeldung.ts";

const quelle = { nummer: 1, text: "Gespräch vom 1. Oktober 2026, 12:25 Uhr", art: "chat", assertion_id: "claim:k-1", episode_id: "e-1" };
const antwort = (context, extra = {}) => ({ role: "assistant", status: "complete", metadata: { context, ...extra } });

test("jede Antwort sagt, worauf sie sich stützt, oder deutlich, dass sie ohne Beleg ist", () => {
  assert.deepEqual(belegStand(antwort({ quellen: [quelle] })), { art: "quellen", anzahl: 1 });
  assert.deepEqual(belegStand(antwort({ source_links: [{ episode_id: "e-2", label: "Angebot" }] })), { art: "quellenlinks", anzahl: 1 });
  assert.deepEqual(belegStand(antwort({ satzantwort: { saetze: [] } })), { art: "saetze" });
  assert.deepEqual(belegStand(antwort({})), { art: "ohne" });
  assert.deepEqual(belegStand({ role: "assistant", status: "complete" }), { art: "ohne" });
  // Ein kaputtes Datenfeld ist kein Beleg.
  assert.deepEqual(belegStand(antwort({ quellen: [{ nummer: 1 }] })), { art: "ohne" });
  assert.match(OHNE_BELEG, /^Ohne Beleg/);
});

test("Fragen, Fehler, Rückfragen und Hinweise des Programms tragen keine Belegzeile", () => {
  assert.equal(belegStand({ role: "user", status: "complete", metadata: { context: { source_links: [{}] } } }).art, "keiner");
  assert.equal(belegStand({ role: "assistant", status: "error" }).art, "keiner");
  assert.equal(belegStand(antwort({ clarification_choices: [{ label: "A" }] })).art, "keiner");
  assert.equal(belegStand(antwort({}, { memory_candidate_id: "p-1" })).art, "keiner");
});

test("„Stimmt nicht?“ nur unter Antworten, nicht unter dem Gedächtnisvorschlag oder anderen Hinweisen (Befund 14)", () => {
  assert.equal(meldbar(antwort({})), true);
  const vorschlag = { role: "assistant", status: "complete", metadata: { memory_candidate_id: "p-1", memory_source_message_id: "m-1" } };
  assert.equal(systemhinweis(vorschlag), true);
  assert.equal(meldbar(vorschlag), false);
  assert.equal(meldbar({ role: "assistant", status: "complete", metadata: { systemhinweis: true } }), false);
});

test("nach „Melden“ steht, was mit der Meldung geschieht (Befund 12)", () => {
  assert.match(GEMELDET, /^Gemerkt\. /);
  assert.match(GEMELDET, /bleibt auf diesem Rechner/);
  assert.match(GEMELDET, /ändert nichts an deinem Gedächtnis/);
  // Fremdprobe 3, Befund 11: vorne nur, was die Nutzerin wissen muss; „Prüffrage“ und „Messlatte“ stehen hinten.
  assert.match(GEMELDET, /^Gemerkt\. Kingfisher soll diesen Fehler nicht wieder machen\. /);
  assert.doesNotMatch(GEMELDET, /Prüffrage|Messlatte|[Ww]er Kingfisher verbessert/);
  const komponente = readFileSync(new URL("../src/Rueckmeldung.tsx", import.meta.url), "utf8");
  assert.match(komponente, /\{GEMELDET\} <Verweis ziel="technik-rueckmeldungen" \/>/);
});

test("die linke Spalte widerspricht keiner belegten Antwort", () => {
  assert.match(kontextLeerSatz([{ role: "user", status: "complete" }, antwort({})]), /noch nichts aus deinem Gedächtnis/);
  const belegt = kontextLeerSatz([{ role: "user", status: "complete" }, antwort({ quellen: [quelle] })]);
  assert.match(belegt, /stützt sich auf dein Gedächtnis/);
  assert.doesNotMatch(belegt, /Keine|keine/);
  assert.match(kontextLeerSatz([antwort({ quellen: [quelle] }), antwort({ source_links: [{}] })]), /^2 Antworten/);
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.doesNotMatch(app, /Keine aktuell verwendbaren Gedächtnispunkte/);
});
