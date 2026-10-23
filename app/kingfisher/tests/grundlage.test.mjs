// Gestaltungsgrundlage vom 23.10.2026 (docs/16-gestaltung.md „Grundlage vom 23.10.2026“, Grundlage.css,
// src/grundlage/). Geprüft wird: Ladereihenfolge, Landschaft nur noch im Kopf von Heute, die Werte, die globale
// Abbildung der vorhandenen Klassen und die Bausteine selbst (Darstellung und Tastatur der Segmente).
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { after, test } from "node:test";
import { fileURLToPath } from "node:url";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement as h } from "react";
import { createServer } from "vite";
import { segmentImFokus, segmentNachTaste } from "../src/grundlage/segmentTasten.ts";

const SRC = new URL("../src/", import.meta.url);
const quelle = (datei) => readFileSync(new URL(datei, SRC), "utf8");
const ohneKommentare = (css) => css.replace(/\/\*[\s\S]*?\*\//g, "");
function dateien(endung, ordner = SRC, praefix = "") {
  return readdirSync(ordner, { withFileTypes: true }).flatMap(e => e.isDirectory()
    ? dateien(endung, new URL(`${e.name}/`, ordner), `${praefix}${e.name}/`)
    : e.name.endsWith(endung) ? [`${praefix}${e.name}`] : []);
}
/** Der Selektor der Regel, in der die Stelle `index` steht. */
function selektorBei(css, index) {
  const auf = css.lastIndexOf("{", index);
  const davor = Math.max(css.lastIndexOf("}", auf), css.lastIndexOf(";", auf));
  return css.slice(davor + 1, auf).trim();
}
const grundlage = ohneKommentare(quelle("Grundlage.css"));

test("Grundlage.css wird direkt vor Seitenbreite.css geladen, die zuletzt bleibt", () => {
  const importe = [...quelle("main.tsx").matchAll(/import "\.\/([^"]+\.css)";/g)].map(m => m[1]);
  assert.deepEqual(importe.slice(-2), ["Grundlage.css", "Seitenbreite.css"], importe.join(", "));
});

test("das Landschaftsbild steht nur noch im Kopf von Heute, nicht hinter Seiten, Köpfen oder der Seitenleiste", () => {
  for (const datei of dateien(".css")) {
    const css = ohneKommentare(quelle(datei));
    for (const m of css.matchAll(/url\([^)]*(landscape|panorama)[^)]*\)/g)) {
      const selektor = selektorBei(css, m.index);
      assert.match(selektor, /today|hero/, `${datei}: Landschaft in „${selektor}“`);
      assert.doesNotMatch(selektor, /sidebar|heading|memory-filter|:not\(:has\(\.today-page\)\)/, `${datei}: „${selektor}“`);
    }
  }
  assert.doesNotMatch(ohneKommentare(quelle("CalmUI.css")), /\.shell:not\(:has\(\.today-page\)\)::before/);
  assert.doesNotMatch(ohneKommentare(quelle("styles.css")), /\.sidebar::before\s*\{[^}]*url\(/);
  // Auch in Komponenten kein Landschaftsbild außerhalb von Heute.
  for (const datei of dateien(".tsx").filter(d => !["App.tsx", "TodayOverview.tsx"].includes(d))) {
    assert.doesNotMatch(quelle(datei), /landscape|panorama/, datei);
  }
});

