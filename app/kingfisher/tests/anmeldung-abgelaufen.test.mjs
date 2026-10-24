// Abgelaufene Anmeldung: Der Satz des Sidecars sagt, was zu tun ist, und der Weg darin ist ein Klick (verweis.ts);
// unter Zugänge steht dann am Postfach „Neu anmelden“ (NeuAnmelden.tsx). Synthetische Daten.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { satzMitVerweis } from "../src/verweis.ts";
import { einlesenStand } from "../src/Einrichtung/einlesen.ts";

const SATZ = "Postfach Probe-Post lässt Kingfisher nicht mehr hinein: Die Anmeldung ist abgelaufen oder das Passwort hat "
  + "sich geändert. Melde dich unter Einstellungen → Zugänge neu an.";

test("Der Weg im Satz wird zum Verweis, der Wortlaut bleibt", () => {
  const teile = satzMitVerweis(SATZ, "zugaenge");
  assert.equal(teile.verweis?.href, "/settings#zugaenge");
  assert.equal(teile.verweis?.text, "Einstellungen → Zugänge");
  assert.equal(teile.vor + teile.verweis?.text + teile.nach, SATZ);
  assert.equal(teile.nach, " neu an.");
});

test("Ohne Ziel, mit unbekanntem Ziel oder ohne den Weg im Satz bleibt er ganz Text", () => {
  for (const [satz, ziel] of [[SATZ, null], [SATZ, undefined], [SATZ, "gibt-es-nicht"], ["Postfach Probe-Post antwortet gerade nicht.", "zugaenge"]]) {
    const teile = satzMitVerweis(satz, ziel);
    assert.equal(teile.verweis, null);
    assert.equal(teile.vor, satz);
    assert.equal(teile.nach, "");
  }
});

test("In der Einrichtung steht dieselbe Aussage wie auf Heute, nicht „stockt gerade“", () => {
  const konto = {account_id: "a", label: "Probe-Post", connected: true, started: true, paused: false, step: "capture",
    error: "anmeldung", scope: "INBOX", folders: [],
    stand: {zustand: "fehler", satz: SATZ, gelesen: null, gesamt: null, zuletzt: null, verweis: "zugaenge"}};
  assert.equal(einlesenStand(konto), SATZ);
  // Gegenbeispiel: Ein Fehler ohne Satz des Sidecars sagt weiter, dass Kingfisher es selbst erneut versucht.
  assert.match(einlesenStand({...konto, stand: null}), /stockt gerade/);
});

test("Heute, Einrichtung und „Für Techniker“ setzen den Verweis aus dem Satz", () => {
  const quelle = datei => readFileSync(new URL(`../src/${datei}`, import.meta.url), "utf8");
  assert.match(quelle("PostfachStand.tsx"), /<SatzMitVerweis satz=\{eintrag\.satz\} ziel=\{eintrag\.verweis\} \/>/);
  assert.match(quelle("Einrichtung/MailEinlesen.tsx"), /<SatzMitVerweis satz=\{einlesenStand\(konto\)\} ziel=\{konto\.stand\?\.verweis\} \/>/);
  assert.match(quelle("MailSyncSettings.tsx"), /<SatzMitVerweis satz=\{kontoStand\(account\)\}/);
});

test("Unter Zugänge: Neu anmelden nur für Postfächer mit Passwort, deren Stand hierher verweist", () => {
  const zugaenge = readFileSync(new URL("../src/Einstellungen/Zugaenge.tsx", import.meta.url), "utf8");
  assert.match(zugaenge, /neuAnmeldenWeg\(account, staende\[account\.id\]\) === "passwort"/);
  const knopf = readFileSync(new URL("../src/Einstellungen/NeuAnmelden.tsx", import.meta.url), "utf8");
  assert.match(knopf, /api\.mailNeuAnmelden\(konto\.id, passwort\)/);
  assert.match(knopf, /role="alert"/, "eine Ablehnung steht als Satz am Knopf");
});

// -- Befunde des Reviews ---------------------------------------------------------------------------------------------
import { angemeldetSatz, googleNeuSatz, neuAnmeldenWeg } from "../src/Einstellungen/neuAnmeldenWeg.ts";
import { postfachMussHandeln } from "../src/heute.ts";

