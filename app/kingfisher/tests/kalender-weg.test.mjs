// Kalender wie Mail (Fremdprobe, Befund 7): Die Mailadresse genügt; ehrlich, wo der Katalog die Adresse nicht weiß.
import assert from "node:assert/strict";
import {test} from "node:test";
import {ADRESSE_FEHLT, ADRESSE_WO, MICROSOFT_EINSTELLUNGEN, SELBST_SUCHEN, kalenderWeg, postfachZurAdresse, verbundenSatz} from "../src/kalenderWeg.ts";

const anbieter = (id, label, extra = {}) => ({id, label, imap_host: "", smtp_host: "", imap_port: 993, smtp_port: 587, app_password: false,
  hint: "", help_url: "", caldav_url: "", caldav_note: "", ...extra});
const KATALOG = [
  anbieter("webde", "WEB.DE", {domains: ["web.de"], caldav_url: "https://caldav.web.de/begenda/dav/"}),
  anbieter("icloud", "iCloud", {domains: ["icloud.com"], caldav_url: "https://caldav.icloud.com/", app_password: true}),
  anbieter("gmail", "Gmail", {domains: ["gmail.com"], caldav_note: "Google lässt den Kalender nicht mit Passwort verbinden.", kalender_ical: true}),
  anbieter("outlook", "Outlook", {domains: ["outlook.com"], caldav_note: "Microsoft lässt den Kalender nicht mit Passwort verbinden."}),
  anbieter("yahoo", "Yahoo", {domains: ["yahoo.de"]}),
];

test("Erst mit vollständiger Adresse gibt es einen Weg", () => {
  assert.equal(kalenderWeg("lena.probe@web", KATALOG).art, "unvollstaendig");
  assert.equal(kalenderWeg("", KATALOG).art, "unvollstaendig");
});

test("Bekannter Anbieter: nur das Passwort, App-Passwort wo nötig", () => {
  const web = kalenderWeg("lena.probe@web.de", KATALOG);
  assert.equal(web.art, "bekannt");
  assert.equal(web.anbieter.label, "WEB.DE");
  assert.equal(web.passwortLabel, "Passwort");
  assert.equal(kalenderWeg("lena.probe@icloud.com", KATALOG).passwortLabel, "App-Passwort");
});

test("Google: der Kalender geht über seine geheime iCal-Adresse, ohne Passwort (Befund 2)", () => {
  const weg = kalenderWeg("lena.probe@gmail.com", KATALOG);
  assert.equal(weg.art, "google_ical");
  assert.equal(weg.anbieter.id, "gmail");
  // Google Workspace mit eigener Domain: erkannt hat es der Sidecar am Mailserver, der Weg ist derselbe.
  assert.equal(kalenderWeg("lena.probe@praxis-probe.example", KATALOG, false, KATALOG[2]).art, "google_ical");
});

test("Microsoft sagt ehrlich, dass es mit Passwort nicht geht", () => {
  const weg = kalenderWeg("lena.probe@outlook.com", KATALOG);
  assert.equal(weg.art, "kein_zugang");
  assert.match(weg.satz, /Microsoft/);
});

test("Ohne bekannte Adresse fragt die Karte nach ihr, statt zu raten", () => {
  assert.equal(kalenderWeg("lena.probe@yahoo.de", KATALOG).art, "adresse_fehlt");
  assert.equal(kalenderWeg("lena.probe@eigene-domain.example", KATALOG, true).art, "adresse_fehlt");
  // Hat der Server die Adresse verlangt (nichts gefunden), gilt das auch für einen bekannten Anbieter.
  assert.equal(kalenderWeg("lena.probe@web.de", KATALOG, true).art, "adresse_fehlt");
  assert.equal(ADRESSE_FEHLT, "Für diesen Anbieter brauche ich die Adresse deines Kalenders.");
});

test("Eigene Domain: erst selbst suchen, dann nach der Adresse fragen (Fremdprobe 2, Befund 5)", () => {
  assert.equal(kalenderWeg("lena.probe@eigene-domain.example", KATALOG).art, "selbst_suchen");
  // Den Mailserver hat der Sidecar selbst gefunden (SRV, Autoconfig): derselbe Weg.
  const gefunden = anbieter("gefunden", "mail.example.org");
  assert.equal(kalenderWeg("lena.probe@example.org", KATALOG, false, gefunden).art, "selbst_suchen");
  assert.equal(kalenderWeg("lena.probe@example.org", KATALOG, true, gefunden).art, "adresse_fehlt");
  assert.match(SELBST_SUCHEN, /Mailserver deiner Domain/);
  assert.match(ADRESSE_WO, /überspringen/);
  assert.ok(MICROSOFT_EINSTELLUNGEN.privat.startsWith("https://outlook.live.com/") && MICROSOFT_EINSTELLUNGEN.organisation.startsWith("https://outlook.office.com/"));
});

test("Das Passwort des Postfachs gilt nur für dieselbe Adresse und nur, wenn eines hinterlegt ist", () => {
  const konten = [{id: "a", user: "Lena.Probe@web.de", secret_present: true}, {id: "b", user: "ohne@web.de", secret_present: false}];
  assert.equal(postfachZurAdresse(" lena.probe@web.de ", konten)?.id, "a");
  assert.equal(postfachZurAdresse("ohne@web.de", konten), null);
  assert.equal(postfachZurAdresse("jemand@web.de", konten), null);
});

test("Nach dem Verbinden ein Satz, was gefunden wurde", () => {
  assert.equal(verbundenSatz(["Privat"], 1), "Verbunden: dein Kalender „Privat“.");
  assert.equal(verbundenSatz(["Privat", "Arbeit"], 2), "Verbunden: 2 Kalender (Privat, Arbeit).");
  assert.equal(verbundenSatz(["Privat"], 0), "Schon verbunden: Privat.");
});
