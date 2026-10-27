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

test("Die Einwilligung zur Cloud für Antworten nennt Anbieter, Land, Region und Inhalte (Paket T, präzisiert in Paket D)", async () => {
  const { zustimmungCloud, SCHALTER } = await import("../src/Einstellungen/gliederung.ts");
  const satz = zustimmungCloud({ wohin: "Anthropic (USA)", region: "nicht nur in der EU verarbeitet" });
  // Was hinausgeht: nicht „Textstellen“, sondern Inhalte, ganz oder in Auszügen; Fragen, Verlauf und Gedächtnisfragen.
  for (const teil of ["Deine Fragen", "der Gesprächsverlauf", "Inhalte deiner Mails, Termine und Notizen", "ganz oder in Auszügen",
    "samt Absender, Betreff und Datum", "auch an dein Gedächtnis", "Ich willige ein."]) assert.ok(satz.includes(teil), teil);
  // An wen und wo: der tatsächlich eingestellte Anbieter mit Land und Region.
  assert.match(satz, /gehen an Anthropic \(USA\) und werden nicht nur in der EU verarbeitet\./);
  // Bis wann: bis zum Ausschalten.
  assert.match(satz, /bis du den Schalter wieder ausschaltest\./);
  assert.doesNotMatch(satz, /den du gewählt hast/);
  // Ohne Anbieter keine Zustimmung, sondern die Bitte, zu wählen.
  assert.doesNotMatch(zustimmungCloud(null), /Ich willige ein/);
  assert.match(SCHALTER.cloud.verlaesst, /Inhalte deiner Mails, Termine und Notizen, ganz oder in Auszügen/);
  assert.match(SCHALTER.cloud.verlaesst, /Aus: alles bleibt auf diesem Rechner\./);
  assert.doesNotMatch(SCHALTER.cloud.verlaesst, /Textstellen/);
});

test("Der Cloud-Schalter steht erst nach der Zustimmung auf an und gilt beim Ausschalten sofort (D1, D5)", () => {
  const schalter = quelle("Einstellungen/CloudSchalter.tsx");
  assert.match(schalter, /an=\{an\}/);
  assert.doesNotMatch(schalter, /an=\{an \|\| frage\}/);
  assert.match(schalter, /SCHALTER\.cloud\.wartet/);
  assert.match(schalter, /setWiderrufen\(true\)/);
  assert.match(schalter, /zustimmungCloud\(gewaehltDaten\)/);
  assert.match(schalter, /<CloudProtokoll \/>/);
});

test("Wo ein Dienst im Netz gefragt wird, steht dabei, dass er die IP-Adresse sieht (Kleinpunkt d, D2, D3)", async () => {
  const { SCHALTER } = await import("../src/Einstellungen/gliederung.ts");
  for (const name of ["wetter", "welt", "wegezeit", "web"]) assert.match(SCHALTER[name].verlaesst, /IP-Adresse/, name);
  assert.match(SCHALTER.web.verlaesst, /erst, wenn du den Abruf im Gespräch freigibst/);
  const darf = quelle("Einstellungen/Darf.tsx");
  assert.match(darf, /<WebSchalter \/>/);
  const technik = quelle("Einstellungen/Technik.tsx");
  assert.match(technik, /außer was unter „Was Kingfisher darf“ eingeschaltet ist\. Von Haus aus ist dort nur eines an, das etwas abruft: Einmal am Tag fragt Kingfisher bei GitHub nach einer neuen Fassung, und GitHub sieht dabei deine IP-Adresse\./);
});
