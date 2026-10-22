// Mitteilungen auf dem Mac (Etappe 5, docs/24): der Schalter unter „Was Kingfisher darf“, die Uhrzeit, der Wochen-Satz
// und der Hinweis, wenn der Mac die Erlaubnis verweigert. Reine Logik in src/mitteilungenSchalter.ts.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { SCHALTER, VORDERE_DATEIEN } from "../src/Einstellungen/gliederung.ts";
import { UHRZEIT_VORGABE, erlaubnisHinweis, mitteilungenSchalter, uhrzeitGueltig, wochenSatz } from "../src/mitteilungenSchalter.ts";

const quelle = (datei) => readFileSync(new URL(`../src/${datei}`, import.meta.url), "utf8");
const MAC = { art: "mac" };
const DOCKER = { art: "docker" };

test("der Schalter steht bei den anderen, Vorgabe aus, und sagt, dass nichts den Rechner verlässt", () => {
  assert.equal(SCHALTER.mitteilungen.titel, "Mitteilungen auf dem {Rechner}");
  assert.match(SCHALTER.mitteilungen.verlaesst, /^Es verlässt nichts den Rechner\./);
  assert.match(SCHALTER.mitteilungen.verlaesst, /Morgens eine Mitteilung/);
  assert.match(SCHALTER.mitteilungen.verlaesst, /höchstens zwei dringende/);
  assert.match(quelle("Einstellungen/Darf.tsx"), /<Mitteilungen \/>/);
  assert.ok(VORDERE_DATEIEN.includes("Einstellungen/Mitteilungen.tsx") && VORDERE_DATEIEN.includes("mitteilungenSchalter.ts"));
  const stand = mitteilungenSchalter({ an: false, morgens: "07:30", erlaubnis: "unbekannt", woche: { gesendet: 0, ueberfluessig: 0 } }, MAC);
  assert.deepEqual(stand, { an: false, gesperrt: false, hinweis: null });
});

test("die Uhrzeit ist HH:MM vor der Ruhezeit, Vorgabe 07:30", () => {
  assert.equal(UHRZEIT_VORGABE, "07:30");
  for (const gut of ["07:30", "00:00", "20:59", "08:15"]) assert.ok(uhrzeitGueltig(gut), gut);
  for (const schlecht of ["7:30", "21:00", "25:00", "07:60", "", "0730", "07:30 Uhr"]) assert.ok(!uhrzeitGueltig(schlecht), schlecht);
});

test("der Wochen-Satz zählt in Alltagssprache", () => {
  assert.equal(wochenSatz({ gesendet: 0, ueberfluessig: 0 }), "Diese Woche keine Mitteilung.");
  assert.equal(wochenSatz({ gesendet: 1, ueberfluessig: 0 }), "Diese Woche 1 Mitteilung, keine als überflüssig gemeldet.");
  assert.equal(wochenSatz({ gesendet: 5, ueberfluessig: 1 }), "Diese Woche 5 Mitteilungen, davon 1 als überflüssig gemeldet.");
  assert.equal(wochenSatz({ gesendet: 5, ueberfluessig: 3 }), "Diese Woche 5 Mitteilungen, davon 3 als überflüssig gemeldet.");
});

test("fehlt die Systemerlaubnis, steht da, wo man sie gibt; ohne Mac-App ist der Schalter gesperrt und sagt warum", () => {
  const woche = { gesendet: 0, ueberfluessig: 0 };
  assert.equal(erlaubnisHinweis({ an: true, erlaubnis: "abgelehnt" }, MAC),
    "Der Mac hat Mitteilungen für Kingfisher nicht erlaubt. Systemeinstellungen → Mitteilungen → Kingfisher.");
  assert.equal(erlaubnisHinweis({ an: true, erlaubnis: "erlaubt" }, MAC), null);
  assert.equal(erlaubnisHinweis({ an: false, erlaubnis: "abgelehnt" }, MAC), null, "aus: kein Hinweis");
  assert.match(erlaubnisHinweis({ an: true, erlaubnis: "unbekannt" }, MAC), /Kingfisher-App/);
  const an = mitteilungenSchalter({ an: true, morgens: "07:30", erlaubnis: "abgelehnt", woche }, MAC);
  assert.equal(an.an, true); assert.equal(an.gesperrt, false); assert.match(an.hinweis, /^Der Mac hat Mitteilungen/);
  const docker = mitteilungenSchalter({ an: false, morgens: "07:30", erlaubnis: "unbekannt", woche }, DOCKER);
  assert.equal(docker.gesperrt, true);
  assert.equal(docker.hinweis, "Mitteilungen gibt es nur in der Kingfisher-App auf dem Mac, nicht im Browser mit Docker.");
  // Einmal eingeschaltet, lässt sich der Schalter überall ausschalten.
  assert.equal(mitteilungenSchalter({ an: true, morgens: "07:30", erlaubnis: "unbekannt", woche }, DOCKER).gesperrt, false);
});

test("die Karte zeigt Uhrzeit, Wochen-Satz und Hinweis aus der Logik", () => {
  const code = quelle("Einstellungen/Mitteilungen.tsx");
  assert.match(code, /wochenSatz\(/);
  assert.match(code, /mitteilungenSchalter\(/);
  assert.match(code, /type="time"/);
  assert.match(code, /role="switch"/);
  assert.match(code, /fuerSystem\(SCHALTER\.mitteilungen\.titel, system\)/);
  assert.match(code, /api\.mitteilungenSetzen\(/);
});
