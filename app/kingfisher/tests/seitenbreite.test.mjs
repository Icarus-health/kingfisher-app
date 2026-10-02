// Seitenbreite für alle Seiten (Fremdprobe, Befunde 1 und 28; docs/16-gestaltung.md, docs/47-einstellungen.md): keine
// globale Mindestbreite, dieselben Stufen überall, und der leere Zustand im Gedächtnis sagt, woher Einträge kommen.
// Ob die Seiten im Browser wirklich passen, misst scripts/probe_seiten_ui.py bei 390, 768 und 1280 px.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { test } from "node:test";

const SRC = new URL("../src/", import.meta.url);
const quelle = (datei) => readFileSync(new URL(datei, SRC), "utf8");
const ohneKommentare = (css) => css.replace(/\/\*[\s\S]*?\*\//g, "");

function cssDateien(ordner = SRC, praefix = "") {
  return readdirSync(ordner, { withFileTypes: true }).flatMap(eintrag => eintrag.isDirectory()
    ? cssDateien(new URL(`${eintrag.name}/`, ordner), `${praefix}${eintrag.name}/`)
    : eintrag.name.endsWith(".css") ? [`${praefix}${eintrag.name}`] : []);
}

test("keine Seite hat eine Mindestbreite: weder global noch in einer einzelnen Regel", () => {
  const dateien = cssDateien();
  assert.ok(dateien.includes("Seitenbreite.css") && dateien.length > 20, dateien.join(", "));
  for (const datei of dateien) {
    const css = ohneKommentare(quelle(datei));
    // `(min-width: 1100px)` in einer Medienabfrage ist keine Mindestbreite; `min-width: 1280px` als Angabe schon.
    const funde = [...css.matchAll(/(?<!\()min-width:\s*(\d+)px/g)].map(m => Number(m[1])).filter(px => px >= 400);
    assert.deepEqual(funde, [], `${datei}: Mindestbreite ${funde.join(", ")} px`);
  }
  assert.doesNotMatch(quelle("styles.css"), /html, body, #root \{[^}]*min-width/);
});

test("die Breitenregeln gelten für alle Seiten und werden zuletzt geladen", () => {
  const main = quelle("main.tsx");
  const importe = [...main.matchAll(/import "\.\/([^"]+\.css)";/g)].map(m => m[1]);
  assert.equal(importe.at(-1), "Seitenbreite.css", importe.join(", "));
  const css = ohneKommentare(quelle("Seitenbreite.css"));
  assert.match(css, /\.shell \{ overflow-x: clip; \}/);
  // Unter 900 px wird die Seitenleiste auf jeder Seite ein Streifen oben, die Seite eine Spalte.
  assert.match(css, /@media \(max-width: 900px\) \{[\s\S]*\.shell \{ grid-template-columns: minmax\(0, 1fr\); \}/);
  assert.match(css, /@media \(max-width: 900px\) \{[\s\S]*\.shell > \.sidebar \{ position: static;/);
  assert.match(css, /@media \(max-width: 900px\) \{[\s\S]*\.briefing-drawer \{ width: 100vw; \}/);
  // Unter 1100 px stapeln sich Gespräch und Gedächtnis; unter 700 px haben Aufgaben eine Spalte.
  assert.match(css, /@media \(max-width: 1100px\) \{[\s\S]*main\.conversation-page \{ grid-template-columns: minmax\(0, 1fr\); \}/);
  assert.match(css, /@media \(max-width: 700px\) \{[\s\S]*\.task-row \{ grid-template-columns: 32px minmax\(0, 1fr\); \}/);
  // Die Bereichsauswahl im Gedächtnis bricht um, statt seitlich aus dem Bild zu rollen.
  assert.match(css, /memory-page-status \.memory-filter \{ display: block; overflow-x: visible;/);
});

test("der leere Zustand im Gedächtnis sagt in einem Satz, woher Einträge kommen, und verweist dorthin", async () => {
  const leer = quelle("GedaechtnisLeer.tsx");
  assert.match(leer, /LEER_ZIEL = "\/settings#zugaenge"/);
  assert.match(leer, /href=\{LEER_ZIEL\}/);
  const satz = leer.match(/LEER_SATZ = "([^"]+)"/)[1];
  assert.equal(satz.split(/[.!?](\s|$)/).filter(t => t && t.trim()).length, 1, "ein Satz");
  for (const datei of ["MemoryDirectory.tsx", "MemoryGraph.tsx", "SachenListe.tsx"]) {
    assert.match(quelle(datei), /<GedaechtnisLeer\b/, datei);
  }
  assert.doesNotMatch(quelle("MemoryDirectory.tsx"), /Sobald belegte Einträge vorliegen, erscheinen sie hier/);
});

// Fremdprobe 3, Befund 14: Die Navigation als Streifen hat keinen eigenen waagerechten Rollbalken und schneidet keine
// Beschriftung ab; es gibt genau eine Regel dafür, nicht je Seite eine eigene. Gemessen im Browser von
// scripts/probe_fremdprobe3_oberflaeche_ui.py bei 390 und 768 px.
test("die Navigation als Streifen rollt nicht und steht nur in Seitenbreite.css", () => {
  for (const datei of cssDateien()) {
    const css = ohneKommentare(quelle(datei));
    assert.doesNotMatch(css, /\.sidebar nav \{[^}]*overflow-x: auto/, `${datei}: die Navigation rollt seitlich`);
    if (datei !== "Seitenbreite.css" && datei !== "styles.css") {
      assert.doesNotMatch(css, /\.sidebar (nav|\.nav-item)\b/, `${datei}: eigene Regel für die Navigation`);
    }
  }
  const css = ohneKommentare(quelle("Seitenbreite.css"));
  assert.match(css, /@media \(max-width: 900px\) \{[\s\S]*\.shell > \.sidebar nav \{[^}]*flex-wrap: wrap;[^}]*overflow: visible;/);
  // Unter 700 px nur Symbole, der aktive Bereich mit Namen; die Namen werden nie abgeschnitten.
  assert.match(css, /@media \(max-width: 700px\) \{[\s\S]*\.shell > \.sidebar \.nav-item:not\(\.active\) span \{ position: absolute;/);
  assert.doesNotMatch(css, /\.nav-item[^{]*\{[^}]*text-overflow: ellipsis/);
});
