// Terminvorbereitung im Kalender (Persona-Prüfung, Befund A6): Sie entsteht aus den Teilnehmern und ihren Akten,
// ohne dass jemand ein Projekt oder eine Person wählt; die Terminkarte nennt Namen statt Adressen.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const quelle = (datei) => readFileSync(new URL(`../src/${datei}`, import.meta.url), "utf8");

test("die Vorbereitung lädt ohne Wahl und zeigt, was in den Akten offen ist", () => {
  const vorbereitung = quelle("CalendarPreparation.tsx");
  assert.match(vorbereitung, /api\.calendarVorbereitung\(event\.uid, event\.start\)/);
  assert.match(vorbereitung, /<TerminVorbereitung termin=\{vorbereitet\} ohneKopf \/>/);
  assert.doesNotMatch(vorbereitung, /Wähle ein Projekt oder eine Person; dann steht hier/);
  // Projekt und Person bleiben als ruhige Verfeinerung erreichbar, nicht als Pflicht.
  assert.match(vorbereitung, /<summary>\{projectId \|\| personId \? "Gewählter Kontext" : "Mehr Kontext: Projekt oder Person wählen"\}<\/summary>/);
  assert.match(quelle("api.ts"), /\/api\/v1\/calendar\/vorbereitung\?/);
});

test("die Terminkarte nennt Namen, wo der Bestand sie kennt", () => {
  assert.match(quelle("CalendarPage.tsx"), /\(detailsEvent\.attendee_names\?\.length \? detailsEvent\.attendee_names : detailsEvent\.attendees\)\.join\(', '\)/);
});
