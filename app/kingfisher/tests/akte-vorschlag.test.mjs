// „Neue Akte?“ (Paket B4): die Zeile in der Akte, der eine Satz auf Heute, zwei Knöpfe, jede Antwort ein Satz mit Rückweg.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { entscheidungSatz, fehlerSatz, vorschlagFrage, zurueckBeschriftung } from "../src/akteVorschlag.ts";

const quelle = (datei) => readFileSync(new URL(`../src/${datei}`, import.meta.url), "utf8");

test("die Zeile fragt zuerst und nennt dann den Grund als Satz", () => {
  assert.equal(vorschlagFrage("In 4 Mails seit 3. Oktober mit Anna Keller und Ben Braun"),
    "Daraus eine Akte machen? In 4 Mails seit 3. Oktober mit Anna Keller und Ben Braun.");
  assert.equal(vorschlagFrage("In 2 Mails seit 1. Mai. "), "Daraus eine Akte machen? In 2 Mails seit 1. Mai.");
  assert.equal(vorschlagFrage(""), "Daraus eine Akte machen?");
});

test("eine gemerkte Entscheidung steht als Satz da und hat einen Rückweg", () => {
  assert.equal(entscheidungSatz("angenommen", 4), "Aus einem Vorschlag angelegt, 4 Quellen zugeordnet.");
  assert.equal(entscheidungSatz("angenommen", 1), "Aus einem Vorschlag angelegt, eine Quelle zugeordnet.");
  assert.equal(entscheidungSatz("angenommen", 0), "Aus einem Vorschlag angelegt, ohne neu zugeordnete Quelle.");
  assert.equal(entscheidungSatz("abgelehnt", 0), "Du hast „Nein danke“ gesagt: Dieser Name wird nicht mehr vorgeschlagen.");
  assert.equal(zurueckBeschriftung("angenommen"), "Akte wieder auflösen");
  assert.equal(zurueckBeschriftung("abgelehnt"), "Doch vorschlagen");
});

test("ein gescheiterter Klick nennt den Grund", () => {
  assert.match(fehlerSatz(409), /schon entschieden/);
  assert.match(fehlerSatz(404), /nicht mehr/);
  assert.match(fehlerSatz(null), /noch einmal versuchen/);
});

test("die Akte zeigt die Zeile mit „Akte anlegen“ und „Nein danke“ oben, vor „Braucht dich“", () => {
  const akte = quelle("AkteAbschnitte.tsx");
  const zeile = akte.indexOf("<NeueAkte stand={data.akte_vorschlag}");
  const braucht = akte.indexOf("<BrauchtDich punkte={braucht.eintraege}");
  assert.ok(zeile > 0 && braucht > zeile, "Die Zeile steht vor „Braucht dich“");
  assert.match(akte, /aria-label="Neue Akte\?"/);
  assert.match(akte, /onClick=\{\(\) => anlegen\(v\.kennung\)\}>Akte anlegen<\/button>/);
  assert.match(akte, /onClick=\{\(\) => ablehnen\(v\.kennung\)\}>Nein danke<\/button>/);
  // Die Textstellen stehen dabei; jede führt zur Quelle.
  assert.match(akte, /v\.quellen\.map\(q => <li key=\{q\.episode_id\}>\{q\.zitat \? <q>\{q\.zitat\}<\/q> : null\} <Quelle zeile=\{q\} \/>/);
  // Annehmen führt in die neue Akte; der Hinweis der App nimmt den Satz samt „Rückgängig“ mit (V4). „Nein danke“ ebenso.
  assert.match(akte, /zeigeHinweis\(\{ text: antwort\.satz, rueckgaengig: vorschlagZurueckWeg\(kennung\) \}\);\n\s*navigate\(antwort\.link\);/);
  assert.equal(akte.match(/rueckgaengig: vorschlagZurueckWeg\(kennung\)/g).length, 2);
  assert.match(akte, /const antwort = await api\.akteVorschlagZuruecknehmen\(kennung\);/);
  // Eine gemerkte Entscheidung zeigt ihren Rückweg.
  assert.match(akte, /onClick=\{\(\) => zurueck\(e\.kennung\)\}>\{zurueckBeschriftung\(e\.entscheidung, e\.herkunft\)\}<\/button>/);
});

test("Heute zeigt den einen Satz mit zwei Knöpfen und behält die Antwort, wenn der Punkt verschwindet", () => {
  const heute = quelle("TodayOverview.tsx");
  const knoepfe = quelle("AkteVorschlagKnoepfe.tsx");
  assert.match(heute, /akte_vorschlag: "Neue Akte\?"/);
  assert.match(heute, /item\.source === "akte_vorschlag" \? <AkteVorschlagKnoepfe/);
  assert.match(heute, /<AkteVorschlagKnoepfe key=\{item\.source_ref \?\? item\.id\} item=\{item\} onDone=\{\(\) => onChange\(\)\} \/>/);
  // Die Antwort steht im Hinweis der App: Er bleibt, wenn der Punkt aus dem Briefing geht, und führt in die Akte.
  assert.match(knoepfe, /zeigeHinweis\(\{ text: ergebnis\.satz, verweis: \{ text: "Akte öffnen", href: ergebnis\.link \},/);
  assert.match(knoepfe, /rueckgaengig: async \(\) => \{ const zurueck = await api\.akteVorschlagZuruecknehmen\(kennung\); onDone\(\); return zurueck\.satz; \}/);
  assert.match(knoepfe, /onClick=\{\(\) => void klick\("anlegen"\)\}>\{busy \? "Wird gespeichert …" : "Akte anlegen"\}<\/button>/);
  assert.match(knoepfe, /onClick=\{\(\) => void klick\("ablehnen"\)\}>Nein danke<\/button>/);
  assert.doesNotMatch(knoepfe, /\.map\(/, "Heute zeigt keine Liste von Vorschlägen");
  const api = quelle("api.ts");
  for (const name of ["akteVorschlagAnnehmen", "akteVorschlagAblehnen", "akteVorschlagZuruecknehmen"]) assert.match(api, new RegExp(`${name}: \\(kennung: string\\)`));
});

test("keine Zeichenkette öffnet mit „ und schließt mit einem ASCII-Anführungszeichen", () => {
  for (const datei of ["akteVorschlag.ts", "AkteVorschlagKnoepfe.tsx", "AkteAbschnitte.tsx", "TodayOverview.tsx"]) {
    assert.doesNotMatch(quelle(datei), /„[^“\n]*"/, datei);
  }
});
