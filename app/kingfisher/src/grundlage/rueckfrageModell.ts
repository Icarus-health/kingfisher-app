// Die Rückfrage als echter Dialog (Persona-Prüfung, Paket B, B3, 27.10.2026): das Modell ohne Browser.
//
// Bis 1.0.29 stand „Quelle wirklich entfernen?“ als Satz mit zwei Knöpfen mitten in der Zeile: Der Fokus fiel ins Leere,
// weil der Knopf, der die Frage auslöste, mit ihr verschwand; Escape brach nicht ab, und der erste Tab landete auf
// „Entfernen“, das sich nicht zurücknehmen lässt. Jetzt ist jede Rückfrage ein Dialog (`Rueckfrage.tsx`): beschriftet,
// modal, der Fokus beginnt auf der sicheren Wahl, Tab bleibt im Dialog, Escape bricht ab, und danach steht der Fokus
// wieder am Auslöser (oder, wenn der mit seiner Zeile verschwand, auf der Liste, in der er stand: `fokusZiel.ts`).

/** Was im Dialog den Fokus nehmen kann (für die Fokusfalle). */
export const RUECKFRAGE_BEDIENBAR = "button, a[href], input:not([type=hidden]), select, textarea, summary, [tabindex]:not([tabindex='-1'])";

/** Rolle der Rückfrage: Sie unterbricht und will eine Antwort (WAI-ARIA `alertdialog`). */
export const RUECKFRAGE_ROLLE = "alertdialog";

/**
 * Fokusfalle: Wohin Tab (oder Umschalt+Tab) vom Element `jetzt` (Index unter `anzahl` bedienbaren, -1: keines davon)
 * führt, wenn es den Dialog sonst verließe. `null` heißt: Der Browser macht den normalen Schritt im Dialog.
 */
export function fallenZiel(jetzt: number, anzahl: number, rueckwaerts: boolean): number | null {
  if (anzahl <= 0) return null;
  if (jetzt < 0) return rueckwaerts ? anzahl - 1 : 0;
  if (rueckwaerts && jetzt === 0) return anzahl - 1;
  if (!rueckwaerts && jetzt === anzahl - 1) return 0;
  return null;
}

/** Womit der Dialog beginnt: auf der sicheren Wahl; nur wenn erst etwas einzutragen ist, das allein nichts auslöst
 * (ein Grund für den Widerruf), im Feld. */
export type RueckfrageStart = "abbrechen" | "feld";
export function startSelektor(start: RueckfrageStart): string {
  return start === "feld" ? "[data-rueckfrage-feld]" : "[data-rueckfrage-abbrechen]";
}
