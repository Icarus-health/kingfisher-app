// Kreis je Person und Art der Akte (M4, docs/49-kreis-und-privat.md): die Sätze der Karten und der Übersicht.
import assert from "node:assert/strict";
import { test } from "node:test";
import { aktePfad, artSatz, kreisGespeichert, kreisSatz, offeneKollegen, sammelFrage, sammelKnopf, sammlungSatz, uebersichtSatz } from "../src/kreis.ts";
import { fachwoerter } from "../src/Einstellungen/gliederung.ts";

const WAHLEN = [
  { kreis: "innerer_kreis", text: "Innerer Kreis", wirkung: "Familie und enge Freunde: Kingfisher nennt sie mit Namen und denkt an ihren Alltag." },
  { kreis: "kollegen", text: "Kollegen", wirkung: "Menschen aus der Arbeit: sachlich und mit Bezug zum Projekt." },
  { kreis: "kontakte", text: "Kontakte", wirkung: "Alle anderen: Kingfisher erwähnt sie nur, wenn es direkt um sie geht." },
];
const stand = (aenderung = {}) => ({
  sache: "person:a:gabi.hartmann@gmx.example", kreis: "unbestimmt", kreis_text: "Noch offen", bestaetigt: false, bestaetigt_am: null,
  vorschlag: { kreis: "innerer_kreis", kreis_text: "Innerer Kreis", begruendung: "6 Mails in beide Richtungen seit April 2026, privater Anbieter." },
  neuer_vorschlag: false, wahlen: WAHLEN, ...aenderung,
});

test("ohne Bestätigung ist es ein Vorschlag, der mit einem Klick fest wird", () => {
  assert.equal(kreisSatz(stand()), "Vorschlag: Innerer Kreis. Ein Klick bestätigt ihn, oder du wählst einen anderen Kreis.");
});

test("bestätigt bleibt bestätigt; ein neuer Vorschlag steht nur daneben", () => {
  const fest = stand({ kreis: "kontakte", kreis_text: "Kontakte", bestaetigt: true });
  assert.equal(kreisSatz(fest), "Bestätigt: Kontakte.");
  const anders = { ...fest, vorschlag: { ...fest.vorschlag, kreis: "kollegen", kreis_text: "Kollegen" }, neuer_vorschlag: true };
  assert.match(kreisSatz(anders), /^Bestätigt: Kontakte\. .*„Kollegen“ vorschlagen\. Es bleibt bei deiner Wahl, bis du sie änderst\.$/);
});

test("nach dem Klick steht, was gespeichert ist und was es bewirkt", () => {
  assert.equal(kreisGespeichert(stand({ kreis: "innerer_kreis", bestaetigt: true })),
    "Gespeichert: Innerer Kreis. Familie und enge Freunde: Kingfisher nennt sie mit Namen und denkt an ihren Alltag.");
  assert.match(kreisGespeichert(stand()), /^Zurückgenommen\./);
});

test("die Übersicht zählt bestätigt, offen je Kreis und geändert in Alltagssprache", () => {
  const leer = { bestaetigt: 0, offen: 0, geaendert: 0, je_kreis: { innerer_kreis: 0, kollegen: 0, kontakte: 0 }, vorschlaege: [] };
  assert.equal(uebersichtSatz(leer), "Noch für niemanden bestätigt. Kein Vorschlag offen.");
  assert.equal(uebersichtSatz({ ...leer, bestaetigt: 1, offen: 1, offen_je_kreis: { innerer_kreis: 1, kollegen: 0 } }),
    "Für eine Person bestätigt. Offen ist ein Vorschlag: einer für den inneren Kreis.");
  assert.equal(uebersichtSatz({ ...leer, bestaetigt: 3, offen: 24, geaendert: 1, offen_je_kreis: { innerer_kreis: 3, kollegen: 21 } }),
    "Für 3 Personen bestätigt. Offen sind 24 Vorschläge: 3 für den inneren Kreis, 21 für Kollegen. Bei einer Person würde Kingfisher heute anders vorschlagen.");
  // Solange der Abgleich läuft, ist die Zahl als vorläufig gekennzeichnet.
  assert.equal(uebersichtSatz({ ...leer, offen: 8, offen_je_kreis: { innerer_kreis: 0, kollegen: 8 }, zaehlt_noch: true }),
    "Noch für niemanden bestätigt. Offen sind 8 Vorschläge: 8 für Kollegen. Kingfisher sortiert noch; die Zahlen werden gleich genauer.");
});

test("die Art der Akte zeigt sich nur mit Vorschlag oder Wahl", () => {
  const art = { sache: "organisation:zahnarztlindqvist", art: null, art_text: "", bestaetigt: false, neuer_vorschlag: false,
    vorschlag: { art: "gesundheit", art_text: "Gesundheit", begruendung: "Absender „Zahnarztpraxis Dr. Lindqvist“." }, wahlen: [] };
  assert.equal(artSatz(art), "Vorschlag: Gesundheit. Ein Klick bestätigt ihn.");
  assert.equal(artSatz({ ...art, vorschlag: { art: null, art_text: "", begruendung: "" } }), null);
  assert.equal(artSatz({ ...art, art: "keine", art_text: "Keine davon", bestaetigt: true }), "Bestätigt: Keine davon.");
});

