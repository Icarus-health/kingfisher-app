// „Dieser Rechner“ (Fremdprobe, Befunde 10 und 11): Fähigkeiten statt Modellnamen, Status passend zum Text,
// die Ausstattung ermittelt das Programm, „Anderes Modell nehmen“ nach nicht bestandener Prüfung.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";
import {FAEHIGKEITEN, abschluss, ausstattungSatz, faehigkeitStand, laeufeAus, ladeSatz, ladenLaeuftSatz, laufAus, naechsteWahl,
  offeneRollen, probleme} from "../src/Einrichtung/rechner.ts";

const eintrag = (name, groesse_gb = 1) => ({name, groesse_gb, speicher_gb: 2, art: "klein", begruendung: "", passt: true, bestaetigung: ""});
const zeile = (rolle, status = "fehlt", name = `${rolle}-modell`, ausweich = []) => ({rolle, titel: rolle, beschreibung: "", empfohlen: eintrag(name, 2),
  alternativen: [], status, wirksam: {modell: null, lokal: null, quelle: "keins"}, ausweich});
const ZEILEN = ["frage", "antwort", "pruefung", "hintergrund", "einbettung"].map(rolle => zeile(rolle));
const pull = (rolle, phase, extra = {}) => ({id: "p", modell: `${rolle}-modell`, rolle, phase, fortschritt: null, text: "", fehler: null, ergebnis: null, ...extra});

test("Drei Fähigkeiten decken alle Aufgaben genau einmal ab", () => {
  assert.deepEqual(FAEHIGKEITEN.flatMap(f => f.rollen).sort(), ["antwort", "einbettung", "frage", "hintergrund", "pruefung"]);
  for (const f of FAEHIGKEITEN) assert.doesNotMatch(f.titel + f.satz, /Modell|Messlatte|nachts|GB|Ollama|Rolle/);
});

test("Nicht bestanden heißt nicht „Fehlt“, und Laden zeigt den Fortschritt", () => {
  const pruefen = FAEHIGKEITEN.find(f => f.id === "pruefen");
  const nicht = laufAus(pull("pruefung", "fehler", {fehler: {grund: "…", naechster_schritt: "…", art: "pruefung"}}));
  assert.equal(nicht.nichtBestanden, true);
  assert.deepEqual(faehigkeitStand(pruefen, ZEILEN, {pruefung: nicht}), {art: "nicht_bestanden", text: "Prüfung nicht bestanden"});
  assert.doesNotMatch(nicht.satz, /Messlatte|Alternativen/);
  const laedt = laufAus(pull("pruefung", "laedt", {fortschritt: 0.4}));
  assert.deepEqual(faehigkeitStand(pruefen, ZEILEN, {pruefung: laedt}), {art: "laedt", text: "Wird geladen … 40 %"});
  assert.deepEqual(faehigkeitStand(pruefen, ZEILEN, {}), {art: "offen", text: "Noch nicht eingerichtet"});
  assert.deepEqual(faehigkeitStand(pruefen, [zeile("pruefung", "eingerichtet")], {}), {art: "bereit", text: "Bereit"});
  // Ein anderer Ladefehler (kein Platz) ist kein „nicht bestanden“ und nennt seinen Grund.
  const platz = laufAus(pull("pruefung", "fehler", {fehler: {grund: "Kein Platz.", naechster_schritt: "Platz schaffen."}}));
  assert.equal(platz.nichtBestanden, false);
  assert.equal(platz.satz, "Kein Platz. Platz schaffen.");
});

test("Antworten ist erst bereit, wenn alle drei Aufgaben dazu bereit sind", () => {
  const antworten = FAEHIGKEITEN.find(f => f.id === "antworten");
  const zeilen = [zeile("frage", "eingerichtet"), zeile("antwort", "eingerichtet"), zeile("einbettung")];
  assert.equal(faehigkeitStand(antworten, zeilen, {}).art, "offen");
  assert.equal(faehigkeitStand(antworten, zeilen, {einbettung: laufAus(pull("einbettung", "fertig"))}).art, "bereit");
});

test("Die Ausstattung in einem Satz, ohne Chip und ohne Frage an den Menschen", () => {
  const geraet = (extra) => ({plattform: "linux", chip: null, arbeitsspeicher_gb: 16, bekannt: true, stufe_gb: 16, stufen: [], ...extra});
  assert.equal(ausstattungSatz(geraet({quelle: "eigene"})), "Dieser Rechner hat 16 GB Arbeitsspeicher; danach wählt Kingfisher aus.");
  assert.equal(ausstattungSatz(geraet({quelle: "untergrenze", arbeitsspeicher_gb: 7.7})), "Kingfisher sieht hier mindestens 7,7 GB Arbeitsspeicher und wählt danach.");
  const unbekannt = ausstattungSatz(geraet({bekannt: false, arbeitsspeicher_gb: null, quelle: "unbekannt"}));
  assert.doesNotMatch(unbekannt, /gemeldet|melde/);
});

