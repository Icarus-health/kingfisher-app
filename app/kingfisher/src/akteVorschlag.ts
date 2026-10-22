// Kleine reine Hilfen für den Vorschlag „Neue Akte?“ (sidecar: akten_vorschlaege.py); ohne React, damit `node --test`
// sie prüft. Ein Projekt ist Ablage, kein Fakt: Es entsteht nur durch den Klick, und jeder Klick antwortet mit einem Satz.

export type AkteVorschlagEntscheidungArt = "angenommen" | "abgelehnt";

/** Die Zeile oben in der Akte eines nur erwähnten Projekts: Frage zuerst, dann der Grund als Satz. */
export function vorschlagFrage(grund: string): string {
  const kern = grund.trim().replace(/[.\s]+$/, "");
  return kern ? `Daraus eine Akte machen? ${kern}.` : "Daraus eine Akte machen?";
}

/** Was unter einer gemerkten Entscheidung steht, damit man sieht, was gilt, und es zurücknehmen kann. */
export function entscheidungSatz(entscheidung: AkteVorschlagEntscheidungArt, quellen: number): string {
  if (entscheidung === "angenommen") {
    const zahl = quellen === 0 ? "ohne neu zugeordnete Quelle" : quellen === 1 ? "eine Quelle zugeordnet" : `${quellen} Quellen zugeordnet`;
    return `Aus einem Vorschlag angelegt, ${zahl}.`;
  }
  return "Du hast „Nein danke“ gesagt: Dieser Name wird nicht mehr vorgeschlagen.";
}

/** Die Beschriftung des Knopfes, der eine Entscheidung zurücknimmt. */
export function zurueckBeschriftung(entscheidung: AkteVorschlagEntscheidungArt): string {
  return entscheidung === "angenommen" ? "Akte wieder auflösen" : "Doch vorschlagen";
}

/** Was nach einem gescheiterten Klick dasteht (Grundsatz 4: jede Aktion antwortet, auch mit dem Grund). */
export function fehlerSatz(status: number | null): string {
  if (status === 409) return "Das ist schon entschieden. Bitte die Seite neu laden.";
  if (status === 404) return "Diesen Vorschlag gibt es nicht mehr. Bitte die Seite neu laden.";
  return "Das ließ sich gerade nicht speichern. Bitte noch einmal versuchen.";
}
