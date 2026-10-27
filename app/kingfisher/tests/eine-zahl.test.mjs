// Eine Zahl je Begriff (Persona-Prüfung, Paket Z1, 27.10.2026): Heute, Aufgaben, Filter, Zugänge und Kalender
// zählen dasselbe. Der Sidecar zählt (`zaehlung.py`, `test_eine_zahl.py`); hier steht, dass jede Anzeige seine Zahl
// mit demselben Satz zeigt und keine Stelle eine eigene Regel hat.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import {
  brauchtDichSatz, brauchtDichZaehler, heuteZahlen, kalenderZeilen, ausgeblendetLage,
} from "../src/zahlen.ts";
import { heuteKopfZeile } from "../src/taskWorkspaceModel.ts";

const quelle = name => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");

test("„braucht dich heute“ ist ein Satz: Heute und Aufgaben sagen dasselbe mit derselben Zahl", () => {
  assert.equal(brauchtDichSatz({ aufgaben: 0, weitere: 0 }), "Dein Überblick ist da.");
  assert.equal(brauchtDichSatz({ aufgaben: 1, weitere: 0 }), "Eine Aufgabe braucht dich heute.");
  assert.equal(brauchtDichSatz({ aufgaben: 18, weitere: 0 }), "18 Aufgaben brauchen dich heute.");
  assert.equal(brauchtDichSatz({ aufgaben: 0, weitere: 1 }), "Ein Punkt braucht dich.");
  assert.equal(brauchtDichSatz({ aufgaben: 0, weitere: 3 }), "3 Punkte brauchen dich.");
  assert.equal(brauchtDichSatz({ aufgaben: 18, weitere: 1 }), "18 Aufgaben und ein weiterer Punkt brauchen dich heute.");
  assert.equal(brauchtDichSatz({ aufgaben: 1, weitere: 2 }), "Eine Aufgabe und 2 weitere Punkte brauchen dich heute.");
  // Aufgaben nimmt dieselbe Funktion: dieselbe Zahl ergibt denselben Satz.
  for (const n of [1, 2, 18, 50, 300]) assert.equal(heuteKopfZeile(n), brauchtDichSatz({ aufgaben: n, weitere: 0 }));
  assert.equal(heuteKopfZeile(0), undefined);
  assert.equal(heuteKopfZeile(null), undefined);
});

test("Heute zählt, wofür die Zeilen stehen, und sagt „von“, wenn es nur das Wichtigste zeigt", () => {
  // Die Assistentin: 18 Aufgaben (eine sichtbar), ein Termin (am Termin gezeigt), ein Vorschlag, zwei abgeschnitten.
  const briefing = {
    braucht_dich: { aufgaben: 18, weitere: 4 },
    needs_you: [{ source: "aufgabe", anzahl: 1 }, { source: "termin", anzahl: 1 }, { source: "zusage", anzahl: 1 }],
  };
  const z = heuteZahlen(briefing);
  assert.deepEqual(z, { aufgaben: 18, weitere: 4, gezeigt: 3, gesamt: 22 });
  assert.equal(brauchtDichZaehler(z), "3 von 22");
  // Helga: eine überfällige und „Heute sind 2 Aufgaben fällig.“: Die zwei Zeilen stehen für alle drei.
  const helga = heuteZahlen({ braucht_dich: { aufgaben: 3, weitere: 0 },
    needs_you: [{ source: "aufgabe", anzahl: 1 }, { source: "aufgabe", anzahl: 2 }] });
  assert.equal(brauchtDichZaehler(helga), "3");
  assert.equal(brauchtDichSatz(helga), "3 Aufgaben brauchen dich heute.");
  assert.equal(brauchtDichZaehler({ gezeigt: 0, gesamt: 0 }), null);
  // Ältere Antwort ohne Zählung (Bildschirmvorlage): die Zeilen, wie bisher.
  assert.deepEqual(heuteZahlen({ needs_you: [{ source: "x" }, { source: "y" }] }), { aufgaben: 0, weitere: 2, gezeigt: 2, gesamt: 2 });
});

test("Heute und Aufgaben rechnen nicht selbst: Heute nimmt braucht_dich, Aufgaben heute_dran des Sidecars", () => {
  const app = quelle("App.tsx");
  const heute = quelle("TodayOverview.tsx");
  assert.match(app, /brauchtDichSatz\(heuteZahlen\(briefing\)\)/);
  assert.doesNotMatch(app, /attentionCount === 1 \? "Ein Punkt braucht dich\."/);
  assert.match(heute, /brauchtDichZaehler\(heuteZahlen\(briefing\)\)/);
  assert.doesNotMatch(heute, /zaehlerText\(attention\.length\)/);
  // Aufgaben: die Zahl des Sidecars für die ganze Auswahl, nicht die Zeilen der Seite.
  assert.match(app, /heuteKopfZeile\(panel === "tasks" && view === "mine" && !search \? taskPage\.heuteDran : null\)/);
  assert.doesNotMatch(app, /visibleTaskGroups\(listTasks, groupTime\)\.filter/);
});

