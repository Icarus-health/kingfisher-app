// Reine Logik der Frage „Kingfisher beim Anmelden starten?“ (ohne React, testbar mit node --test).
import type {AutostartStand} from "../api";

export const AUTOSTART_WARUM =
  "Dann arbeitet Kingfisher im Hintergrund weiter, und dein Briefing ist fertig, ohne dass du daran denken musst.";

/** Ein Satz, was gerade gilt. Ohne Antwort steht nichts da: Die Frage ist offen, nicht beantwortet. */
export function autostartMeldung(stand: AutostartStand | null): string {
  if (stand === null) return "Wird geladen …";
  if (!stand.verfuegbar) return "Auf diesem System ist das noch nicht verfügbar. Kingfisher startet, wenn du es öffnest.";
  if (stand.gewuenscht === true) return stand.eingerichtet
    ? "Eingerichtet. Kingfisher startet ab der nächsten Anmeldung von selbst."
    : "Wird eingerichtet …";
  if (stand.gewuenscht === false) return stand.eingerichtet
    ? "Wird entfernt …"
    : "Aus. Kingfisher startet, wenn du es öffnest.";
  return "";
}

/** Ob der Schritt als beantwortet gilt (dann „Weiter“, sonst „Überspringen“). */
export const autostartBeantwortet = (stand: AutostartStand | null) => stand !== null && stand.gewuenscht !== null;
