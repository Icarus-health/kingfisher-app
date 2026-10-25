import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {SCHRITTE, VORSCHLAG_HERKUNFT, namensStart, namensVorschlag, schrittTitel, sichtbareSchritte, anbieterZurAdresse, namensEntwurf, ersterOffener, istSchritt, nachbar, naechsterHinweis, offeneSchritte, schrittStand, schrittZaehler, sollZeigen, startSchritt} from "../src/Einrichtung/schritte.ts";

const stand = (extra = {}) => ({name: "", schritte: {}, abgeschlossen: false, zeigen: true,
  vorhanden: {mail: false, kalender: false, modell: false}, ...extra});

test("Die Reihenfolge ist Name, Mail, Kalender, Rechner, Freigaben, Anmelden, Fertig", () => {
  assert.deepEqual(SCHRITTE.map(schritt => schritt.id), ["name", "mail", "kalender", "modell", "freigaben", "autostart", "fertig"]);
  // Kein Fachwort in den Titeln, die der Nutzer liest.
  for (const schritt of SCHRITTE) assert.doesNotMatch(schritt.titel + schritt.kurz, /IMAP|Host|Port|Modellrouting|Token|Sidecar|Provider/i);
});

test("Frischer Bestand beginnt beim Namen", () => {
  assert.equal(ersterOffener(stand()), "name");
  assert.equal(startSchritt(stand()), "name");
});

test("Überspringen zählt als Fortschritt: der nächste offene Schritt ist dran", () => {
  const s = stand({schritte: {name: "uebersprungen", mail: "uebersprungen"}});
  assert.equal(ersterOffener(s), "kalender");
  assert.equal(schrittStand("mail", s), "uebersprungen");
});

test("Wiederaufnahme: dort weitermachen, wo man aufgehört hat", () => {
  const s = stand({name: "Lea", schritte: {name: "erledigt", mail: "erledigt", kalender: "uebersprungen"}});
  assert.equal(startSchritt(s), "modell");
  assert.equal(startSchritt(s, null), "modell");
});

test("Ein ausdrücklich gewünschter Schritt geht vor (Link „Mail verbinden“ auf der Startseite)", () => {
  assert.equal(startSchritt(stand({name: "Lea"}), "kalender"), "kalender");
  // Unsinn in der Adresse fällt auf den ersten offenen Schritt zurück.
  assert.equal(startSchritt(stand(), "ufo"), "name");
  assert.equal(istSchritt("mail"), true);
  assert.equal(istSchritt("ufo"), false);
});

test("Was schon da ist, zählt als erledigt, auch ohne Assistenten", () => {
  const s = stand({name: "Lea", vorhanden: {mail: true, kalender: true, modell: false}});
  assert.equal(schrittStand("name", s), "erledigt");
  assert.equal(schrittStand("mail", s), "erledigt");
  assert.equal(schrittStand("kalender", s), "erledigt");
  assert.equal(ersterOffener(s), "modell");
});

test("Sind alle Schritte getan oder übersprungen, ist „fertig“ dran", () => {
  const s = stand({schritte: {name: "erledigt", mail: "uebersprungen", kalender: "uebersprungen", modell: "uebersprungen", freigaben: "uebersprungen", autostart: "uebersprungen"}});
  assert.equal(ersterOffener(s), "fertig");
  assert.deepEqual(offeneSchritte(s), []);
});

test("Ein wieder geöffneter Schritt ist wieder offen", () => {
  assert.equal(schrittStand("mail", stand({schritte: {}})), "offen");
  assert.deepEqual(offeneSchritte(stand({name: "Lea"})).map(schritt => schritt.id), ["mail", "kalender", "modell", "freigaben", "autostart"]);
});

test("Weiter und Zurück bleiben in den Grenzen", () => {
  assert.equal(nachbar("name", -1), "name");
  assert.equal(nachbar("name", 1), "mail");
  assert.equal(nachbar("fertig", 1), "fertig");
  assert.equal(nachbar("fertig", -1), "autostart");
});

