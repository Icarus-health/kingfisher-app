// Reine Logik der Beleghinweise im „Weg nach unten“ (ohne React, testbar mit node --test): was der Sidecar an einem
// Beleg kennzeichnet, steht dort ruhig hinter dem Titel. Überholt, andere Person gleichen Namens, außerhalb des Zeitraums.
import type { SatzBeleg } from "./api";

/** Die Hinweise eines Belegs in fester Reihenfolge: überholt zuerst, danach die Kennzeichen des Sidecars. */
export function belegHinweise(beleg: Pick<SatzBeleg, "ueberholt" | "kennzeichen">): string[] {
  const hinweise: string[] = [];
  if (beleg.ueberholt) hinweise.push(beleg.ueberholt.text);
  for (const kennzeichen of beleg.kennzeichen ?? []) {
    if (kennzeichen.text && !hinweise.includes(kennzeichen.text)) hinweise.push(kennzeichen.text);
  }
  return hinweise;
}

/** Ein Beleg mit Hinweis steht gedämpft da: die Quelle ist da, gehört aber nicht zum Kern der Antwort. */
export function istGekennzeichnet(beleg: Pick<SatzBeleg, "ueberholt" | "kennzeichen">): boolean {
  return belegHinweise(beleg).length > 0;
}
