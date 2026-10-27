// Paket P (Persona-Prüfung, D7, 27.10.2026): Auskunft und Löschen je Person, Sicherung aus der Liste wiederherstellen.
// Hier die Sätze und Regeln ohne Browser; der Dialog selbst ist der geprüfte Baustein `Rueckfrage` (Paket B).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { anzahl, exportSatz, geloeschtSatz, holeStand, loeschRueckfrage, merkeStand, sicherungArt, sicherungZeit,
  sichtbareSicherungen, standSatz, wiederherstellenFrage } from "../src/personDaten.ts";

const NULL = { quellen_nur_ihre: 0, quellen_geteilt: 0, aussagen: 0, vorschlaege: 0, offene_vorschlaege: 0, aufgaben: 0,
  zusammenfuehrungen: 0, schreibweisen: 0, adressen: 0, vermerke: 0, zusammenfassungen: 0, gespraeche: 0, projekte: 0 };

test("Die Rückfrage vor dem Löschen nennt Anzahlen, was bleibt und warum", () => {
  const f = loeschRueckfrage({ name: "Dora Lind", projekte: ["Mietsache Lind"], zahlen: { ...NULL, quellen_nur_ihre: 7,
    quellen_geteilt: 1, aufgaben: 1, adressen: 1, schreibweisen: 1, vermerke: 3, gespraeche: 2, projekte: 1 } });
  assert.equal(f.frage, "Alles zu Dora Lind löschen?");
  assert.match(f.satz, /nicht rückgängig/);
  assert.match(f.satz, /Einstellungen → Kingfisher und du/);
  assert.ok(f.geloescht.some(z => z.startsWith("7 Quellen nur mit dieser Person")));
  assert.ok(f.geloescht.some(z => z.includes("1 Quelle, an der auch andere")));
  assert.ok(f.geloescht.includes("1 Aufgabe von ihr oder für sie"));
  assert.ok(f.geloescht.includes("ihre Adresse und Schreibweisen"));
  assert.ok(f.geloescht.includes("3 Vermerke"));
  assert.ok(f.bleibt[0].includes("Postfach und Kalender"));
  assert.ok(f.bleibt.some(z => z.includes("ohne Bezug zu ihr")));
  assert.ok(f.bleibt.some(z => z.startsWith("2 Gespräche mit Kingfisher")));
  assert.ok(f.bleibt.some(z => z.includes("„Mietsache Lind“")));
  assert.ok(f.bleibt.some(z => z.includes("Ältere Sicherungen")));
});

test("Was es nicht gibt, steht nicht in der Rückfrage", () => {
  const f = loeschRueckfrage({ name: "Ben", projekte: [], zahlen: { ...NULL, quellen_nur_ihre: 1, adressen: 1 } });
  assert.deepEqual(f.geloescht, ["1 Quelle nur mit dieser Person (aus Kingfisher, nicht aus Postfach oder Kalender)", "ihre Adresse"]);
  assert.ok(!f.bleibt.some(z => /Gespräch|Projekt|anderen Beteiligten/.test(z)));
});