test("Schrittzähler zählt, was die Schrittleiste zeigt (Befund 27)", () => {
  assert.deepEqual(schrittZaehler("name"), {nummer: 1, gesamt: SCHRITTE.length});
  assert.deepEqual(schrittZaehler("mail"), {nummer: 2, gesamt: 7});
  assert.deepEqual(schrittZaehler("fertig"), {nummer: 7, gesamt: 7});
});

test("Später weitermachen nimmt den getippten Namen mit (Befund 21)", () => {
  assert.deepEqual(namensEntwurf("  Lena ", ""), {name: "Lena"});
  assert.equal(namensEntwurf("Lena", "Lena"), null);
  assert.equal(namensEntwurf("   ", "Lena"), null);
});

test("Der Assistent geht nur auf, wenn der Sidecar es sagt", () => {
  assert.equal(sollZeigen(null), false);
  assert.equal(sollZeigen(stand({zeigen: false})), false);
  assert.equal(sollZeigen(stand()), true);
});

test("Leere Startseite: genau ein nächster Schritt, Mail zuerst", () => {
  const nichts = {mail: false, kalender: false, modell: false};
  const h = naechsterHinweis(nichts, false);
  assert.equal(h.schritt, "mail");
  assert.equal(h.text, "Mail verbinden, dann kann ich dir morgen früh sagen, was wichtig ist.");
  // Ohne Mail bleibt es bei Mail, auch wenn sonst etwas läuft.
  assert.equal(naechsterHinweis(nichts, true).schritt, "mail");
  assert.equal(naechsterHinweis({mail: true, kalender: false, modell: false}, false).schritt, "kalender");
  assert.equal(naechsterHinweis({mail: true, kalender: true, modell: false}, false).schritt, "modell");
  assert.equal(naechsterHinweis({mail: true, kalender: true, modell: true}, false), null);
});

test("Während die Mails gelesen werden, zeigt die Startseite den Fortschritt statt eines weiteren Hinweises", () => {
  assert.equal(naechsterHinweis({mail: true, kalender: false, modell: false}, true), null);
});

test("Der Anbieter wird an der Adresse erkannt, nie nach einem Server gefragt", () => {
  const liste = [{id: "gmx", label: "GMX", domains: ["gmx.de", "gmx.net"]}, {id: "gmail", label: "Gmail", domains: ["gmail.com"]}, {id: "alt"}];
  assert.equal(anbieterZurAdresse("lea@GMX.de", liste).id, "gmx");
  assert.equal(anbieterZurAdresse(" lea@gmail.com", liste).id, "gmail");
  assert.equal(anbieterZurAdresse("lea@eigene-firma.example", liste), null);
  assert.equal(anbieterZurAdresse("lea", liste), null);
  assert.equal(anbieterZurAdresse("lea@", liste), null);
});

test("Ohne Autostart-Helfer entfällt „Beim Anmelden“, und die Zählung bleibt stimmig (Befund 26)", () => {
  const ohne = stand({autostart_verfuegbar: false});
  assert.deepEqual(sichtbareSchritte(ohne).map(schritt => schritt.id), ["name", "mail", "kalender", "modell", "freigaben", "fertig"]);
  assert.deepEqual(schrittZaehler("freigaben", ohne), {nummer: 5, gesamt: 6});
  assert.deepEqual(schrittZaehler("fertig", ohne), {nummer: 6, gesamt: 6});
  assert.equal(schrittZaehler("autostart", ohne), null);
  assert.equal(nachbar("freigaben", 1, ohne), "fertig");
  assert.equal(nachbar("fertig", -1, ohne), "freigaben");
  // Wer bis zu den Freigaben durch ist, landet bei „Fertig“, nicht in einem unsichtbaren Schritt.
  const durch = stand({autostart_verfuegbar: false, schritte: {name: "erledigt", mail: "uebersprungen", kalender: "uebersprungen", modell: "uebersprungen", freigaben: "erledigt"}});
  assert.equal(ersterOffener(durch), "fertig");
  assert.deepEqual(offeneSchritte(durch), []);
  // Ein Verweis auf den ausgeblendeten Schritt führt zum ersten offenen.
  assert.equal(startSchritt(ohne, "autostart"), "name");
  // Auf dem Mac (Helfer da) und ohne Angabe bleibt die Frage stehen: sieben Schritte.
  assert.equal(sichtbareSchritte(stand({autostart_verfuegbar: true})).length, 7);
  assert.equal(sichtbareSchritte(stand()).length, 7);
  assert.deepEqual(schrittZaehler("autostart", stand({autostart_verfuegbar: true})), {nummer: 6, gesamt: 7});
});

