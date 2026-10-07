// Gliederung der Einstellungen in zwei Ebenen (docs/47-einstellungen.md): vier Bereiche vorne, „Für Techniker“ hinten,
// kein Fachwort vorne, alte Verweise kommen an, die Seite ist nicht mehr 1280 px breit.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import {
  AUSNAHMEN, BEREICHE, FACHWOERTER, ICH, SCHALTER, TECHNIK, VORDERE_DATEIEN, ZUGAENGE,
  fachwoerter, kennungVon, vordereTexte, zielAus,
} from "../src/Einstellungen/gliederung.ts";

const quelle = (datei) => readFileSync(new URL(`../src/${datei}`, import.meta.url), "utf8");

/** Die Texte, die eine Datei dem Nutzer zeigen kann: Zeichenketten und Text zwischen Tags, ohne Kommentare. */
export function sichtbareTexte(code) {
  const ohne = code.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/^\s*\/\/.*$/gm, " ").replace(/\s\/\/\s.*$/gm, " ");
  const treffer = [];
  for (const m of ohne.matchAll(/"((?:[^"\\\n]|\\.)*)"|'((?:[^'\\\n]|\\.)*)'|`((?:[^`\\]|\\.)*)`/g)) treffer.push((m[1] ?? m[2] ?? m[3]).replace(/\$\{[^}]*\}/g, "…"));
  // Text zwischen Tags: nicht der Pfeil `=>` und nicht Reste von Ausdrücken (`: !x ?`), die mit einem Zeichen statt einem Buchstaben beginnen.
  for (const m of ohne.matchAll(/(?<![=\-])>([^<>{}]+)</g)) if (/^\s*\p{L}/u.test(m[1]) && !/&&|\|\||=>|![\w(]|\s\?\s|;\s*$/.test(m[1])) treffer.push(m[1]);
  // Ein Wort allein zählt nur, wenn es wie ein Wort für Menschen aussieht (Großbuchstabe), nicht wie eine Kennung (`welt-feed-url`).
  return treffer.map(t => t.trim()).filter(t => t.length > 1 && (/\s/.test(t) || /^[A-ZÄÖÜ]/.test(t)));
}

test("KI-Modelle sind direkt erreichbar; „Für Techniker“ steht hinten und als einziger abgesetzt", () => {
  assert.deepEqual(BEREICHE.map(b => b.label), ["Zugänge", "KI & Modelle", "Was Kingfisher darf", "Kingfisher und du", "Sicherung", "Für Techniker"]);
  assert.deepEqual(BEREICHE.filter(b => b.hinten).map(b => b.id), ["technik"]);
  assert.equal(BEREICHE.at(-1).id, "technik");
  assert.match(BEREICHE.at(-1).satz, /nichts geändert werden/);
  for (const alt of ["Erweitert", "Automatik", "Gedächtnis", "Lokale KI", "Dokumente", "Arbeitsvorlieben", "Rückmeldungen"]) {
    assert.ok(!BEREICHE.some(b => b.label === alt), `„${alt}“ ist kein Reiter mehr`);
  }
});

test("es gibt genau fünf Schalter, und bei jedem steht, was den Rechner verlässt", () => {
  assert.deepEqual(Object.keys(SCHALTER), ["wetter", "welt", "wegezeit", "autostart", "cloud"]);
  for (const [id, schalter] of Object.entries(SCHALTER)) {
    assert.match(schalter.verlaesst, /verl(ä|a)ss/, `${id}: sagt nicht, was den Rechner verlässt`);
    assert.ok(schalter.titel.length > 8 && schalter.verlaesst.length < 260, id);
  }
  assert.match(SCHALTER.autostart.verlaesst, /nichts/);
  assert.match(SCHALTER.cloud.verlaesst, /Aus: alles bleibt auf diesem Rechner/);
  assert.match(SCHALTER.cloud.zustimmung, /willige ein/);
});

test("die Technik-Abschnitte sind vollständig, eindeutig und in Technik.tsx verdrahtet", () => {
  const erwartet = ["routing", "antwortzeiten", "suchindex", "akten", "rueckmeldungen", "befunde", "hintergrund", "filter", "quellen", "kartendienst", "google", "microsoft", "stand", "speicherorte", "fassung"];
  assert.deepEqual(TECHNIK.map(t => t.id), erwartet);
  const technik = quelle("Einstellungen/Technik.tsx");
  for (const { id, titel, satz } of TECHNIK) {
    assert.ok(new RegExp(`\\b${id}:\\s*<`).test(technik), `${id}: kein Inhalt in Technik.tsx`);
    assert.ok(titel && satz.endsWith("."), id);
  }
});

