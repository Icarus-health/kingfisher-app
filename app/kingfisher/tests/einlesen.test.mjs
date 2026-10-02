import {test} from "node:test";
import assert from "node:assert/strict";
import {einlesenStand} from "../src/Einrichtung/einlesen.ts";

const folder = (extra = {}) => ({folder: "INBOX", inventory_complete: true, total: 1200, captured: 300, duplicates: 0, failed: 0, pending: 900,
  live_pending: 0, analyzed: 0, analysis_failed: 0, deferred: 0, excluded: 0, categorized: 0, categories_pending: 0, categories_failed: 0, ...extra});
const konto = (extra = {}, ordner = {}) => ({account_id: "a", label: "Probe-Post", connected: true, started: true, paused: false, step: "capture",
  error: null, scope: "INBOX", folders: [folder(ordner)], ...extra});

test("Nach dem Start steht der Fortschritt da, nicht nur „gestartet“", () => {
  assert.equal(einlesenStand(konto()), "Probe-Post: 300 von 1.200 Mails gelesen.");
});

test("Während gezählt wird, sagt der Satz das", () => {
  assert.equal(einlesenStand(konto({}, {inventory_complete: false, total: null, captured: 0})),
    "Probe-Post: Kingfisher liest deine Mails und zählt sie gerade.");
});

test("Ein Fehler und eine Pause werden genannt", () => {
  assert.match(einlesenStand(konto({error: "IMAP-Zugriff fehlgeschlagen"})), /stockt gerade/);
  assert.match(einlesenStand(konto({paused: true})), /pausiert/);
});

test("Fertig heißt: alle gelesen", () => {
  assert.equal(einlesenStand(konto({}, {captured: 1200, pending: 0})), "Probe-Post: Alle 1.200 Mails sind gelesen.");
});

test("Gescheiterte Mails: der Satz mit Grund statt „0 von 5 Mails gelesen“ (Fremdprobe 3, Befund 2)", () => {
  const satz = "Postfach Probe-Post: 5 Mails kamen nicht ins Gedächtnis. Ihr Inhalt ließ sich nicht lesen. Kingfisher versucht es später von selbst noch einmal.";
  assert.equal(einlesenStand(konto({stand: {zustand: "gescheitert", satz, gelesen: 0, gesamt: null, zuletzt: null}},
    {total: 5, captured: 0, failed: 5, pending: 0})), satz);
});

test("Ein ausgefilterter Newsletter zählt als gelesen; das Postfach bleibt nicht bei „4 von 5“ stehen", () => {
  assert.equal(einlesenStand(konto({}, {total: 5, captured: 4, filtered: 1, pending: 0})), "Probe-Post: Alle 5 Mails sind gelesen.");
});
