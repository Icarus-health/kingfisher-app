// Konten und Bereiche (Paket K): Vorschlagssatz, „Alle Vorschläge übernehmen“, Filter nur ab zwei Bereichen, gemerkte Wahl.
import assert from "node:assert/strict";
import {test} from "node:test";
import {ALLE, alleUebernommenText, bereichText, filterOptionen, gemerkteWahl, gueltigeWahl, kalenderNeben, merkeWahl,
  neuerName, offeneVorschlaege, passtZuBereich, vorschlagSatz, zurueckZuOhne} from "../src/kontenBereiche.ts";

const BEREICHE = [{id: "arbeit", name: "Arbeit", eigen: false}, {id: "privat", name: "Privat", eigen: false},
  {id: "eigen-verein", name: "Verein", eigen: true}];
const konto = (id, bereich, vorschlag = null) => ({id, name: id, adresse: "", bereich, vorschlag, stand: null});

test("Der Vorschlag steht als Vorschlag da, mit Grund", () => {
  assert.equal(vorschlagSatz({bereiche: BEREICHE}, {vorschlag: {bereich: "privat", grund: "gmail.com ist ein privater Anbieter."}}),
    "Vorschlag: Privat. gmail.com ist ein privater Anbieter.");
  assert.equal(vorschlagSatz({bereiche: BEREICHE}, {vorschlag: null}), "");
});

test("Alle Vorschläge übernehmen nimmt nur unbestätigte mit Vorschlag, und Rückgängig löst sie wieder", () => {
  const konten = {bereiche: BEREICHE, in_gebrauch: [], ausgeblendet: [],
    postfaecher: [konto("mail-a", null, {bereich: "privat", grund: ""}), konto("mail-c", "arbeit", null), konto("mail-d", null, null),
      konto("mail-e", "arbeit", {bereich: "privat", grund: ""})],
    kalender: [konto("calendar-x", null, {bereich: "arbeit", grund: ""})]};
  const zuordnung = offeneVorschlaege(konten);
  assert.deepEqual(zuordnung, {"mail-a": "privat", "calendar-x": "arbeit"});
  assert.deepEqual(zurueckZuOhne(zuordnung), {"mail-a": null, "calendar-x": null});
  assert.equal(alleUebernommenText(2), "2 Vorschläge übernommen.");
  assert.equal(alleUebernommenText(1), "Ein Vorschlag übernommen.");
});

test("Den Filter gibt es erst ab zwei Bereichen; eine gemerkte Wahl gilt nur, wenn es sie noch gibt", () => {
  assert.deepEqual(filterOptionen({bereiche: BEREICHE, in_gebrauch: ["privat"]}), []);
  assert.deepEqual(filterOptionen(null), []);
  const optionen = filterOptionen({bereiche: BEREICHE, in_gebrauch: ["arbeit", "eigen-verein"]});
  assert.deepEqual(optionen.map(o => o.titel), ["Alle", "Arbeit", "Verein"]);
  assert.equal(gueltigeWahl("eigen-verein", optionen), "eigen-verein");
  assert.equal(gueltigeWahl("privat", optionen), ALLE);
  assert.equal(gueltigeWahl(null, optionen), ALLE);
});

test("Gefiltert wird genau nach dem Bereich; ohne Bereich nur unter „Alle“", () => {
  assert.equal(passtZuBereich({bereich: "arbeit"}, "arbeit"), true);
  assert.equal(passtZuBereich({bereich: "privat"}, "arbeit"), false);
  assert.equal(passtZuBereich({bereich: null}, "arbeit"), false);
  assert.equal(passtZuBereich({}, ALLE), true);
});

test("Die Wahl wird je Seite gemerkt; ohne Speicher gilt „Alle“", () => {
  const daten = new Map();
  const speicher = {getItem: k => daten.get(k) ?? null, setItem: (k, v) => daten.set(k, v)};
  merkeWahl("kalender", "privat", speicher);
  assert.equal(gemerkteWahl("kalender", speicher), "privat");
  assert.equal(gemerkteWahl("aufgaben", speicher), ALLE);
  const kaputt = {getItem: () => { throw new Error("gesperrt"); }, setItem: () => { throw new Error("gesperrt"); }};
  assert.equal(gemerkteWahl("kalender", kaputt), ALLE);
  assert.doesNotThrow(() => merkeWahl("kalender", "arbeit", kaputt));
});

test("Sätze nach Umbenennen und Bereichswahl; ein leerer oder gleicher Name ändert nichts", () => {
  assert.equal(bereichText({bereiche: BEREICHE}, "Firma", "arbeit"), "„Firma“ gehört jetzt zum Bereich Arbeit.");
  assert.equal(bereichText({bereiche: BEREICHE}, "Firma", null), "„Firma“ hat keinen Bereich mehr.");
  // Paket S, Befund 6: vorher „Privat gehört jetzt zu Privat.“
  assert.equal(bereichText({bereiche: BEREICHE}, "Privat", "privat"), "„Privat“ gehört jetzt zum Bereich Privat.");
  assert.equal(neuerName("  Anna   privat ", "x"), "Anna privat");
  assert.equal(neuerName("x", "x"), null);
  assert.equal(neuerName("   ", "x"), null);
  assert.equal(kalenderNeben({art: "mac", adresse: ""}), "Mac-Kalender");
  assert.equal(kalenderNeben({art: "caldav", adresse: "anna@firma.example"}), "anna@firma.example · Mit Benutzername und Passwort");
});
