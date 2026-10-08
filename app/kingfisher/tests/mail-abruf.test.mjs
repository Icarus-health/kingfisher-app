// „Mails regelmäßig abrufen“ statt Fachwörtern und Zahlenfeld (Fremdprobe, Befund 12): src/mailAbruf.ts und die
// sichtbaren Texte von MailSyncSettings.tsx und MailIntake.tsx.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { ALTE_WOERTER, VORGABE_MINUTEN, abrufSatz, abstandAuswahl, abstandText, ordnerName } from "../src/mailAbruf.ts";

const quelle = (datei) => readFileSync(new URL(`../src/${datei}`, import.meta.url), "utf8");
/** Zeichenketten und Text zwischen Tags, ohne Kommentare: was der Nutzer sehen kann. */
function sichtbar(code) {
  const ohne = code.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/^\s*\/\/.*$/gm, " ").replace(/\s\/\/\s.*$/gm, " ");
  const texte = [...ohne.matchAll(/"((?:[^"\\\n]|\\.)*)"|`((?:[^`\\]|\\.)*)`/g)].map(m => m[1] ?? m[2]);
  for (const m of ohne.matchAll(/(?<![=\-])>([^<>{}]+)</g)) texte.push(m[1]);
  return texte.join("\n");
}

test("vier Abstände zur Wahl, Vorgabe alle 30 Minuten (Fremdprobe 3, Befund 13); ein früherer Wert bleibt sichtbar", () => {
  assert.equal(VORGABE_MINUTEN, 30);
  assert.deepEqual(abstandAuswahl(30), [{ minuten: 30, text: "alle 30 Minuten" },
    { minuten: 60, text: "jede Stunde" }, { minuten: 240, text: "alle vier Stunden" }, { minuten: 1440, text: "täglich" }]);
  assert.deepEqual(abstandAuswahl(480).map(e => e.text), ["alle 30 Minuten", "jede Stunde", "alle vier Stunden", "alle 8 Stunden", "täglich"]);
  assert.equal(abstandText(480), "alle 8 Stunden");
  assert.equal(abstandAuswahl(5).length, 4, "unter 15 Minuten nimmt der Sidecar nicht an");
});

test("ein Satz sagt, was gilt", () => {
  assert.equal(abrufSatz(true, 240, ["WEB.DE"]), "An. Kingfisher ruft die Mails aus WEB.DE alle vier Stunden ab.");
  assert.equal(abrufSatz(true, 60, ["WEB.DE", "Gmail"]), "An. Kingfisher ruft die Mails aus 2 Postfächern jede Stunde ab.");
  assert.match(abrufSatz(false, 240, ["WEB.DE"]), /^Aus\./);
  assert.match(abrufSatz(true, 240, []), /^Verbinde zuerst ein Postfach/);
  assert.equal(ordnerName("INBOX"), "Posteingang");
  assert.equal(ordnerName("Gesendet"), "Gesendet");
});

test("ein Schalter und eine Auswahl, kein Zahlenfeld und keines der alten Fachwörter", () => {
  const sync = quelle("MailSyncSettings.tsx");
  assert.match(sync, /type="checkbox" role="switch"/);
  assert.match(sync, /<strong>Mails regelmäßig abrufen<\/strong>/);
  assert.match(sync, /<select value=\{minuten\}/);
  assert.doesNotMatch(sync, /type="number"/);
  for (const datei of ["MailSyncSettings.tsx", "MailIntake.tsx", "SetupOverview.tsx"]) {
    const text = sichtbar(quelle(datei));
    const funde = ALTE_WOERTER.filter(wort => text.includes(wort));
    assert.deepEqual(funde, [], datei);
  }
  // Ordnernamen gehen durch ordnerName: „INBOX“ steht nur noch in einem Vergleich, nie in einem Text.
  assert.doesNotMatch(sichtbar(quelle("MailIntake.tsx")).replace(/^INBOX$/m, ""), /INBOX/);
});

test("ausgefilterte Mails können ausdrücklich und manuell erneut geprüft werden", () => {
  const intake = quelle("MailIntake.tsx");
  assert.match(intake, /const filtered = progress\.filtered \+ progress\.liveFiltered/);
  assert.match(intake, /filtered\s*>\s*0/);
  assert.match(sichtbar(intake), /Ausgefilterte Mails(?: und Fehler)? erneut prüfen/);
  assert.match(intake, /mit den aktuellen Regeln erneut geprüft/);
  assert.match(intake, /nicht automatisch/);
});
