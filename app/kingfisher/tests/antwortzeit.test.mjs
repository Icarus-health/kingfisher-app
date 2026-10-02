import {test} from "node:test";
import assert from "node:assert/strict";
import {LANGSAM_S, gueltigeZeiten, protokollSatz, protokollZeilen, sekunden, ursacheSatz, zeitZeile} from "../src/antwortzeit.ts";

const protokoll = (extra = {}) => ({
  antworten: 12, ziel_s: 8, saetze: "an", modelle: {frage: null, antwort: "qwen"},
  abschnitte: {gesamt: {median: 3.24, p90: 9.1, anzahl: 12}, suche: {median: 0.3, p90: 0.5, anzahl: 12},
    saetze_modell: {median: 2.1, p90: 6.4, anzahl: 11}}, ...extra});

test("Sekunden: unter zehn mit Komma und einer Stelle, darüber ganz", () => {
  assert.equal(sekunden(3.24), "3,2");
  assert.equal(sekunden(0.04), "0,0");
  assert.equal(sekunden(9.96), "10");
  assert.equal(sekunden(12.4), "12");
  assert.equal(sekunden(8), "8,0");
});

test("Die Zeile nennt die Gesamtzeit und die Teile ab einer Zehntelsekunde", () => {
  assert.equal(zeitZeile({gesamt: 3.2, suche: 0.3, antwort_modell: 0.6, saetze_modell: 2.1}), "3,2 s · Suche 0,3 · Auswahl 0,6 · Sätze 2,1");
  assert.equal(zeitZeile({gesamt: 0.8, frage: 0.01, suche: 0.7, satzpruefung: 0.02}), "0,8 s · Suche 0,7");
  assert.equal(zeitZeile({gesamt: 1.5}), "1,5 s", "ohne Teile nur die Gesamtzeit");
});

test("Ohne gemessene Zeiten gibt es nichts zu zeigen", () => {
  for (const roh of [undefined, null, {}, "3 s", {gesamt: "3"}, {gesamt: -1}, {gesamt: NaN}]) assert.equal(gueltigeZeiten(roh), null, String(roh));
  assert.deepEqual(gueltigeZeiten({gesamt: 2}), {gesamt: 2});
});

test("Bis zur Grenze gibt es keinen Satz zur Ursache", () => {
  assert.equal(LANGSAM_S, 8);
  assert.equal(ursacheSatz({gesamt: 8, saetze_modell: 7}), null);
  assert.equal(ursacheSatz({gesamt: 2, saetze_modell: 1.5}), null);
});

test("Über der Grenze nennt ein Satz den größten Teil", () => {
  assert.equal(ursacheSatz({gesamt: 13, suche: 0.4, antwort_modell: 0.6, saetze_modell: 12}),
    "Der zweite Modellaufruf für die Sätze brauchte 12 s. Unter Einstellungen, Lokale KI, lassen sich die Sätze ausschalten.");
  assert.equal(ursacheSatz({gesamt: 9.5, antwort_modell: 9, saetze_modell: 0.3}), "Der erste Modellaufruf, der die Quellen auswählt, brauchte 9,0 s.");
  assert.equal(ursacheSatz({gesamt: 10, suche: 9.5}), "Die Suche in deinen Quellen brauchte 9,5 s.");
  assert.equal(ursacheSatz({gesamt: 10, frage: 9.5}), "Das Verstehen der Frage brauchte 9,5 s.");
  assert.equal(ursacheSatz({gesamt: 10, satzpruefung: 9.5}), "Die Prüfung der Sätze brauchte 9,5 s.");
});

test("Prägt kein einzelner Teil die Zeit, sagt der Satz das", () => {
  assert.equal(ursacheSatz({gesamt: 12, suche: 3, antwort_modell: 3, saetze_modell: 3}), "Die Zeit verteilt sich auf mehrere Schritte.");
  assert.equal(ursacheSatz({gesamt: 12}), "Die Zeit verteilt sich auf mehrere Schritte.");
});

test("Das Protokoll zeigt nur gemessene Abschnitte, die Gesamtzeit zuletzt", () => {
  const zeilen = protokollZeilen(protokoll());
  assert.deepEqual(zeilen.map(z => z.name), ["suche", "saetze_modell", "gesamt"]);
  assert.deepEqual(zeilen[2], {name: "gesamt", titel: "Antwort insgesamt", median: "3,2", p90: "9,1", anzahl: 12});
});

test("Der Satz über dem Protokoll sagt im Ziel oder darüber, ohne Technik", () => {
  assert.match(protokollSatz(protokoll()), /^Typisch sind 3,2 s \(Median\), das ist im Ziel von 8,0 s\. Neun von zehn Antworten kamen in höchstens 9,1 s\./);
  const langsam = protokoll({abschnitte: {gesamt: {median: 14.2, p90: 30, anzahl: 5}}});
  assert.match(protokollSatz(langsam), /über dem Ziel von 8,0 s/);
  assert.match(protokollSatz(protokoll({abschnitte: {}})), /^Noch keine gemessene Antwort/);
});