test("Größe und Dauer des Ladens aus einer Quelle; nichts zu laden heißt leer (Fremdprobe 2, Befund 6)", () => {
  const orchester = (gesamt, noch, frei = 120) => ({festplatte_gb: gesamt, festplatte_noch_gb: noch, festplatte_frei_gb: frei});
  assert.match(ladeSatz(orchester(14, 14)), /^Einmal laden: etwa 14 GB, je nach Internetleitung 4 bis 20 Minuten\. Das Laden läuft im Hintergrund weiter; du machst gleich mit der Einrichtung weiter\. Frei sind etwa 120 GB\.$/);
  // Nach einem Fehlschlag liegt ein Teil schon da: keine kleinere Zahl ohne Erklärung.
  assert.match(ladeSatz(orchester(14, 1.2, null)), /^Noch zu laden: etwa 1,2 von 14 GB; der Rest liegt schon auf diesem Rechner\./);
  assert.equal(ladeSatz(orchester(14, 0)), "");
  assert.deepEqual(offeneRollen([zeile("frage", "eingerichtet"), zeile("antwort", "installiert")]), ["antwort"]);
});

const auftrag = (rolle, phase, extra = {}) => pull(rolle, phase, extra);
const laden = (auftraege, laeuft = false, prozent = 100) => ({laeuft, prozent, gesamt_gb: 14, satz: "", auftraege,
  eingerichtet: auftraege.filter(a => a.phase === "fertig").map(a => a.rolle), fehlgeschlagen: auftraege.filter(a => a.phase === "fehler").map(a => a.rolle)});
const NICHT = {grund: "…", naechster_schritt: "…", art: "pruefung"};

test("Am Ende genau ein Satz: alles, teilweise oder nichts; nie „Fast alles“ (Fremdprobe 2, Befund 7)", () => {
  assert.equal(abschluss(null), null);
  assert.equal(abschluss(laden([auftrag("frage", "laedt")], true, 40)), null);
  assert.deepEqual(abschluss(laden([auftrag("frage", "fertig"), auftrag("antwort", "fertig")])), {ok: true, text: "Alles eingerichtet und geprüft.", nochmal: false});
  const nichts = abschluss(laden(["frage", "antwort", "pruefung"].map(r => auftrag(r, "fehler", {fehler: NICHT}))));
  assert.equal(nichts.ok, false);
  assert.equal(nichts.nochmal, true);
  assert.match(nichts.text, /^Nichts ist eingerichtet/);
  const teil = abschluss(laden([auftrag("frage", "fertig"), auftrag("antwort", "fehler", {fehler: NICHT})]));
  assert.match(teil.text, /^Teilweise eingerichtet: 1 von 2 Aufgaben\./);
  for (const ende of [nichts, teil]) assert.doesNotMatch(ende.text, /Fast alles/);
  assert.equal(ladenLaeuftSatz({prozent: 60}).startsWith("Kingfisher lädt sein Sprachmodell: 60 %."), true);
});

test("Jedes Problem steht einmal, nicht je Aufgabe einer Fähigkeit (Befund 7)", () => {
  const laeufe = laeufeAus(laden(["frage", "antwort", "einbettung", "pruefung"].map(r => auftrag(r, "fehler", {fehler: NICHT}))));
  const liste = probleme(ZEILEN, laeufe);
  assert.deepEqual(liste.map(p => p.titel), ["Deine Fragen beantworten", "Antworten prüfen"]);
});

test("Anderes Modell nehmen versucht jedes Modell höchstens einmal", () => {
  const z = zeile("pruefung", "installiert", "klein:1b", [eintrag("mittel:4b"), eintrag("gross:7b")]);
  assert.equal(naechsteWahl(z, ["klein:1b"])?.name, "mittel:4b");
  assert.equal(naechsteWahl(z, ["klein:1b", "mittel:4b"])?.name, "gross:7b");
  assert.equal(naechsteWahl(z, ["klein:1b", "mittel:4b", "gross:7b"]), null);
});

test("Vorne keine Modellnamen: der Schritt nutzt die Karte mit Fähigkeiten, Namen nur im Aufklapper", () => {
  const schritt = readFileSync(new URL("../src/Einrichtung/ModellSchritt.tsx", import.meta.url), "utf8");
  assert.doesNotMatch(schritt, /ModelRecommendation/);
  const karte = readFileSync(new URL("../src/Einrichtung/RechnerKarte.tsx", import.meta.url), "utf8");
  const vorne = karte.slice(0, karte.indexOf('<details className="rechner-techniker">'));
  assert.doesNotMatch(vorne.replace(/\/\*[\s\S]*?\*\//g, ""), /empfohlen\.name\}|Messlatte|nachts/);
  assert.match(karte, /Anderes Modell nehmen/);
});
