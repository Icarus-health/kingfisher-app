// Die Pause trennt ältere Mails von neuer Post (docs/46-hintergrund.md): Was der Nutzer liest, verspricht nicht mehr,
// dass „Pausieren“ alles anhält, und die Karte zeigt den Satz des Sidecars. Synthetische Daten.
import {test} from "node:test";
import assert from "node:assert/strict";
import {einlesenFrage} from "../src/Einrichtung/postfach.ts";
import {PAUSIEREN_AUF_HEUTE} from "../src/Einrichtung/fertig.ts";
import {lerntFuss, lerntZeilen} from "../src/Einrichtung/lernt.ts";

const SATZ = "Postfach Probe-Post: Neue Post wird weiter geholt; ältere Mails sind pausiert (bereits 20 von 100 Mails gelesen). "
  + "Auf Heute geht es mit „Weiter“ weiter.";
const GRUND = "Pausiert. Neue Post und Termine kommen weiter an; ältere Mails und das Lernen warten, bis du „Weiter“ wählst.";

const ordner = {folder: "INBOX", inventory_complete: true, total: 100, captured: 20, duplicates: 0, failed: 0, pending: 80,
  live_pending: 0, analyzed: 0, analysis_failed: 0, deferred: 0, excluded: 0, categorized: 0, categories_pending: 0, categories_failed: 0};
const konto = (stand) => ({account_id: "a", label: "Probe-Post", connected: true, started: true, paused: false, step: "capture",
  error: null, scope: "INBOX", folders: [ordner], stand});
const pausiert = {zustand: "ohne_modell", grund: GRUND, pausiert: true, fortschritt: {gesamt: 0, fertig: 0, offen: 0},
  rate_pro_stunde: null, schaetzung: null, schaetzung_text: null, satz: null, schlange: []};

test("Der Assistent verspricht beim Pausieren nur, was die Pause tut", () => {
  const frage = einlesenFrage("Probe-Post", "lena.probe@example.org");
  assert.match(frage, /Die älteren Mails hältst du jederzeit auf Heute mit „Pausieren“ an; neue Post kommt weiter\.$/);
  assert.doesNotMatch(frage, /Anhalten kannst du es jederzeit/);
  assert.match(PAUSIEREN_AUF_HEUTE, /neue Post holt Kingfisher dann weiter/);
});

test("In der Karte steht der Satz des Sidecars über das Postfach, darunter der Grund mit „Weiter“", () => {
  const zeilen = lerntZeilen({accounts: [konto({zustand: "pausiert", satz: SATZ, gelesen: 20, gesamt: 100, zuletzt: null})],
    analysis_active: false, background_paused: true}, null, pausiert);
  assert.equal(zeilen.find(zeile => zeile.id === "mail")?.text, SATZ);
  const fuss = lerntFuss(pausiert, true);
  assert.equal(fuss.grund, GRUND);
  assert.equal(fuss.knopf, "Weiter");
});

test("Ohne Satz des Sidecars heißt die Zeile „Ältere Mails pausiert“, nicht „Einlesen pausiert“", () => {
  const zeilen = lerntZeilen({accounts: [konto(null)], analysis_active: false, background_paused: true}, null, pausiert);
  assert.equal(zeilen.find(zeile => zeile.id === "mail")?.text, "Ältere Mails pausiert: 20 von 100 Mails gelesen");
});
