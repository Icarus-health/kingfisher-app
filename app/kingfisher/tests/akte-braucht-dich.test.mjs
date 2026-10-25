import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const akte = readFileSync(new URL("../src/AkteAbschnitte.tsx", import.meta.url), "utf8");
const api = readFileSync(new URL("../src/api.ts", import.meta.url), "utf8");

test("Braucht dich: jede Wahl ist ein Klick und antwortet mit dem Hinweis samt Rückgängig (V4)", () => {
  assert.match(akte, /p\.wahl\.map\(w => <button[^>]*onClick=\{\(\) => entscheiden\(p\.ziel, w\.entscheidung/);
  // Der Hinweis der App statt einer eigenen Meldung; „Rückgängig“ stellt den Vorwert wieder her (vorher), sonst die Vermutung.
  assert.match(akte, /zeigeHinweis\(\{ text: \(termin \? GEMERKT_TERMIN : GEMERKT\)\[entscheidung\], rueckgaengig: zurueckWeg\(ziel, antwort\.vorher\) \}\)/);
  assert.match(akte, /if \(vorher\) await api\.akteEntscheiden\(sache, ziel, vorher\);\n\s*else await api\.akteEntscheidungZuruecknehmen\(sache, ziel\);/);
  assert.doesNotMatch(akte, /akte-meldung|setMeldung|uebergabe/);
  // Wer eine eigene Entscheidung zurücknimmt, kann im Hinweis die frühere wiederherstellen.
  assert.match(akte, /zuruecknehmen=\{ziel => void zuruecknehmen\(ziel, "offen"\)\}/);
  assert.match(akte, /zuruecknehmen\(t\.ziel!, t\.entscheidung \?\? null\)/);
  assert.match(api, /akteEntscheiden: \(sache: string, ziel: string, entscheidung: AkteEntscheidung\)/);
  assert.match(api, /akteEntscheidungZuruecknehmen: \(sache: string, ziel: string\)/);
});

test("Zeitstrahl: Punkte sind Knöpfe mit Beschriftung für Tastatur und Bildschirmleser", () => {
  assert.match(akte, /className=\{`akte-punkt akte-punkt-\$\{x\.p\.art\}/);
  assert.match(akte, /aria-label=\{beschreibung\(x\.p\)\}/);
  assert.match(akte, /aria-pressed=\{gewaehlt === x\.p\}/);
});

test("Offene Punkte nennen ihre Richtung und lassen sich ablegen", () => {
  for (const titel of ["Du hast zugesagt", "Du wartest auf", "Bitten an dich"]) assert.match(akte, new RegExp(`titel: "${titel}"`));
  assert.match(akte, /entscheiden\(e\.ziel!, "erledigt"\)\}>Erledigt<\/button>/);
  assert.match(akte, /entscheiden\(e\.ziel!, "offen"\)\}>Doch noch offen<\/button>/);
});

test("Zeitstrahl: ein Tab-Stopp, Pfeiltasten führen von Punkt zu Punkt", () => {
  assert.match(akte, /tabIndex=\{nummer\.get\(x\.p\) === aktiv \? 0 : -1\}/);
  assert.match(akte, /ereignis\.key === "ArrowRight"/);
  assert.match(akte, /onKeyDown=\{tasten\}/);
});
