// Paket P4 (Nachrichten und Kalender): Anzeige wie in Apple Mail und Apple Kalender. Nur Darstellung; synthetische Daten.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { postfachDatum } from "../src/postfachAnzeige.ts";
import { ganztaegig, nachTagen, terminZeit } from "../src/calendarAnzeige.ts";

const quelle = (datei) => readFileSync(new URL(`../src/${datei}`, import.meta.url), "utf8");
process.env.TZ = "Europe/Berlin";

test("N1: Datum rechts in der Postfachzeile wie in Apple Mail", () => {
  const jetzt = new Date("2026-09-29T07:31:00+02:00");
  assert.equal(postfachDatum("2026-09-29T06:48:00+02:00", jetzt), "06:48");
  assert.equal(postfachDatum("2026-09-28T17:05:00+02:00", jetzt), "Gestern");
  assert.equal(postfachDatum("2026-09-26T09:00:00+02:00", jetzt), "Samstag");
  assert.equal(postfachDatum("2026-09-22T09:00:00+02:00", jetzt), "22.09.26");
  assert.equal(postfachDatum(null, jetzt), "Ohne Datum");
  assert.equal(postfachDatum("kaputt", jetzt), "Ohne Datum");
});

test("K9: Termindetails sagen in einer Zeile, wann; ganztägig ohne einen Tag zu viel", () => {
  assert.equal(terminZeit({start: "2026-09-09T10:00:00+02:00", end: "2026-09-09T11:00:00+02:00", all_day: false}),
    "Mittwoch, 9. September 2026 · 10:00–11:00");
  // Ganztägig: das Ende ist der erste Tag danach.
  assert.equal(terminZeit({start: "2026-10-03T00:00:00+02:00", end: "2026-10-04T00:00:00+02:00", all_day: true}),
    "Ganztägig · Samstag, 3. Oktober 2026");
  assert.equal(terminZeit({start: "2026-10-03T00:00:00+02:00", end: "2026-10-06T00:00:00+02:00", all_day: true}),
    "Ganztägig · Samstag, 3. Oktober 2026 bis Montag, 5. Oktober 2026");
  // Geburtstag als 00:00–23:59 geliefert: ganztägig, ein Tag.
  assert.equal(terminZeit({start: "2026-10-03T00:00:00+02:00", end: "2026-10-03T23:59:00+02:00", all_day: false}),
    "Ganztägig · Samstag, 3. Oktober 2026");
  assert.equal(terminZeit({start: "2026-10-03T00:00:00+02:00", end: "2026-10-05T23:59:00+02:00", all_day: false}),
    "Ganztägig · Samstag, 3. Oktober 2026 bis Montag, 5. Oktober 2026");
  assert.equal(terminZeit({start: "2026-09-30T22:00:00+02:00", end: "2026-10-01T01:00:00+02:00", all_day: false}),
    "Mi., 30. Sept., 22:00 – Do., 1. Okt., 01:00");
  assert.equal(terminZeit({start: null, end: null, all_day: false}), "Beginn unbekannt");
});

test("K2: ein Termin über den ganzen Tag steht in der Ganztagszeile, nicht als Block über das Raster", () => {
  assert.equal(ganztaegig({start: "2026-10-03T00:00:00+02:00", end: "2026-10-03T23:59:00+02:00", all_day: false}), true);
  assert.equal(ganztaegig({start: "2026-10-03T00:00:00+02:00", end: "2026-10-03T12:00:00+02:00", all_day: false}), false);
  assert.equal(ganztaegig({start: "2026-10-03T08:00:00+02:00", end: "2026-10-04T08:00:00+02:00", all_day: false}), false);
  assert.equal(ganztaegig({start: "2026-10-03T00:00:00+02:00", end: null, all_day: true}), true);
  const page = quelle("CalendarPage.tsx");
  assert.match(page, /calendarDayLayout\(onDay\(day\)\.filter\(event=>!ganztaegig\(event\)\),day\)/);
  assert.match(page, /onDay\(day\)\.filter\(ganztaegig\)/);
});

test("K4: die Liste steht nach Tagen, jede Zeile öffnet die Details", () => {
  const termine = [{start: "2026-09-30T14:00:00+02:00", id: 1}, {start: "2026-09-30T19:30:00+02:00", id: 2}, {start: "2026-10-03T00:00:00+02:00", id: 3}, {start: null, id: 4}];
  const gruppen = nachTagen(termine);
  assert.deepEqual(gruppen.map(g => g.termine.map(t => t.id)), [[1, 2], [3], [4]]);
  assert.equal(gruppen[0].tag.getDate(), 30);
  assert.equal(gruppen[2].tag, null);
  const page = quelle("CalendarPage.tsx");
  assert.match(page, /<button type="button" className="calendar-entry" key=\{calendarEventKey\(item\)\} onClick=\{\(\)=>setDetailsKey\(calendarEventKey\(item\)\)\}>/);
});

test("K3, K8: schmal stehen im Monat Punkte, die Termine des gewählten Tages gleich darunter", () => {
  const page = quelle("CalendarPage.tsx"), css = quelle("CalendarPage.css");
  assert.match(page, /useState\(schmal\)/);
  assert.match(page, /if \(media\.matches\) setAgendaOpen\(true\)/);
  const schmalTeil = css.slice(css.indexOf("@media(max-width:700px)"));
  assert.match(schmalTeil, /\.calendar-month-event :is\(\.calendar-zeit, \.calendar-titel\) \{ display:none; \}/);
  assert.match(schmalTeil, /\.calendar-agenda > \.text-action \{ display:none; \}/);
});

test("Grundlage: Kalender und Nachrichten nutzen Seitenkopf, Segmente und Leer; keine warmen Altfarben im Leser", () => {
  const kalender = quelle("CalendarPage.tsx"), post = quelle("Messages.tsx");
  assert.match(kalender, /<Seitenkopf titel="Kalender"/);
  assert.match(kalender, /<Segmente label="Kalenderansicht"/);
  assert.match(kalender, /<Leer className="calendar-leer" satz="Noch kein Kalender verbunden\."/);
  assert.match(post, /<Seitenkopf titel="Nachrichten" className="inbox-heading"/);
  assert.match(post, /<Leer className="mail-reader-placeholder"/);
  for (const datei of ["MailReader.css", "MailStyle.css", "SavedMailWorkflow.css", "CalendarPage.css", "Messages.css"]) {
    const css = quelle(datei);
    assert.doesNotMatch(css, /--kf-|Cormorant|#[0-9a-f]{3,6}\b/i, `${datei}: nur --g-/--calm-Werte`);
  }
});

test("N8–N13: im Mail-Leser höchstens ein gefüllter Knopf je Werkzeug", () => {
  assert.doesNotMatch(quelle("MailQuickTask.tsx"), /mail-reader-primary/, "Schnellübernahme ist eine Zeilenaktion");
  assert.doesNotMatch(quelle("MailReplySuggestion.tsx"), /mail-reader-primary/, "Vorschlag übernehmen ist nicht die Hauptaktion");
  assert.doesNotMatch(quelle("MailStyle.tsx"), /primary-action/, "der Ton-Vorschlag steht neben dem Antwort-Versand");
  const leser = quelle("MailReader.tsx");
  assert.equal((leser.match(/onToggle=\{nurEinWerkzeug\}/g) ?? []).length, 3, "Aufgabe, Termin, Antwort klappen wie eine Liste");
});