// -- V3: vorschlagen statt fragen ---------------------------------------------------------------------------------
const LEA = {name: "Lea Hartmann", vorname: "Lea", quelle: "postfach"};

test("Mit gefundenem Namen: „Hallo Lea.“ und der Vorname im Feld; ohne Quelle die Frage mit leerem Feld", () => {
  const mit = stand({name_vorschlag: LEA});
  assert.equal(schrittTitel("name", mit), "Hallo Lea.");
  assert.equal(namensStart(mit), "Lea");
  assert.deepEqual(namensVorschlag(mit), LEA);
  for (const ohne of [stand(), stand({name_vorschlag: null}), stand({name_vorschlag: {...LEA, vorname: "  "}})]) {
    assert.equal(schrittTitel("name", ohne), "Wie heißt du?");
    assert.equal(namensStart(ohne), "");
    assert.equal(namensVorschlag(ohne), null);
  }
  // Andere Schritte behalten ihren Titel.
  assert.equal(schrittTitel("mail", mit), "Deine Mail verbinden");
});

test("Ein gespeicherter Name geht dem Vorschlag vor; der Vorschlag allein erledigt den Schritt nicht", () => {
  const gespeichert = stand({name: "Leonie", name_vorschlag: LEA});
  assert.equal(namensVorschlag(gespeichert), null);
  assert.equal(namensStart(gespeichert), "Leonie");
  assert.equal(schrittTitel("name", gespeichert), "Wie heißt du?");
  // Kein Fakt ohne Bestätigung: Solange nur vorgeschlagen ist, bleibt der Schritt offen und der Assistent beginnt dort.
  const vorgeschlagen = stand({name_vorschlag: LEA});
  assert.equal(schrittStand("name", vorgeschlagen), "offen");
  assert.equal(ersterOffener(vorgeschlagen), "name");
  // Ein unberührter Vorschlag ist kein Entwurf, den „Später weitermachen“ speichern würde.
  assert.equal(namensEntwurf("", ""), null);
});

test("Der Satz zur Herkunft nennt die Quelle und keinen festen Mac", () => {
  assert.deepEqual(Object.keys(VORSCHLAG_HERKUNFT).sort(), ["postfach", "rechner", "umgebung"]);
  assert.match(VORSCHLAG_HERKUNFT.rechner, /\{Rechner\}/);
  for (const satz of Object.values(VORSCHLAG_HERKUNFT)) assert.doesNotMatch(satz, /\bMac\b|„|"/);
});

test("Der Namensschritt speichert nur über „Weiter“ und bietet den Vorschlag im Feld an", () => {
  const code = readFileSync(new URL("../src/Einrichtung/NameSchritt.tsx", import.meta.url), "utf8");
  assert.match(code, /useState\(\(\) => namensStart\(stand\)\)/);
  // Gespeichert wird nur im Absenden; der Vorschlag wird nicht beim Öffnen als Entwurf gemerkt.
  assert.equal((code.match(/weiter\(\{name/g) ?? []).length, 1);
  assert.doesNotMatch(code, /entwurf\(namensEntwurf\(namensStart|useEffect/);
  const erststart = readFileSync(new URL("../src/Einrichtung/Erststart.tsx", import.meta.url), "utf8");
  assert.match(erststart, /schrittTitel\(info\.id, stand\)/);
});
