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
  assert.match(zugaenge, /!account\.auth && staende\[account\.id\]\?\.verweis === "zugaenge"/);
  const knopf = readFileSync(new URL("../src/Einstellungen/NeuAnmelden.tsx", import.meta.url), "utf8");
  assert.match(knopf, /api\.mailNeuAnmelden\(konto\.id, passwort\)/);
  assert.match(knopf, /role="alert"/, "eine Ablehnung steht als Satz am Knopf");
});
