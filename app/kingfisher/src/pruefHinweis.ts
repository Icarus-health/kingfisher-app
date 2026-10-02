// Reine Logik zum zweiten Tor der Satzprüfung (sidecar: satzpruefung_modell.py) und zur Verlässlichkeit je Satz
// (verlaesslichkeit.py): welche Sätze unter und hinter einer Antwort stehen. Ohne React, testbar mit node --test.

export type PruefZustand = "an" | "aus" | "kein_modell";

/** Nebensatz hinter einem Satz: nur bei „einfach“ und „dünn“ und nur, wenn es etwas über diesen Satz zu sagen gibt. */
export function nebensatz(satz: { verlaesslichkeit?: string; hinweis?: string }) {
  if (satz.verlaesslichkeit !== "einfach" && satz.verlaesslichkeit !== "duenn") return "";
  return (satz.hinweis ?? "").trim();
}

/** „1 Satz verworfen (Prüfmodell)“; leer ohne verworfene Sätze. */
export function verworfenPruefmodell(anzahl: number | undefined) {
  if (!anzahl || anzahl < 1) return "";
  return anzahl === 1 ? "1 Satz verworfen (Prüfmodell)" : `${anzahl} Sätze verworfen (Prüfmodell)`;
}

/** Der Satz im Fuß der Antwort: wie die Sätze geprüft wurden. */
export function pruefungFuss(zustand: PruefZustand | undefined) {
  if (zustand === "an") return "Von einem lokalen Modell formuliert, Satz für Satz gegen die Belege geprüft, dazu von einem Prüfmodell.";
  if (zustand === "aus") return "Von einem lokalen Modell formuliert, Satz für Satz gegen die Belege geprüft. Das Prüfmodell ist ausgeschaltet.";
  return "Von einem lokalen Modell formuliert, Satz für Satz gegen die Belege geprüft. Ein Prüfmodell ist nicht eingerichtet.";
}

/** Der Satz unter dem Schalter in den Einstellungen: was er bewirkt, und ob überhaupt ein Prüfmodell da ist. */
export function pruefungSchalterSatz(stand: { schalter: "an" | "aus"; zustand: PruefZustand; modell: string | null }) {
  if (stand.zustand === "kein_modell") {
    return "Noch kein Prüfmodell eingerichtet; bis dahin ist diese Prüfung aus. Unter „Für diesen Rechner empfohlen“ lässt es sich mit einem Klick laden.";
  }
  const modell = stand.modell ? ` (${stand.modell})` : "";
  return stand.schalter === "an"
    ? `Ein kleines Modell${modell} prüft jeden Satz noch einmal gegen seine Belege; was es nicht bestätigt, entfällt.`
    : `Aus: Die Sätze werden nur ohne Modell geprüft; das spart etwas Zeit je Antwort.${modell ? ` Prüfmodell${modell} bleibt geladen.` : ""}`;
}

/** Für die Modellkarte: ein Satz, wenn der Rolle „pruefung“ kein Modell zugewiesen ist. */
export function pruefRolleOhneModell(row: { rolle: string; wirksam?: { modell: string | null } }) {
  return row.rolle === "pruefung" && !row.wirksam?.modell
    ? "Noch nicht eingerichtet: Bis dahin werden Sätze nur ohne Modell geprüft."
    : "";
}