test("die Werte: Systemschrift, Typo-Skala, Abstände, Radien, Haarschatten und Haarlinie", () => {
  const wert = (name) => grundlage.match(new RegExp(`--g-${name}:\\s*([^;]+);`))?.[1].trim();
  assert.equal(wert("schrift"), '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "Segoe UI", sans-serif');
  assert.equal(wert("titel-gross"), "700 34px/1.15 var(--g-schrift)");
  assert.equal(wert("titel-gross-schmal"), "28px");
  assert.equal(wert("titel"), "650 22px/1.25 var(--g-schrift)");
  assert.equal(wert("ueberschrift"), "600 17px/1.35 var(--g-schrift)");
  assert.equal(wert("text"), "400 16px/1.5 var(--g-schrift)");
  assert.equal(wert("neben"), "400 14px/1.45 var(--g-schrift)");
  assert.equal(wert("fussnote"), "400 13px/1.4 var(--g-schrift)");
  assert.deepEqual([1, 2, 3, 4, 5, 6, 7, 8].map(i => wert(`a${i}`)), ["4px", "8px", "12px", "16px", "24px", "32px", "48px", "64px"]);
  assert.deepEqual(["radius-flaeche", "radius-bedien", "radius-pille"].map(wert), ["14px", "10px", "999px"]);
  assert.equal(wert("schatten"), "0 0 0 1px rgba(23,38,53,.05), 0 1px 2px rgba(23,38,53,.04)");
  assert.equal(wert("linie"), "rgba(23,38,53,.08)");
  assert.equal(wert("grund"), "#f5f6f8");
  assert.deepEqual([wert("ziel"), wert("ziel-kompakt"), wert("zeile")], ["44px", "36px", "52px"]);
  // Keine neue Palette: Tinte, Akzent und Verweis kommen aus CalmUI.css.
  for (const [name, calm] of [["tinte", "ink"], ["leise", "muted"], ["akzent", "primary"], ["verweis", "link"]]) {
    assert.match(wert(name), new RegExp(`^var\\(--calm-${calm}\\b`), name);
  }
  // Eine Familie überall; der große Titel wird schmal kleiner.
  assert.match(grundlage, /#root :not\([^)]*\) \{ font-family: var\(--g-schrift\) !important; \}/);
  assert.match(grundlage, /@media \(max-width: 700px\) \{[^}]*\.g-seitenkopf-titel, \.g-titel-gross \{ font-size: var\(--g-titel-gross-schmal\); \}/);
});

test("global: Köpfe als großer Titel, Reiterleisten als Segmente, Aufklapper mit drehendem Pfeil, Felder 44 px", () => {
  const kopf = /#root main :is\(\.tasks-heading, \.settings-heading, \.inbox-heading, \.history-heading, \.profile-heading, \.memory-heading-row\) h1/;
  assert.match(grundlage, new RegExp(kopf.source + String.raw`[^{]*\{[^}]*font: var\(--g-titel-gross\)`));
  for (const leiste of [".task-tabs", ".profile-tabs", ".view-switch", ".memory-area-tabs", ".inbox-filter"]) {
    assert.ok(grundlage.includes(leiste), leiste);
  }
  const segment = grundlage.match(/#root main :is\(\.task-tabs[^{]*\{([^}]*)\}/)[1];
  assert.match(segment, /flex-wrap: nowrap;/);
  assert.match(segment, /overflow-x: auto;/);
  assert.match(segment, /border-radius: var\(--g-radius-pille\);/);
  // Der eigene Pfeil statt ▶: das Dreieck des Browsers ist aus, der Pfeil dreht sich beim Öffnen.
  assert.match(grundlage, /#root summary \{ list-style: none;/);
  assert.match(grundlage, /#root summary::-webkit-details-marker \{ display: none; \}/);
  assert.match(grundlage, /#root details > summary::before \{[^}]*transform: rotate\(-45deg\);[^}]*transition: transform/);
  assert.match(grundlage, /#root details\[open\] > summary::before \{[^}]*rotate\(45deg\)/);
  assert.match(grundlage, /:not\(\.history-search input\) \{\s*min-height: var\(--g-ziel\);/);
  assert.match(grundlage, /border-radius: var\(--g-radius-bedien\); background-color/);
  // Knöpfe: drei Stufen, Höhe 44; Entfernen bleibt rot.
  assert.match(grundlage, /\.shell :is\(\.primary-action, \.tasks-add[^{]*\{[^}]*min-height: var\(--g-ziel\);[^}]*background: var\(--g-akzent\)/);
  assert.match(grundlage, /\.shell :is\(\.secondary-action[^{]*\{[^}]*min-height: var\(--g-ziel\);[^}]*background: var\(--g-getoent\)/);
  assert.match(grundlage, /decision-confirm[^{]*\{[^}]*color: var\(--g-rot\)/);
  // Bewegung leise und abschaltbar.
  assert.match(grundlage, /--g-bewegung: 200ms/);
  assert.match(grundlage, /@media \(prefers-reduced-motion: reduce\) \{[^}]*#root details > summary::before \{ transition: none; \}/);
});

test("Segmente: Pfeile, Pos1 und Ende wählen, überspringen Abgeschaltetes und laufen am Ende herum", () => {
  const frei = [false, false, false, false];
  assert.equal(segmentNachTaste("ArrowRight", 0, frei), 1);
  assert.equal(segmentNachTaste("ArrowDown", 1, frei), 2);
  assert.equal(segmentNachTaste("ArrowRight", 3, frei), 0, "am Ende geht es vorne weiter");
  assert.equal(segmentNachTaste("ArrowLeft", 0, frei), 3);
  assert.equal(segmentNachTaste("ArrowUp", 2, frei), 1);
  assert.equal(segmentNachTaste("Home", 2, frei), 0);
  assert.equal(segmentNachTaste("End", 0, frei), 3);
  assert.equal(segmentNachTaste("Home", 0, frei), null, "schon da");
  assert.equal(segmentNachTaste("Enter", 0, frei), null);
  assert.equal(segmentNachTaste("a", 0, frei), null);
  const teils = [true, false, true, false];
  assert.equal(segmentNachTaste("ArrowRight", 1, teils), 3);
  assert.equal(segmentNachTaste("ArrowRight", 3, teils), 1);
  assert.equal(segmentNachTaste("Home", 3, teils), 1);
  assert.equal(segmentNachTaste("End", 1, teils), 3);
  assert.equal(segmentNachTaste("ArrowRight", 1, [true, false, true]), null, "nur eine wählbare Stelle");
  assert.equal(segmentNachTaste("ArrowRight", 0, [true, true]), null);
  assert.equal(segmentNachTaste("ArrowRight", -1, frei), 0, "ohne Auswahl beginnt es vorne");
  assert.equal(segmentNachTaste("ArrowLeft", -1, frei), 3);
  assert.equal(segmentImFokus(2, frei), 2);
  assert.equal(segmentImFokus(-1, teils), 1, "ohne Auswahl ist die erste wählbare Stelle per Tab erreichbar");
  assert.equal(segmentImFokus(0, teils), 1);
});

const server = await createServer({
  root: fileURLToPath(new URL("..", import.meta.url)), configFile: false, cacheDir: `/tmp/kingfisher-grundlage-tests-${process.pid}`,
  server: { middlewareMode: true, watch: null, ws: false, hmr: false }, appType: "custom", logLevel: "error",
});
after(() => server.close());
const g = await server.ssrLoadModule("/src/grundlage/index.ts");
const html = (el) => renderToStaticMarkup(el);
function knoten(n, p, aus = []) {
  if (!n || typeof n !== "object") return aus;
  if (p(n)) aus.push(n);
  [n.props?.children].flat(20).forEach(c => knoten(c, p, aus));
  return aus;
}

test("Seitenkopf: ein großer Titel, höchstens eine Zeile darunter, Aktionen daneben, klebende Leiste nur für Vorleser stumm", () => {
  const voll = html(h(g.Seitenkopf, { titel: "Aufgaben", zeile: "6 offen", aktionen: h("button", { className: "g-knopf" }, "Aufgabe") }));
  assert.equal(voll.match(/<h1/g).length, 1);
  assert.match(voll, /<h1 class="g-seitenkopf-titel">Aufgaben<\/h1><p class="g-seitenkopf-zeile">6 offen<\/p>/);
  assert.match(voll, /<div class="g-seitenkopf-aktionen"><button class="g-knopf">Aufgabe<\/button><\/div>/);
  assert.match(voll, /<div class="g-kopfleiste" data-sichtbar="false" aria-hidden="true">/);
  const knapp = html(h(g.Seitenkopf, { titel: "Kalender" }));
  assert.doesNotMatch(knapp, /g-seitenkopf-zeile|g-seitenkopf-aktionen/);
});

test("Gruppe: Überschrift klein über der Fläche, Fußnote darunter, Fläche benannt", () => {
  const voll = html(h(g.Gruppe, { titel: "Zugänge", fussnote: "Es verlässt nichts den Rechner." }, h(g.Zeile, { titel: "Postfach" })));
  assert.match(voll, /^<section class="g-gruppe" aria-labelledby="([^"]+)"><div class="g-gruppe-kopf"><h2 class="g-gruppe-titel" id="\1">Zugänge<\/h2><\/div><div class="g-flaeche">/);
  assert.match(voll, /<p class="g-gruppe-fussnote">Es verlässt nichts den Rechner.<\/p><\/section>$/);
  const frei = html(h(g.Gruppe, { frei: true }, "Text"));
  assert.equal(frei, '<section class="g-gruppe"><div class="g-flaeche g-flaeche-frei">Text</div></section>');
});

test("Zeile: die ganze Zeile ist Knopf oder Verweis; statisch nur mit Zusatz; Pfeil bei Verweisen", () => {
  const knopf = html(h(g.Zeile, { titel: "Silke Vogt", neben: "Akademie Taunus", wert: "18.9.", onClick() {} }));
  assert.match(knopf, /^<button type="button" class="g-zeile"><span class="g-zeile-text"><span class="g-zeile-titel">Silke Vogt<\/span><span class="g-zeile-neben">Akademie Taunus<\/span><\/span><span class="g-zeile-wert">18.9.<\/span><\/button>$/);
  const verweis = html(h(g.Zeile, { titel: "Kalender", href: "/calendar", aktiv: true, symbol: "K" }));
  assert.match(verweis, /^<a class="g-zeile" href="\/calendar" aria-current="page"><span class="g-zeile-symbol" aria-hidden="true">K<\/span>.*<span class="g-zeile-pfeil" aria-hidden="true"><\/span><\/a>$/);
  const aus = html(h(g.Zeile, { titel: "Weg", onClick() {}, deaktiviert: true, pfeil: true }));
  assert.match(aus, /disabled=""/);
  assert.match(aus, /g-zeile-pfeil/);
  const statisch = html(h(g.Zeile, { titel: "Mitteilungen", zusatz: h("input", { type: "checkbox" }) }));
  assert.match(statisch, /^<div class="g-zeile">.*<span class="g-zeile-zusatz"><input type="checkbox"\/><\/span><\/div>$/);
  assert.doesNotMatch(statisch, /<button|<a /);
  assert.doesNotMatch(html(h(g.Zeile, { titel: "Ohne Wert", wert: "" })), /g-zeile-wert/);
});

test("Segmente: eine Auswahl, nur sie per Tab erreichbar, Zahlen nur über null, Tasten wählen und fokussieren", () => {
  const optionen = [{ wert: "mein", titel: "Meine", zahl: 6 }, { wert: "warte", titel: "Warte auf andere", zahl: 0 },
    { wert: "pruef", titel: "Zur Prüfung", deaktiviert: true }, { wert: "fertig", titel: "Erledigt" }];
  let gewaehlt = null;
  const props = { optionen, wert: "warte", onWahl: w => { gewaehlt = w; }, label: "Aufgaben" };
  const markup = html(h(g.Segmente, props));
  assert.match(markup, /^<div role="tablist" aria-label="Aufgaben" aria-orientation="horizontal" class="g-segmente">/);
  assert.equal(markup.match(/aria-selected="true"/g).length, 1);
  assert.equal(markup.match(/tabindex="0"/g).length, 1);
  assert.match(markup, /aria-selected="true" tabindex="0"[^>]*><span>Warte auf andere<\/span><\/button>/, "keine Null");
  assert.match(markup, /<span>Meine<\/span><span class="g-segment-zahl">6<\/span>/);
  assert.match(html(h(g.Segmente, { ...props, kompakt: true })), /class="g-segmente g-kompakt"/);

  // Tastatur: ohne Browser über das Element selbst.
  const baum = g.Segmente(props);
  const knoepfe = optionen.map(() => ({ fokussiert: false, focus() { this.fokussiert = true; }, scrollIntoView() {} }));
  let verhindert = false;
  const ereignis = (key, ziel) => ({ key, target: knoepfe[ziel], preventDefault() { verhindert = true; },
    currentTarget: { querySelectorAll: () => knoepfe } });
  baum.props.onKeyDown(ereignis("ArrowRight", 1));
  assert.equal(gewaehlt, "fertig", "das abgeschaltete Segment wird übersprungen");
  assert.ok(knoepfe[3].fokussiert && verhindert);
  baum.props.onKeyDown(ereignis("Home", 3));
  assert.equal(gewaehlt, "mein");
  gewaehlt = null; verhindert = false;
  baum.props.onKeyDown(ereignis("Tab", 1));
  assert.equal(gewaehlt, null);
  assert.equal(verhindert, false, "Tab bleibt beim Browser");
  // Klick wählt.
  const buttons = knoten(baum, n => n.type === "button");
  buttons[3].props.onClick({ currentTarget: {} });
  assert.equal(gewaehlt, "fertig");
});

test("Leer: ein Zeichen, ein Satz, höchstens ein Knopf", () => {
  const voll = html(h(g.Leer, { satz: "Nichts wartet auf dich.", zeichen: "check", aktion: h("button", { className: "g-knopf" }, "Aufgabe") }));
  assert.match(voll, /^<div class="g-leer"><span class="g-leer-zeichen" aria-hidden="true"><svg class="interface-icon"/);
  assert.match(voll, /<p class="g-leer-satz">Nichts wartet auf dich.<\/p><div class="g-leer-aktion"><button class="g-knopf">Aufgabe<\/button><\/div><\/div>$/);
  assert.equal(html(h(g.Leer, { satz: "Keine Termine." })), '<div class="g-leer"><p class="g-leer-satz">Keine Termine.</p></div>');
});

test("Aufklapper: details mit Titel und leiser Angabe; der Pfeil kommt aus der globalen Regel, kein ▶ im Text", () => {
  const zu = html(h(g.Aufklapper, { titel: "Verlauf", neben: "8" }, "Inhalt"));
  assert.equal(zu, '<details class="g-aufklapper"><summary><span class="g-aufklapper-titel">Verlauf</span><span class="g-aufklapper-neben">8</span></summary><div class="g-aufklapper-inhalt">Inhalt</div></details>');
  assert.match(html(h(g.Aufklapper, { titel: "Offen", offen: true }, "x")), /^<details class="g-aufklapper" open="">/);
  let offen = null;
  const baum = g.Aufklapper({ titel: "T", onToggle: o => { offen = o; }, children: "x" });
  baum.props.onToggle({ currentTarget: { open: true } });
  assert.equal(offen, true);
  for (const datei of dateien(".tsx").filter(d => d.startsWith("grundlage/"))) assert.doesNotMatch(quelle(datei), /▶|▸|▾/, datei);
});

test("jede Baustein-Klasse hat ihre Regel in Grundlage.css, und die Bausteine laden keine eigenen Stile", () => {
  const klassen = new Set();
  for (const datei of dateien(".tsx").filter(d => d.startsWith("grundlage/"))) {
    const text = quelle(datei);
    assert.doesNotMatch(text, /import ["'][^"']+\.css["']/, datei);
    for (const m of text.matchAll(/["'\s](g-[a-z-]+)/g)) klassen.add(m[1]);
  }
  assert.ok(klassen.size >= 20, [...klassen].join(", "));
  for (const k of klassen) assert.match(grundlage, new RegExp(`\\.${k}(?![a-z-])`), k);
  for (const k of ["g-knopf", "g-knopf-getoent", "g-knopf-schlicht", "g-kompakt"]) assert.match(grundlage, new RegExp(`\\.${k}\\b`), k);
});
