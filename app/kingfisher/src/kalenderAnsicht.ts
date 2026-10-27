// Welche Kalenderansicht beim Öffnen steht (Persona-Prüfung, Paket H, H1, 27.10.2026): das Modell ohne Browser.
//
// Bis 1.0.29 war der Monat überall die Vorgabe, und die Seite schrieb jede Ansicht beim Öffnen zurück in den Speicher,
// auch die Vorgabe selbst. Am Handy stand so der Monat mit Punkten statt Titeln, und eine Wahl des Nutzers war von der
// Vorgabe nicht zu unterscheiden. Jetzt gilt:
//
// * Schmal (bis 700 px, das Handy) ist die Vorgabe die Liste: die nächsten sieben Tage ab heute, jeder Termin mit
//   Uhrzeit, ganzem Titel und Ort, ohne seitliches Rollen. Breit bleibt es der Monat.
// * Gemerkt wird nur, was der Nutzer selbst im Umschalter wählt (eigener Schlüssel). Der alte Schlüssel gilt weiter, außer
//   er sagt „Monat“ am Handy: Das war fast immer die alte Vorgabe, nicht eine Wahl.

export type KalenderAnsicht = "Tag" | "Woche" | "Monat" | "Liste" | "Jahr";
export const KALENDER_ANSICHTEN: KalenderAnsicht[] = ["Tag", "Woche", "Monat", "Liste", "Jahr"];
/** Nur die Wahl des Nutzers. */
export const WAHL_SCHLUESSEL = "kingfisher-kalender-wahl";
/** Bis 1.0.29: jede Ansicht, auch die Vorgabe. */
export const ALTER_SCHLUESSEL = "kingfisher-calendar-view";
/** Bis zu dieser Breite ist der Kalender „schmal“ (wie `Seitenbreite.css`). */
export const SCHMAL = "(max-width: 700px)";

type Speicher = Pick<Storage, "getItem" | "setItem" | "removeItem">;
const gueltig = (wert: string | null): wert is KalenderAnsicht => KALENDER_ANSICHTEN.includes(wert as KalenderAnsicht);

/** Die Vorgabe, wenn der Nutzer nichts gewählt hat: am Handy die Liste, sonst der Monat. */
export function vorgabeAnsicht(schmal: boolean): KalenderAnsicht {
  return schmal ? "Liste" : "Monat";
}

/** Was der Nutzer gewählt hat, oder `null`. Ohne Speicher (privates Fenster) gibt es keine Wahl, nur die Vorgabe. */
export function gewaehlteAnsicht(speicher: Speicher | null | undefined, schmal: boolean): KalenderAnsicht | null {
  try {
    const wahl = speicher?.getItem(WAHL_SCHLUESSEL) ?? null;
    if (gueltig(wahl)) return wahl;
    const alt = speicher?.getItem(ALTER_SCHLUESSEL) ?? null;
    if (gueltig(alt) && !(schmal && alt === "Monat")) return alt;
  } catch { /* Ohne Speicher bleibt die Vorgabe. */ }
  return null;
}

/** Die Ansicht beim Öffnen: die Wahl des Nutzers, sonst die Vorgabe für diese Breite. */
export function anfangsAnsicht(speicher: Speicher | null | undefined, schmal: boolean): KalenderAnsicht {
  return gewaehlteAnsicht(speicher, schmal) ?? vorgabeAnsicht(schmal);
}

/** Merkt eine Wahl im Umschalter (und nur sie); der alte Schlüssel wird damit überflüssig. */
export function merkeAnsicht(speicher: Speicher | null | undefined, ansicht: KalenderAnsicht): void {
  try {
    speicher?.setItem(WAHL_SCHLUESSEL, ansicht);
    speicher?.removeItem(ALTER_SCHLUESSEL);
  } catch { /* Gilt dann für diese Sitzung. */ }
}

/**
 * Wie weit die Seite rollen muss, damit eine Zeile (die laufende Woche im Monat) ganz im Bild steht: 0, wenn sie schon
 * steht; sonst gerade so weit, dass sie über dem unteren Rand (Navigationsleiste am Handy) bzw. unter dem oberen steht.
 * Passt sie nicht ganz hinein, steht ihr Anfang oben.
 */
export function rollenFuerZeile(zeile: { oben: number; unten: number }, bild: { oben: number; unten: number }, luft = 12): number {
  const hoch = bild.unten - bild.oben;
  if (zeile.oben >= bild.oben && zeile.unten <= bild.unten) return 0;
  if (zeile.unten - zeile.oben + 2 * luft > hoch || zeile.oben < bild.oben) return Math.round(zeile.oben - bild.oben - luft);
  return Math.round(zeile.unten - bild.unten + luft);
}
