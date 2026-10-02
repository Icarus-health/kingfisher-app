// Die Quellenvorgaben unter „Was Kingfisher darf“: ein Klick fügt hinzu, ein zweiter entfernt; eigene Quellen bleiben eigene.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { eigeneQuellen, normiereAdresse, vorgabeZustand, vorgabenStandSatz } from "../src/weltVorgaben.ts";

const VORGABEN = [
  { id: "tagesschau", url: "https://www.tagesschau.de/index~rss2.xml", feed_id: "f1" },
  { id: "heise", url: "https://www.heise.de/rss/heise-atom.xml", feed_id: null },
  { id: "zeit", url: "https://newsfeed.zeit.de/index", feed_id: "f3" },
];
const FEEDS = [
  { id: "f1", url: VORGABEN[0].url, enabled: true },
  { id: "f3", url: VORGABEN[2].url, enabled: false },
  { id: "f9", url: "https://eigene.example/feed.xml", enabled: true },
];

test("eine Vorgabe ist an, abbestellt oder aus, je nachdem, ob und wie sie hinzugefügt wurde", () => {
  assert.deepEqual(VORGABEN.map(v => vorgabeZustand(v, FEEDS)), ["an", "aus", "abbestellt"]);
  assert.equal(vorgabeZustand({ feed_id: "gibt-es-nicht" }, FEEDS), "aus");
  assert.equal(vorgabeZustand({ feed_id: null }, []), "aus");
});

test("eigene Quellen sind die Feeds, die nicht aus der Vorgabeliste stammen", () => {
  assert.deepEqual(eigeneQuellen(FEEDS, VORGABEN).map(f => f.id), ["f9"]);
  assert.deepEqual(eigeneQuellen([], VORGABEN), []);
});

test("die Adresse: ohne Schema kommt https davor, Leerzeichen und Namen ohne Punkt sind keine Adresse", () => {
  assert.equal(normiereAdresse("https://www.tagesschau.de/feed.xml"), "https://www.tagesschau.de/feed.xml");
  assert.equal(normiereAdresse("  www.tagesschau.de/feed.xml "), "https://www.tagesschau.de/feed.xml");
  assert.equal(normiereAdresse("http://example.org/feed"), "http://example.org/feed", "http bleibt, der Sidecar lehnt es mit einem Satz ab");
  assert.equal(normiereAdresse(""), "");
  assert.equal(normiereAdresse("tagesschau"), "");
  assert.equal(normiereAdresse("zwei Wörter.de"), "");
  assert.equal(normiereAdresse("https://"), "");
});

test("unter den Vorgaben steht, von wann die Liste ist und dass die Adressen nicht abgerufen wurden", () => {
  const satz = vorgabenStandSatz({ stand: "2026-09-30", abgerufen: null });
  assert.match(satz, /30\. September 2026/);
  assert.match(satz, /noch nicht abgerufen/);
  const geprueft = vorgabenStandSatz({ stand: "2026-09-30", abgerufen: "2026-10-05" });
  assert.match(geprueft, /5\. Oktober 2026 geprüft/);
  assert.doesNotMatch(geprueft, /noch nicht abgerufen/);
});

test("die Oberfläche schaltet mit einem Klick ein und mit dem zweiten aus, und legt nichts ohne Klick an", () => {
  const code = readFileSync(new URL("../src/WeltSettings.tsx", import.meta.url), "utf8");
  assert.match(code, /aria-pressed=\{zustand === "an"\}/);
  assert.match(code, /zustand === "an" \? api\.weltFeedWeg\(/);
  assert.match(code, /: api\.weltFeedNeu\(v\.url, v\.label\)/);
  assert.match(code, /zustand === "abbestellt" \? api\.weltFeedSchalter\(/);
  // Die Vorgaben erscheinen erst, wenn der Schalter an ist: ohne Einwilligung kein Abruf.
  assert.match(code, /\{stand\.aktiv && <>\s*<p className="source-hint">Höchstens eine Meldung/);
});
