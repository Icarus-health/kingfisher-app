// Tageslage (Persona-Prüfung, Befund A4): sofort der fertige Teil und der Zwischenstand, dann die volle Fassung.
// Im Browser prüft das scripts/probe_seiten_ui.py nicht; die Bilder im Protokoll A-II zeigen es.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const quelle = (datei) => readFileSync(new URL(`../src/${datei}`, import.meta.url), "utf8");

test("erst die schnelle Fassung, die volle überschreibt sie, nie umgekehrt", () => {
  const lage = quelle("TagesLage.tsx");
  assert.match(lage, /api\.tagBriefing\(false, true\)\.then\(teil => \{ if \(!voll\) setDaten\(alt => alt \?\? teil\); \}\)/);
  assert.match(lage, /void laden\(\)\.then\(\(\) => \{ voll = true; \}\)/);
  assert.match(quelle("api.ts"), /schnell \? "\?schnell=true" : nachladen \? "\?nachladen=true" : ""/);
});

test("vor der ersten Antwort ein Satz statt einer leeren Fläche, danach der Zwischenstand", () => {
  const lage = quelle("TagesLage.tsx");
  assert.match(lage, /if \(!daten\) return <section className="tageslage" aria-label="Das zählt heute" aria-busy="true"><p className="tageslage-hinweis" role="status">Kingfisher stellt die Tageslage zusammen/);
  assert.match(lage, /daten\.zwischenstand \? <p className="tageslage-hinweis tageslage-zwischenstand" role="status">\{daten\.zwischenstand\}<\/p> : null/);
});
