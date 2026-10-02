// Sicherung (Fremdprobe, Befunde 8 und 31): ohne Helfer kein Formular, das ins Leere führt, sondern ein Download;
// ein Passwortfeld mit „anzeigen“ statt doppelter Eingabe.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { sicherungWeg } from "../src/sicherung.ts";

const code = () => readFileSync(new URL("../src/RecoverySettings.tsx", import.meta.url), "utf8");

test("Ohne Helfer der Download, mit Helfer dessen Weg", () => {
  assert.equal(sicherungWeg({ online: false, job: null }), "download");
  assert.equal(sicherungWeg({ online: true, job: null }), "helfer");
  // Ein Auftrag, der beim Helfer läuft, bleibt dort, auch wenn er sich gerade nicht meldet.
  assert.equal(sicherungWeg({ online: false, job: { id: "a", status: "running", message: "", path: null } }), "helfer");
  assert.equal(sicherungWeg({ online: false, job: { id: "a", status: "failed", message: "", path: null } }), "download");
  assert.equal(sicherungWeg(null), "download");
});

test("Kein Satz mehr, der auf einen fehlenden Helfer verweist", () => {
  assert.doesNotMatch(code(), /Sicherungshelfer ist nicht erreichbar/);
  // Der Knopf hängt nicht mehr an `state.online`: ohne Helfer gibt es den Download.
  assert.doesNotMatch(code(), /disabled=\{!state\?\.online/);
});

test("ein Passwortfeld, das sich anzeigen lässt; keine Wiederholung", () => {
  const quelle = code();
  assert.equal([...quelle.matchAll(/<input\b/g)].length, 1, "genau ein Eingabefeld");
  assert.match(quelle, /type=\{zeigen \? "text" : "password"\}/);
  assert.match(quelle, /aria-pressed=\{zeigen\}/);
  assert.match(quelle, /\{zeigen \? "verbergen" : "anzeigen"\}/);
  assert.doesNotMatch(quelle, /Passwort wiederholen|stimmen nicht überein|repeat/);
});
