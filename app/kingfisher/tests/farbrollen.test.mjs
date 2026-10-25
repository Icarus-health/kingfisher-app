// Dunkelmodus (V5, 25.10.2026; docs/16-gestaltung.md „Dunkelmodus vom 25.10.2026“): Alle Farben kommen aus Rollen.
// Geprüft wird: keine harten Farbwerte außerhalb der Rollendefinitionen (mit kleiner, begründeter Ausnahmeliste), jede
// Rolle mit hellem Wert hat einen dunklen, die Hauptpaare erfüllen WCAG AA in beiden Modi, die Navigation bleibt dunkel,
// die Landschaft bekommt im Dunkeln einen Schleier, Kalender- und Kartenfarben sind Rollen.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { test } from "node:test";
import { calendarColor } from "../src/calendarLayout.ts";

const SRC = new URL("../src/", import.meta.url);
const quelle = (datei) => readFileSync(new URL(datei, SRC), "utf8");
function dateien(ordner = SRC, praefix = "") {
  return readdirSync(ordner, { withFileTypes: true }).flatMap(e => e.isDirectory()
    ? dateien(new URL(`${e.name}/`, ordner), `${praefix}${e.name}/`)
    : /\.(css|tsx?)$/.test(e.name) ? [`${praefix}${e.name}`] : []);
}
const ohneKommentare = (css) => css.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "));

/** Die Dateien, in denen Rollen definiert werden – nur dort, und nur in `:root`, stehen Farbwerte. */
export const ROLLEN_DATEIEN = ["theme.css", "CalmUI.css", "NordicWorkspace.css", "Grundlage.css"];

/** Ausnahmen: Eigenschaften, deren Farbe nie zu sehen ist, und Dateien außerhalb der Oberfläche. Jede mit Grund. */
export const AUSNAHMEN = [
  { eigenschaft: /^(-webkit-)?mask(-image)?$/, grund: "Masken nutzen nur die Deckkraft (#000 = sichtbar), keine Farbe." },
];
// Nicht geprüft, weil keine Farbe der Oberfläche: Bilder (Eisvogel, Landschaft, Logo, Symbole) liegen als Dateien in
// design-source und bleiben in beiden Modi, wie sie freigegeben sind; leaflet.css kommt aus dem Paket und wird in
// WorkspaceMemoryDetails.css für den Dunkelmodus überschrieben; die Fensterleiste (index.html, theme-color) trägt die
// Farbe der Navigation, die in beiden Modi gleich bleibt.

const NAMEN = "white|black|red|green|blue|gray|grey|orange|yellow|navy|silver|teal|purple|pink|brown|maroon|olive|lime|aqua|fuchsia|gold|beige|ivory|khaki|coral|crimson|tomato|salmon|indigo|violet|plum|tan|linen|snow|wheat|azure|lavender|chocolate|firebrick|whitesmoke|gainsboro|darkgray|lightgray|dimgray";
const FARBE = new RegExp(String.raw`#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch)\(\s*(?!var\()|(?<![-\w])(?:${NAMEN})(?![-\w])`, "gi");

/** Alle Deklarationen einer CSS-Datei mit dem Stapel ihrer Selektoren. */
export function deklarationen(css) {
  const text = ohneKommentare(css); const aus = []; const stapel = []; let puffer = ""; let zeile = 1; let start = 1;
  for (const z of text) {
    if (z === "{") { stapel.push(puffer.trim()); puffer = ""; }
    else if (z === "}") { if (puffer.trim()) aus.push({ stapel: [...stapel], dekl: puffer.trim(), zeile: start }); puffer = ""; stapel.pop(); }
    else if (z === ";") { aus.push({ stapel: [...stapel], dekl: puffer.trim(), zeile: start }); puffer = ""; }
    else { if (z === "\n") zeile++; if (!puffer.trim()) start = zeile; puffer += z; }
  }
  return aus.filter(d => d.dekl.includes(":") && !d.dekl.startsWith("@")).map(d => {
    const i = d.dekl.indexOf(":");
    return { ...d, eigenschaft: d.dekl.slice(0, i).trim().toLowerCase(), wert: d.dekl.slice(i + 1).trim() };
  });
}
const istRolle = (datei, d) => ROLLEN_DATEIEN.includes(datei) && d.eigenschaft.startsWith("--") && d.stapel.at(-1) === ":root";

