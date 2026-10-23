// Tastatursteuerung der Segmente (Segmente.tsx, docs/16-gestaltung.md „Grundlage vom 23.10.2026“).
// Reine Funktion, damit sie ohne Browser prüfbar ist: Welche Stelle wird nach einem Tastendruck gewählt?

/** Die Stelle, die nach `taste` gewählt wird, oder `null`, wenn die Taste nichts bewirkt. Pfeil rechts/unten geht
 * zur nächsten, Pfeil links/oben zur vorigen wählbaren Stelle (am Ende geht es vorne weiter), Pos1/Ende zur ersten
 * bzw. letzten. Abgeschaltete Stellen werden übersprungen. */
export function segmentNachTaste(taste: string, aktuell: number, abgeschaltet: readonly boolean[]): number | null {
  const anzahl = abgeschaltet.length;
  const waehlbar = (i: number) => !abgeschaltet[i];
  if (!anzahl || !abgeschaltet.some(a => !a)) return null;
  const schritt = taste === "ArrowRight" || taste === "ArrowDown" ? 1 : taste === "ArrowLeft" || taste === "ArrowUp" ? -1 : 0;
  if (schritt) {
    const start = aktuell >= 0 && aktuell < anzahl ? aktuell : schritt > 0 ? -1 : anzahl;
    for (let n = 1; n <= anzahl; n++) {
      const i = (((start + schritt * n) % anzahl) + anzahl) % anzahl;
      if (waehlbar(i)) return i === aktuell ? null : i;
    }
    return null;
  }
  if (taste === "Home" || taste === "End") {
    const reihe = taste === "Home" ? abgeschaltet.map((_, i) => i) : abgeschaltet.map((_, i) => anzahl - 1 - i);
    const i = reihe.find(waehlbar)!;
    return i === aktuell ? null : i;
  }
  return null;
}

/** Welche Stelle per Tab erreichbar ist: die gewählte, sonst die erste wählbare. */
export function segmentImFokus(gewaehlt: number, abgeschaltet: readonly boolean[]): number {
  if (gewaehlt >= 0 && gewaehlt < abgeschaltet.length && !abgeschaltet[gewaehlt]) return gewaehlt;
  return abgeschaltet.findIndex(a => !a);
}
