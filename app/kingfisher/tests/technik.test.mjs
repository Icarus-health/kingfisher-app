// „Für Techniker“ ohne Widerspruch (Fremdprobe 2, Befunde 27 bis 29).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { dokumenteSatz, kostenSatz, laufZeile } from "../src/technik.ts";
import { ausstattungQuelle, ausstattungSatz } from "../src/system.ts";

const SRC = new URL("../src/", import.meta.url);

test("Ausstattung: eine Aussage, selbst gemessen oder gemeldet, nie „Chip unbekannt“ und „noch unbekannt“ zugleich", () => {
  assert.equal(ausstattungSatz({ chip: null, gb: 15.7, quelle: "eigene" }), "15,7 GB Arbeitsspeicher, selbst gemessen");
  assert.equal(ausstattungSatz({ chip: "Apple M2", gb: 16, quelle: "bericht" }), "Apple M2 · 16 GB Arbeitsspeicher");
  assert.match(ausstattungSatz({ gb: 7.6, quelle: "untergrenze" }), /^Mindestens 7,6 GB Arbeitsspeicher, im Container gemessen/);
  assert.equal(ausstattungSatz({ gb: null, quelle: "unbekannt" }), null);
  assert.equal(ausstattungQuelle("eigene"), "eigene");
  assert.equal(ausstattungQuelle("macos_host_report"), "bericht");
  assert.equal(ausstattungQuelle("unknown"), "unbekannt");
  for (const datei of ["DeviceModelHelp.tsx", "ModelRecommendation.tsx"]) {
    const text = readFileSync(new URL(datei, SRC), "utf8");
    assert.match(text, /ausstattungSatz\(/, datei);
    assert.doesNotMatch(text, /Chip unbekannt/, datei);
  }
});

test("richtige Einzahl bei Dokumenten", () => {
  assert.equal(dokumenteSatz(1), "1 gespeichertes Dokument");
  assert.equal(dokumenteSatz(0), "0 gespeicherte Dokumente");
  assert.equal(dokumenteSatz(50, true), "Mindestens 50 gespeicherte Dokumente");
});

test("Kostenwarnung nur bei einem Modell außerhalb dieses Rechners, und dann welches (Befund 28)", () => {
  assert.equal(kostenSatz(false, null), "Dabei wird kein Sprachmodell gerufen.");
  assert.doesNotMatch(kostenSatz(true, null), /Kosten verursach/);
  assert.match(kostenSatz(true, null), /auf diesem Rechner; das kostet nichts/);
  assert.match(kostenSatz(true, "gpt-oss:120b-cloud"), /^Dabei kann gpt-oss:120b-cloud gerufen werden; .*Kosten verursachen\.$/);
});

test("Was zuletzt lief: entweder Fehler mit Grund oder „nichts zu tun“, nie beides (Befund 29)", () => {
  assert.equal(laufZeile("Wissensvorschläge", true, "Nichts zu tun."), "Wissensvorschläge: Nichts zu tun.");
  const ohneGrund = laufZeile("Wissensvorschläge", false, "Nichts zu tun.");
  assert.doesNotMatch(ohneGrund, /Nichts zu tun/);
  assert.match(ohneGrund, /^Wissensvorschläge: Fehler ohne genannten Grund\./);
  assert.equal(laufZeile("Wissensvorschläge", false, "Fehler bei e-1: Zeitüberschreitung. Der nächste Lauf versucht es erneut."),
    "Wissensvorschläge: Fehler bei e-1: Zeitüberschreitung. Der nächste Lauf versucht es erneut.");
  assert.equal(laufZeile("Privat", false, "Mailaufnahme fehlgeschlagen."), "Privat: Fehler: Mailaufnahme fehlgeschlagen.");
  assert.doesNotMatch(readFileSync(new URL("MailSyncSettings.tsx", SRC), "utf8"), /"Fehler · "/);
});