/** Harte Farbwerte einer Datei außerhalb der Rollendefinitionen. */
export function harteFarben(datei, text) {
  const funde = [];
  if (datei.endsWith(".css")) {
    for (const d of deklarationen(text)) {
      if (istRolle(datei, d) || AUSNAHMEN.some(a => a.eigenschaft.test(d.eigenschaft))) continue;
      const wert = d.wert.replace(/url\([^)]*\)/g, "url()");
      for (const m of wert.matchAll(FARBE)) funde.push(`${datei}:${d.zeile} ${d.eigenschaft}: ${m[0]}`);
    }
  } else {
    // Skripte: Farbwerte in Zeichenketten (Inline-Stile, Leaflet, SVG-Attribute) sind verboten, Rollen nicht.
    text.split("\n").forEach((z, i) => {
      if (/^\s*(\/\/|\*)/.test(z)) return;
      for (const m of z.matchAll(new RegExp(String.raw`["'\`](?:#[0-9a-fA-F]{3,8}|(?:rgba?|hsla?)\(\s*\d[^"'\`]*|${NAMEN})["'\`]`, "gi")))
        funde.push(`${datei}:${i + 1} ${m[0]}`);
    });
  }
  return funde;
}

test("keine harten Farbwerte außerhalb der Rollendefinitionen (CSS, Inline-Stile, Skripte)", () => {
  const funde = dateien().flatMap(d => harteFarben(d, quelle(d)));
  assert.deepEqual(funde, [], `Farben gehören in eine Rolle (CalmUI.css, NordicWorkspace.css, Grundlage.css):\n${funde.join("\n")}`);
});

test("der Prüfer findet harte Werte wirklich (Gegenprobe ohne Dateien)", () => {
  assert.equal(harteFarben("X.css", ".a { color: #123456; }").length, 1);
  assert.equal(harteFarben("X.css", ".a { box-shadow: 0 1px 2px rgba(0,0,0,.2); }").length, 1);
  assert.equal(harteFarben("X.css", ".a { border: 1px solid white; }").length, 1);
  assert.equal(harteFarben("X.css", ".a { --lokal: #fff; }").length, 1, "eine Rolle außerhalb von :root ist keine Rolle");
  assert.equal(harteFarben("Grundlage.css", ".a { --lokal: #fff; }").length, 1);
  assert.equal(harteFarben("X.css", ":root { --x: #fff; }").length, 1, "nur in den Rollendateien");
  assert.equal(harteFarben("X.css", ".a { color: var(--g-rot, #bf3b44); }").length, 1, "auch kein Ersatzwert");
  assert.equal(harteFarben("X.tsx", "<i style={{background:'#fff'}} />").length, 1);
  assert.equal(harteFarben("X.ts", "L.circleMarker(p,{color:'rgba(1,2,3,.5)'})").length, 1);
  assert.deepEqual(harteFarben("X.css", ".a { color: rgba(var(--g-tinte-rgb), .5); background: var(--g-grund); mask-image: linear-gradient(#000, transparent); }"), []);
  assert.deepEqual(harteFarben("Grundlage.css", "@media (prefers-color-scheme: dark) { :root { --g-grund: #181d23; } }"), []);
  assert.deepEqual(harteFarben("X.css", ".whitespace { white-space: nowrap; }"), []);
});

// ── Rollen: hell und dunkel ─────────────────────────────────────────────────────────────────────────────────────
/** Die Rollen einer Datei, getrennt nach hell (`:root`) und dunkel (`@media (prefers-color-scheme: dark) { :root }`). */
function rollen(datei) {
  const hell = {}, dunkel = {};
  for (const d of deklarationen(quelle(datei))) {
    if (!d.eigenschaft.startsWith("--") || d.stapel.at(-1) !== ":root") continue;
    if (d.stapel.length === 1) hell[d.eigenschaft] = d.wert;
    else if (/prefers-color-scheme:\s*dark/.test(d.stapel[0])) dunkel[d.eigenschaft] = d.wert;
  }
  return { hell, dunkel };
}
const alle = Object.fromEntries(ROLLEN_DATEIEN.map(d => [d, rollen(d)]));
const hellAlle = Object.assign({}, ...ROLLEN_DATEIEN.map(d => alle[d].hell));
const dunkelAlle = Object.assign({}, hellAlle, ...ROLLEN_DATEIEN.map(d => alle[d].dunkel));

/** Den Wert einer Rolle auflösen (var(), auch geschachtelt) bis zum Farbwert. */
function aufloesen(wert, tabelle, tiefe = 0) {
  assert.ok(tiefe < 12, `Zirkel bei ${wert}`);
  return wert.replace(/var\((--[\w-]+)(?:\s*,[^)]*)?\)/g, (_, n) => {
    assert.ok(n in tabelle, `Rolle ${n} ist nicht definiert`);
    return aufloesen(tabelle[n], tabelle, tiefe + 1);
  });
}
function rgb(wert) {
  const w = wert.trim();
  let m = w.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (m) { const h = m[1].length === 3 ? [...m[1]].map(c => c + c).join("") : m[1]; return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16)); }
  m = w.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i); if (m) return m.slice(1, 4).map(Number);
  m = w.match(/^(\d+)\s*,\s*(\d+)\s*,\s*(\d+)$/); if (m) return m.slice(1, 4).map(Number);
  return null;
}
const lum = (c) => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
export const kontrast = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
const farbe = (name, tabelle) => { const c = rgb(aufloesen(`var(${name})`, tabelle)); assert.ok(c, `${name} ist keine Farbe`); return c; };

