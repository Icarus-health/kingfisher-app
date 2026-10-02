import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {automatikAngebote, fertigLeerText, liestSatz, ordnetEin, schonDaZahlen, stummTitel} from "../src/Einrichtung/fertig.ts";
import {verbindungenPruefen} from "../src/verbindungen.ts";

const stumm = (extra = {}) => ({account_id: "a", label: "Probe-Post", erreichbar: false, grund: "nicht_erreichbar",
  satz: "Probe-Post antwortet gerade nicht. Prüfe die Internetverbindung und versuche es gleich noch einmal.", ...extra});
const konto = (extra = {}) => ({account_id: "a", label: "Probe-Post", connected: true, started: false, paused: false, step: "paused",
  error: null, scope: "", folders: [], ...extra});
const intake = (konten) => ({accounts: konten, attachments_supported: false, analysis_active: false});
const automatik = (extra = {}) => ({state: "paused", requested: false, pending: 3, model: "qwen3.5:2b", ...extra});

test("„Dein Briefing ist bereit“ nur, wenn das Postfach antwortet (Befund 5)", () => {
  const lage = {mail: true, kalender: false, nichtEingelesen: 0};
  assert.equal(fertigLeerText({...lage, stumm: [stumm()]}), "Dein Briefing kommt ohne Mails aus, bis dein Postfach wieder antwortet.");
  assert.equal(fertigLeerText({...lage, stumm: null}), "Kingfisher sieht nach, ob dein Postfach antwortet …");
  assert.equal(fertigLeerText({...lage, stumm: []}), "Gerade läuft nichts mehr im Hintergrund. Dein Briefing ist bereit.");
  assert.equal(fertigLeerText({...lage, stumm: [], nichtEingelesen: 1}), "Deine Mails sind noch nicht eingelesen; das Briefing wartet darauf.");
  assert.equal(fertigLeerText({mail: false, kalender: false, stumm: [], nichtEingelesen: 0}), undefined);
  assert.equal(stummTitel([stumm()]), "Dein Postfach antwortet nicht");
  assert.equal(stummTitel([stumm(), stumm({account_id: "b"})]), "Deine Postfächer antworten nicht");
});

test("Die Automatik wird einmal angeboten, nur wo sie laufen kann (Befund 17)", () => {
  assert.deepEqual(automatikAngebote(intake([konto()]), automatik(), []), {einlesen: ["a"], sortieren: true, sortierenSpaeter: false});
  // Ein Postfach, das nicht antwortet, wird nicht zum Einlesen angeboten; solange geprüft wird, auch nicht.
  assert.deepEqual(automatikAngebote(intake([konto()]), automatik(), [stumm()]).einlesen, []);
  assert.deepEqual(automatikAngebote(intake([konto()]), automatik(), null).einlesen, []);
  // Schon gestartet oder schon eingeschaltet: nichts anzubieten.
  assert.deepEqual(automatikAngebote(intake([konto({started: true})]), automatik({state: "active", requested: true}), []),
    {einlesen: [], sortieren: false, sortierenSpaeter: false});
  // Ein Modell im Internet wird nie vorgemerkt.
  for (const state of ["cloud_ueber_ollama", "wrong_model", "legacy_active"]) {
    assert.equal(automatikAngebote(null, automatik({state}), []).sortieren, false, state);
  }
});

test("Lädt das Sprachmodell noch, wird das Sortieren vorgemerkt: die Fertig-Seite verspricht die Einordnung (Fremdprobe 3, Befund 3)", () => {
  for (const state of ["model_missing", "local_model_unavailable"]) {
    assert.deepEqual(automatikAngebote(null, automatik({state}), []), {einlesen: [], sortieren: true, sortierenSpaeter: true}, state);
  }
  const angebote = automatikAngebote(null, automatik({state: "model_missing"}), []);
  assert.equal(ordnetEin(automatik({state: "model_missing"}), angebote, true), true);
  // Häkchen weg: Dann verspricht die Seite die Einordnung nicht.
  assert.equal(ordnetEin(automatik({state: "model_missing"}), angebote, false), false);
  assert.equal(ordnetEin(automatik({state: "active", requested: true}), {einlesen: [], sortieren: false, sortierenSpaeter: false}, false), true);
});

test("„Verbindungen prüfen“ führt in den betroffenen Bereich (Befund 30)", () => {
  assert.equal(verbindungenPruefen([{section: "weather"}, {section: "mail"}]), "/settings#zugaenge");
  assert.equal(verbindungenPruefen([{section: "calendar"}]), "/settings#zugaenge");
  assert.equal(verbindungenPruefen([{section: "weather"}]), "/settings#darf");
  assert.equal(verbindungenPruefen([{section: "tasks"}]), "/settings#zugaenge");
});

test("Die Fertig-Seite nennt nur, was verbunden ist (Fremdprobe 2, Befund 8)", () => {
  assert.equal(liestSatz({mail: true, kalender: true}), "Kingfisher liest deine Mails und Termine. Das bleibt auf diesem Rechner.");
  assert.equal(liestSatz({mail: true, kalender: false}), "Kingfisher liest deine Mails. Das bleibt auf diesem Rechner.");
  assert.equal(liestSatz({mail: false, kalender: true}), "Kingfisher liest deine Termine. Das bleibt auf diesem Rechner.");
  assert.equal(liestSatz({mail: false, kalender: false}), null);
});

// Fremdprobe 3, Befund 6: „Mails 0 · Termine 0“, obwohl der Termin schon aufgenommen war.
test("„Schon da“ zeigt nur Zahlen, die stimmen", () => {
  const ordner = {folder: "INBOX", inventory_complete: true, total: 5, captured: 2, duplicates: 0, failed: 0, pending: 3,
    live_pending: 0, analyzed: 0, analysis_failed: 0, deferred: 0, excluded: 0, categorized: 0, categories_pending: 0, categories_failed: 0};
  // Solange der Abgleich läuft, steht „…“ (null), nicht 0.
  assert.deepEqual(schonDaZahlen({mail: false, kalender: true, intake: null, termine: null}), [{titel: "Termine aufgenommen", wert: null}]);
  assert.deepEqual(schonDaZahlen({mail: false, kalender: true, intake: null, termine: 1}), [{titel: "Termine aufgenommen", wert: 1}]);
  // Mails erst, wenn das Einlesen läuft; dann, wie viele gelesen sind.
  assert.deepEqual(schonDaZahlen({mail: true, kalender: false, intake: intake([konto()]), termine: null}), []);
  assert.deepEqual(schonDaZahlen({mail: true, kalender: false, intake: intake([konto({started: true, folders: [ordner]})]), termine: null}),
    [{titel: "Mails gelesen", wert: 2}]);
  assert.deepEqual(schonDaZahlen({mail: false, kalender: false, intake: null, termine: null}), []);
});

test("Gezählt werden die Termine erst nach dem Abgleich", () => {
  const code = readFileSync(new URL("../src/Einrichtung/FertigSchritt.tsx", import.meta.url), "utf8");
  assert.match(code, /api\.syncCalendarMemory\(\)\.catch\(\(\) => undefined\)\.then\(\(\) => \{ if \(lebt\) void lesen\(\); \}\)/);
});
