// „Neue Mails in der Cloud einordnen“ (Was Kingfisher darf): aus ist die Vorgabe; ohne Zugang ein Satz; mit Zugang
// muss der Satz des Sidecars angehakt sein; an zeigt Modell und Aufrufe; die Fachwörter stehen in gliederung.ts.
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  OHNE_ZUGANG, WIEDER_LOKAL, einschaltenMoeglich, frageArt, hintergrundZeile, statusSatz, zustimmungsSatz,
} from "../src/Einstellungen/cloudEinordnung.ts";
import { SCHALTER } from "../src/Einstellungen/gliederung.ts";

const SATZ = "Jede neue Mail geht mit Inhalt, Absender und Betreff an Anthropic (Claude API), damit Kingfisher sie einordnet und Bitten und Zusagen erkennt. Das kostet API-Guthaben, höchstens 300 Aufrufe am Tag, und ist nicht auf die EU begrenzt.";
const stand = (extra = {}) => ({ aktiv: false, modell: "", seit: null, heute: 0, tagesbudget: 300, erschoepft: false, zugang_da: false, ...extra });
const zeile = (extra = {}) => ({ rolle: "hintergrund", titel: "Im Hintergrund ordnen", beschreibung: "", cloud_moeglich: true, cloud_satz: SATZ,
  cloud_anbieter: ["anthropic"], wahl: { modell: "", cloud: false, anbieter: "", cloud_einwilligung: "", einwilligung_gueltig: false },
  wirksam: { modell: null, lokal: null, quelle: "keins" }, cloud_einordnung: stand(), ...extra });

test("aus ist die Vorgabe: der Stand des Sidecars entscheidet, nicht die Oberfläche", () => {
  assert.equal(hintergrundZeile([zeile()]).cloud_einordnung.aktiv, false);
  assert.equal(hintergrundZeile([{ ...zeile(), cloud_einordnung: undefined }]), null, "ohne Stand kein Schalter");
  assert.equal(hintergrundZeile([{ ...zeile(), rolle: "antwort" }]), null);
  assert.equal(SCHALTER.cloud_einordnung.titel, "Neue Mails in der Cloud einordnen");
});

test("einschalten ohne Zugang: ein Satz mit dem Weg zu KI & Modelle, kein Knopf", () => {
  assert.equal(frageArt(stand()), "ohne_zugang");
  assert.match(OHNE_ZUGANG, /Claude-Zugang/);
  assert.match(OHNE_ZUGANG, /Schlüssel und Modell/);
  assert.equal(einschaltenMoeglich(stand(), true), false, "ohne Zugang geht auch mit Haken nichts");
});

test("einschalten mit Zugang: der Satz des Sidecars plus „Ich willige ein.“ muss angehakt sein", () => {
  const mit = stand({ zugang_da: true, modell: "claude-synthetic" });
  assert.equal(frageArt(mit), "zustimmung");
  assert.equal(zustimmungsSatz(zeile()), `${SATZ} Ich willige ein.`);
  assert.ok(zustimmungsSatz(zeile()).includes("300 Aufrufe am Tag"), "der Satz aus dem Sidecar wird nicht doppelt gepflegt");
  assert.equal(einschaltenMoeglich(mit, false), false);
  assert.equal(einschaltenMoeglich(mit, true), true);
});

test("an: Status mit Modell und Aufrufen; aufgebraucht sagt, dass es morgen weitergeht; aus wieder lokal", () => {
  assert.equal(statusSatz(stand({ aktiv: true, zugang_da: true, modell: "claude-synthetic", heute: 12 })),
    "Neue Mails werden über Anthropic (claude-synthetic) eingeordnet. Heute 12 von 300 Aufrufen.");
  assert.equal(statusSatz(stand({ aktiv: true, zugang_da: true, modell: "claude-synthetic", heute: 300, erschoepft: true })),
    "Heute sind die 300 Aufrufe aufgebraucht; morgen geht es weiter.");
  assert.equal(WIEDER_LOKAL, "Einordnen läuft wieder nur auf diesem Rechner.");
});
