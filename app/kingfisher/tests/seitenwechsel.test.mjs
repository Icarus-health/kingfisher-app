// Nach dem Seitenwechsel weiß man, wo man ist (Persona-Prüfung, Paket B, B2, 27.10.2026).
// Vorher: Jede Seite hieß „Kingfisher“, nach jedem Wechsel lag der Fokus auf body, und es gab kein „Zum Inhalt springen“.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { MARKE, fokusVerloren, seiteGewechselt, seitenTitel } from "../src/grundlage/seitenwechselModell.ts";

const quelle = name => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");
const ohneKommentare = css => css.replace(/\/\*[\s\S]*?\*\//g, "");

test("jede Seite trägt ihren Namen im Fenstertitel, ein einzelner Gegenstand dazu seinen", () => {
  assert.equal(seitenTitel("/today"), "Heute – Kingfisher");
  assert.equal(seitenTitel("/vorhaben"), "Aufgaben – Kingfisher");
  assert.equal(seitenTitel("/memory"), "Gedächtnis – Kingfisher");
  assert.equal(seitenTitel("/nachrichten", "Automatische Antwort"), "Nachrichten – Kingfisher", "die Liste heißt nach dem Bereich, nicht nach der gewählten Mail");
  assert.equal(seitenTitel("/calendar"), "Kalender – Kingfisher");
  assert.equal(seitenTitel("/settings"), "Einstellungen – Kingfisher");
  assert.equal(seitenTitel("/conversations", "Was beschäftigt dich?"), "Gespräche – Kingfisher");
  assert.equal(seitenTitel("/conversations/c-1", "Wurde die Frist geändert"), "Wurde die Frist geändert – Gespräche – Kingfisher");
  assert.equal(seitenTitel("/memory/people/Alex", "Alex  Winter\n"), "Alex Winter – Gedächtnis – Kingfisher");
  assert.equal(seitenTitel("/conversations/c-1", null), "Gespräche – Kingfisher", "ohne Überschrift (noch geladen) der Bereich");
  assert.ok(seitenTitel("/conversations/c-1", "x".repeat(200)).length < 100, "ein langer Name wird gekürzt");
});

test("keine Seite der App heißt nur „Kingfisher“", () => {
  const app = quelle("App.tsx");
  const pfade = [...app.matchAll(/path === ["'](\/[^"']*)["']/g)].map(m => m[1]);
  const muster = [...app.matchAll(/path\.match\(\/\^((?:\\\/[a-z]+)+)\\\/\(\[\^\/\]\+\)\$\/\)/g)].map(m => m[1].replaceAll("\\/", "/") + "/beispiel");
  assert.ok(pfade.length >= 10 && muster.length >= 5, `${pfade.length} Pfade, ${muster.length} Muster`);
  for (const pfad of [...pfade, ...muster]) assert.notEqual(seitenTitel(pfad, "Name"), MARKE, pfad);
});

test("Fokus: nur wenn er beim Wechsel verloren ging (body, entfernt, die ganze Seite), sonst bleibt er", () => {
  const body = { isConnected: true }, seite = { isConnected: true };
  assert.equal(fokusVerloren(null, body, seite), true);
  assert.equal(fokusVerloren(body, body, seite), true);
  assert.equal(fokusVerloren({ isConnected: false }, body, seite), true, "der Knopf der alten Seite ist weg");
  assert.equal(fokusVerloren(seite, body, seite), true, "die Seite selbst ist nur ein Ersatz");
  assert.equal(fokusVerloren({ isConnected: true }, body, seite), false, "das Eingabefeld, das die neue Seite fokussiert hat, bleibt");
  assert.equal(seiteGewechselt("/vorhaben", "/calendar"), true);
  assert.equal(seiteGewechselt("/vorhaben", "/vorhaben"), false, "Ansicht und Filter wechseln die Seite nicht");
  assert.equal(seiteGewechselt(null, "/today"), false, "das erste Laden ist kein Wechsel");
});

test("die Anzeige: Titel nach jedem Wechsel und jeder neuen Überschrift, Fokus auf die Hauptüberschrift", () => {
  const code = quelle("grundlage/Seitenwechsel.tsx");
  assert.match(code, /window\.addEventListener\("popstate", wechsel\)/);
  assert.match(code, /document\.title = neu/);
  assert.match(code, /new MutationObserver\(titelBald\)/);
  assert.match(code, /if \(!fokusVerloren\(document\.activeElement, document\.body, document\.querySelector\("main"\)\)\) return;/);
  assert.match(code, /if \(h\) \{ fokussieren\(h\); return; \}/);
  assert.match(code, /ziel\.setAttribute\("tabindex", "-1"\)/, "die Überschrift wird kein Tab-Halt");
  assert.match(code, /querySelectorAll<HTMLElement>\("main h1"\)/);
});

test("„Zum Inhalt springen“ ist der erste Tab-Halt, sichtbar beim Fokus, und führt zur Hauptüberschrift", () => {
  const main = quelle("main.tsx");
  assert.ok(main.indexOf("<Sprunglink />") > 0 && main.indexOf("<Sprunglink />") < main.indexOf("<App />"), "vor der App");
  assert.match(main, /<Seitenwechsel \/>/);
  const code = quelle("grundlage/Seitenwechsel.tsx");
  assert.match(code, /<a className="g-sprunglink" href="#inhalt" onClick=\{springen\}>Zum Inhalt springen<\/a>/);
  assert.match(code, /const ziel = hauptueberschrift\(\) \?\? document\.querySelector<HTMLElement>\("main"\);/);
  const css = ohneKommentare(quelle("Grundlage.css"));
  assert.match(css, /\.g-sprunglink \{[^}]*position: fixed;[^}]*transform: translateY\(calc\(-100% - var\(--g-a5\)\)\);/);
  assert.match(css, /\.g-sprunglink:focus \{ transform: none; outline: 2px solid var\(--g-auswahl-kante\)/);
});

test("beim Laden setzt nichts den Ausgangspunkt für Tab hinter die Navigation (kein scrollIntoView ohne Fokus)", () => {
  const app = quelle("App.tsx");
  assert.doesNotMatch(app, /\[aria-selected="true"\]'\)\?\.scrollIntoView/, "die Aufgabenseite rollte das Segment mit scrollIntoView in den Blick");
  const segmente = quelle("grundlage/Segmente.tsx");
  assert.match(segmente, /export function segmentInsBild\(leiste: HTMLElement \| null\)/);
  assert.match(segmente, /leiste\.scrollLeft = links/);
});
