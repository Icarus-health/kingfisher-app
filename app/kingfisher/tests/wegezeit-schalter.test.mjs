// „Wegezeit berechnen“ lässt sich erst einschalten, wenn es rechnen kann (Fremdprobe, Befund 19).
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";
import {wegezeitSchalter} from "../src/wegezeitSchalter.ts";

test("Ohne Startort gesperrt, und es fehlt der Startort", () => {
  assert.deepEqual(wegezeitSchalter({aktiv: false, kann_rechnen: false, fehlt: "startort"}), {an: false, gesperrt: true, fehlt: "startort"});
});

test("Ohne Kartendienst gesperrt, und es fehlt der Dienst", () => {
  assert.deepEqual(wegezeitSchalter({aktiv: false, kann_rechnen: false, fehlt: "dienst"}), {an: false, gesperrt: true, fehlt: "dienst"});
});

test("Kann es rechnen, ist der Schalter frei", () => {
  assert.deepEqual(wegezeitSchalter({aktiv: false, kann_rechnen: true, fehlt: null}), {an: false, gesperrt: false, fehlt: null});
});

test("Ausschalten ist nie gesperrt, auch wenn inzwischen etwas fehlt", () => {
  assert.equal(wegezeitSchalter({aktiv: true, kann_rechnen: false, fehlt: "startort"}).gesperrt, false);
});

test("Die Marke im Assistenten folgt dem Schalter ohne Neuladen", () => {
  const code = readFileSync(new URL("../src/Einrichtung/FreigabenSchritt.tsx", import.meta.url), "utf8");
  assert.match(code, /<WegezeitSettings beiAenderung=\{neu => melden\(\{art: "geaendert", id: "fahrzeiten", an: neu\.aktiv\}\)\} \/>/);
});
