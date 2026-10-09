import {test} from "node:test";
import assert from "node:assert/strict";
import {actionLabel, allConfirmation, cloudReady, describePull, downloadSize, orchesterZeile, pendingRoles, pullPercent, statusLabel, watchPull} from "../src/modelSetup.ts";

const entry = (name, gb) => ({name, groesse_gb: gb, speicher_gb: gb + 3, art: "moe", begruendung: "x.", passt: true, bestaetigung: "x"});
const row = (rolle, status, name, gb) => ({rolle, titel: rolle, beschreibung: "", empfohlen: entry(name, gb), alternativen: [], status,
  wirksam: {modell: null, lokal: null, quelle: "keins"}});
const stand = (phase, extra = {}) => ({id: "a", modell: "m", rolle: "antwort", phase, fortschritt: null, text: "", fehler: null, ergebnis: null, ...extra});

test("Status und Knopf je Zeile", () => {
  assert.equal(statusLabel("eingerichtet"), "Eingerichtet");
  assert.equal(statusLabel("installiert"), "Installiert");
  assert.equal(statusLabel("fehlt"), "Fehlt");
  assert.equal(actionLabel("eingerichtet"), null);
  assert.equal(actionLabel("installiert"), "Übernehmen");
  assert.equal(actionLabel("fehlt"), "Einrichten");
});

test("Alles einrichten überspringt Eingerichtetes und zählt jedes Modell nur einmal", () => {
  const rows = [row("frage", "fehlt", "qwen3.5:9b", 6.6), row("antwort", "fehlt", "qwen3.6:35b", 24),
    row("hintergrund", "fehlt", "qwen3.6:35b", 24), row("einbettung", "eingerichtet", "bge-m3", 1.2)];
  assert.deepEqual(pendingRoles(rows), ["frage", "antwort", "hintergrund"]);
  const size = downloadSize(rows);
  assert.deepEqual(size.models, ["qwen3.5:9b", "qwen3.6:35b"]);
  assert.ok(Math.abs(size.gb - 30.6) < 1e-9);
  const sentence = allConfirmation(rows);
  assert.match(sentence, /2 Modelle/);
  assert.match(sentence, /30,6 GB/);
  assert.match(sentence, /Minuten/);
});

test("Schon installierte Modelle zählen nicht zur Ladegröße", () => {
  const rows = [row("antwort", "installiert", "qwen3.6:35b", 24)];
  assert.equal(downloadSize(rows).gb, 0);
  assert.match(allConfirmation(rows), /nichts heruntergeladen/);
});

test("Fortschritt in Prozent, unbekannt bleibt unbekannt", () => {
  assert.equal(pullPercent({fortschritt: null}), null);
  assert.equal(pullPercent({fortschritt: 0.426}), 42);
  assert.equal(pullPercent({fortschritt: 1.7}), 100);
  assert.equal(pullPercent({fortschritt: Number.NaN}), null);
});

test("Beschreibung des Ladevorgangs nennt Prozent, Prüfung, Ergebnis und Fehlergrund mit nächstem Schritt", () => {
  assert.equal(describePull(stand("laedt", {fortschritt: 0.5})), "Das Modell wird geladen … 50 %");
  assert.equal(describePull(stand("laedt")), "Das Modell wird geladen …");
  assert.equal(describePull(stand("prueft", {fortschritt: 1})), "Das Modell wird geprüft …");
  assert.equal(describePull(stand("fertig")), "Eingerichtet und geprüft.");
  const failed = stand("fehler", {fehler: {grund: "Ollama ist nicht erreichbar.", naechster_schritt: "Ollama starten."}});
  assert.equal(describePull(failed), "Ollama ist nicht erreichbar. Ollama starten.");
});

test("Cloud nur mit Anbieter, Schlüssel und Einwilligung", () => {
  assert.equal(cloudReady("anthropic", true, true), true);
  assert.equal(cloudReady("", true, true), false);
  assert.equal(cloudReady("anthropic", false, true), false);
  assert.equal(cloudReady("anthropic", true, false), false);
});

