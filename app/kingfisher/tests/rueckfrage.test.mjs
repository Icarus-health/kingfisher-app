// Jede Rückfrage ist ein echter Dialog (Persona-Prüfung, Paket B, B3, 27.10.2026).
// Vorher: „Quelle wirklich entfernen?“ stand als Satz in der Zeile; der Fokus fiel ins Leere, Escape brach nicht ab, und
// der erste Tab landete auf „Entfernen“, das sich nicht zurücknehmen lässt.
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { test, after } from "node:test";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { testCache } from "./testcache.mjs";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { fallenZiel, startSelektor, RUECKFRAGE_ROLLE, RUECKFRAGE_BEDIENBAR } from "../src/grundlage/rueckfrageModell.ts";

const root = fileURLToPath(new URL("..", import.meta.url));
const quelle = name => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");
const server = await createServer({ cacheDir: testCache("rueckfrage"), root, configFile: false, logLevel: "silent",
  server: { middlewareMode: true, watch: null, ws: false, hmr: false }, appType: "custom" });
after(() => server.close());

async function zeichne(props) {
  const { Rueckfrage } = await server.ssrLoadModule("/src/grundlage/Rueckfrage.tsx");
  return renderToStaticMarkup(createElement(Rueckfrage, { onBestaetigen() {}, onAbbrechen() {}, ...props }));
}

test("Fokusfalle: Tab vom letzten Knopf führt zum ersten, Umschalt+Tab vom ersten zum letzten; dazwischen der Browser", () => {
  assert.equal(fallenZiel(1, 2, false), 0, "von der Aktion vorwärts zurück auf Abbrechen");
  assert.equal(fallenZiel(0, 2, true), 1, "von Abbrechen rückwärts auf die Aktion, nicht hinaus");
  assert.equal(fallenZiel(0, 3, false), null);
  assert.equal(fallenZiel(1, 3, true), null);
  assert.equal(fallenZiel(-1, 2, false), 0, "liegt der Fokus außerhalb, kommt er in den Dialog");
  assert.equal(fallenZiel(-1, 2, true), 1);
  assert.equal(fallenZiel(0, 0, false), null);
  assert.match(RUECKFRAGE_BEDIENBAR, /button/);
  assert.match(RUECKFRAGE_BEDIENBAR, /textarea/);
});

test("ein beschrifteter, modaler Alarmdialog: die Frage als Name, der Satz als Beschreibung, Abbrechen zuerst", async () => {
  const html = await zeichne({ frage: "„Probe-Post“ wirklich entfernen?", satz: "Das lässt sich nicht zurücknehmen.", bestaetigen: "Entfernen", rot: true });
  assert.equal(RUECKFRAGE_ROLLE, "alertdialog");
  assert.match(html, /^<dialog [^>]*role="alertdialog"/);
  assert.match(html, /aria-modal="true"/);
  const name = html.match(/aria-labelledby="([^"]+)"/)[1];
  const beschreibung = html.match(/aria-describedby="([^"]+)"/)[1];
  assert.match(html, new RegExp(`<h2 class="g-rueckfrage-frage" id="${name}">„Probe-Post“ wirklich entfernen\\?</h2>`));
  assert.match(html, new RegExp(`<p class="g-rueckfrage-satz" id="${beschreibung}">Das lässt sich nicht zurücknehmen.</p>`));
  const knoepfe = [...html.matchAll(/<button[^>]*>([^<]*)<\/button>/g)].map(m => m[0]);
  assert.equal(knoepfe.length, 2);
  assert.match(knoepfe[0], /data-rueckfrage-abbrechen=""[^>]*>Abbrechen</, "die sichere Wahl steht zuerst");
  assert.match(knoepfe[1], /class="g-knopf-rot"[^>]*>Entfernen</, "was unwiderruflich entfernt, bleibt rot");
  assert.equal(startSelektor("abbrechen"), "[data-rueckfrage-abbrechen]");
  assert.equal(startSelektor("feld"), "[data-rueckfrage-feld]");
});

test("während die Aktion läuft, bleiben beide Knöpfe stehen (aria-disabled statt disabled, sonst verlöre er den Fokus)", async () => {
  const html = await zeichne({ frage: "Ordner trennen?", bestaetigen: "Ordner trennen", arbeitet: true, fehler: "Das hat nicht geklappt." });
  assert.doesNotMatch(html, /<button[^>]* disabled=""/);
  assert.equal([...html.matchAll(/aria-disabled="true"/g)].length, 2);
  assert.match(html, /aria-busy="true"/);
  assert.match(html, /<p class="g-rueckfrage-fehler" role="alert">Das hat nicht geklappt.<\/p>/, "ein Fehler steht im Dialog, nicht dahinter");
  assert.doesNotMatch(html, /aria-describedby/, "ohne Satz keine leere Beschreibung");
});