test("Kein „…\" in den Sätzen: nur „…“", () => {
  for (const datei of ["../src/personDaten.ts", "../src/PersonMehr.tsx", "../src/SicherungZurueck.tsx", "../src/PersonSperren.tsx"]) {
    const text = readFileSync(new URL(datei, import.meta.url), "utf8");
    assert.doesNotMatch(text, /„[^“"\n]*"/, datei);
  }
});

test("Sätze nach Export und Löschen sagen, was passiert ist", () => {
  assert.match(exportSatz("Auskunft-Dora-Lind-2026-10-27.zip"), /„Auskunft-Dora-Lind-2026-10-27\.zip“.*Downloads.*Nichts davon hat den Rechner verlassen/);
  assert.equal(geloeschtSatz("Dora Lind"), "Alles zu Dora Lind gelöscht. Kingfisher legt die Person nicht wieder an.");
  assert.equal(anzahl(1, "Quelle", "Quellen"), "1 Quelle");
  assert.equal(anzahl(0, "Quelle", "Quellen"), "0 Quellen");
});

test("Wiederherstellen: Frage in einem Satz mit dem Zeitpunkt, Art in Alltagssprache", () => {
  const f = wiederherstellenFrage({ erstellt: "2026-10-26T14:05:00+01:00" });
  assert.match(f.frage, /^Stand vom 26\. Oktober, \d\d:\d\d wiederherstellen\?$/);
  assert.match(f.satz, /^Was seitdem dazukam, geht verloren\./);
  assert.match(f.satz, /rückgängig/);
  assert.equal(sicherungArt("regelmaessig"), "regelmäßig");
  assert.equal(sicherungArt("vor_update"), "vor einem Update");
  assert.equal(sicherungArt("vor_wiederherstellung"), "vor dem Wiederherstellen");
  assert.match(sicherungZeit("2026-10-26T14:05:00+01:00"), /^Mo\., 26\. Oktober 2026, \d\d:\d\d$/);
  assert.equal(sicherungZeit("kaputt"), "kaputt");
  assert.match(standSatz({ stand: "2026-10-26T14:05:00+01:00", art: "regelmaessig" }), /^Wiederhergestellt: Jetzt gilt der Stand vom 26\. Oktober/);
  assert.match(standSatz({ stand: "2026-10-27T09:00:00+01:00", art: "vor_wiederherstellung" }), /^Der Stand von vorher/);
});

test("Vorne die jüngsten Sicherungen, „vor dem Wiederherstellen“ nur die letzte", () => {
  const e = (name, art) => ({ name, erstellt: name, art, bytes: 1 });
  const liste = [e("9", "vor_wiederherstellung"), e("8", "vor_wiederherstellung"), e("7", "regelmaessig"),
    e("6", "regelmaessig"), e("5", "vor_update"), e("4", "regelmaessig"), e("3", "regelmaessig"), e("2", "regelmaessig")];
  assert.deepEqual(sichtbareSicherungen(liste, false).map(x => x.name), ["9", "7", "6", "5", "4"]);
  assert.equal(sichtbareSicherungen(liste, true).length, 8);
});

test("Der Stand wartet über das Neuladen und gilt einmal", () => {
  const ablage = new Map();
  const speicher = { setItem: (k, v) => ablage.set(k, v), getItem: k => ablage.get(k) ?? null, removeItem: k => ablage.delete(k) };
  const stand = { name: "kingfisher-20261026T130500Z", stand: "2026-10-26T14:05:00+01:00", art: "regelmaessig", am: "x", rueckgaengig: "vor-wiederherstellung-20261027T080000Z" };
  merkeStand(stand, speicher);
  assert.deepEqual(holeStand(speicher), stand);
  assert.equal(holeStand(speicher), null);
  // Ohne Speicher (privates Fenster) und mit Unsinn darin: kein Absturz.
  assert.equal(holeStand(null), null);
  ablage.set("kingfisher.sicherung.wiederhergestellt", "{kaputt");
  assert.equal(holeStand(speicher), null);
  const wirft = { getItem: () => { throw new Error("gesperrt"); }, removeItem: () => {}, setItem: () => { throw new Error("gesperrt"); } };
  assert.equal(holeStand(wirft), null);
  merkeStand(stand, wirft);
});

test("Personenakte und Sicherung hängen an den bestehenden Seiten, keine neue Seite", () => {
  const akte = readFileSync(new URL("../src/MemoryProfile.tsx", import.meta.url), "utf8");
  assert.match(akte, /<PersonMehr /);
  const seite = readFileSync(new URL("../src/Einstellungen/Seite.tsx", import.meta.url), "utf8");
  assert.match(seite, /sicherung: <><RecoverySettings \/><SicherungZurueck \/><\/>/);
  const ich = readFileSync(new URL("../src/Einstellungen/Ich.tsx", import.meta.url), "utf8");
  assert.match(ich, /<PersonSperren \/>/);
  const mehr = readFileSync(new URL("../src/PersonMehr.tsx", import.meta.url), "utf8");
  // Löschen nur über die Rückfrage, rot, mit Fokus auf „Abbrechen“ (Vorgabe des Bausteins).
  assert.match(mehr, /<Rueckfrage [^>]*bestaetigen="Endgültig löschen" rot/);
  assert.doesNotMatch(mehr, /start="feld"/);
});