test("Neu anmelden: Passwort, Google mit demselben Konto, Microsoft über seine Karte, sonst nichts", () => {
  const verweist = {verweis: "zugaenge"};
  assert.equal(neuAnmeldenWeg({}, verweist), "passwort");
  assert.equal(neuAnmeldenWeg({auth: "google"}, verweist), "google");
  assert.equal(neuAnmeldenWeg({auth: "microsoft"}, verweist), null);
  assert.equal(neuAnmeldenWeg({}, {verweis: null}), null);
  assert.equal(neuAnmeldenWeg({}, null), null);
  assert.match(googleNeuSatz(true), /„Mit Google anmelden“ und demselben Google-Konto/);
  assert.match(googleNeuSatz(false), /Für Techniker → Google-Anmeldung vorbereiten/);
});

test("Nach dem Neu-Anmelden steht „Angemeldet“, oder der Satz zum Kalender, der das Passwort nicht annahm", () => {
  assert.equal(angemeldetSatz("Probe-Post"), "Angemeldet. Kingfisher liest Probe-Post gleich weiter.");
  const kalender = "Dein Postfach ist wieder angemeldet. Den Kalender „Privat“ konnte Kingfisher mit dem neuen Passwort nicht öffnen; er hat wohl ein eigenes. Entferne ihn unter Einstellungen → Zugänge und verbinde ihn mit „Kalender hinzufügen“ neu.";
  assert.equal(angemeldetSatz("Probe-Post", kalender), kalender);
  const zugaenge = readFileSync(new URL("../src/Einstellungen/Zugaenge.tsx", import.meta.url), "utf8");
  assert.match(zugaenge, /angemeldetSatz\(account\.label, neu\.satz\)/);
  // Die Statuszeile steht immer im DOM (sonst ist die Ansage unsicher), und der Fokus landet nach dem Erfolg dort.
  assert.match(zugaenge, /<p className="source-hint neu-anmelden-status" role="status" tabIndex=\{-1\}/);
  assert.match(zugaenge, /setFokusAuf\(account\.id\)/);
  assert.match(zugaenge, /statusZeilen\.current\[fokusAuf\]\?\.focus\(\)/);
});

test("Neu anmelden: Escape bricht ab, nach einer Ablehnung bleibt der Fokus im Feld", () => {
  const knopf = readFileSync(new URL("../src/Einstellungen/NeuAnmelden.tsx", import.meta.url), "utf8");
  assert.match(knopf, /event\.key === "Escape"/);
  assert.match(knopf, /onKeyDown=\{taste\}/);
  assert.match(knopf, /requestAnimationFrame\(\(\) => \{ feld\.current\?\.focus\(\)/);
  assert.match(knopf, /knopf\.current\?\.focus\(\)/, "nach Abbrechen zurück auf „Neu anmelden“");
});

test("Der Postfachstand steht auf Heute nur, wenn ein Postfach den Menschen braucht, dann offen (Paket U, H6)", () => {
  assert.equal(postfachMussHandeln([{zustand: "fehler", verweis: "zugaenge"}]), true);
  assert.equal(postfachMussHandeln([{zustand: "fehler", verweis: null}, {zustand: "leer"}]), false);
  assert.equal(postfachMussHandeln([{zustand: "aktuell", verweis: "zugaenge"}]), false, "nur, was Heute auch zeigt");
  const stand = readFileSync(new URL("../src/PostfachStand.tsx", import.meta.url), "utf8");
  assert.match(stand, /const mussHandeln = postfachMussHandeln\(zeigen\);/);
  assert.match(stand, /if \(ausstehend \|\| !mussHandeln\) return null;/);
  assert.doesNotMatch(stand, /<details/, "was zu tun ist, steht offen da, nicht hinter einer Klappe");
});

test("Die Statuszeile nach dem Neu-Anmelden bekommt den Fokus, aber keinen Rahmen (kein Bedienelement)", () => {
  // Nach-Review 9: `:focus` zeichnete einen dauerhaften cyanfarbenen Rahmen um einen Satz (docs/16-gestaltung.md).
  const css = readFileSync(new URL("../src/Einstellungen/Einstellungen.css", import.meta.url), "utf8");
  assert.match(css, /\.neu-anmelden-status:focus(?:,\s*\.neu-anmelden-status:focus-visible)?\s*\{\s*outline:\s*none;?\s*\}/);
  assert.doesNotMatch(css, /\.neu-anmelden-status:focus(?:-visible)?\s*\{[^}]*outline:\s*\d/);
});
