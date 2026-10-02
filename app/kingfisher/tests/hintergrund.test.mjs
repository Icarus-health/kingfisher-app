import {test} from "node:test";
import assert from "node:assert/strict";
import {fertigText, lerntFuss, lerntZeilen} from "../src/Einrichtung/lernt.ts";
import {autostartBeantwortet, autostartMeldung} from "../src/Einrichtung/autostart.ts";
import {MELDE_ABSTAND_MS, eingabenMelden, sollMelden} from "../src/aktivitaet.ts";

const hintergrund = (extra = {}) => ({zustand: "laeuft", grund: null, pausiert: false,
  fortschritt: {gesamt: 18000, fertig: 2400, offen: 15600}, rate_pro_stunde: 600,
  schaetzung: {sekunden: 93600, fertig_um: "2026-10-01T12:00:00+00:00", text: "morgen Mittag"},
  schaetzung_text: "morgen Mittag", satz: "Es geht schneller, wenn der Rechner heute anbleibt.", schlange: [], ...extra});

const folder = (extra = {}) => ({folder: "INBOX", inventory_complete: true, total: 100, captured: 100, duplicates: 0, failed: 0, pending: 0,
  live_pending: 0, analyzed: 30, analysis_failed: 0, deferred: 0, excluded: 0, categorized: 30, categories_pending: 0, categories_failed: 0, ...extra});
const konto = {account_id: "a", label: "Privat", connected: true, started: true, paused: false, step: "analysis",
  error: null, scope: "", folders: [folder()]};

test("Die Gesamtzeile nennt Quellen und Schätzung", () => {
  const [zeile] = lerntZeilen(null, null, hintergrund());
  assert.equal(zeile.id, "einordnen");
  assert.equal(zeile.text, "2.400 von 18.000 Quellen, fertig etwa morgen Mittag");
  assert.equal(fertigText(hintergrund({schaetzung: null, schaetzung_text: "noch unklar"})), "wann es fertig ist, ist noch unklar");
  assert.equal(fertigText(hintergrund({schaetzung: {sekunden: 600, fertig_um: "", text: "in weniger als einer Stunde"}})), "fertig in weniger als einer Stunde");
});

test("Dieselbe Arbeit erscheint nicht zweimal: mit Gesamtzeile kein Sortieren der Mails", () => {
  const status = {accounts: [konto], attachments_supported: false, analysis_active: true};
  assert.ok(lerntZeilen(status, null).some(zeile => zeile.id === "sortieren"));
  const mit = lerntZeilen(status, null, hintergrund());
  assert.deepEqual(mit.map(zeile => zeile.id), ["einordnen"]);
});

test("Ohne Freigabe, ohne Modell oder fertig: keine Zeile, kein Satz, kein Knopf", () => {
  for (const zustand of ["aus", "ohne_modell", "fertig"]) {
    assert.deepEqual(lerntZeilen(null, null, hintergrund({zustand})), []);
    assert.deepEqual(lerntFuss(hintergrund({zustand})), {satz: null, grund: null, knopf: null});
  }
});

test("Pausiert: die Zeile bleibt mit Knopf „Weiter“, ohne Satz zum Anbleiben", () => {
  const stand = hintergrund({zustand: "pausiert", pausiert: true, grund: "Pausiert. Kingfisher lernt weiter, wenn du „Weiter“ wählst."});
  assert.equal(lerntZeilen(null, null, stand)[0].text, "2.400 von 18.000 Quellen, pausiert");
  assert.deepEqual(lerntFuss(stand), {satz: null, grund: stand.grund, knopf: "Weiter"});
  assert.equal(lerntFuss(hintergrund()).knopf, "Pausieren");
  assert.equal(lerntFuss(hintergrund()).satz, "Es geht schneller, wenn der Rechner heute anbleibt.");
});

test("Ohne Modell, aber Mails werden gelesen: „Pausieren“ steht auf Heute (Fremdprobe 3, Befund 5)", () => {
  assert.equal(lerntFuss(hintergrund({zustand: "ohne_modell"}), true).knopf, "Pausieren");
  assert.equal(lerntFuss(hintergrund({zustand: "ohne_modell", pausiert: true}), true).knopf, "Weiter");
  assert.equal(lerntFuss(hintergrund({zustand: "ohne_modell"}), false).knopf, null);
  assert.equal(lerntFuss(null, true).knopf, null);
});

test("Eingaben werden gedrosselt gemeldet", () => {
  assert.equal(sollMelden(0, null), true);
  assert.equal(sollMelden(MELDE_ABSTAND_MS - 1, 0), false);
  assert.equal(sollMelden(MELDE_ABSTAND_MS, 0), true);
  const hoerer = new Map();
  const ziel = {addEventListener: (name, fn) => hoerer.set(name, fn), removeEventListener: name => hoerer.delete(name)};
  let jetzt = 1000;
  let meldungen = 0;
  const abmelden = eingabenMelden(() => { meldungen += 1; }, ziel, () => jetzt);
  hoerer.get("keydown")(); hoerer.get("keydown")(); hoerer.get("pointerdown")();
  assert.equal(meldungen, 1);
  jetzt += MELDE_ABSTAND_MS;
  hoerer.get("wheel")();
  assert.equal(meldungen, 2);
  abmelden();
  assert.equal(hoerer.size, 0);
});

test("Autostart: ohne Antwort offen, ohne Helfer „noch nicht verfügbar“", () => {
  assert.equal(autostartBeantwortet({gewuenscht: null, verfuegbar: true, eingerichtet: false, plattform: "macos"}), false);
  assert.equal(autostartMeldung({gewuenscht: null, verfuegbar: true, eingerichtet: false, plattform: "macos"}), "");
  assert.match(autostartMeldung({gewuenscht: null, verfuegbar: false, eingerichtet: null, plattform: null}), /noch nicht verfügbar/);
  assert.match(autostartMeldung({gewuenscht: true, verfuegbar: true, eingerichtet: true, plattform: "macos"}), /Eingerichtet/);
  assert.equal(autostartBeantwortet({gewuenscht: false, verfuegbar: true, eingerichtet: false, plattform: "macos"}), true);
});
