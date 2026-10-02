import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync, readdirSync} from "node:fs";
import {ARTEN, kurz, meldbar, zaehlSatz} from "../src/rueckmeldung.ts";

test("Die Arten sind die des Sidecars, in der Reihenfolge der Auswahl", () => {
  assert.deepEqual(ARTEN.map(a => a.id), ["falsch", "unvollstaendig", "veraltet", "zu_langsam", "sonstiges"]);
  assert.ok(ARTEN.every(a => a.text.length > 0));
});

test("Zählsatz nennt Anzahl und offene, ohne Prozent", () => {
  assert.equal(zaehlSatz({gesamt: 0, offen: 0}), "Noch keine Meldungen.");
  assert.equal(zaehlSatz({gesamt: 1, offen: 1}), "1 Meldung, 1 offen.");
  assert.equal(zaehlSatz({gesamt: 3, offen: 2}), "3 Meldungen, 2 offen.");
  assert.equal(zaehlSatz({gesamt: 2, offen: 0}), "2 Meldungen, alle erledigt.");
});

test("Kürzen schneidet am Wortende und lässt Kurzes stehen", () => {
  assert.equal(kurz("Bis wann?"), "Bis wann?");
  assert.equal(kurz("  viel\n   Platz  "), "viel Platz");
  const lang = "Bis wann muss ich das Angebot für die Firma Muster schicken und wer bekommt eine Kopie davon?";
  const k = kurz(lang, 40);
  assert.ok(k.length <= 40 && k.endsWith("…") && !k.includes("  "), k);
  assert.ok(lang.startsWith(k.slice(0, -1)), k);
});

test("Gemeldet werden nur fertige Antworten, keine Rückfragen", () => {
  const antwort = {role: "assistant", status: "complete"};
  assert.equal(meldbar(antwort), true);
  assert.equal(meldbar({role: "user", status: "complete"}), false);
  assert.equal(meldbar({role: "assistant", status: "error"}), false);
  assert.equal(meldbar({...antwort, metadata: {context: {clarification_choices: [{label: "A"}]}}}), false);
  assert.equal(meldbar({...antwort, metadata: {context: {clarification_date: true}}}), false);
  assert.equal(meldbar({...antwort, metadata: {context: {clarification_choices: []}}}), true);
});

// Fremdprobe, Befund 16: kein Kommandozeilenbefehl in der Oberfläche; sie sagt, was aus einer Meldung wird.
test("Die Oberfläche nennt keinen Befehl, sondern was aus einer Meldung wird", () => {
  const src = new URL("../src/", import.meta.url);
  const dateien = (ordner, praefix = "") => readdirSync(ordner, {withFileTypes: true}).flatMap(e => e.isDirectory()
    ? dateien(new URL(`${e.name}/`, ordner), `${praefix}${e.name}/`) : /\.tsx?$/.test(e.name) ? [`${praefix}${e.name}`] : []);
  const befehl = /\bpython3? -m\b|\bnpm (run|test|ci)\b|\bmake (start|test)\b|docker compose|--fragen\b/;
  const funde = dateien(src).filter(datei => {
    const code = readFileSync(new URL(datei, src), "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "").replace(/\{\/\*[\s\S]*?\*\/\}/g, "");
    return befehl.test(code);
  });
  assert.deepEqual(funde, []);
  assert.match(readFileSync(new URL("Rueckmeldung.tsx", src), "utf8"), /Was daraus wird: Jede Meldung wird eine Prüffrage\./);
});