test("Verhalten im Browser: modal öffnen, Fokus auf die sichere Wahl, Tab bleibt drin, Escape bricht ab, Fokus zurück", () => {
  const code = quelle("grundlage/Rueckfrage.tsx");
  assert.match(code, /el\.showModal\(\)/);
  assert.match(code, /querySelector<HTMLElement>\(startSelektor\(start\)\)[^\n]*\.focus\(\)/);
  assert.match(code, /onCancel=\{e => \{ e\.preventDefault\(\); if \(!arbeitetRef\.current\) abbrechenRef\.current\(\); \}\}/);
  assert.match(code, /if \(e\.key !== "Tab"/);
  assert.match(code, /fallenZiel\(bedienbar\.indexOf\(document\.activeElement as HTMLElement\), bedienbar\.length, e\.shiftKey\)/);
  // Zurück zum Auslöser über die Regel aus Paket Z3: Auslöser, sonst seine Liste (nie ins Leere).
  assert.match(code, /merk\.current = merkeFokus\(ausloeser\(\)\)/);
  assert.match(code, /fokusZurueck\(merk\.current\)/);
  assert.match(code, /const ziel = fokusZiel\(merk, seite\)/);
  assert.match(code, /createPortal\(inhalt, document\.body\)/);
});

// -- Alle Rückfragen ---------------------------------------------------------------------------------------------

function dateien(ordner, aus = []) {
  for (const name of readdirSync(ordner)) {
    const pfad = join(ordner, name);
    if (statSync(pfad).isDirectory()) dateien(pfad, aus); else if (/\.tsx$/.test(name)) aus.push(pfad);
  }
  return aus;
}
const ALLE = dateien(join(root, "src")).map(pfad => [pfad.slice(root.length + 4), readFileSync(pfad, "utf8")]);

/** Jede Stelle, die vor einer Aktion fragt (gefunden am 27.10.2026), und ihre Frage. */
const RUECKFRAGEN = {
  "Einstellungen/KontoZeile.tsx": ["wirklich entfernen?"],
  "Einstellungen/Quellenformulare.tsx": ["wirklich entfernen?"],
  "ProfileSource.tsx": ["Automatisches Sortierergebnis verwerfen?", "Diese Frage nicht mehr verwenden?", "Diese Frage wieder verwenden?", "Quelle ausschließen?", "Quelle wieder zulassen?"],
  "DecisionControls.tsx": ["Entscheidung wirklich zurücknehmen?"],
  "GoalControls.tsx": ["War diese Zielangabe falsch?"],
  "PeopleReview.tsx": ["Zusammenführung aufheben?"],
  "HealthPage.tsx": ["Diese Angabe nicht mehr verwenden?"],
  "IdentityControls.tsx": ["lösen?"],
  "DocumentSources.tsx": ["als Quelle ausschließen?"],
  "DocumentImport.tsx": ["Vorschau verwerfen?"],
  "TranscriptSettings.tsx": ["Ordner trennen?"],
  "ModelRecommendation.tsx": ["laden und einrichten?", "Alle Modelle laden und einrichten?"],
  "ClaimControls.tsx": ["Aussage widerrufen?"],
};

test("jede Rückfrage nutzt den einen Baustein und steht als Frage im Dialog", () => {
  for (const [datei, fragen] of Object.entries(RUECKFRAGEN)) {
    const code = quelle(datei);
    assert.match(code, /import \{[^}]*\bRueckfrage\b[^}]*\} from ["']\.\.?\/grundlage["']/, `${datei} nutzt Rueckfrage`);
    const im = [...code.matchAll(/<Rueckfrage\b[\s\S]*?frage=(?:"([^"]*)"|\{`([^`]*)`\})/g)].map(m => m[1] ?? m[2]);
    for (const frage of fragen) assert.ok(im.some(f => f.endsWith(frage) || f === frage), `${datei}: „${frage}“ als Frage eines Dialogs (${im.join(" | ")})`);
  }
});

test("keine Rückfrage mehr in der Zeile: kein eigener Alarmdialog, keine Bestätigungsgruppe, kein „wirklich“ außerhalb des Dialogs", () => {
  const verboten = /role="alertdialog"|className="(?:source-remove-confirm|goal-rueckfrage|people-review-confirm|health-confirm|transkript-bestaetigung)"|role="group" aria-label="(?:[^"]*(?:entfernen|lösen|ausschließen|widerrufen|verwerfen|Bestätigung|bestätigen|wieder zulassen|Wieder verwenden|Nicht mehr verwenden|schließen))"/;
  for (const [datei, code] of ALLE) {
    if (datei === "grundlage/Rueckfrage.tsx") continue;
    assert.doesNotMatch(code, verboten, `${datei}: eine Rückfrage in der Zeile`);
    for (const zeile of code.split("\n")) {
      if (/\bwirklich [a-zäöü]+\?/i.test(zeile.replace(/frage=\{?[`"][^`"]*[`"]\}?/g, "")) && !/^\s*(\/\/|\*|\/\*)/.test(zeile))
        assert.fail(`${datei}: „wirklich …?“ außerhalb einer Rückfrage: ${zeile.trim().slice(0, 120)}`);
    }
  }
});

test("Gestaltung: ein ruhiges Blatt über allem, rot nur getönt, Fokus sichtbar; hell und dunkel aus Rollen", () => {
  const css = readFileSync(join(root, "src/Grundlage.css"), "utf8");
  assert.match(css, /\.g-rueckfrage \{[^}]*background: var\(--g-flaeche\)/);
  assert.match(css, /\.g-rueckfrage::backdrop \{ background: rgba\(var\(--g-schatten-rgb\),\.32\); \}/);
  assert.match(css, /\.g-knopf-rot \{ background: rgba\(var\(--g-rot-rgb\),\.1\); color: var\(--g-rot\); \}/);
  assert.match(css, /\.g-rueckfrage :is\(button, textarea, input\):focus-visible \{ outline: 2px solid var\(--g-auswahl-kante\)/);
});
