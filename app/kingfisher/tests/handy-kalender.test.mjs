// Kalender am Handy (Persona-Prüfung, Paket H, H1). Vorher: Die Woche zeigte bei 390 px nur Montag bis Donnerstag,
// Freitag bis Sonntag lagen seitlich versteckt, Titel brachen mitten im Wort. Vorgabe war überall der Monat, und die
// laufende Woche lag unter dem Rand (auch bei 1024 px mit Zoom 200 %). Die Seite schrieb jede Ansicht zurück in den
// Speicher, auch die Vorgabe; eine Wahl war von ihr nicht zu unterscheiden.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { ALTER_SCHLUESSEL, WAHL_SCHLUESSEL, anfangsAnsicht, gewaehlteAnsicht, merkeAnsicht, rollenFuerZeile, vorgabeAnsicht } from "../src/kalenderAnsicht.ts";

const quelle = name => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");
const ohneKommentare = css => css.replace(/\/\*[\s\S]*?\*\//g, "");
function speicher(werte = {}) {
  const daten = new Map(Object.entries(werte));
  return { daten, getItem: k => daten.has(k) ? daten.get(k) : null, setItem: (k, v) => daten.set(k, String(v)), removeItem: k => daten.delete(k) };
}

test("die Vorgabe: am Handy die Liste der nächsten sieben Tage, breit der Monat", () => {
  assert.equal(vorgabeAnsicht(true), "Liste");
  assert.equal(vorgabeAnsicht(false), "Monat");
  assert.equal(anfangsAnsicht(speicher(), true), "Liste");
  assert.equal(anfangsAnsicht(speicher(), false), "Monat");
  assert.equal(anfangsAnsicht(null, true), "Liste", "ohne Speicher");
  const kaputt = { getItem() { throw new Error("gesperrt"); }, setItem() { throw new Error("gesperrt"); }, removeItem() {} };
  assert.equal(anfangsAnsicht(kaputt, true), "Liste");
  assert.doesNotThrow(() => merkeAnsicht(kaputt, "Woche"));
});

test("eine Wahl des Nutzers bleibt gemerkt, die alte Vorgabe zählt am Handy nicht als Wahl", () => {
  assert.equal(anfangsAnsicht(speicher({ [WAHL_SCHLUESSEL]: "Woche" }), true), "Woche");
  assert.equal(anfangsAnsicht(speicher({ [WAHL_SCHLUESSEL]: "Monat" }), true), "Monat", "Monat am Handy, wenn gewählt");
  assert.equal(anfangsAnsicht(speicher({ [WAHL_SCHLUESSEL]: "Monat", [ALTER_SCHLUESSEL]: "Woche" }), true), "Monat", "die neue Wahl vor der alten");
  // Bis 1.0.29 stand im alten Schlüssel fast immer die Vorgabe „Monat“; am Handy gilt sie nicht mehr als Wahl.
  assert.equal(gewaehlteAnsicht(speicher({ [ALTER_SCHLUESSEL]: "Monat" }), true), null);
  assert.equal(anfangsAnsicht(speicher({ [ALTER_SCHLUESSEL]: "Monat" }), true), "Liste");
  assert.equal(anfangsAnsicht(speicher({ [ALTER_SCHLUESSEL]: "Monat" }), false), "Monat", "am Desktop wie bisher");
  assert.equal(anfangsAnsicht(speicher({ [ALTER_SCHLUESSEL]: "Woche" }), true), "Woche", "eine andere war gewählt");
  assert.equal(anfangsAnsicht(speicher({ [ALTER_SCHLUESSEL]: "Jahr" }), false), "Jahr");
  assert.equal(anfangsAnsicht(speicher({ [WAHL_SCHLUESSEL]: "Quartal" }), true), "Liste", "Ungültiges zählt nicht");
  const s = speicher({ [ALTER_SCHLUESSEL]: "Monat" });
  merkeAnsicht(s, "Woche");
  assert.equal(s.daten.get(WAHL_SCHLUESSEL), "Woche");
  assert.equal(s.daten.has(ALTER_SCHLUESSEL), false);
  assert.equal(anfangsAnsicht(s, true), "Woche");
});

test("die laufende Woche rückt ins Bild, so wenig wie nötig, und über die Leiste unten", () => {
  const bild = { oben: 0, unten: 384 - 64 };
  assert.equal(rollenFuerZeile({ oben: 100, unten: 160 }, bild), 0, "steht schon im Bild");
  assert.equal(rollenFuerZeile({ oben: 718, unten: 787 }, bild), 787 - 320 + 12, "unter dem Rand: gerade so weit");
  assert.equal(rollenFuerZeile({ oben: -80, unten: -20 }, bild), -92, "über dem Rand: zurück");
  assert.equal(rollenFuerZeile({ oben: 500, unten: 1000 }, bild), 488, "zu hoch: der Anfang oben");
  assert.equal(rollenFuerZeile({ oben: 746, unten: 864 }, { oben: 0, unten: 800 }), 76, "1280 × 800");
});

test("die Seite: Vorgabe nach Breite, gemerkt wird nur die Wahl, die Woche rollt ohne scrollIntoView ins Bild", () => {
  const kal = quelle("CalendarPage.tsx");
  assert.match(kal, /anfangsAnsicht\(speicherOderNichts\(\), schmal\(\)\)/);
  assert.match(kal, /onWahl=\{waehleAnsicht\}/);
  assert.match(kal, /function waehleAnsicht\(neu: View\) \{\s*merkeAnsicht\(speicherOderNichts\(\), neu\);/);
  assert.doesNotMatch(kal, /localStorage\.setItem\("kingfisher-calendar-view"/, "die Vorgabe wird nicht mehr als Wahl gespeichert");
  // Ohne eigene Wahl folgt die Ansicht der Breite (Fenster schmaler gezogen, Handy gedreht).
  assert.match(kal, /if \(!gewaehlteAnsicht\(speicherOderNichts\(\), media\.matches\)\) setView\(vorgabeAnsicht\(media\.matches\)\);/);
  assert.match(kal, /rollenFuerZeile\(/);
  assert.match(kal, /window\.scrollBy\(\{ top: delta, behavior: "auto" \}\)/);
  const monat = kal.slice(kal.indexOf("wocheImBild"), kal.indexOf("wocheImBild") + 1400);
  assert.doesNotMatch(monat, /scrollIntoView/, "Chrome setzte damit den Ausgangspunkt für Tab (B2)");
});

test("Woche am Handy: alle sieben Tage ohne seitliches Rollen; Titel brechen an Wortgrenzen, mit Trennstrich", () => {
  const css = ohneKommentare(quelle("CalendarPage.css"));
  const schmal = css.slice(css.indexOf("@media(max-width:700px)"));
  assert.match(schmal, /\.calendar-time-grid:not\(\.single-day\) \{ grid-template-columns:var\(--g-kal-zeitspalte-schmal\) repeat\(7,minmax\(0,1fr\)\); \}/);
  assert.doesNotMatch(schmal, /repeat\(7,minmax\(var\(--g-kal-tag-schmal\)/, "keine Mindestbreite je Tag mehr");
  // Schmal bricht ein Titel nur an Wortgrenzen und trennt mit Strich (hyphens:auto, lang=de); ein Wort wird nie ohne
  // Strich zerschnitten (kein overflow-wrap:anywhere/break-word in der engen Spalte).
  assert.match(schmal, /\.calendar-time-event strong \{[^}]*overflow-wrap:normal;[^}]*hyphens:auto;/);
  assert.match(quelle("../index.html"), /<html lang="de">/);
  for (const regel of ["calendar-time-event strong", "calendar-month-event", "calendar-entry-text strong", "calendar-detail h3"]) {
    const block = css.match(new RegExp(`\\.${regel.replace(" ", " ")} \\{[^}]*\\}`))?.[0] ?? "";
    assert.match(block, /hyphens:auto/, `${regel}: hyphens:auto`);
    assert.doesNotMatch(block, /overflow-wrap:anywhere/, `${regel}: nie mitten im Wort`);
  }
});