test("watchPull meldet jeden Stand und endet mit dem Endstand", async () => {
  const states = [stand("wartet"), stand("laedt", {fortschritt: 0.3}), stand("prueft", {fortschritt: 1}), stand("fertig", {fortschritt: 1})];
  const seen = [];
  const waits = [];
  const last = await watchPull({read: async () => states.shift(), onState: value => seen.push(value.phase), wait: async ms => { waits.push(ms); }});
  assert.deepEqual(seen, ["wartet", "laedt", "prueft", "fertig"]);
  assert.equal(last.phase, "fertig");
  assert.equal(waits.length, 3);
});

test("watchPull hält bei einem Fehlerstand an und gibt ihn zurück", async () => {
  const states = [stand("laedt", {fortschritt: 0.1}), stand("fehler", {fehler: {grund: "g", naechster_schritt: "n"}})];
  const last = await watchPull({read: async () => states.shift(), onState: () => undefined, wait: async () => undefined});
  assert.equal(last.phase, "fehler");
});

test("watchPull übersteht kurze Aussetzer, gibt aber nach mehreren in Folge auf", async () => {
  let calls = 0;
  const flaky = async () => { calls++; if (calls <= 2) throw new Error("netz"); return stand("fertig"); };
  assert.equal((await watchPull({read: flaky, onState: () => undefined, wait: async () => undefined})).phase, "fertig");
  const dead = async () => { throw new Error("weg"); };
  assert.equal(await watchPull({read: dead, onState: () => undefined, wait: async () => undefined}), null);
});

test("watchPull hört auf, wenn die Ansicht verschwindet", async () => {
  let stopped = false;
  const seen = [];
  const last = await watchPull({read: async () => stand("laedt"), onState: value => { seen.push(value); stopped = true; },
    wait: async () => undefined, isStopped: () => stopped});
  assert.equal(last, null);
  assert.equal(seen.length, 1);
});

const orchester = (extra = {}) => ({tag_gb: 13, nacht_gb: 27, festplatte_gb: 32, festplatte_noch_gb: 32, nutzbar_gb: 27.2,
  festplatte_frei_gb: 210, passt_tag: true, passt_nacht: true, passt_festplatte: true, unbekannte_modelle: [], hinweise: [], ...extra});

test("Die Zeile nennt Tag, Nacht, Festplatte und freien Platz in Alltagssprache", () => {
  assert.equal(orchesterZeile(orchester()), "Zusammen: 13 GB Arbeitsspeicher am Tag, 27 GB nachts, 32 GB Festplatte (frei: 210 GB).");
  assert.match(orchesterZeile(orchester({tag_gb: 12.5, festplatte_frei_gb: 9.4})), /12,5 GB Arbeitsspeicher am Tag.*frei: 9,4 GB/);
});

test("Unbekannter Platz und unbekannte Modelle werden gesagt, nicht geraten", () => {
  assert.match(orchesterZeile(orchester({festplatte_frei_gb: null})), /freier Platz unbekannt/);
  assert.doesNotMatch(orchesterZeile(orchester({festplatte_frei_gb: null})), /frei: /);
  assert.match(orchesterZeile(orchester({unbekannte_modelle: ["eigen:7b"]})), /Größe von eigen:7b ist nicht bekannt/);
});

test('setup blocks an oversized full plan before the first role is installed', async () => {
  const {setupFits} = await import('../src/modelSetup.ts');
  const rows=[{rolle:'frage',empfohlen:{passt:true}},{rolle:'antwort',empfohlen:{passt:true}}];
  const plan={passt_tag:false,passt_nacht:true};
  assert.equal(setupFits(rows,plan,['frage','antwort']),false);
  assert.equal(setupFits(rows,plan,['frage']),true);
  assert.equal(setupFits([{rolle:'antwort',empfohlen:{passt:false}}],plan,['antwort']),false);
  assert.equal(setupFits(rows,{passt_tag:true,passt_nacht:true},['frage','antwort']),true);
  assert.equal(setupFits(rows,undefined,['unknown']),false);
});
