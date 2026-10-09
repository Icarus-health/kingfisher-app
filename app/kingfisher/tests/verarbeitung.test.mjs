// Gedächtnis → Verarbeitung & Verlauf in Alltagssprache (Fremdprobe 2, Befund 16).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { FUNDE_SATZ, pruefSatz, sortiertGerade, sortierStand, sortierWirkung } from "../src/verarbeitung.ts";

test("läuft das Sortieren, steht kein „wenn du es einschaltest“ und kein Modellname da", () => {
  const an = { state: "active", pending: 3, cloud_modell: null };
  assert.match(sortierStand(an), /^An: /);
  assert.doesNotMatch(sortierWirkung(an), /einschaltest|aktivierst/);
  assert.match(sortierWirkung(an), /3 Quellen warten noch darauf\.$/);
  assert.doesNotMatch(sortierStand(an) + sortierWirkung(an), /qwen|Modell[^e]/);
  const aus = { state: "paused", pending: 1 };
  assert.match(sortierStand(aus), /^Aus: /);
  assert.match(sortierWirkung(aus), /^Wenn du es einschaltest/);
  assert.match(sortierWirkung(aus), /1 Quelle wartet noch darauf\.$/);
  for (const state of ["model_missing", "wrong_model", "local_model_unavailable", "cloud_ueber_ollama"]) {
    assert.match(sortierStand({ state }), /^Pausiert: /, state);
    assert.doesNotMatch(sortierStand({ state }), /Ollama|lokal|Hintergrundprüfung/, state);
  }
});

test("statt der Kacheln ein Satz zur Prüfung, mit „du musst nichts tun“ bei Fehlschlägen", () => {
  assert.equal(pruefSatz({ completed: 0, pending: 0, running: 0, partial: 0, failed: 0, excluded: 0 }), "Noch nichts zu prüfen.");
  assert.equal(pruefSatz({ completed: 1, pending: 1, running: 0, partial: 1, failed: 2, excluded: 0 }),
    "1 Quelle ist fertig durchgesehen, 1 wartet noch und 1 ist erst zum Teil durchgesehen. Bei 2 Quellen hat es nicht geklappt; du musst nichts tun, Kingfisher versucht es von selbst noch einmal.");
  assert.equal(pruefSatz({ completed: 4, pending: 0, running: 0, partial: 0, failed: 0, excluded: 2 }),
    "4 Quellen sind fertig durchgesehen und 2 sind ausgenommen.");
  assert.doesNotMatch(FUNDE_SATZ, /Einzelbestätigung/);
});

test("vorne keine Kacheln mit „Prüflauf“; sie stehen nur hinter „Für Techniker“", () => {
  const seite = readFileSync(new URL("../src/MemoryStatus.tsx", import.meta.url), "utf8");
  const vorne = seite.slice(0, seite.indexOf("memory-status-technik"));
  assert.doesNotMatch(vorne, /Prüflauf durchgeführt|Wenn du sie aktivierst|Aktiv\$\{|ohne Einzelbestätigung/);
  assert.match(seite.slice(seite.indexOf("memory-status-technik")), /Prüflauf durchgeführt/);
});

test("Vorgemerkt, während das Sprachmodell lädt: „An“, nicht „Pausiert“, und kein „wenn du es einschaltest“ (Fremdprobe 3, Befund 3)", () => {
  for (const state of ["model_missing", "local_model_unavailable"]) {
    const vorgemerkt = { state, requested: true, pending: 2 };
    assert.match(sortierStand(vorgemerkt), /^An: .*sobald das Sprachmodell/);
    assert.doesNotMatch(sortierWirkung(vorgemerkt), /einschaltest/);
  }
});

test("Fortschritt und Stand sagen dasselbe (Fremdprobe 3, Befund 12)", () => {
  assert.equal(sortiertGerade({ state: "active" }), true);
  assert.equal(sortiertGerade({ state: "legacy_active" }), true);
  for (const state of ["paused", "model_missing", "local_model_unavailable", "wrong_model", "cloud_ueber_ollama"]) {
    assert.equal(sortiertGerade({ state }), false, state);
    assert.doesNotMatch(sortierStand({ state }), /^An: /, state);
  }
  assert.match(sortierStand({ state: "active" }), /^An: /);
});

test('enabled automation with a live execution pause is not described as running', () => {
  const paused={state:'active',requested:true,pending:7,execution_pause_reason:'Pausiert. Mit Weiter geht es weiter.'};
  assert.equal(sortiertGerade(paused),false);
  assert.match(sortierStand(paused),/Verarbeitung wartet|Verarbeitung pausiert/);
  assert.doesNotMatch(sortierStand(paused),/sortiert deine Quellen selbst/);
});

test('failed checks do not promise automatic retries while processing is blocked',()=>{
  const text=pruefSatz({completed:0,pending:0,running:0,partial:0,failed:1,excluded:0},false);
  assert.match(text,/noch aus|vorgemerkt/);
  assert.doesNotMatch(text,/von selbst|du musst nichts tun/);
});