test("jede alte Kennung und jede neue führt an einen Ort, der existiert", () => {
  const alt = { setup: "zugaenge", mail: "zugaenge", calendar: "zugaenge", documents: "zugaenge", world: "darf", profile: "ich",
    recovery: "sicherung", model: "ki", "technik-modelle": "ki", memory: "technik", automation: "technik", rueckmeldungen: "technik", advanced: "technik" };
  for (const [kennung, bereich] of Object.entries(alt)) assert.equal(zielAus(`#${kennung}`).bereich, bereich, kennung);
  assert.deepEqual(zielAus("#model"), { bereich: "ki", technik: null });
  assert.deepEqual(zielAus("#technik-modelle"), { bereich: "ki", technik: null });
  assert.deepEqual(zielAus("#memory"), { bereich: "technik", technik: "suchindex" });
  assert.deepEqual(zielAus("#technik-akten"), { bereich: "technik", technik: "akten" });
  assert.deepEqual(zielAus("#technik-gibtesnicht"), { bereich: "technik", technik: null });
  assert.deepEqual(zielAus(""), { bereich: "zugaenge", technik: null });
  assert.deepEqual(zielAus("#unsinn"), { bereich: "zugaenge", technik: null });
  for (const b of BEREICHE) assert.equal(kennungVon(zielAus(b.id)), b.id);
  for (const t of TECHNIK) assert.equal(kennungVon(zielAus(`technik-${t.id}`)), `technik-${t.id}`);
});

test("der Fachwort-Erkenner findet ganze Wörter und lässt Alltagswörter in Ruhe", () => {
  assert.deepEqual(fachwoerter("IMAP-Server und Port").sort(), ["IMAP", "Port", "Server"]);
  assert.deepEqual(fachwoerter("Ein Embedding für den Feed"), ["Embedding", "Feed"]);
  assert.deepEqual(fachwoerter("Die Rolle spielt eine Rolle"), ["Rolle"]);
  assert.deepEqual(fachwoerter("Postfach, Kalender, Ordner, Wetter, Wegezeit, Startort, Portrait, Hostel"), []);
  assert.ok(FACHWOERTER.includes("IMAP") && FACHWOERTER.includes("Embedding") && FACHWOERTER.includes("Rolle"));
});

test("vorne steht kein Fachwort: nicht in den Texten der Gliederung", () => {
  const texte = vordereTexte();
  assert.ok(texte.length > 30, "die Gliederung liefert ihre vorderen Texte");
  for (const text of texte) assert.deepEqual(fachwoerter(text), [], `Fachwort vorne: „${text}“`);
  assert.ok(ICH.name.frage && ZUGAENGE.ordner.satz);
});

test("vorne steht kein Fachwort: auch nicht in den Dateien, die vorne angezeigt werden", () => {
  for (const datei of VORDERE_DATEIEN) {
    const texte = sichtbareTexte(quelle(datei));
    assert.ok(texte.length > 0, `${datei}: keine Texte erkannt (Erkennung kaputt oder Datei leer)`);
    for (const text of texte) {
      const funde = fachwoerter(text).filter(wort => !AUSNAHMEN.some(a => a.datei === datei && a.wort === wort));
      assert.deepEqual(funde, [], `${datei}: Fachwort vorne: „${text}“`);
    }
  }
});

test("die Texterkennung sieht Zeichenketten und Text zwischen Tags, aber keine Kommentare", () => {
  const code = `// IMAP nur im Kommentar\nconst a = "Gib den IMAP-Host ein"; /* Feed */ return <p>Der Feed fehlt</p>; const b = "welt-feed-url";`;
  const texte = sichtbareTexte(code);
  assert.deepEqual(texte, ["Gib den IMAP-Host ein", "Der Feed fehlt"]);
});

test("die Seite ist nicht mehr 1280 px breit: Mindestbreite aufgehoben, Karten stapeln, Seitenleiste wird ein Streifen", () => {
  const css = quelle("Einstellungen/Einstellungen.css");
  assert.match(css, /html:has\(\.settings-shell\)[^{]*\{\s*min-width:\s*0/);
  assert.doesNotMatch(css.replace(/\/\*[\s\S]*?\*\//g, ""), /(?<!\()min-width:\s*\d{3,4}px/); // Abfragen wie `(min-width: 1100px)` sind keine Mindestbreite
  // Die Seitenleiste als Streifen gilt für alle Seiten und steht nur in Seitenbreite.css (Fremdprobe 3, Befund 14).
  assert.doesNotMatch(css, /\.settings-shell \.sidebar/);
  assert.match(quelle("Seitenbreite.css"), /@media \(max-width: 900px\)[\s\S]*\.shell > \.sidebar \{ position: static/);
  assert.match(css, /@media \(max-width: 700px\)[\s\S]*\.source-form \{ grid-template-columns: minmax\(0, 1fr\)/);
  assert.match(css, /settings-layout \{ grid-template-columns: minmax\(0, 1fr\); \}/);
  // Die globale Mindestbreite ist seit der Fremdprobe (Befund 1) für alle Seiten aufgehoben (tests/seitenbreite.test.mjs).
  assert.doesNotMatch(quelle("styles.css"), /html, body, #root \{ min-width: 1280px/);
});
