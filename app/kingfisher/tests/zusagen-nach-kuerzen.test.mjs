// Beim Kürzen der Texte (Paket Oberfläche, 23.10.2026) dürfen Grenz- und Antwortsätze nicht verloren gehen.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const quelle = (datei) => readFileSync(new URL(`../src/${datei}`, import.meta.url), "utf8");

test("Termin aus Mail nennt die Grenze des gespeicherten Mailverlaufs", () => {
  assert.match(quelle("MailCalendarPreparation.tsx"),
    /Ein begrenzter Mailverlauf kann spätere Absagen außerhalb des gespeicherten Bestands nicht ausschließen\./);
});

test("Aufgabe aus Mail sagt auch ohne Datum, was beim Speichern geschieht", () => {
  const form = quelle("MailTaskForm.tsx");
  assert.match(form, /id="mail-task-due-hint">\{due \? "[^"]+" : "Ohne Datum wird die Aufgabe ohne Termin gespeichert\."\}/);
});

test("Die Einwilligung zur Cloud für Antworten nennt Fragen, Textstellen und Gedächtnisfragen (Paket T)", () => {
  const satz = quelle("Einstellungen/gliederung.ts");
  assert.match(satz, /zustimmung: "Deine Fragen und die dazu gefundenen Textstellen samt Absender, Betreff und Datum gehen an den Cloudanbieter, den du gewählt hast, auch bei Fragen an dein Gedächtnis\. Ich willige ein\."/);
  assert.match(satz, /Aus: alles bleibt auf diesem Rechner\./);
});
