import {test} from "node:test";
import assert from "node:assert/strict";
import {ergebnisSatz, gruppieren, waehlbar, wahlTexte, zaehlSatz} from "../src/befunde.ts";

const widerspruch = {art: "widerspruch", schwere: "wichtig", unterart: "frist", werte: {alt: "20.10.2026", neu: "06.11.2026"},
  vorschlaege: [{wahl: "neu", zustand: "pending"}, {wahl: "alt", zustand: "pending"}]};
const aussage = {art: "aussage_gegen_quelle", schwere: "wichtig", unterart: "k-1", werte: {alt: "Gutenbergring 3", neu: "Mühlweg 8"},
  vorschlaege: [{wahl: "neu", zustand: "pending"}]};
const ruhend = {art: "waise", schwere: "hinweis", unterart: "ruhend", werte: {}, vorschlaege: []};
const querverweis = {art: "querverweis", schwere: "hinweis", unterart: "", werte: {}, vorschlaege: []};

test("Zählsatz ohne Prozent und ohne Fachwort", () => {
  assert.equal(zaehlSatz({offen: 0, wichtig: 0}), "Nichts aufgefallen. Die Akten widersprechen sich nicht.");
  assert.equal(zaehlSatz({offen: 1, wichtig: 0}), "1 Punkt, nur zur Kenntnis.");
  assert.equal(zaehlSatz({offen: 3, wichtig: 2}), "3 Punkte, davon 2 zum Entscheiden.");
});

test("Zwei Klicks nur bei Widersprüchen mit offenem Vorschlag; auf dem Knopf steht der Wert", () => {
  assert.equal(waehlbar(widerspruch), true);
  assert.equal(waehlbar(aussage), true);
  assert.equal(waehlbar(ruhend), false);
  assert.equal(waehlbar({...widerspruch, vorschlaege: [{wahl: "neu", zustand: "rejected"}]}), false);
  assert.deepEqual(wahlTexte(widerspruch), {neu: "06.11.2026 gilt", alt: "20.10.2026 gilt"});
  assert.deepEqual(wahlTexte(aussage), {neu: "„Mühlweg 8“ übernehmen", alt: "„Gutenbergring 3“ bleibt"});
});

test("Entscheidungen zuerst, ruhende Akten gesammelt unten", () => {
  const {oben, ruhend: unten} = gruppieren([querverweis, ruhend, widerspruch]);
  assert.deepEqual(oben.map(b => b.art), ["widerspruch", "querverweis"]);
  assert.deepEqual(unten.map(b => b.unterart), ["ruhend"]);
});

test("Nach jedem Klick ein Satz, was passiert ist", () => {
  assert.equal(ergebnisSatz("neu", widerspruch), "Gespeichert: 06.11.2026 gilt jetzt. Kingfisher nutzt diesen Stand ab sofort.");
  assert.equal(ergebnisSatz("alt", aussage), "„Gutenbergring 3“ bleibt, wie du es angenommen hattest.");
  assert.equal(ergebnisSatz("erledigt", ruhend), "Als erledigt vermerkt.");
  assert.match(ergebnisSatz("abgewiesen", querverweis), /^Ignoriert\./);
});
