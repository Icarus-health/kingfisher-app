import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {ergebnisText, groesseText, jahreAuswahl, quellen, standText} from "../src/suchindex.ts";

const stand = (extra = {}) => ({wortteile_jahre: 0, quellen: 1200, mit_wortteilen: 1200, nur_woerter: 0, groesse_mb: 210.4, ...extra});

test("Gewählt wird aus einer Liste, nicht getippt; ein früherer Wert außerhalb der Liste bleibt sichtbar", () => {
  const auswahl = jahreAuswahl(0);
  assert.deepEqual(auswahl.map(e => e.jahre), [0, 1, 2, 3, 5, 10]);
  assert.equal(auswahl[0].text, "in allen Quellen");
  assert.equal(auswahl[1].text, "in den Quellen des letzten Jahres");
  assert.equal(auswahl[2].text, "in den Quellen der letzten 2 Jahre");
  assert.deepEqual(jahreAuswahl(7).map(e => e.jahre), [0, 1, 2, 3, 5, 7, 10]);
  for (const falsch of [-1, 101, 2.5]) assert.deepEqual(jahreAuswahl(falsch).map(e => e.jahre), [0, 1, 2, 3, 5, 10], String(falsch));
  // Die Oberfläche hat kein Zahlenfeld mehr (Fremdprobe, Befund 28).
  const quelle = readFileSync(new URL("../src/SuchindexSettings.tsx", import.meta.url), "utf8");
  assert.match(quelle, /<select id="suchindex-jahre"/);
  assert.doesNotMatch(quelle, /<input id="suchindex-jahre"|N Jahre|0 = alle/);
});

test("Eine Quelle steht im Singular, nie „Alle 1 Quellen“", () => {
  assert.equal(quellen(1), "1 Quelle");
  assert.equal(quellen(1200), "1.200 Quellen");
  assert.equal(standText(stand({quellen: 1, mit_wortteilen: 1})), "Die eine Quelle wird nach Wortteilen durchsucht. Der Suchindex belegt 210 MB.");
  assert.match(standText(stand({quellen: 0, mit_wortteilen: 0})), /^Noch keine Quellen/);
  assert.equal(standText(stand({wortteile_jahre: 2, mit_wortteilen: 1, nur_woerter: 1, groesse_mb: 1})),
    "1 Quelle wird nach Wortteilen durchsucht, 1 ältere nur nach ganzen Wörtern. Der Suchindex belegt 1 MB.");
  for (const n of [0, 1, 2, 1200]) assert.doesNotMatch(standText(stand({quellen: n, mit_wortteilen: n})), /Alle 1 Quellen|\b1 Quellen/);
  assert.equal(ergebnisText(stand({umgestuft: 1})), "Gespeichert. 1 Quelle wurde umgestellt.");
});

test("Größen stehen für Menschen da: unbekannt, klein, MB, GB", () => {
  assert.equal(groesseText(null), "unbekannt");
  assert.equal(groesseText(0.4), "unter 1 MB");
  assert.equal(groesseText(210.4), "210 MB");
  assert.equal(groesseText(1536), "1,5 GB");
});

test("Der Stand nennt bei 0 alle Quellen, sonst die Aufteilung, und immer die Größe", () => {
  assert.equal(standText(stand()), "Alle 1.200 Quellen werden nach Wortteilen durchsucht. Der Suchindex belegt 210 MB.");
  assert.equal(standText(stand({wortteile_jahre: 2, mit_wortteilen: 900, nur_woerter: 300, groesse_mb: 90})),
    "900 Quellen werden nach Wortteilen durchsucht, 300 ältere nur nach ganzen Wörtern. Der Suchindex belegt 90 MB.");
  assert.match(standText(stand({groesse_mb: null})), /belegt unbekannt/);
});

test("Nach dem Umbau steht, was geschah", () => {
  assert.equal(ergebnisText(stand({umgestuft: 300})), "Gespeichert. 300 Quellen wurden umgestellt.");
  assert.match(ergebnisText(stand({wortteile_jahre: 2, mit_wortteilen: 900, nur_woerter: 300, umgestuft: 300})), /^Gespeichert\. 300 Quellen wurden umgestellt\./);
  assert.match(ergebnisText(stand({umgestuft: 0})), /Es musste nichts umgestellt werden\./);
});