/** Rollen, die im Dunkeln bewusst gleich bleiben (mit Grund). */
const BLEIBT = {
  "--nordic-nav": "die Navigation bleibt dunkel", "--nordic-nav-active": "", "--nordic-nav-tinte": "", "--nordic-nav-tinte-aktiv": "",
  "--nordic-nav-hover": "", "--nordic-nav-leise": "", "--nordic-nav-fokus": "", "--nordic-nav-glanz": "", "--nordic-nav-tiefe": "",
  "--g-schalter-knopf": "der Knopf des Schalters ist am Mac auch dunkel weiß", "--g-hinweis-hauch": "Hauch auf dem dunklen Hinweis, in beiden Modi",
  "--g-ort": "Kartenpunkte stehen auf den hellen Kacheln, nicht auf der Fläche", "--g-ort-gewaehlt": "", "--g-ort-neu": "",
};

test("jede helle Rolle hat einen dunklen Wert, außer der Navigation und ausdrücklich gleichen Rollen", () => {
  const fehlt = [];
  for (const datei of ["CalmUI.css", "NordicWorkspace.css", "Grundlage.css"]) {
    const { hell, dunkel } = alle[datei];
    for (const [name, wert] of Object.entries(hell)) {
      // Was nur auf eine andere Rolle verweist (auch mit Ersatzwert), folgt ihr von selbst.
      const eigen = wert.replace(/var\([^()]*(?:\([^()]*\)[^()]*)*\)/g, "");
      if (!/#[0-9a-f]{3,8}\b|rgba?\(|^\d+\s*,/i.test(eigen) || name in dunkel || name in BLEIBT) continue;
      fehlt.push(`${datei}: ${name}`);
    }
  }
  assert.deepEqual(fehlt, []);
  // Der Bestand (theme.css): Jede helle Fläche oder Kante und jede dunkle Schrift bekommt eine dunkle Rolle; was schon
  // hell auf Dunklem steht oder dunkel gefüllt ist (Navigation, Marken), bleibt.
  const { hell, dunkel } = alle["theme.css"];
  const offen = Object.entries(hell).filter(([name, wert]) => {
    const c = rgb(wert); if (!c || name in dunkel) return false;
    if (/^--kf-(flaeche|rand)-(?!rgb-(b5ced0|ffffff)$)/.test(name) && !/^--kf-rand-(ffffff|rgb-ffffff|rgb-b5ced0)$/.test(name)) return lum(c) > 0.45;
    if (/^--kf-schrift-/.test(name)) return lum(c) < 0.2;
    return false;
  }).map(([n]) => n);
  assert.deepEqual(offen, [], "helle Flächen/Kanten oder dunkle Schrift ohne dunkle Rolle");
  for (const d of ["theme.css", "NordicWorkspace.css"]) assert.match(quelle(d), /@media \(prefers-color-scheme: dark\) \{\s*:root \{[^}]*color-scheme: dark;/, `${d}: color-scheme dunkel`);
});

test("WCAG AA in beiden Modi: Text 4,5:1, große Schrift und Bedienelemente 3:1", () => {
  // [Vordergrund, Hintergrund, Schwelle]
  const paare = [
    ["--calm-ink", "--calm-surface", 4.5], ["--calm-ink", "--calm-inset", 4.5], ["--calm-ink", "--calm-soft", 4.5],
    ["--calm-muted", "--calm-surface", 4.5], ["--calm-muted", "--calm-inset", 4.5], ["--calm-muted", "--calm-soft", 4.5],
    ["--calm-link", "--calm-surface", 4.5], ["--calm-link", "--calm-inset", 4.5],
    ["--calm-on-primary", "--calm-primary", 4.5], ["--g-auf-akzent", "--g-akzent", 4.5],
    ["--calm-ink", "--nordic-selection", 4.5], ["--calm-muted", "--nordic-selection", 4.5],
    ["--g-rot", "--calm-surface", 4.5], ["--g-gruen", "--calm-surface", 4.5], ["--g-warnung", "--g-warnung-grund", 4.5],
    ["--nordic-note", "--nordic-note-ground", 4.5], ["--g-hinweis-tinte", "--g-hinweis-grund", 4.5],
    ["--nordic-nav-tinte", "--nordic-nav", 4.5], ["--nordic-nav-leise", "--nordic-nav", 4.5],
    ["--calm-primary", "--calm-inset", 3], ["--nordic-selection-edge", "--calm-surface", 3], ["--nordic-selection-edge", "--calm-inset", 3],
    ...[1, 2, 3, 4, 5, 6, 7].map(i => [`--g-kal-farbe-${i}`, "--calm-surface", 3]),
  ];
  const zu = [];
  for (const [modus, tabelle] of [["hell", hellAlle], ["dunkel", dunkelAlle]]) {
    for (const [vorne, hinten, schwelle] of paare) {
      const k = kontrast(farbe(vorne, tabelle), farbe(hinten, tabelle));
      if (k < schwelle) zu.push(`${modus}: ${vorne} auf ${hinten} ${k.toFixed(2)} < ${schwelle}`);
    }
  }
  assert.deepEqual(zu, []);
});

test("im Dunkeln: Schiefer statt Schwarz, Flächen eine Stufe heller als der Grund, Tinte nicht reinweiß, ein Akzent", () => {
  const grund = farbe("--g-grund", dunkelAlle), flaeche = farbe("--calm-surface", dunkelAlle), tinte = farbe("--calm-ink", dunkelAlle);
  assert.ok(lum(grund) > 0.005 && Math.max(...grund) >= 0x14, "kein Schwarz");
  assert.ok(lum(flaeche) > lum(grund) && kontrast(flaeche, grund) < 1.5, "Fläche eine Stufe heller, nicht mehr");
  assert.ok(Math.max(...tinte) < 0xf5, "Tinte nicht reinweiß");
  assert.deepEqual(farbe("--calm-primary", dunkelAlle), farbe("--calm-link", dunkelAlle), "ein Akzent: Knopf und Verweis");
  assert.deepEqual(farbe("--g-akzent", dunkelAlle), farbe("--calm-primary", dunkelAlle));
  // Die Navigation bleibt dunkel und gleich.
  assert.deepEqual(farbe("--nordic-nav", dunkelAlle), farbe("--nordic-nav", hellAlle));
  assert.match(quelle("styles.css"), /@media \(prefers-color-scheme: dark\) \{\s*\.shell > \.sidebar \{ box-shadow: inset -1px 0 0 var\(--nordic-nav-glanz\); \}/, "Haarlinie zur Arbeitsfläche");
  // Hell bleibt der freigegebene Stand.
  assert.deepEqual([farbe("--g-grund", hellAlle), farbe("--calm-surface", hellAlle), farbe("--calm-ink", hellAlle)], [[245, 246, 248], [255, 255, 255], [23, 38, 53]]);
});

test("Sonderfälle: Schleier über der Landschaft, Kalenderfarben und Kartenpunkte als Rollen", () => {
  const heute = ohneKommentare(quelle("TodayOverview.css"));
  assert.match(heute, /@media \(prefers-color-scheme: dark\) \{\s*\.today-landscape \{ filter: brightness\(\.5\)/, "die Landschaft ist im Dunkeln gedämpft");
  assert.match(heute, /\.today-landscape \{[^}]*linear-gradient\(90deg, rgba\(var\(--g-grund-rgb\)/, "der Verlauf läuft in den Grund des Modus aus");
  for (const id of ["a", "Privat", "lea@example.org", "google:arbeit"]) {
    const wert = calendarColor(id);
    assert.match(wert, /^var\(--g-kal-farbe-[1-7]\)$/, wert);
    const name = wert.slice(4, -1); assert.ok(name in hellAlle && name in alle["Grundlage.css"].dunkel, name);
  }
  const leaflet = quelle("LeafletPlaces.ts");
  assert.match(leaflet, /className:point\.id===selected\?'kf-ort kf-ort-gewaehlt':'kf-ort'/);
  assert.doesNotMatch(leaflet, /color:'/);
  const karte = ohneKommentare(quelle("WorkspaceMemoryDetails.css"));
  for (const k of ["kf-ort", "kf-ort-gewaehlt", "kf-ort-neu"]) assert.match(karte, new RegExp(`\\.${k} \\{ stroke: var\\(--g-ort`), k);
  assert.match(karte, /@media \(prefers-color-scheme: dark\) \{[\s\S]*\.leaflet-tile-pane \{ filter: brightness/, "Kacheln im Dunkeln gedämpft");
  // Der Hinweis ist im Dunkeln eine erhöhte Fläche, kein heller Balken.
  assert.match(quelle("Grundlage.css"), /\.g-hinweis \{[^}]*background: var\(--g-hinweis-grund\); color: var\(--g-hinweis-tinte\);/);
});
