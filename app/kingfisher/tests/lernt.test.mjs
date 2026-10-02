import {test} from "node:test";
import assert from "node:assert/strict";
import {abfrageAbstandMs, lerntZeilen, prozent} from "../src/Einrichtung/lernt.ts";

const folder = (extra = {}) => ({folder: "INBOX", inventory_complete: true, total: 100, captured: 40, duplicates: 10, failed: 0, pending: 50,
  live_pending: 0, analyzed: 0, analysis_failed: 0, deferred: 0, excluded: 0, categorized: 0, categories_pending: 0, categories_failed: 0, ...extra});
const konto = (extra = {}, ordner = {}) => ({account_id: "a", label: "Privat", connected: true, started: true, paused: false, step: "capture",
  error: null, scope: "", folders: [folder(ordner)], ...extra});
const status = (konten, extra = {}) => ({accounts: konten, attachments_supported: false, analysis_active: true, ...extra});

test("Läuft nichts, gibt es keine Zeile", () => {
  assert.deepEqual(lerntZeilen(null, null), []);
  assert.deepEqual(lerntZeilen(status([]), null), []);
  assert.deepEqual(lerntZeilen(status([konto({started: false})]), {offen: 0, gesamt: 50}), []);
  // Fertig aufgenommen und eingeordnet: nichts mehr zu zeigen.
  const fertig = folder({captured: 100, duplicates: 0, pending: 0, analyzed: 100, categorized: 100});
  assert.deepEqual(lerntZeilen(status([konto({}, fertig)]), null), []);
});

test("Mailaufnahme zeigt x von y", () => {
  const zeilen = lerntZeilen(status([konto()]), null);
  const mail = zeilen.find(zeile => zeile.id === "mail");
  assert.equal(mail.text, "Deine Mails werden gelesen: 50 von 100");
  assert.equal(prozent(mail), 50);
});

test("Ist der Gesamtumfang unbekannt, steht „bisher“ und es gibt keinen Prozentbalken", () => {
  const zeilen = lerntZeilen(status([konto({}, {inventory_complete: false, total: null, captured: 12, duplicates: 0})]), null);
  assert.equal(zeilen[0].text, "Deine Mails werden gelesen: bisher 12 gefunden");
  assert.equal(zeilen[0].gesamt, null);
  assert.equal(prozent(zeilen[0]), null);
});

test("Ein pausiertes oder getrenntes Konto läuft nicht", () => {
  assert.deepEqual(lerntZeilen(status([konto({paused: true})]), null), []);
  assert.deepEqual(lerntZeilen(status([konto({connected: false})]), null), []);
});

test("Der Nachtrag der Empfänger erscheint nur, solange er offen ist", () => {
  const fertig = folder({captured: 100, duplicates: 0, pending: 0, analyzed: 100, categorized: 100});
  const offen = konto({empfaengernachtrag: {offen: 1234, ergaenzt: 5, ohne_kopfzeilen: 0, gedrosselt: false, fertig: false}}, fertig);
  const zeilen = lerntZeilen(status([offen]), null);
  assert.equal(zeilen.length, 1);
  assert.equal(zeilen[0].id, "nachtrag");
  assert.match(zeilen[0].text, /noch 1\.234/);
  const erledigt = konto({empfaengernachtrag: {offen: 0, ergaenzt: 5, ohne_kopfzeilen: 0, gedrosselt: false, fertig: true}}, fertig);
  assert.deepEqual(lerntZeilen(status([erledigt]), null), []);
  assert.deepEqual(lerntZeilen(status([konto({empfaengernachtrag: null}, fertig)]), null), []);
});

test("Das Sortieren nach Themen zeigt sich nur, wenn es auch läuft", () => {
  const erfasst = folder({captured: 100, duplicates: 0, pending: 0, analyzed: 30, categorized: 30});
  const laeuft = lerntZeilen(status([konto({}, erfasst)]), null);
  assert.equal(laeuft.find(zeile => zeile.id === "sortieren").text, "Deine Mails werden nach Themen sortiert: 30 von 100");
  const aus = lerntZeilen(status([konto({}, erfasst)], {analysis_active: false}), null);
  assert.equal(aus.find(zeile => zeile.id === "sortieren"), undefined);
});

