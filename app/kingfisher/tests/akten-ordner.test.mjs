import {test} from "node:test";
import assert from "node:assert/strict";
import {aussage, kurzerPfad, unterwegs} from "../src/aktenOrdner.ts";

const stand = (extra = {}) => ({aktiv: true, quellen: false, ordner: "/Users/anna/Documents/Kingfisher/Akten", ordnername: "Kingfisher Akten",
  vorgabe: "Dokumente/Kingfisher/Akten", laeuft: false, running: true, pick_request: null,
  stand: {erzeugt_am: "2026-09-30T09:00:00+00:00", dateien: 14, akten: 11, mit_quellen: false, uebersprungen: 0},
  gespiegelt: {am: "2026-09-30T09:01:00+00:00", dateien: 14}, angekommen: true, fehler: null, ...extra});

test("Ohne Ordner sagt die Karte nichts zum Stand und fragt nicht nach", () => {
  assert.equal(aussage(stand({ordner: null, stand: null, gespiegelt: null, angekommen: false, aktiv: false})), null);
  assert.equal(unterwegs(null), false);
  assert.equal(unterwegs(stand({ordner: null, aktiv: false, stand: null, angekommen: false})), false);
});

test("Angekommen: letzter Stand mit Dateizahl, ruhig", () => {
  const a = aussage(stand());
  assert.match(a.text, /^Zuletzt geschrieben: .+, 14 Dateien\.$/);
  assert.equal(a.fehler, false);
  assert.equal(a.ruhig, true);
  assert.equal(unterwegs(stand()), false);
});

test("Unterwegs: der Helfer fehlt, der Helfer schreibt, der Lauf läuft", () => {
  const bereit = stand({angekommen: false, gespiegelt: null});
  assert.match(aussage({...bereit, running: true}).text, /14 Dateien sind bereit und werden jetzt in den Ordner geschrieben/);
  assert.match(aussage({...bereit, running: false}).text, /Der Helfer der Kingfisher-App, der den Ordner schreibt, meldet sich gerade nicht/);
  assert.doesNotMatch(aussage({...bereit, running: false}).text, /Mac/);
  assert.equal(aussage({...bereit, running: false}, "Gibt es hier nicht.").text, "14 Dateien sind bereit. Gibt es hier nicht.");
  assert.equal(unterwegs(bereit), true);
  assert.match(aussage(stand({laeuft: true})).text, /werden gerade geschrieben/);
  assert.equal(unterwegs(stand({laeuft: true})), true);
  assert.equal(unterwegs(stand({pick_request: {id: "x", modus: "waehlen"}, ordner: null})), true);
});

test("Ein Grund wird als Grund gezeigt und löst keine Dauerabfrage aus", () => {
  const kaputt = stand({angekommen: false, fehler: "Im Ordner liegt schon „Kingfisher Akten“ mit anderem Inhalt. Bitte einen anderen Ordner wählen."});
  const a = aussage(kaputt);
  assert.equal(a.fehler, true);
  assert.match(a.text, /mit anderem Inhalt/);
  assert.equal(unterwegs(kaputt), false);
});

test("Ausgeschaltet heißt: es wird nichts geschrieben", () => {
  assert.match(aussage(stand({aktiv: false})).text, /^Ausgeschaltet\./);
  assert.match(aussage(stand({aktiv: false, gespiegelt: null, angekommen: false})).text, /Es wird nichts geschrieben/);
  assert.equal(unterwegs(stand({aktiv: false, angekommen: false})), false);
});

test("Nicht geschriebene Akten werden genannt, nie verschwiegen", () => {
  const eine = stand({stand: {erzeugt_am: null, dateien: 3, akten: 2, mit_quellen: false, uebersprungen: 1}, gespiegelt: {am: null, dateien: 3}});
  assert.match(aussage(eine).text, /Eine Akte konnte nicht geschrieben werden/);
});

test("Pfade ohne Benutzerverzeichnis und Dateizahl im Singular", () => {
  assert.equal(kurzerPfad("/Users/anna/Documents/Kingfisher/Akten/"), "~/Documents/Kingfisher/Akten");
  assert.equal(kurzerPfad("/Volumes/Vault"), "~/Volumes/Vault");
  assert.match(aussage(stand({gespiegelt: {am: null, dateien: 1}})).text, /1 Datei\.$/);
});
