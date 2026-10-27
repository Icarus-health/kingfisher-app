// Sichtbarer Fokus überall, lesbare Platzhalter, lesbarer Text auf dem Bild (Persona-Prüfung, Paket B, B4, 27.10.2026).
// Vorher: Die Suchfelder unter Aufgaben zeigten keinen Fokus (ein lokaler Schatten überschrieb den Fokushauch), die
// Platzhalter lagen bei 2,6–3,9:1, „Stand 07:30“ auf dem Bergbild bei 3,2–3,8:1.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { test } from "node:test";

const css = name => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");
const ohneKommentare = text => text.replace(/\/\*[\s\S]*?\*\//g, "");
const grundlage = ohneKommentare(css("Grundlage.css"));

function lum([r, g, b]) {
  const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}
const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
const kontrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
/** Ein Wert aus dem hellen `:root` (erster Treffer) oder dem dunklen Block (zweiter Treffer). */
function rolle(name, dunkel = false) {
  const treffer = [...grundlage.matchAll(new RegExp(`${name}: (#[0-9a-f]{6})`, "gi"))].map(m => m[1]);
  assert.ok(treffer.length >= 2, `${name} hell und dunkel`);
  return hex(treffer[dunkel ? 1 : 0]);
}

// Die Feldgründe, auf denen Platzhalter stehen (gemessen im Rundgang, Seiten /vorhaben, /nachrichten, /conversations).
const FELDGRUND_HELL = [[255, 255, 255], [241, 242, 243], [232, 234, 236]];
const FELDGRUND_DUNKEL = [[34, 41, 49], [49, 56, 64]];

test("Platzhalter erreichen 4,5:1 auf jedem Feldgrund, hell und dunkel", () => {
  for (const grund of FELDGRUND_HELL) assert.ok(kontrast(rolle("--g-platzhalter"), grund) >= 4.5, `hell auf ${grund}: ${kontrast(rolle("--g-platzhalter"), grund).toFixed(2)}`);
  for (const grund of FELDGRUND_DUNKEL) assert.ok(kontrast(rolle("--g-platzhalter", true), grund) >= 4.5, `dunkel auf ${grund}: ${kontrast(rolle("--g-platzhalter", true), grund).toFixed(2)}`);
});

test("jeder Platzhalter benutzt die eine Rolle", () => {
  for (const name of readdirSync(new URL("../src/", import.meta.url)).filter(n => n.endsWith(".css"))) {
    for (const m of ohneKommentare(css(name)).matchAll(/::placeholder\s*\{([^}]*)\}/g))
      assert.match(m[1], /color: var\(--g-platzhalter\)/, `${name}: ${m[0]}`);
  }
});

test("Fokus in Feldern ist eine Kante von 2 px in der Auswahlfarbe, mit 3:1 gegen Fläche und Grund", () => {
  assert.match(grundlage, /:focus-visible \{\s*outline: 2px solid var\(--g-auswahl-kante\); outline-offset: 1px; border-color: var\(--g-auswahl-kante\);\s*\}/);
  const kanten = [...grundlage.matchAll(/--g-auswahl-kante-rgb: (\d+),(\d+),(\d+)/g)].map(m => m.slice(1, 4).map(Number));
  assert.equal(kanten.length, 2, "hell und dunkel");
  for (const [kante, gruende] of [[kanten[0], [[255, 255, 255], [245, 246, 248]]], [kanten[1], [[34, 41, 49], [24, 29, 35]]]])
    for (const grund of gruende) assert.ok(kontrast(kante, grund) >= 3, `${kante} auf ${grund}: ${kontrast(kante, grund).toFixed(2)}`);
  // Die Felder, deren Fokus ihr Rahmen zeigt (Suche und Eingabe im Gespräch), zeigen ihn ebenso.
  const ws = ohneKommentare(css("Workspace.css"));
  assert.match(ws, /\.conversation-nav-search:focus-within \{ outline: 2px solid var\(--g-auswahl-kante\)/);
  assert.match(ws, /\.conversation-command:focus-within \{ outline: 2px solid var\(--g-auswahl-kante\)/);
});

test("kein Fokus wird weggenommen, ohne dass ein Rahmen ihn zeigt", () => {
  const erlaubt = [
    /\.g-zeile-bedient \.g-zeile-ziel:focus-visible/,        // die ganze Zeile zeigt ihn (:has)
    /\.conversation-nav-search input:focus-visible/,          // der Rahmen der Suche zeigt ihn (:focus-within)
  ];
  for (const name of readdirSync(new URL("../src/", import.meta.url)).filter(n => n.endsWith(".css"))) {
    for (const m of ohneKommentare(css(name)).matchAll(/([^{}]*:focus(?:-visible|-within)?[^{}]*)\{([^}]*)\}/g)) {
      const [, selektor, regel] = m;
      if (!/outline:\s*(?:0|none)\b/.test(regel)) continue;
      assert.ok(erlaubt.some(e => e.test(selektor)), `${name}: Fokus weggenommen in ${selektor.trim()}`);
    }
  }
});

test("„Stand 07:30“ auf dem Bergbild in Tinte; zurück tritt er über die Strichstärke", () => {
  assert.match(ohneKommentare(css("TodayOverview.css")), /\.today-stand \{ color: var\(--g-tinte\); font-weight: 400;/);
  // Tinte auf dem hellsten und dem dunkelsten Bildpunkt hinter dem Stand (Rundgang V5 und B4: hell 113,124,136 bis
  // 222,225,230; dunkel unter dem Schleier 41,50,61 bis 96,104,112).
  assert.ok(kontrast(hex("#172635"), [222, 225, 230]) >= 4.5 && kontrast(hex("#172635"), [160, 170, 181]) >= 4.5);
});

test("der rote Knopf der Rückfrage ist lesbar, hell und dunkel", () => {
  // Rot getönt auf der Fläche: #bf3b44 auf 10 % Rot über Weiß; dunkel #f08b8b auf 10 % über #222931.
  const misch = (a, b, t) => a.map((v, i) => Math.round(v * t + b[i] * (1 - t)));
  assert.ok(kontrast(hex("#bf3b44"), misch(hex("#bf3b44"), [255, 255, 255], 0.1)) >= 4.5);
  assert.ok(kontrast(hex("#f08b8b"), misch(hex("#f08b8b"), [34, 41, 49], 0.1)) >= 4.5);
});

test("die Zahl im Segment erreicht 4,5:1 auf dem Grund der Leiste", () => {
  assert.match(grundlage, /\.g-segment-zahl \{ font-weight: 500; color: rgba\(var\(--g-tinte-rgb\),\.72\);/);
  const misch = (a, b, t) => a.map((v, i) => v * t + b[i] * (1 - t));
  for (const [tinte, grund] of [[[23, 38, 53], [245, 246, 248]], [[227, 232, 237], [24, 29, 35]]]) {
    const leiste = misch(tinte, grund, tinte[0] > 100 ? 0.08 : 0.06);
    assert.ok(kontrast(misch(tinte, leiste, 0.72), leiste) >= 4.5, `${tinte}: ${kontrast(misch(tinte, leiste, 0.72), leiste).toFixed(2)}`);
  }
});
