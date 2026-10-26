import {test} from "node:test";
import assert from "node:assert/strict";
import {
  LANGSAM_MERKER, LANGSAM_SATZ, WARTEN_VORGABE, frageSchonDa, langsamHinweis, merkeFrage, nimmFrage, warteSatz,
  weggeklickt, wegklicken,
} from "../src/wartenImGespraech.ts";

const speicher = () => { const daten = new Map(); return {getItem: k => daten.get(k) ?? null, setItem: (k, v) => daten.set(k, String(v))}; };

test("Während des Wartens steht der echte Schritt des Sidecars, sonst die schlichte Vorgabe", () => {
  assert.equal(warteSatz(null), WARTEN_VORGABE);
  assert.equal(warteSatz({laeuft: false, schritt: null, satz: null}), WARTEN_VORGABE);
  assert.equal(warteSatz({laeuft: true, schritt: "antwort_modell", satz: "Wählt Quellen …"}), "Wählt Quellen …");
  // Nie eine Zeitangabe, nie ein erfundener Satz: Ein leerer oder fremder Wert ergibt die Vorgabe.
  assert.equal(warteSatz({laeuft: true, schritt: "x", satz: ""}), WARTEN_VORGABE);
  assert.equal(warteSatz({laeuft: true, schritt: "x", satz: 3}), WARTEN_VORGABE);
});

test("Der Satz zur Cloud steht nur unter einer langsamen lokalen Antwort, wenn die Cloud aus ist", () => {
  const langsam = {zeiten: {gesamt: 31.4, antwort_modell: 28}};
  assert.equal(langsamHinweis(langsam, {cloudAn: false, weggeklickt: false}), true);
  assert.equal(langsamHinweis({zeiten: {gesamt: 8}}, {cloudAn: false, weggeklickt: false}), false, "8 s ist nicht langsam");
  assert.equal(langsamHinweis({zeiten: {gesamt: 8.1}}, {cloudAn: false, weggeklickt: false}), true);
  assert.equal(langsamHinweis(langsam, {cloudAn: true, weggeklickt: false}), false, "Cloud an: kein Satz");
  assert.equal(langsamHinweis(langsam, {cloudAn: null, weggeklickt: false}), false, "Stand unbekannt: kein Satz");
  assert.equal(langsamHinweis(langsam, {cloudAn: false, weggeklickt: true}), false, "weggeklickt: kein Satz");
  assert.equal(langsamHinweis({...langsam, gedaechtnis_cloud: {anbieter: "anthropic", modell: "m", gesendet: []}},
    {cloudAn: false, weggeklickt: false}), false, "eine Cloudantwort war nicht lokal");
  assert.equal(langsamHinweis(undefined, {cloudAn: false, weggeklickt: false}), false);
  assert.equal(langsamHinweis({}, {cloudAn: false, weggeklickt: false}), false, "ohne gemessene Zeit kein Satz");
  assert.match(LANGSAM_SATZ, /^Lokal dauert das\. Mit der Cloud geht es in wenigen Sekunden\.$/);
});

test("Einmal weggeklickt, bleibt der Satz weg; ohne Speicher fällt nichts um", () => {
  const s = speicher();
  assert.equal(weggeklickt(s), false);
  wegklicken(s);
  assert.equal(weggeklickt(s), true);
  assert.equal(s.getItem(LANGSAM_MERKER), "1");
  const kaputt = {getItem() { throw new Error("gesperrt"); }, setItem() { throw new Error("gesperrt"); }};
  assert.equal(weggeklickt(kaputt), false);
  assert.doesNotThrow(() => wegklicken(kaputt));
  assert.equal(weggeklickt(undefined), false);
});

test("Eine Frage von Heute oder vom Gesprächsanfang wartet genau einmal auf ihr Gespräch", () => {
  merkeFrage("g1", "Wann ist die Abnahme?");
  assert.equal(nimmFrage("g2"), null);
  assert.equal(nimmFrage("g1"), "Wann ist die Abnahme?");
  assert.equal(nimmFrage("g1"), null);
});

test("Die eigene Frage steht nicht doppelt, wenn der Server sie schon zeigt", () => {
  const frage = "Wann ist die Abnahme?";
  assert.equal(frageSchonDa([], frage), false);
  assert.equal(frageSchonDa([{role: "user", content: frage}], frage), true);
  assert.equal(frageSchonDa([{role: "user", content: frage}, {role: "assistant", content: "Antwort"}], frage), false);
  assert.equal(frageSchonDa([{role: "user", content: "andere"}], frage), false);
});

test("Eine Cloudantwort sagt, über wen sie lief; eine lokale sagt nichts", async () => {
  const {cloudVermerk} = await import("../src/wartenImGespraech.ts");
  assert.equal(cloudVermerk({gedaechtnis_cloud: {anbieter: "anthropic", modell: "m", gesendet: ["frage", "textstellen"]}}), "Über Anthropic beantwortet.");
  assert.equal(cloudVermerk({gedaechtnis_cloud: {anbieter: "unbekannt"}}), "Über die Cloud beantwortet.");
  assert.equal(cloudVermerk({}), null);
  assert.equal(cloudVermerk(undefined), null);
});