test("der Bereichsfilter filtert im Sidecar: Segment, Überblick und Liste fragen mit demselben Bereich", () => {
  const app = quelle("App.tsx");
  // Liste und Zahlen am Segment mit Bereich, die Liste filtert nicht noch einmal selbst.
  assert.match(app, /api\.tasks\(selection\.view, selection\.projectId, \{q: selection\.q, cursor, bereich: selection\.bereich\}\)/);
  assert.match(app, /api\.tasks\("mine", projectId, \{limit: 1, bereich: bereichFilter\.wahl\}\)/);
  assert.match(app, /api\.tasks\("waiting", projectId, \{limit: 1, bereich: bereichFilter\.wahl\}\)/);
  assert.doesNotMatch(app, /bereichFilter\.passt\(task\)/);
  assert.match(app, /<ProjectOverview key=\{projectId\} projectId=\{projectId\} bereich=\{bereichFilter\.wahl\}/);
  assert.match(quelle("ProjectOverview.tsx"), /api\.projectOverview\(projectId, bereich\)/);
  assert.match(quelle("api.ts"), /\.\.\.\(options\.bereich && options\.bereich !== "alle" \? \{bereich: options\.bereich\} : \{\}\)/);
});

test("Zugänge: „N Kalender verbunden“ zählt die Zeilen, die darunter stehen, auch die Mac-Kalender", () => {
  const overview = { calendar_sources: [{ id: "calendar-google" }, { id: "calendar-firma" }] };
  const konten = { kalender: [{ id: "calendar-google", art: "ical" }, { id: "calendar-firma", art: "ical" }, { id: "mac-calendar:m1", art: "mac" }] };
  const zeilen = kalenderZeilen(overview, konten);
  assert.deepEqual(zeilen.map(z => z.id), ["calendar-google", "calendar-firma", "mac-calendar:m1"]);
  assert.equal(kalenderZeilen(overview, null).length, 2);
  const zugaenge = quelle("Einstellungen/Zugaenge.tsx");
  assert.match(zugaenge, /zaehlen\(kalenderListe\.length, "Kalender", "Kalender"\)/);
  assert.match(zugaenge, /kalenderListe\.map\(/);
  assert.doesNotMatch(zugaenge, /zaehlen\(calendars\.length/);
});

test("Kalender: liegen die Termine in ausgeblendeten Kalendern, sagt er das und blendet mit einem Klick ein", () => {
  const termine = [
    { uid: "a", source_id: "calendar-google", bereich: "privat" },
    { uid: "b", source_id: "calendar-google", bereich: "privat" },
    { uid: "c", source_id: "calendar-firma", bereich: "arbeit" },
  ];
  const quellen = [{ id: "calendar-google", label: "lea.privat@gmail.com" }, { id: "calendar-firma", label: "Beratung" }];
  const quelleVon = t => t.source_id;
  // Privat gewählt, privater Kalender ausgeblendet: nicht „keine Termine“, sondern ehrlich, mit dem Weg zurück.
  const lage = ausgeblendetLage({ termine, quellen, ausgeblendet: new Set(["calendar-google"]), passt: t => t.bereich === "privat", quelleVon });
  assert.deepEqual(lage, { anzahl: 2, kalender: [{ id: "calendar-google", label: "lea.privat@gmail.com" }],
    satz: "2 Termine in diesem Zeitraum liegen in einem ausgeblendeten Kalender: lea.privat@gmail.com.", knopf: "Einblenden" });
  // Sichtbare Termine: kein Satz. Nichts ausgeblendet: kein Satz.
  assert.equal(ausgeblendetLage({ termine, quellen, ausgeblendet: new Set(), passt: () => true, quelleVon }), null);
  assert.equal(ausgeblendetLage({ termine, quellen, ausgeblendet: new Set(["calendar-firma"]), passt: t => t.bereich === "arbeit", quelleVon }).anzahl, 1);
  // Nur, was zum gewählten Bereich passt: Ein ausgeblendeter Arbeitskalender zählt unter „Privat“ nicht mit.
  const nurPrivat = ausgeblendetLage({ termine, quellen, ausgeblendet: new Set(["calendar-google", "calendar-firma"]), passt: t => t.bereich === "privat", quelleVon });
  assert.equal(nurPrivat.anzahl, 2);
  assert.deepEqual(nurPrivat.kalender.map(k => k.id), ["calendar-google"]);
  assert.equal(ausgeblendetLage({ termine, quellen, ausgeblendet: new Set(["calendar-firma"]), passt: t => t.bereich === "privat", quelleVon }), null);
  const zwei = ausgeblendetLage({ termine, quellen, ausgeblendet: new Set(["calendar-google", "calendar-firma"]), passt: () => true, quelleVon });
  assert.equal(zwei.satz, "3 Termine in diesem Zeitraum liegen in ausgeblendeten Kalendern: lea.privat@gmail.com, Beratung.");
  assert.equal(zwei.knopf, "Beide einblenden");
  const seite = quelle("CalendarPage.tsx");
  assert.match(seite, /ausgeblendetLage\(/);
  assert.match(seite, /className="calendar-hinweis calendar-ausgeblendet" role="status"/);
  assert.doesNotMatch(seite, /Die Termine dieses Zeitraums stehen in ausgeblendeten Kalendern\./);
});
