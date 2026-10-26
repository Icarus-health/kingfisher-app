// Flächenpaket P5 (Einstellungen, Einrichtung, Gesundheit) nach der Grundlage vom 23.10.2026 (docs/16-gestaltung.md).
// Zusicherungen: jeder Verweis in die Einstellungen kommt an (ein falscher ließ den Schritt „Dieser Rechner“ abstürzen),
// Schalter stehen rechtsbündig, je Ansicht höchstens ein gefüllter Knopf, der Datenschutz-Satz steht offen da, die
// Seitenliste hat ein Zeichen je Bereich, Für Techniker ist eine ruhige Liste ohne zweiten Pfeil. Synthetische Daten.
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { BEREICHE } from "../src/Einstellungen/gliederung.ts";
import { verweis } from "../src/verweis.ts";

const SRC = fileURLToPath(new URL("../src/", import.meta.url));
const quelle = (datei) => readFileSync(join(SRC, datei), "utf8");
const ohneKommentare = (css) => css.replace(/\/\*[\s\S]*?\*\//g, "");
function dateien(ordner = SRC) {
  return readdirSync(ordner).flatMap(name => {
    const pfad = join(ordner, name);
    return statSync(pfad).isDirectory() ? dateien(pfad) : /\.tsx$/.test(name) ? [pfad] : [];
  });
}

test("P5: jeder feste Verweis in die Einstellungen führt an einen Ort, den es gibt", () => {
  const ziele = [];
  for (const pfad of dateien()) {
    for (const treffer of readFileSync(pfad, "utf8").matchAll(/<Verweis ziel="([^"]+)"/g)) ziele.push([pfad.slice(SRC.length), treffer[1]]);
  }
  assert.ok(ziele.length >= 8, `zu wenige Verweise gefunden: ${ziele.length}`);
  for (const [datei, ziel] of ziele) assert.doesNotThrow(() => verweis(ziel), `${datei}: <Verweis ziel="${ziel}"> gibt es nicht`);
  assert.match(quelle("Einrichtung/RechnerKarte.tsx"), /<Verweis ziel="ki" \/>/, "„Alles Weitere“ führt zu KI & Modelle");
});

test("P5: Schalter sind Umlegeschalter rechts in ihrer Zeile, in den Einstellungen und im Assistenten", () => {
  // Seit V4 der Baustein `Schalter` mit seinen Stilen in Grundlage.css (dieselbe Schärfe, gilt in jeder Fläche).
  const css = ohneKommentare(quelle("Grundlage.css"));
  assert.match(css, /#root \.shell input\[type="checkbox"\]\[role="switch"\] \{[^}]*appearance: none/);
  assert.doesNotMatch(ohneKommentare(quelle("Einstellungen/Einstellungen.css")), /input\[type="checkbox"\]\[role="switch"\] \{/, "kein lokaler Nachbau");
  assert.match(css, /label:has\(> input\[role="switch"\]\) > input\[role="switch"\] \{ order: 2; margin-left: auto; \}/);
  assert.match(css, /input\[type="checkbox"\]\[role="switch"\]:checked \{ background: var\(--g-akzent\); \}/);
  // Jeder Schalter unter „Was Kingfisher darf“ und „Bilder und Karte“ ist ein switch mit Titel und dem Satz, was den Rechner verlässt.
  const online = quelle("WorkspaceOnlineSettings.tsx");
  assert.equal((online.match(/<Schalter /g) ?? []).length, 2);
  assert.doesNotMatch(online, /Auswahl speichern/, "ein Umlegen gilt sofort, kein eigener Speichern-Knopf");
  assert.match(online, /OpenStreetMap deine Internetadresse/);
  assert.match(online, /keine Mails, Namen oder Rechnungen übertragen/);
});

test("P5: höchstens ein gefüllter Knopf je Ansicht unter Zugänge, in der Einrichtung oben und auf Gesundheit", () => {
  const kopf = quelle("Einrichtung/EinrichtungKopf.tsx");
  assert.equal((kopf.match(/className="g-knopf"/g) ?? []).length, 1, "nur „Einrichtung fortsetzen“");
  assert.doesNotMatch(kopf, /primary-action|secondary-action/);
  const zugaenge = quelle("Einstellungen/Zugaenge.tsx");
  assert.doesNotMatch(zugaenge, /className="(g-knopf|primary-action)"/, "gefüllt nur über knopf()");
  assert.match(zugaenge, /const knopf = \(art: "mail" \| "calendar"\) => gefuellt === art \? "g-knopf zugang-neu" : "g-knopf-getoent zugang-neu";/);
  const formulare = quelle("Einstellungen/Quellenformulare.tsx");
  assert.doesNotMatch(formulare, /primary-action/, "die Formulare für Techniker füllen keinen zweiten Knopf");
  const gesundheit = quelle("HealthPage.tsx");
  assert.equal((gesundheit.match(/className="g-knopf"/g) ?? []).length, 1, "nur „Eigene Angabe festhalten“ im Kopf");
  assert.doesNotMatch(gesundheit, /className="primary"/);
  assert.match(gesundheit, /<Seitenkopf titel="Gesundheit"/);
  assert.match(gesundheit, /<Leer zeichen="check"/, "der leere Verlauf ist ein Leerzustand mit einem Satz");
});

test("P5: Datenschutz & Speicherung steht offen als Satz, die Seitenliste hat ein Zeichen je Bereich", () => {
  const seite = quelle("Einstellungen/Seite.tsx");
  assert.match(seite, /<section className="settings-storage" aria-label="Datenschutz & Speicherung">/);
  assert.doesNotMatch(seite, /<details className="settings-storage/);
  assert.match(seite, /<Seitenkopf titel="Einstellungen"/);
  const block = seite.split("const ZEICHEN")[1].split("};")[0];
  const zeichen = [...block.matchAll(/(\w+): "/g)].map(m => m[1]);
  assert.deepEqual(zeichen, BEREICHE.map(b => b.id), "ein Zeichen je Bereich, in der Reihenfolge der Gliederung");
  assert.match(quelle("SettingsSections.tsx"), /className="settings-nav-zeichen" aria-hidden="true"/);
  // „Trennen“ sagt in einem Satz, was es bedeutet, unter der Gruppe.
  assert.match(quelle("Einstellungen/gliederung.ts"), /trennen: "Trennen entfernt nur den Zugang auf diesem Rechner, keine Daten beim Anbieter\."/);
});

test("P5: Für Techniker ist eine ruhige Liste, der Satz steht erst aufgeklappt, nur ein Pfeil", () => {
  const aufklapp = quelle("Einstellungen/Aufklapp.tsx");
  assert.match(aufklapp, /<summary><span>\{titel\}<\/span><\/summary>/);
  assert.match(aufklapp, /<p className="einstellungen-satz">\{satz\}<\/p>\{children\}/);
  const css = ohneKommentare(quelle("Einstellungen/Einstellungen.css"));
  assert.match(css, /#root \.settings-shell \.einstellungen-aufklapp > summary::before \{ content: none; display: none; \}/, "kein zweiter Pfeil der Grundlage");
  assert.match(css, /#root \.settings-shell \.technik \{ display: block; padding: 0; overflow: hidden; \}/, "eine Fläche für alle Abschnitte");
});

test("P5: der Assistent ist ruhig: großer Titel, keine Überzeile, keine Werte außerhalb der Grundlage", () => {
  const erst = quelle("Einrichtung/Erststart.tsx");
  assert.doesNotMatch(erst, /WILLKOMMEN BEI KINGFISHER|className="eyebrow"/);
  const css = ohneKommentare(quelle("Einrichtung/Einrichtung.css"));
  assert.match(css, /#root \.erststart-karte h1 \{[^}]*font: var\(--g-titel-gross\)/);
  // Im Assistenten keine eigenen Farben mehr: Farben kommen aus der Grundlage (Ausnahme: der Hinweis auf Heute, P1).
  const assistent = ohneKommentare(quelle("Einrichtung/Einrichtung.css").split("/* Leere Startseite")[0]);
  assert.ok(assistent.includes(".erststart-karte"), "der Teil des Assistenten ist gefunden");
  assert.doesNotMatch(assistent, /#[0-9a-f]{3,6}\b(?![^{]*\{)/i, "keine festen Farben im Assistenten");
  assert.doesNotMatch(assistent, /--kf-|--calm-/, "keine alten Farbwerte im Assistenten");
});
