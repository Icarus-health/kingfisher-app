// Sprache und Kleinigkeiten (Persona-Prüfung, Paket S, 27.10.2026). Je Test der Befund aus Abschnitt 6 des Berichts
// (docs/runs/2026-10-26-persona-pruefung/README.md) oder der offene Rest eines vorigen Pakets.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { after, test } from "node:test";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { schonVerbunden, schonVerbundenSatz } from "../src/postfachWeg.ts";
import { vorbelegteAdresse } from "../src/kalenderWeg.ts";
import { testCache } from "./testcache.mjs";

const quelle = name => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");
const server = await createServer({ cacheDir: testCache("sprache-paket-s"), root: fileURLToPath(new URL("..", import.meta.url)),
  configFile: false, logLevel: "silent", server: { middlewareMode: true, watch: null, ws: false, hmr: false }, appType: "custom" });
after(() => server.close());

// -- Befund 4: doppeltes Postfach gleich nach der Adresse, ruhig ---------------------------------------------------

test("ein schon verbundenes Postfach wird an der Adresse erkannt, gleich welche Schreibweise", () => {
  const liste = [{ id: "mail-a", name: "Kanzlei", adresse: "Lea@Hartmann-Beratung.example" }];
  assert.deepEqual(schonVerbunden("  lea@hartmann-beratung.example ", liste), liste[0]);
  assert.equal(schonVerbunden("lea@hartmann-beratung.exampl", liste), null, "halb getippt: noch nichts");
  assert.equal(schonVerbunden("lea@hartmann", liste), null);
  assert.equal(schonVerbunden("anna@hartmann-beratung.example", liste), null);
  assert.equal(schonVerbundenSatz("Kanzlei"), "Dieses Postfach ist schon verbunden: Kanzlei. Kingfisher liest es bereits.");
});

test("die Karte sagt es vor dem Passwort, ohne roten Rahmen, mit dem Weg dorthin; auch die Antwort 409 steht ruhig da", () => {
  const karte = quelle("PostfachMitAdresse.tsx");
  const hinweis = karte.slice(karte.indexOf("{schon || doppeltSatz"), karte.indexOf("{schon ? null : <>"));
  assert.ok(hinweis.length > 0, "der Hinweis steht direkt unter der Adresse");
  assert.ok(karte.indexOf("{schon || doppeltSatz") < karte.indexOf("<PasswortFeld"), "vor dem Passwortfeld");
  assert.match(hinweis, /role="status"/);
  assert.doesNotMatch(hinweis, /settings-error|role="alert"/, "kein roter Fehler");
  assert.match(hinweis, /Zum Postfach/);
  assert.match(karte, /problem\.status === 409[^\n]*setDoppeltSatz/);
  // Ist es schon verbunden, wird die Domain nicht gefragt.
  assert.match(karte, /useAnbieter\(schon \? "" : adresse/);
  assert.match(quelle("Einstellungen/Zugaenge.tsx"), /zumPostfach=\{kontoId =>/);
});

// -- Befund 8: Passwort anzeigen, Kalender vom selben Anbieter vorbelegt ---------------------------------------------

test("jedes Passwortfeld vorne hat „Anzeigen“, verborgen als Vorgabe", async () => {
  const { PasswortFeld } = await server.ssrLoadModule("/src/grundlage/PasswortFeld.tsx");
  const html = renderToStaticMarkup(createElement(PasswortFeld, { id: "p", wert: "geheim", onWert() {} }));
  assert.match(html, /type="password"/);
  assert.match(html, /aria-pressed="false"/);
  assert.match(html, />Anzeigen</);
  assert.match(html, /aria-label="Passwort anzeigen"/);
  for (const datei of ["PostfachMitAdresse.tsx", "KalenderMitAdresse.tsx", "Einstellungen/NeuAnmelden.tsx"])
    assert.doesNotMatch(quelle(datei), /type="password"/, `${datei}: das Feld mit „Anzeigen“`);
});

test("der Kalender nimmt zuerst das Postfach, dessen Anbieter den Kalender mit demselben Passwort hat", () => {
  const anbieter = [{ id: "gmail", label: "Gmail", imap_host: "imap.gmail.com", domains: ["gmail.com"], kalender_ical: true },
    { id: "gmx", label: "GMX", imap_host: "imap.gmx.net", domains: ["gmx.de"], caldav_url: "https://caldav.gmx.net" }];
  const praxis = { user: "praxis@praxis-fehr.example", secret_present: true };
  const gmail = { user: "miriam.fehr@gmail.com", secret_present: true };
  assert.equal(vorbelegteAdresse([gmail, praxis], anbieter), "praxis@praxis-fehr.example", "eigene Domain: beim Mailserver suchen");
  assert.equal(vorbelegteAdresse([gmail, { user: "m@gmx.de", secret_present: true }], anbieter), "m@gmx.de");
  assert.equal(vorbelegteAdresse([gmail], anbieter), "miriam.fehr@gmail.com", "nur Gmail: dann Gmail");
  assert.equal(vorbelegteAdresse([{ ...praxis, secret_present: false }, gmail], anbieter), "miriam.fehr@gmail.com",
    "ohne gespeichertes Passwort zählt das Postfach nicht als gleicher Weg");
  assert.equal(vorbelegteAdresse([], anbieter), "");
});