test("der Weg zur Akte ist die Seite der Akte, sicher kodiert", () => {
  assert.equal(aktePfad("person:a:gabi.hartmann@gmx.example"), "/memory/akte/person%3Aa%3Agabi.hartmann%40gmx.example");
});

test("kein Fachwort in den Sätzen", () => {
  const saetze = [kreisSatz(stand()), kreisGespeichert(stand({ kreis: "kollegen", bestaetigt: true })),
    uebersichtSatz({ bestaetigt: 2, offen: 1, geaendert: 1, je_kreis: {}, vorschlaege: [] }), ...WAHLEN.map(w => w.wirkung)];
  for (const satz of saetze) assert.deepEqual(fachwoerter(satz), [], satz);
});

test("Sammelbestätigung: Rückfrage in einem Satz, nur Kollegen, alle offenen gezählt", () => {
  assert.equal(sammelFrage(21), "21 Personen als Kollegen festlegen?");
  assert.equal(sammelFrage(1), "Eine Person als Kollegen festlegen?");
  assert.equal(sammelKnopf(21), "Alle 21 als Kollegen festlegen");
  assert.equal(sammlungSatz({ anzahl: 21 }), "Zuletzt 21 Personen gesammelt als Kollegen festgelegt.");
  // Gezählt wird, was offen ist, nicht nur, was die Liste zeigt (sie ist auf 20 begrenzt).
  const u = { bestaetigt: 0, offen: 23, geaendert: 0, je_kreis: {}, offen_je_kreis: { innerer_kreis: 2, kollegen: 21 },
    vorschlaege: [{ sache: "person:a:x", name: "X", kreis: "innerer_kreis", kreis_text: "Innerer Kreis", begruendung: "" }] };
  assert.equal(offeneKollegen(u), 21);
  for (const satz of [sammelFrage(21), sammelKnopf(21), sammlungSatz({ anzahl: 3 })]) assert.deepEqual(fachwoerter(satz), [], satz);
});

import { kontakteText, kreisSache } from "../src/kreis.ts";
import { readFileSync } from "node:fs";

test("ohne Vorschlag: du legst den Kreis selbst fest, ohne „vorgeschlagen“ (Fremdprobe 2, Befund 19)", () => {
  const ohne = { sache: "person:n:anna berg", kreis: "unbestimmt", kreis_text: "Noch offen", bestaetigt: false, bestaetigt_am: null,
    vorschlag: { kreis: "kontakte", kreis_text: "Kontakte", begruendung: "Kein Mailwechsel." }, neuer_vorschlag: false, wahlen: [], ohne_vorschlag: true };
  assert.equal(kreisSatz(ohne), "Noch kein Vorschlag; du kannst den Kreis selbst festlegen.");
  assert.match(kreisSatz({ ...ohne, bestaetigt: true, kreis: "innerer_kreis", kreis_text: "Innerer Kreis" }), /^Bestätigt: Innerer Kreis\.$/);
  const karte = readFileSync(new URL("../src/KreisKarten.tsx", import.meta.url), "utf8");
  assert.match(karte, /stand\.ohne_vorschlag \? null : <p className="kreis-warum">/);
  assert.match(karte, /!stand\.bestaetigt && !stand\.ohne_vorschlag && stand\.vorschlag\.kreis === w\.kreis/);
});

test("jede Personenakte hat eine Kreis-Sache: Adresse, sonst Name; eine offene Nennung keine", () => {
  assert.equal(kreisSache({ id: "a:anna@example.org", adressen: ["Anna@Example.org"] }), "person:a:anna@example.org");
  assert.equal(kreisSache({ id: "n:anna berg", adressen: [] }), "person:n:anna berg");
  assert.equal(kreisSache({ id: "n:anna", adressen: [], offen_mit: ["a@x.org", "b@y.org"] }), null);
  const profil = readFileSync(new URL("../src/MemoryProfile.tsx", import.meta.url), "utf8");
  assert.match(profil, /<KreisKarte sache=\{sache\} \/><GeburtstagKarte sache=\{sache\} \/>/);
  const akte = readFileSync(new URL("../src/AkteAbschnitte.tsx", import.meta.url), "utf8");
  assert.match(akte, /data\.art === "person" \? <KreisKarte sache=\{data\.sache\} \/> : null/);
});

test("„Kingfisher und du“ sagt dasselbe wie die Akte, und Kingfisher ist „es“ (Befunde 19 und 26)", () => {
  const gliederung = readFileSync(new URL("../src/Einstellungen/gliederung.ts", import.meta.url), "utf8");
  assert.match(gliederung, /In jeder Akte einer Person steht die Karte „Kreis“/);
  assert.match(gliederung, /sonst legst du ihn dort selbst fest/);
  assert.doesNotMatch(gliederung, /wie er dir|Für jede Person schlägt Kingfisher/);
});

test("belegte Kontakte zählen nur Quellen mit Beteiligung (Befund 21)", () => {
  assert.equal(kontakteText({ kontakte: 0, episoden_anzahl: 1 }), "Noch kein Kontakt belegt; bisher nur in deinen Gesprächen mit Kingfisher erwähnt");
  assert.equal(kontakteText({ kontakte: 1, episoden_anzahl: 3 }), "1 belegter Kontakt");
  assert.equal(kontakteText({ kontakte: 4, episoden_anzahl: 4 }), "4 belegte Kontakte");
});
