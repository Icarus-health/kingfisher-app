// Reine Logik des Schalters „Wegezeit berechnen“ (ohne React, testbar mit node --test). Fremdprobe, Befund 19:
// Einschalten geht erst, wenn Kingfisher auch rechnen kann; bis dahin sagt die Karte, was fehlt, und bietet es an.
import type {WegezeitStand} from "./api";

export type WegezeitSchalter = {
  /** Der Schalter steht auf „an“. */
  an: boolean;
  /** Der Schalter lässt sich nicht einschalten, weil etwas fehlt. Ausschalten ist nie gesperrt. */
  gesperrt: boolean;
  /** Was fehlt: der Startort (dann steht das Feld da) oder ein Kartendienst (dann ein Satz und ein Verweis). */
  fehlt: "startort" | "dienst" | null;
};

export function wegezeitSchalter(stand: Pick<WegezeitStand, "aktiv" | "kann_rechnen" | "fehlt">): WegezeitSchalter {
  const fehlt = stand.kann_rechnen === false ? (stand.fehlt ?? "dienst") : null;
  return {an: stand.aktiv, gesperrt: !stand.aktiv && fehlt !== null, fehlt};
}
