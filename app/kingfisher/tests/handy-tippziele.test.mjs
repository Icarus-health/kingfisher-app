// Tippziele am Handy (Persona-Prüfung, Paket H, H3). Vorher: „Rückgängig“ 83 × 20, „Ansehen“ 58 × 17, Belegnummern
// 22 × 22, Segmente 38 und kompakte Knöpfe 36 px hoch, die Tage der Woche 39 px breit, die Punkte im Zeitstrahl 15 × 24.
// Im Browser misst scripts/probe_tippziele_ui.py die wirksame Trefffläche jedes Bedienelements; hier stehen die Regeln.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { naechsterPunkt } from "../src/tippFlaeche.ts";

const quelle = name => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");
const skript = name => readFileSync(new URL(`../../../scripts/${name}`, import.meta.url), "utf8");
const ohneKommentare = css => css.replace(/\/\*[\s\S]*?\*\//g, "");
const grob = () => {
  const css = ohneKommentare(quelle("Seitenbreite.css"));
  const anfang = css.indexOf("@media (pointer: coarse) {");
  assert.ok(anfang > 0, "eine Regel für den Finger");
  return css.slice(anfang);
};

test("mit dem Finger: leise Knöpfe, Verweise und Segmente haben eine unsichtbare Fläche von 44 × 44", () => {
  const css = grob();
  const ziele = css.match(/#root :is\(([^)]*(?:\([^)]*\)[^)]*)*)\)::after \{/)?.[1] ?? "";
  for (const klasse of [".g-segment", ".text-action", ".quiet-source-toggle", ".today-text-link", ".g-knopf-schlicht", ".satz-nr", ".calendar-grid-date", "a[href]"])
    assert.ok(ziele.includes(klasse), `${klasse} hat die Fläche`);
  assert.match(css, /::after \{\s*content: ""; position: absolute; left: 50%; top: 50%; width: max\(100%, var\(--g-ziel\)\); height: max\(100%, var\(--g-ziel\)\);\s*transform: translate\(-50%, -50%\);/);
  // Die Fläche braucht ein Bezugssystem: dieselben Ziele sind `position: relative` (keines hat eine eigene Lage).
  assert.match(css, /#root :is\(\.g-segment, [^{]*\) \{ position: relative; \}/);
  assert.match(css, /button\.satz-nr \+ button\.satz-nr \{ margin-left: 22px; \}/, "Belegnummern nebeneinander teilen sich keine Fläche");
});

test("Knöpfe mit Grund, Felder und Aufklapper sind am Finger 44 hoch; der Zeitstrahl nimmt die ganze Spur", () => {
  const css = grob();
  assert.match(css, /#root :is\(\.g-kompakt, \.secondary-action, \.primary-action, \.tasks-add, \.akte-knopf, [^{]*\.text-action:not\(small \*\)[^{]*\) \{ min-height: var\(--g-ziel\) !important; \}/);
  assert.match(css, /#root details > summary \{ min-height: var\(--g-ziel\) !important;/);
  assert.match(css, /#root \.shell main :is\(select, input[^{]*\) \{ min-height: var\(--g-ziel\) !important; \}/);
  assert.match(css, /#root \.akte-punkt \{ pointer-events: none; \}/);
  const akte = quelle("AkteAbschnitte.tsx");
  assert.match(akte, /<div className="akte-spur-bahn" onClick=\{ereignis => \{[\s\S]*naechsterPunkt\(liste\.map\(x => r\.left \+ r\.width \* lage\(x\.zeit\.getTime\(\)\) \/ 100\), ereignis\.clientX\);/);
  // Breit und mit Maus bleibt alles, wie es war: die Regeln stehen nur unter `pointer: coarse`.
  const vorher = ohneKommentare(quelle("Seitenbreite.css")).slice(0, ohneKommentare(quelle("Seitenbreite.css")).indexOf("@media (pointer: coarse) {"));
  assert.doesNotMatch(vorher, /::after \{\s*content: ""; position: absolute; left: 50%/);
});

test("ein Tipp auf die Spur wählt den nächsten Punkt bis 22 px daneben", () => {
  assert.equal(naechsterPunkt([10, 50, 120], 55), 1);
  assert.equal(naechsterPunkt([10, 50, 120], 72), 1, "22 px daneben");
  assert.equal(naechsterPunkt([10, 50, 120], 73), null, "23 px daneben: nichts");
  assert.equal(naechsterPunkt([], 10), null);
  assert.equal(naechsterPunkt([100, 104], 103), 1, "der nähere von zwei dichten");
});

test("die Woche am Handy: sieben Tage zu mindestens 44 px bei 390 px", () => {
  const grundlage = quelle("Grundlage.css");
  const zeit = Number(grundlage.match(/--g-kal-zeitspalte-woche-schmal: (\d+)px;/)?.[1]);
  const rand = 16; // `main.calendar-page` schmal: var(--g-a4)
  assert.match(ohneKommentare(quelle("CalendarPage.css")), /#root main\.calendar-page \{ padding-left:var\(--g-a4\); padding-right:var\(--g-a4\); \}/);
  assert.ok((390 - 2 * rand - zeit) / 7 - 1 >= 44, `je Tag ${((390 - 2 * rand - zeit) / 7 - 1).toFixed(1)} px`);
});

test("die Probe misst am Handy mit grobem Zeiger, die wirksame Fläche, und meldet alles unter 44 px", () => {
  const probe = skript("probe_tippziele_ui.py");
  assert.match(probe, /MINDEST = 44/);
  assert.match(probe, /viewport=\{'width': 390, 'height': 844\}, is_mobile=True, has_touch=True/);
  assert.match(probe, /matchMedia\('\(pointer: coarse\)'\)\.matches/);
  assert.match(probe, /return 0 if ergebnis\['ok'\] else 1/);
  const js = skript("tippziele.js");
  assert.match(js, /document\.elementFromPoint\(x, y\)/, "gemessen wird, was ein Tipp trifft");
  assert.match(js, /if \(w < min \|\| h < min\) aus\.klein\.push/);
  for (const seite of ["'/today'", "'/vorhaben'", "'/nachrichten'", "'/calendar'", "'/memory'", "'/settings'", "'/conversations'"]) assert.ok(probe.includes(seite), seite);
});
