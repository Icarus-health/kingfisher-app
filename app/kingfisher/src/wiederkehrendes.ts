// Reine Hilfen für Geburtstage und Wiederkehrendes in der Akte (M4, docs/49-kreis-und-privat.md); ohne React, damit
// `node --test` sie prüfen kann. Ein Vorschlag ist kein Fakt: Erst „Stimmt, übernehmen“ legt eine Aussage an.

export type WkEintrag = {
  id: string; art: "vorschlag" | "aussage"; praedikat: "geburtstag" | "wiederkehrend"; wert: string; aussage: string;
  begruendung: string; beleg: { episode_id: string; zitat: string } | null;
};
export type WkStand = { sache: string; offen: WkEintrag[]; angenommen: WkEintrag[] };

/** Die Überschrift der Karte: bei Personen der Geburtstag, sonst das, was sich wiederholt. */
export function wkTitel(stand: WkStand): string {
  const alle = [...stand.offen, ...stand.angenommen];
  return alle.length && alle.every(e => e.praedikat === "geburtstag") ? "Geburtstag" : "Wiederkehrend";
}

/** Gibt es etwas zu zeigen? Ohne Vorschlag und ohne Aussage bleibt die Akte ohne Karte. */
export function wkSichtbar(stand: WkStand | null): boolean {
  return !!stand && (stand.offen.length > 0 || stand.angenommen.length > 0);
}

/** Der Satz über einem Eintrag. */
export function wkSatz(e: WkEintrag): string {
  return e.art === "vorschlag" ? `Vorschlag: ${e.aussage}` : `Steht fest: ${e.aussage}`;
}

/** Was nach dem Klick zu sagen ist, in einem Satz. */
export function wkAntwort(e: WkEintrag, angenommen: boolean): string {
  if (!angenommen) return "Verworfen. Kingfisher schlägt das nicht noch einmal vor.";
  return e.praedikat === "geburtstag"
    ? "Übernommen. Steht die Person bestätigt im inneren Kreis, nennt das Briefing den Geburtstag am Tag davor."
    : "Übernommen. Es steht jetzt in der Akte.";
}