test("Die Berechnung der Akten zeigt die offenen Quellen und verschwindet, wenn nichts offen ist", () => {
  const fertig = folder({captured: 100, duplicates: 0, pending: 0, analyzed: 100, categorized: 100});
  const zeilen = lerntZeilen(status([konto({}, fertig)]), {offen: 20, gesamt: 100});
  assert.equal(zeilen.length, 1);
  assert.equal(zeilen[0].text, "Personen, Projekte und Orte werden zusammengestellt: noch 20 Quellen");
  assert.equal(prozent(zeilen[0]), 80);
  assert.deepEqual(lerntZeilen(status([konto({}, fertig)]), {offen: 0, gesamt: 100}), []);
});

test("Die Alltagssprache der Zeilen enthält keine Fachwörter", () => {
  const zeilen = lerntZeilen(status([konto({empfaengernachtrag: {offen: 3, ergaenzt: 0, ohne_kopfzeilen: 0, gedrosselt: false, fertig: false}})]), {offen: 5, gesamt: 9});
  for (const zeile of zeilen) assert.doesNotMatch(zeile.text, /IMAP|uidvalidity|Einordnung|Embedding|Sidecar|Token|Provider/i);
});

test("Es wird zügig nachgesehen, solange etwas läuft, sonst gemächlich", () => {
  assert.ok(abfrageAbstandMs(true) < abfrageAbstandMs(false));
});

test("Mit dem Stand des Sidecars steht dessen Satz da, und ein leeres Postfach liest nicht (Fremdprobe 2, Befund 17)", () => {
  const liest = {zustand: "liest", satz: "Postfach Privat wird gelesen: 50 von 100 Mails.", gelesen: 50, gesamt: 100, zuletzt: null};
  const zeilen = lerntZeilen(status([konto({stand: liest})]), null);
  assert.equal(zeilen.find(zeile => zeile.id === "mail").text, "Postfach Privat wird gelesen: 50 von 100 Mails.");
  assert.equal(prozent(zeilen[0]), 50);
  // Noch nicht fertig gezählt, aber der Sidecar weiß: leer. Dann gibt es keine Zeile „bisher 0 gefunden“.
  const leer = {zustand: "leer", satz: "Postfach Privat ist verbunden und leer, abgerufen um 14:43.", gelesen: 0, gesamt: 0, zuletzt: null};
  const zaehlt = konto({stand: leer}, {inventory_complete: false, total: null, captured: 0, duplicates: 0, pending: 0});
  assert.deepEqual(lerntZeilen(status([zaehlt]), null).filter(zeile => zeile.id === "mail"), []);
});

test("Das Sprachmodell lädt im Hintergrund: eine Zeile mit Prozent, zuerst, bis es fertig ist (Fremdprobe 2, Befund 6)", () => {
  const zeilen = lerntZeilen(null, {offen: 2, gesamt: 4}, null, {laeuft: true, prozent: 60});
  assert.equal(zeilen[0].id, "modell");
  assert.equal(zeilen[0].text, "Kingfisher lädt sein Sprachmodell: 60 %");
  assert.equal(prozent(zeilen[0]), 60);
  assert.deepEqual(lerntZeilen(null, null, null, {laeuft: false, prozent: 100}), []);
});

test("Gescheiterte Mails stehen als Satz mit Grund da, nie als „wird gelesen“ (Fremdprobe 3, Befund 2)", () => {
  const gescheitert = {zustand: "gescheitert", gelesen: 0, gesamt: null, zuletzt: null,
    satz: "Postfach Privat: 5 Mails kamen nicht ins Gedächtnis. Das Postfach hat beim Abholen nicht geantwortet. Kingfisher versucht es später von selbst noch einmal.",
    technik: "INBOX: 5 × postfach_schweigt (MailError ← TimeoutError)"};
  const zeilen = lerntZeilen(status([konto({stand: gescheitert}, {captured: 0, duplicates: 0, failed: 5, pending: 0, total: 5})]), null);
  assert.equal(zeilen.find(zeile => zeile.id === "mail"), undefined);
  const fehler = zeilen.find(zeile => zeile.id === "mail_fehler");
  assert.equal(fehler.text, gescheitert.satz);
  assert.equal(fehler.konto, "a");
  assert.equal(fehler.technik, gescheitert.technik);
  for (const zeile of zeilen) assert.doesNotMatch(zeile.text, /wird gelesen|MailError|IMAP/);
});
