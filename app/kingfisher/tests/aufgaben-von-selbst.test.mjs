// Aufgaben von selbst (Paket A, 26.10.2026): „Von Kingfisher angelegt · Rückgängig“, die Zeile auf Heute, „Alle
// übernehmen“ und der Schalter. Synthetische Daten (Anna Berg, Lena Probe).
import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {alleHinweis, alleKnopf, anlageZeile, gruppeZurueckText, heuteSatz, heuteZurueck, personHref, personName} from "../src/aufgabenVonSelbst.ts";

const src = name => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");
const angelegt = (richtung, wer = "Anna Berg") => ({art: "automatisch", am: "2026-09-29T08:00:00+00:00", satz: "Von Kingfisher angelegt, weil …",
  grundsatz: "Eine Bitte von Anna Berg direkt an dich, aus einer neuen Mail.", richtung, episode_id: "e-1", wer,
  datum: "2026-09-28T09:30:00+00:00"});

test("Die Zeile nennt Herkunft, Mail und Tag, nur bei selbst angelegten Aufgaben", () => {
  assert.equal(anlageZeile({angelegt: angelegt("bitte")}), "Von Kingfisher angelegt · aus der Mail von Anna Berg vom 28. September");
  assert.equal(anlageZeile({angelegt: angelegt("zusage")}), "Von Kingfisher angelegt · aus deiner Mail an Anna Berg vom 28. September");
  assert.equal(anlageZeile({angelegt: {...angelegt("bitte"), datum: null}}), "Von Kingfisher angelegt · aus der Mail von Anna Berg");
  // Von Hand oder mit „Alle übernehmen“ übernommen: keine Zeile „Von Kingfisher angelegt“.
  assert.equal(anlageZeile({angelegt: {art: "alle_uebernehmen", am: "x", gruppe: "g-1"}}), null);
  assert.equal(anlageZeile({angelegt: null}), null);
  assert.equal(anlageZeile({}), null);
});

test("Die Person steht mit Namen da und führt zur Akte", () => {
  const person = {adresse: "anna.berg@example.org", name: "Anna Berg"};
  assert.equal(personName({person}), "Anna Berg");
  assert.equal(personName({person: {adresse: "anna.berg@example.org", name: ""}}), "anna.berg@example.org");
  assert.equal(personName({}), "");
  assert.equal(personHref(person), "/memory/people/anna.berg%40example.org");
});

test("Heute: eine Zeile statt jeder Aufgabe einzeln; Rückgängig nimmt nur Offenes zurück", () => {
  assert.equal(heuteSatz(null), null);
  assert.equal(heuteSatz({anzahl: 0, satz: "", aufgaben: []}), null);
  const heute = {anzahl: 3, satz: "3 Aufgaben aus der Post angelegt.", aufgaben: [
    {id: "t1", title: "A", status: "open", satz: ""}, {id: "t2", title: "B", status: "done", satz: ""}, {id: "t3", title: "C", status: "open", satz: ""}]};
  assert.equal(heuteSatz(heute), "3 Aufgaben aus der Post angelegt.");
  assert.deepEqual(heuteZurueck(heute), ["t1", "t3"]);
});

test("„Alle übernehmen“ sagt, was geschah, und Rückgängig, was wieder zur Prüfung steht", () => {
  assert.equal(alleKnopf(1), "Übernehmen");
  assert.equal(alleKnopf(7), "Alle 7 übernehmen");
  assert.equal(alleHinweis({aufgaben: [{}, {}], fehler: []}), "2 Aufgaben übernommen.");
  assert.equal(alleHinweis({aufgaben: [{}], fehler: [{id: "v", grund: "x"}]}),
    "1 Aufgabe übernommen. 1 Vorschlag bleibt zur Prüfung, die Quelle hat sich geändert.");
  assert.equal(gruppeZurueckText({zurueckgenommen: 2, geblieben: 0}), "2 Vorschläge stehen wieder zur Prüfung.");
});

test("Verdrahtung: Zeile mit Rückgängig, Heute, Alle übernehmen, Projekthinweis statt keines, Schalter", () => {
  assert.match(src("TaskRow.tsx"), /anlageZeile\(task\)[\s\S]*onAnlageZurueck && task\.status === "open"/);
  assert.match(src("App.tsx"), /onAnlageZurueck=\{\(\)=>void anlageZuruecknehmen\(task\.id/);
  assert.match(src("TaskDetail.tsx"), /onAnlageZurueck=/);
  assert.match(src("TodayOverview.tsx"), /<AufgabenVonSelbstZeile /);
  assert.match(src("AufgabenSelbstHeute.tsx"), /aufgabenVonSelbstWiederherstellen/, "Rückgängig des Zurücknehmens stellt wieder her");
  assert.match(src("TaskSuggestions.tsx"), /api\.alleUebernehmen\(ids\)[\s\S]*gruppeZuruecknehmen\(ergebnis\.gruppe\)/);
  assert.match(src("TaskSuggestions.tsx"), /item\.person_vorschlag/);
  // Heute und das Mail-Briefing übernehmen den Projekthinweis, nicht mehr „ohne Projekt“ ohne Grund.
  assert.match(src("BriefingSuggestion.tsx"), /zuordnung_aus_vorschlag: true/);
  assert.doesNotMatch(src("MailQuickTask.tsx"), /Ohne Datum und weitere Zuordnung gespeichert/);
  assert.match(src("Einstellungen/Darf.tsx"), /<AufgabenSelbstSchalter \/>/);
});
