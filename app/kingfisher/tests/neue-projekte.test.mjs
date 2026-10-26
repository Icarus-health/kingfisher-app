// Paket P (Projekte von selbst): die eine Zeile auf Heute mit Grund, Ansehen und Rückgängig; die abgeleitete Zeile
// „Projekte: …“/„Beteiligte: …“ in der Akte; „Zugeordnet nach Absender · Ändern · Rückgängig“ an der Quelle.
// Synthetische Daten (Anna Keller, Ben Braun, Umbau Praxis).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { aufzaehlung, neueProjekteZeile, projektGrund, verbundenZeile } from "../src/projektAutomatik.ts";
import { entscheidungSatz, zurueckBeschriftung } from "../src/akteVorschlag.ts";

const quelle = (datei) => readFileSync(new URL(`../src/${datei}`, import.meta.url), "utf8");
const UMBAU = { name: "Umbau Praxis", anzahl: 4, wort: "Mails", personen: ["Anna Keller", "Ben Braun"] };

test("ein neues Projekt steht in einem Satz mit Zahl und Menschen", () => {
  assert.equal(neueProjekteZeile([UMBAU]), "Neues Projekt: Umbau Praxis, aus 4 Mails mit Anna Keller und Ben Braun");
  assert.equal(projektGrund({ ...UMBAU, anzahl: 1, personen: [] }), "Umbau Praxis, aus 1 Mail");
  assert.equal(projektGrund({ ...UMBAU, anzahl: 0, personen: ["Anna Keller"] }), "Umbau Praxis mit Anna Keller");
  assert.equal(neueProjekteZeile([]), null, "ohne neues Projekt kein Satz");
});

test("mehrere neue Projekte stehen zusammengefasst in einer Zeile", () => {
  const drei = [UMBAU, { ...UMBAU, name: "Atlas" }, { ...UMBAU, name: "Orion" }];
  assert.equal(neueProjekteZeile(drei), "3 neue Projekte: Umbau Praxis, Atlas und Orion");
  assert.equal(aufzaehlung(["A"]), "A");
  assert.equal(aufzaehlung(["A", "B"]), "A und B");
  assert.equal(aufzaehlung([]), "");
});

test("Personen ↔ Projekte: abgeleitet aus Zusammenhänge, nur angelegte Projekte, höchstens drei Namen", () => {
  const beteiligte = [
    { sache: "projekt:p-1", name: "Umbau Praxis", art: "projekt" },
    { sache: "projekt:n:atlas", name: "Projekt Atlas", art: "projekt" },
    { sache: "person:a:ben@x.example", name: "Ben Braun", art: "person" },
    { sache: "projekt:p-2", name: "Orion", art: "projekt" },
    { sache: "projekt:p-3", name: "Vega", art: "projekt" },
    { sache: "projekt:p-4", name: "Sirius", art: "projekt" },
    { sache: "organisation:nordlicht", name: "Nordlicht", art: "organisation" },
  ];
  const person = verbundenZeile("person", beteiligte);
  assert.equal(person.titel, "Projekte");
  assert.deepEqual(person.eintraege.map(b => b.name), ["Umbau Praxis", "Orion", "Vega"]);
  assert.equal(person.weitere, 1);
  const projekt = verbundenZeile("projekt", beteiligte);
  assert.deepEqual([projekt.titel, projekt.eintraege.map(b => b.name), projekt.weitere], ["Beteiligte", ["Ben Braun"], 0]);
  assert.equal(verbundenZeile("organisation", beteiligte), null);
  assert.equal(verbundenZeile("person", beteiligte.filter(b => b.art !== "projekt" || b.sache.startsWith("projekt:n:"))), null,
    "eine bloße Erwähnung ist kein Projekt der Person");
});

test("die Akte nennt, wenn Kingfisher selbst angelegt hat, mit Grund und „Rückgängig“", () => {
  assert.equal(entscheidungSatz("angenommen", 4, "automatisch", "In 4 Mails seit 3. Oktober mit Anna Keller und Ben Braun"),
    "Von Kingfisher angelegt. In 4 Mails seit 3. Oktober mit Anna Keller und Ben Braun.");
  assert.equal(entscheidungSatz("abgelehnt", 0, "automatisch"), "Von Kingfisher angelegt und von dir zurückgenommen: Es wird nicht wieder angelegt.");
  assert.equal(zurueckBeschriftung("angenommen", "automatisch"), "Rückgängig");
  assert.equal(zurueckBeschriftung("abgelehnt", "automatisch"), "Doch vorschlagen");
  // Was der Nutzer selbst entschieden hat, bleibt wie bisher.
  assert.equal(entscheidungSatz("angenommen", 4, "nutzer"), "Aus einem Vorschlag angelegt, 4 Quellen zugeordnet.");
  assert.equal(zurueckBeschriftung("angenommen", "nutzer"), "Akte wieder auflösen");
});

test("Heute zeigt die Zeile unter „Braucht dich“ mit Ansehen und Rückgängig, keine eigene Liste-Seite", () => {
  const heute = quelle("TodayOverview.tsx");
  const zeile = quelle("NeueProjekte.tsx");
  assert.match(heute, /<NeueProjekte onChange=\{\(\) => onChange\(\)\} \/>/);
  assert.ok(heute.indexOf("<NeueProjekte") > heute.indexOf("today-attention-list"), "unter der Liste von „Braucht dich“");
  assert.match(zeile, /api\.neueProjekte\(\)/);
  assert.match(zeile, /const antwort = await api\.akteVorschlagZuruecknehmen\(projekt\.kennung\);/);
  assert.match(zeile, /zeigeHinweis\(\{ text: antwort\.satz \}\);/, "jede Aktion antwortet");
  assert.match(zeile, />Ansehen</);
  assert.match(zeile, />Rückgängig<\/button>/);
  assert.doesNotMatch(zeile, /g-knopf"/, "kein gefüllter Knopf: Heute hat seinen schon");
});

test("die Quelle zeigt „Zugeordnet nach Absender · Ändern · Rückgängig“", () => {
  const quelleProjekt = quelle("SourceProject.tsx");
  assert.match(quelleProjekt, /hint\.automatisch\.projekt_id === value/);
  assert.match(quelleProjekt, /\{automatisch\.satz\}\{" · "\}/);
  assert.match(quelleProjekt, /onClick=\{\(\) => auswahl\.current\?\.focus\(\)\}>Ändern<\/button>/);
  assert.match(quelleProjekt, /api\.projektZuordnungZuruecknehmen\(id\)/);
  assert.match(quelleProjekt, /zeigeHinweis\(\{text: antwort\.satz\}\);/);
  const api = quelle("api.ts");
  assert.match(api, /\/api\/v1\/projekte\/automatik\/zuordnung\/\$\{encodeURIComponent\(episodeId\)\}\/zuruecknehmen/);
});

test("die Akte zeigt Projekte oder Beteiligte unter dem Namen, jeder Name führt zur Akte", () => {
  const akte = quelle("AkteAbschnitte.tsx");
  assert.match(akte, /const verbunden = verbundenZeile\(data\.art, data\.beteiligte\.eintraege\);/);
  assert.match(akte, /\{verbunden \? <VerbundenZeile \{\.\.\.verbunden\} \/> : null\}/);
  assert.match(akte, /href=\{`\/memory\/akte\/\$\{encodeURIComponent\(b\.sache\)\}`\}/);
});
