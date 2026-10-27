// Navigation am Handy (Persona-Prüfung, Paket H, H2). Vorher: sieben Symbole ohne Beschriftung in einem Streifen oben,
// der mit der Seite wegrollte; Akten und Personen unter „Gedächtnis → Menschen / Projekte“, und „Projekte“ gab es
// zusätzlich unter Aufgaben (dieselben Projekte, zwei Orte).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { after, test } from "node:test";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import { LEISTE, MEHR, aktivUnterMehr } from "../src/handyLeiste.ts";
import { PROJEKTE_ORT, projekteImGedaechtnis } from "../src/projekteOrt.ts";
import { testCache } from "./testcache.mjs";

const quelle = name => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");
const ohneKommentare = css => css.replace(/\/\*[\s\S]*?\*\//g, "");
const server = await createServer({ cacheDir: testCache("handy-leiste"), root: fileURLToPath(new URL("..", import.meta.url)),
  server: { middlewareMode: true, watch: null, ws: false, hmr: false }, appType: "custom", logLevel: "silent" });
after(() => server.close());

test("höchstens fünf Plätze mit Zeichen und kurzem Wort; alles andere unter „Mehr“, jedes Ziel genau einmal", async () => {
  const { NAV } = await server.ssrLoadModule("/src/ui.ts");
  assert.ok(LEISTE.length + 1 <= 5, "vier Ziele und „Mehr“");
  assert.deepEqual(LEISTE.map(z => z.label), ["Heute", "Gespräche", "Aufgaben", "Kalender"]);
  const alle = [...LEISTE, ...MEHR].map(z => z.label);
  for (const [label] of NAV) assert.equal(alle.filter(l => l === label).length, 1, label);
  assert.equal(alle.filter(l => l === "Einstellungen").length, 1);
  for (const z of [...LEISTE, ...MEHR]) {
    assert.ok(z.label.length <= 13 && !/\s/.test(z.label), `${z.label}: ein kurzes Wort`);
    assert.ok(z.zeichen && z.pfad.startsWith("/"), z.label);
  }
  for (const z of MEHR) assert.equal(z.satz.split(/[.!?](\s|$)/).filter(t => t && t.trim()).length, 1, `${z.label}: ein Satz`);
  assert.match(MEHR.find(z => z.label === "Gedächtnis").satz, /Menschen/, "wo die Akten der Menschen stehen");
  assert.equal(aktivUnterMehr("Nachrichten")?.label, "Nachrichten");
  assert.equal(aktivUnterMehr("Kalender"), null);
});

test("die Leiste: beschriftet, „Mehr“ als Aufklapper mit Rückweg, die aktive Seite angesagt", async () => {
  const { Sidebar } = await server.ssrLoadModule("/src/chrome.tsx");
  const html = renderToStaticMarkup(createElement(Sidebar, { active: "Nachrichten", recentConversation: null }));
  const leiste = html.slice(html.indexOf('class="handy-leiste"'));
  assert.equal((leiste.match(/class="handy-ziel/g) || []).length, 5);
  for (const wort of ["Heute", "Gespräche", "Aufgaben", "Kalender", "Mehr"]) assert.match(leiste, new RegExp(`<span>${wort}</span>`), `${wort} steht sichtbar da`);
  assert.match(leiste, /class="handy-ziel aktiv" aria-expanded="false" aria-controls="handy-mehr">.*Mehr<\/span><span class="visually-hidden">, gerade Nachrichten<\/span>/);
  assert.match(leiste, /<div id="handy-mehr" class="handy-mehr" hidden="">/);
  assert.match(leiste, /class="handy-mehr-ziel aktiv" aria-current="page"/);
  const kalender = renderToStaticMarkup(createElement(Sidebar, { active: "Kalender", recentConversation: null }));
  assert.match(kalender.slice(kalender.indexOf("handy-leiste")), /class="handy-ziel aktiv" aria-current="page"><svg[^]*?<span>Kalender<\/span>/);
  const chrome = quelle("HandyLeiste.tsx");
  assert.match(chrome, /if \(e\.key !== "Escape"\) return;[\s\S]*setOffen\(false\);\s*mehrKnopf\.current\?\.focus\(\);/, "Escape klappt zu, Fokus auf „Mehr“");
  assert.match(chrome, /document\.addEventListener\("pointerdown", daneben, true\);/, "ein Tipp daneben klappt zu");
});

test("fest unten, über der sicheren Kante, verdeckt nichts; breit bleibt die Seitenleiste", () => {
  const css = ohneKommentare(quelle("Seitenbreite.css"));
  const handy = css.slice(css.lastIndexOf(".shell > .sidebar > .handy-leiste { display: none; }"));
  assert.ok(handy.length > 100);
  assert.match(handy, /@media \(max-width: 700px\) \{\s*\.shell \{ padding-bottom: var\(--g-unten\); \}/, "die Seite hat unten Platz");
  assert.match(handy, /\.shell > \.sidebar \{ position: fixed; inset: auto 0 0 0;[^}]*padding: 0 env\(safe-area-inset-right\) env\(safe-area-inset-bottom\) env\(safe-area-inset-left\);/);
  assert.match(handy, /\.shell > \.sidebar > :not\(\.handy-leiste\) \{ display: none; \}/);
  assert.match(handy, /\.handy-ziel \{[^}]*min-width: var\(--g-ziel\); min-height: var\(--g-ziel\);/);
  assert.doesNotMatch(css, /\.nav-item:not\(\.active\) span \{ position: absolute;/, "keine Ziele ohne Namen mehr");
  assert.match(handy, /#root \.workspace-detail \{ bottom: var\(--g-unten\); \}/);
  assert.match(handy, /\.task-vorschlaege-auswahl \{ bottom: calc\(var\(--g-unten\) \+ var\(--g-a3\)\); \}/);
  const grundlage = ohneKommentare(quelle("Grundlage.css"));
  assert.match(grundlage, /:root \{ --g-leiste: 60px; --g-unten: calc\(var\(--g-leiste\) \+ env\(safe-area-inset-bottom\)\); \}/);
  assert.match(grundlage, /body:has\(\.shell > \.sidebar\) \.g-hinweis-ort \{ bottom: calc\(var\(--g-unten\) \+ var\(--g-a2\)\); \}/, "der Hinweis sitzt über der Leiste");
  assert.match(quelle("../index.html"), /viewport-fit=cover/, "ohne das ist safe-area-inset auf dem iPhone 0");
});

test("der Hinweis hat am Handy einen festen Platz über der Leiste; was dort stand, rückt nach oben", () => {
  const hinweis = quelle("grundlage/Hinweis.tsx");
  assert.match(hinweis, /const leiste = schmal \? festeLeiste\(\) : null;/);
  assert.match(hinweis, /if \(verdeckt\(platz\.oben, platz\.unten, 0, window\.innerWidth\) > 0\) window\.scrollBy\(\{ top: platz\.unten - platz\.oben, behavior: "auto" \}\);/);
});

test("Projekte: ein Name, ein Ort (Aufgaben); das Gedächtnis und alte Verweise führen dorthin", () => {
  assert.equal(PROJEKTE_ORT, "/vorhaben?view=projects");
  assert.equal(projekteImGedaechtnis("?tab=projects&q=Verein"), true);
  assert.equal(projekteImGedaechtnis("?tab=people"), false);
  const graph = quelle("MemoryGraph.tsx");
  const filter = graph.slice(graph.indexOf("const FILTERS"), graph.indexOf("const MORE_FILTERS"));
  assert.doesNotMatch(filter, /Projekte/, "kein zweites „Projekte“ im Gedächtnis");
  assert.match(graph, /<a href=\{PROJEKTE_ORT\}>Projekte unter Aufgaben<\/a>/);
  const app = quelle("App.tsx");
  assert.match(app, /if \(path === "\/memory" && projekteImGedaechtnis\(window\.location\.search\)\) \{\s*window\.history\.replaceState\(\{\}, "", PROJEKTE_ORT\);/);
  assert.match(app, /q\.get\("view"\) === "projects" \? "projects"/);
  assert.match(app, />Akte öffnen<\/a>/);
  assert.doesNotMatch(app + quelle("TaskDetail.tsx"), /Im Gedächtnis öffnen|Projekt im Gedächtnis öffnen/);
});
