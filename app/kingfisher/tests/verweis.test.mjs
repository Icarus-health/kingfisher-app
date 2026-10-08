// Verweise in die Einstellungen sind Ziele, kein Text (Fremdprobe, Befund 25).
import assert from "node:assert/strict";
import {readFileSync, readdirSync} from "node:fs";
import {test} from "node:test";
import {verweis} from "../src/verweis.ts";
import {einlesenStand, einlesenVerweis} from "../src/Einrichtung/einlesen.ts";

test("Ein Verweis nennt den Weg und springt genau dorthin", () => {
  assert.deepEqual(verweis("darf"), {href: "/settings#darf", text: "Einstellungen → Was Kingfisher darf"});
  assert.deepEqual(verweis("zugaenge"), {href: "/settings#zugaenge", text: "Einstellungen → Zugänge"});
  assert.deepEqual(verweis("technik-hintergrund"),
    {href: "/settings#technik-hintergrund", text: "Einstellungen → Für Techniker → Zeitplan und Hintergrund"});
  assert.deepEqual(verweis("technik-kartendienst"),
    {href: "/settings#technik-kartendienst", text: "Einstellungen → Für Techniker → Eigener Kartendienst für die Wegezeit"});
});

test("Ein Ziel, das es nicht gibt, ist ein Fehler im Code und kein stiller Sprung woandershin", () => {
  assert.throws(() => verweis("wetter"));
  assert.throws(() => verweis("technik-gibtsnicht"));
  assert.throws(() => verweis("mail"));  // alte Kennung: im Code die neue verwenden
});

test("Das pausierte Einlesen verweist auf den Zeitplan", () => {
  const konto = {account_id: "a", label: "Probe-Post", connected: true, started: true, paused: true, step: "capture", error: null,
    scope: "INBOX", folders: [{folder: "INBOX", inventory_complete: true, total: 10, captured: 1, duplicates: 0, failed: 0, pending: 9,
      live_pending: 0, analyzed: 0, analysis_failed: 0, deferred: 0, excluded: 0, categorized: 0, categories_pending: 0, categories_failed: 0}]};
  assert.equal(einlesenVerweis(konto), "technik-hintergrund");
  assert.doesNotMatch(einlesenStand(konto), /Einstellungen →/);
  assert.equal(einlesenVerweis({...konto, paused: false}), null);
});

// Wo ein Mensch liest, steht kein Weg in Worten („unter Einstellungen → …“), sondern ein <Verweis>. Kommentare zählen nicht.
const ORTE = [
  ...readdirSync(new URL("../src/Einrichtung/", import.meta.url)).filter(name => /\.tsx?$/.test(name)).map(name => `Einrichtung/${name}`),
  "App.tsx",
];

test("Einrichtung und Briefing nennen Einstellungen nur als Verweis", () => {
  for (const datei of ORTE) {
    const code = readFileSync(new URL(`../src/${datei}`, import.meta.url), "utf8")
      .replace(/\/\*[\s\S]*?\*\//g, " ").replace(/^\s*\/\/.*$/gm, " ").replace(/\s\/\/\s.*$/gm, " ");
    assert.doesNotMatch(code, /Einstellungen\s*→/, `${datei} nennt einen Weg in die Einstellungen als Text`);
    assert.doesNotMatch(code, /unter Einstellungen\b(?!\s*<)/, `${datei}: „unter Einstellungen“ ohne Verweis`);
  }
});

test("Globale Pause wird im Assistenten auch bei unbekanntem Umfang nicht als Lesen ausgegeben", () => {
  for (const total of [100, null]) {
    const satz = "Postfach Probe: Einlesen pausiert. Bisher 20 Mails gelesen. Auf Heute geht es mit „Weiter“ weiter.";
    const konto = {account_id: "a", label: "Probe", connected: true, started: true, paused: false, step: "capture", error: null,
      folders: [{folder: "INBOX", inventory_complete: total !== null, total, captured: 20, duplicates: 0, failed: 0, pending: 80}],
      stand: {zustand: "pausiert", satz, gelesen: 20, gesamt: total, zuletzt: null}};
    assert.equal(einlesenStand(konto), satz);
    assert.equal(einlesenVerweis(konto), null, "globale Pause führt nicht zur Konto-Pause");
  }
});
