// Google ohne eigenes Cloud-Projekt (Fremdprobe, Befund 2): Gmail mit App-Passwort, Kalender über die geheime iCal-Adresse,
// „Mit Google anmelden“ vorne nur, wenn es eingerichtet ist.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";
import {WO_FINDEN, aboVerbundenSatz, googleAnmeldungVorne, hilfeText, siehtNachAdresseAus} from "../src/googleWeg.ts";

const quelle = (datei) => readFileSync(new URL(`../src/${datei}`, import.meta.url), "utf8");

test("Ohne Einrichtung steht „Mit Google anmelden“ nicht vorne", () => {
  assert.equal(googleAnmeldungVorne(null), false);
  assert.equal(googleAnmeldungVorne({configured: false, secure_storage: true}), false);
  assert.equal(googleAnmeldungVorne({configured: true, secure_storage: false}), false);
  assert.equal(googleAnmeldungVorne({configured: true, secure_storage: true}), true);
});

test("Jede Stelle mit „Mit Google anmelden“ fragt vorher, ob es eingerichtet ist", () => {
  for (const datei of ["Einrichtung/MailSchritt.tsx", "Einrichtung/KalenderSchritt.tsx", "Einstellungen/Zugaenge.tsx"]) {
    const code = quelle(datei);
    const stellen = [...code.matchAll(/<GoogleSignIn\b/g)].length;
    assert.ok(stellen > 0, datei);
    const bedingt = [...code.matchAll(/googleVorne[^\n]*<GoogleSignIn\b/g)].length;
    assert.equal(bedingt, stellen, `${datei}: jede <GoogleSignIn> steht hinter googleVorne`);
  }
  // Der Knopf „Mit Google anmelden“ der Mail steht in der Gruppe, die nur mit googleVorne erscheint.
  assert.match(quelle("Einrichtung/MailSchritt.tsx"), /\{wege && googleVorne \? <div className="erststart-wege"/);
});

test("Der Kalender-Weg mit Google zeigt das Feld für die geheime Adresse, auch ohne Einrichtung", () => {
  assert.match(quelle("Einrichtung/KalenderSchritt.tsx"), /weg === "google" \? <GoogleKalenderAdresse/);
  assert.match(quelle("KalenderMitAdresse.tsx"), /weg\.art === "google_ical" \? <GoogleKalenderAdresse/);
});

test("Die Karte sagt in zwei Sätzen, wo die Adresse steht und was hinausgeht", () => {
  assert.equal(WO_FINDEN.split(/(?<=\.) /).length, 2);
  assert.match(WO_FINDEN, /Geheime Adresse im iCal-Format/);
  assert.match(WO_FINDEN, /hinaus geht nichts außer dem Abruf dieser Adresse/);
});

test("Adresse und Ergebnis", () => {
  assert.equal(siehtNachAdresseAus("https://calendar.google.com/calendar/ical/x/private-1/basic.ics"), true);
  assert.equal(siehtNachAdresseAus(" webcal://calendar.google.com/x "), true);
  assert.equal(siehtNachAdresseAus("lena.probe@example.org"), false);
  assert.equal(siehtNachAdresseAus("http://kalender.example.org/a.ics"), false);
  assert.equal(aboVerbundenSatz("Google: Lena Probe", 2, 1), "Verbunden: Google: Lena Probe (2 Termine, nur lesen).");
  assert.equal(aboVerbundenSatz("Google: Lena Probe", 1, 1), "Verbunden: Google: Lena Probe (1 Termin, nur lesen).");
  assert.equal(aboVerbundenSatz("Google: Lena Probe", 2, 0), "Schon verbunden: Google: Lena Probe.");
});

test("Der Verweis zur Google-Seite heißt, wohin er führt", () => {
  assert.equal(hilfeText({help_label: "Zur Google-Seite „App-Passwörter“"}), "Zur Google-Seite „App-Passwörter“");
  assert.equal(hilfeText({help_label: ""}), "So bekommst du es");
});
