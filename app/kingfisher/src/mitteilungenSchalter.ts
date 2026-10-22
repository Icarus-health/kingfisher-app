// Reine Logik des Schalters „Mitteilungen auf dem {Rechner}“ (ohne React, testbar mit node --test; Etappe 5 in
// docs/24-weg-zum-jarvis.md). Die Mitteilungen zeigt die Kingfisher-App auf dem Mac; der Sidecar sagt nur, was fällig ist.
// Hier: ob der Schalter frei ist, der Wochen-Satz für „Fertig heißt“ und der Hinweis, wenn der Mac die Erlaubnis verweigert.
import type { MitteilungenEinstellung, MitteilungenWoche } from "./api";
import { fuerSystem, nurAufDemMac, type SystemAngabe } from "./system.ts";

export const UHRZEIT_VORGABE = "07:30";

export type MitteilungenSchalter = {
  an: boolean;
  /** Ohne Mac-App lässt sich nichts einschalten; Ausschalten geht immer. */
  gesperrt: boolean;
  /** Was der Mensch wissen muss: die fehlende Erlaubnis, oder dass es die Mitteilungen hier nicht gibt. */
  hinweis: string | null;
};

/** `HH:MM`, zwei Ziffern je Teil, vor der Ruhezeit um 21:00 Uhr (dieselbe Regel wie `mitteilungen.uhrzeit_gueltig`). */
export function uhrzeitGueltig(text: string): boolean {
  const treffer = /^([01]\d|2[0-3]):([0-5]\d)$/.exec(text);
  return treffer !== null && Number(treffer[1]) < 21;
}

/** „Diese Woche 5 Mitteilungen, davon 1 als überflüssig gemeldet.“: die Zahl, an der Etappe 5 gemessen wird. */
export function wochenSatz(woche: MitteilungenWoche): string {
  if (woche.gesendet === 0) return "Diese Woche keine Mitteilung.";
  const anzahl = woche.gesendet === 1 ? "1 Mitteilung" : `${woche.gesendet} Mitteilungen`;
  const davon = woche.ueberfluessig === 0 ? "keine" : `davon ${woche.ueberfluessig}`;
  return `Diese Woche ${anzahl}, ${davon} als überflüssig gemeldet.`;
}

/** Nur wenn der Schalter an ist: Ohne Erlaubnis des Systems kommt keine Mitteilung an, und der Satz sagt, wo man sie gibt. */
export function erlaubnisHinweis(stand: Pick<MitteilungenEinstellung, "an" | "erlaubnis">, system: Pick<SystemAngabe, "art">): string | null {
  if (!stand.an) return null;
  if (stand.erlaubnis === "abgelehnt") {
    return fuerSystem("Der {Rechner} hat Mitteilungen für Kingfisher nicht erlaubt. Systemeinstellungen → Mitteilungen → Kingfisher.", system);
  }
  if (stand.erlaubnis === "unbekannt") return "Die Kingfisher-App fragt beim nächsten Start einmal nach der Erlaubnis für Mitteilungen.";
  return null;
}

export function mitteilungenSchalter(stand: MitteilungenEinstellung, system: Pick<SystemAngabe, "art">): MitteilungenSchalter {
  if (system.art !== "mac") {
    return { an: stand.an, gesperrt: !stand.an, hinweis: nurAufDemMac(system, "Mitteilungen") };
  }
  return { an: stand.an, gesperrt: false, hinweis: erlaubnisHinweis(stand, system) };
}
