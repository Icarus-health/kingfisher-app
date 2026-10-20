// Gesendete Mails einlesen (Paket B1): Der Satz zum Umfang kommt vom Sidecar; der Knopf „Gesendete Mails auch
// einlesen“ steht nur, wo nur der Posteingang läuft und ein Gesendet-Ordner noch erkennbar sein kann. Synthetische Daten.
import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {gesendetKnopfSichtbar, umfangSatz, ergaenzenSatz} from "../src/mailIntakeGesendet.ts";

const ordner = (folder) => ({folder, inventory_complete: true, total: 5, captured: 5, duplicates: 0, failed: 0, pending: 0,
  live_pending: 0, analyzed: 0, analysis_failed: 0, deferred: 0, excluded: 0});
const konto = (mehr = {}) => ({account_id: "a", label: "Probe-Post", connected: true, started: true, paused: false,
  step: "capture", error: null, scope: "INBOX", folders: [ordner("INBOX")],
  umfang: "Nur der Posteingang; gesendete und archivierte Mails sind bei diesem Konto nicht dabei.",
  gesendet_dabei: false, gesendet_erkennbar: null, ...mehr});

test("Der Satz zum Umfang ist der des Sidecars; ohne ihn die bisherigen Sätze", () => {
  assert.equal(umfangSatz(konto()), "Nur der Posteingang; gesendete und archivierte Mails sind bei diesem Konto nicht dabei.");
  assert.equal(umfangSatz(konto({umfang: "Posteingang und Gesendet; ohne Spam und Papierkorb.", gesendet_dabei: true,
    folders: [ordner("INBOX"), ordner("Gesendet")]})), "Posteingang und Gesendet; ohne Spam und Papierkorb.");
  assert.equal(umfangSatz(konto({started: false})),
    "Kingfisher schaut zuerst nach, welche Ordner es gibt, und zeigt sie dir vor dem Einlesen.");
  assert.equal(umfangSatz(konto({umfang: undefined})), "Nur der Posteingang. Gesendete und archivierte Mails sind nicht dabei.");
  assert.equal(umfangSatz(konto({umfang: null, folders: [ordner("INBOX"), ordner("Gesendet")]})),
    "Gelesen werden: Posteingang, Gesendet. Neue Mails aus diesen Ordnern kommen laufend dazu.");
});

test("Der Knopf steht nur im Posteingang-Fall, solange ein Gesendet-Ordner erkennbar sein kann", () => {
  assert.equal(gesendetKnopfSichtbar(konto()), true);
  assert.equal(gesendetKnopfSichtbar(konto({gesendet_erkennbar: true})), true);
  // Nachgesehen, keiner da: kein Knopf, nur der Satz.
  assert.equal(gesendetKnopfSichtbar(konto({gesendet_erkennbar: false})), false);
  // Gesendet schon dabei (IMAP mit Gesendet, Gmail-Gesamtbestand, Microsoft): kein Knopf.
  assert.equal(gesendetKnopfSichtbar(konto({gesendet_dabei: true, folders: [ordner("INBOX"), ordner("Gesendet")]})), false);
  assert.equal(gesendetKnopfSichtbar(konto({gesendet_dabei: true, folders: [ordner("[Gmail]/All Mail")]})), false);
  // Nicht gestartet oder ohne Zugang: kein Knopf.
  assert.equal(gesendetKnopfSichtbar(konto({started: false})), false);
  assert.equal(gesendetKnopfSichtbar(konto({connected: false})), false);
  // Älterer Sidecar ohne die Felder: kein Knopf, nichts versprechen.
  assert.equal(gesendetKnopfSichtbar(konto({gesendet_dabei: undefined, gesendet_erkennbar: undefined})), false);
});

test("Die Antwort des Sidecars wird als Status gezeigt, ohne Satz ein ehrlicher Ersatz", () => {
  assert.equal(ergaenzenSatz({satz: "Gesendete Mails werden jetzt mit eingelesen.", ergaenzt: ["Gesendet"]}),
    "Gesendete Mails werden jetzt mit eingelesen.");
  assert.equal(ergaenzenSatz({satz: "", ergaenzt: []}), "Kingfisher hat nachgesehen; der Stand unten zeigt, was gelesen wird.");
});

test("MailIntake zeigt den Knopf, ruft die Route und meldet Antwort als Status, Fehler als Alert", () => {
  const quelle = readFileSync(new URL("../src/MailIntake.tsx", import.meta.url), "utf8");
  assert.match(quelle, /gesendetKnopfSichtbar\(account\)/);
  assert.match(quelle, /Gesendete Mails auch einlesen/);
  assert.match(quelle, /api\.ordnerErgaenzen\(/);
  assert.match(quelle, /role="status"[^\n]*gesendetSatz|gesendetSatz[^\n]*role="status"/);
  assert.match(quelle, /umfangSatz\(account\)/);
  assert.doesNotMatch(quelle, /„[^“\n]*"/, "nie „…\" in einer Zeichenkette");
  const api = readFileSync(new URL("../src/api.ts", import.meta.url), "utf8");
  assert.match(api, /ordner-ergaenzen/);
});
