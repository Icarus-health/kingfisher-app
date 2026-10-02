// Briefing (Fremdprobe, Befunde 20 und 24): deutsch, ohne Tageszeit in der Beschriftung, kein Spieler ohne lokales
// Audio, Datum und Überschrift auf einer lesbaren Fläche. Im Browser prüft scripts/probe_seiten_ui.py dasselbe.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const quelle = (datei) => readFileSync(new URL(`../src/${datei}`, import.meta.url), "utf8");

test("keine englischen Beschriftungen im Briefing, Zurück heißt „Zurück zu Heute“", () => {
  const app = quelle("App.tsx");
  assert.doesNotMatch(app, /MORNING|Morning Briefing|>Dashboard</);
  assert.match(app, /<p>BRIEFING<\/p>/);
  assert.match(app, /<span>Zurück zu Heute<\/span>/);
});

test("ohne lokales Audio kein Spieler", () => {
  const audio = quelle("AudioBriefing.tsx");
  assert.match(audio, /if \(available !== true && \(status === "idle" \|\| status === "unavailable"\)\) return null;/);
});

test("Datum und Überschrift liegen auf einer Fläche über dem Bild", () => {
  const css = quelle("styles.css");
  const regel = css.match(/\.drawer-heading \{[^}]*\}/)[0];
  assert.match(regel, /background: rgba\(var\(--kf-flaeche-rgb-fffefa\),\.88\)/);
  assert.match(regel, /z-index: 3/);
});
