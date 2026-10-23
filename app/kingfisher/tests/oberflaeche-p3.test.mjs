// Flächenpaket P3 (Gedächtnis, Akte, Prüfen, Welt) nach der Grundlage vom 23.10.2026: Segmente statt Reiterleisten,
// Zeilen mit Bild oder Zeichen statt Karten, die Akte als Gruppen ohne dunkle Plakette und ohne Chips, höchstens ein
// gefüllter Knopf, keine Überzeilen und keine Einleitungsprosa. Quelltext- und Rendertests; synthetische Daten.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { after, test } from "node:test";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { initials } from "../src/WorkspaceMemoryModel.ts";

const quelle = (datei) => readFileSync(new URL(`../src/${datei}`, import.meta.url), "utf8");
const server = await createServer({cacheDir: `/private/tmp/kf-p3-${process.pid}`, root: fileURLToPath(new URL("..", import.meta.url)),
  server: {middlewareMode: true, watch: null, ws: false, hmr: false}, appType: "custom"});
after(() => server.close());

test("P3: Gedächtnis, Bereiche und Profile wählen ihre Ansicht mit dem Baustein Segmente", () => {
  const graph = quelle("MemoryGraph.tsx");
  assert.match(graph, /<Seitenkopf titel="Gedächtnis"/);
  assert.match(graph, /<Segmente label="Gedächtnisbereich"/);
  assert.match(graph, /<Segmente kompakt className="memory-person-filter"/);
  assert.doesNotMatch(graph, /FILTERS\.map\(\(item\) => \(\s*<button/, "keine eigene Knopfleiste mehr");
  assert.match(quelle("MemoryAreas.tsx"), /<Segmente kompakt className="memory-area-tabs"/);
  const profil = quelle("MemoryProfile.tsx");
  assert.equal((profil.match(/<Segmente className="profile-segmente"/g) ?? []).length, 2, "Person und Projekt");
  assert.doesNotMatch(profil, /className="profile-tabs"/);
});

test("P3: Listen sind Zeilen mit Bild oder Zeichen, ohne Überzeile, Hilfe-Aufklapper und „Akte öffnen →“", () => {
  for (const datei of ["SachenListe.tsx", "MemoryDirectory.tsx"]) {
    const text = quelle(datei);
    assert.match(text, /className="g-zeile gd-zeile"/, datei);
    assert.match(text, /className="g-zeile-pfeil"/, datei);
    assert.doesNotMatch(text, /Über diese Akten|eyebrow|directory-open/, datei);
  }
  assert.match(quelle("SachenListe.tsx"), /art === "ort" \|\| art === "thema" \? <span className="g-zeile-symbol gd-zeichen"/);
});

test("P3: eine Zeile im Verzeichnis ist ein Knopf mit Bild, Name, Nebenzeile und Pfeil", async () => {
  const {MemoryDirectory} = await server.ssrLoadModule("/src/MemoryDirectory.tsx");
  const nodes = [{id: "person:a", kind: "person", label: "Anna Probe <anna@example.invalid>", attributes: {}}];
  const html = renderToStaticMarkup(createElement(MemoryDirectory, {nodes, title: "Menschen", onOpen() {}}));
  assert.match(html, /<button type="button" class="g-zeile gd-zeile" aria-label="Akte öffnen: Anna Probe &lt;anna@example.invalid&gt;">/);
  assert.match(html, /class="memory-avatar"[^>]*>AP</);
  assert.match(html, /<span class="g-zeile-titel">Anna Probe<\/span><span class="g-zeile-neben">anna@example.invalid<\/span>/);
  assert.doesNotMatch(html, /Akte öffnen <span/);
  assert.doesNotMatch(html, /<h1/);
});

test("P3: Initialen überspringen Klammern und Zeichen", () => {
  assert.equal(initials("Rüsselsheim (Produktionsküche)"), "RP");
  assert.equal(initials("Lea Sommer <lea@example.test>"), "LS");
});

test("P3: die Akte ist eine Folge von Gruppen; „Braucht dich“ ohne dunkle Plakette, Zusammenhänge ohne Chips", () => {
  const akte = quelle("AkteAbschnitte.tsx");
  const css = quelle("AkteAbschnitte.css");
  assert.match(akte, /className=\{`mappe-teil akte-teil g-gruppe/);
  assert.match(akte, /<section className="akte-braucht g-gruppe" aria-label="Braucht dich">/);
  assert.match(akte, /\{gesamt > 1 \? <span className="akte-zahl">\{gesamt\}<\/span> : null\}/);
  assert.match(css, /#root \.akte \.akte-zahl \{[^}]*background: none;/, "die Zahl steht leise neben der Überschrift");
  assert.doesNotMatch(css, /\.akte-zahl \{[^}]*background: var\(--calm-primary\)/);
  assert.doesNotMatch(akte, /akte-gewicht/, "keine Striche unter den Zusammenhängen");
  assert.match(akte, /<MemoryEntityLink className="g-zeile gd-zeile"/);
  // Kopf: Bild, Name, eine Zeile; die Herkunft steht als Fußnote am Ende.
  assert.match(akte, /<div className="akte-kopf-bild">/);
  assert.match(akte, /<footer className="akte-fuss">\{herkunftHinweis\}<\/footer>/);
});

test("P3: höchstens ein gefüllter Knopf; Entscheidungen in Akte, Kreis und Befunden sind getönt", () => {
  const akte = quelle("AkteAbschnitte.tsx");
  assert.equal((akte.match(/className="[^"]*\bg-knopf\b(?!-)[^"]*"/g) ?? []).length, 1, "nur „Akte anlegen“");
  assert.doesNotMatch(akte, /primary-action/);
  const kreis = quelle("KreisKarten.tsx");
  const karten = kreis.slice(0, kreis.indexOf("export function KreisStandAnzeige"));
  assert.doesNotMatch(karten, /primary-action/, "Kreis und Art wählen wie Segmente");
  for (const datei of ["WiederkehrendKarte.tsx", "BefundeAnsicht.tsx", "KnowledgeQuestions.tsx"]) assert.doesNotMatch(quelle(datei), /primary-action/, datei);
});

test("P3: Unteransichten ohne Überzeile, Prüfen und Welt ohne Einleitungsprosa", () => {
  for (const datei of ["SelfModelSupportReview.tsx", "MemoryStatus.tsx", "MemoryAreas.tsx", "MemorySearch.tsx", "WorldPage.tsx", "ReviewPage.tsx"]) {
    assert.doesNotMatch(quelle(datei), /className="eyebrow"/, datei);
  }
  const welt = quelle("WorldPage.tsx");
  assert.match(welt, /<Seitenkopf titel="Öffentliches Wissen"/);
  assert.doesNotMatch(welt, /Verwalte die Seiten|development-links/);
  const pruefen = quelle("ReviewPage.tsx");
  assert.match(pruefen, /<Seitenkopf titel="Prüfen und entscheiden" \/>/);
  assert.equal((pruefen.match(/<Zeile href=/g) ?? []).length, 3, "die seltenen Prüfwege als ganze Zeilen");
  assert.doesNotMatch(quelle("MemoryAreas.tsx"), /Über die Zuordnung|Quellenstand|Ansicht aktualisieren/);
});

test("P3: die eigenen Stile nehmen nur Werte der Grundlage, keine eigenen Hexfarben", () => {
  for (const datei of ["Gedaechtnis.css"]) assert.doesNotMatch(quelle(datei), /#[0-9a-fA-F]{3,8}\b/, datei);
  const akte = quelle("AkteAbschnitte.css");
  const oben = akte.slice(0, akte.indexOf("/* ── Der Zeitstrahl"));
  assert.doesNotMatch(oben, /#[0-9a-fA-F]{3,8}\b/);
});
