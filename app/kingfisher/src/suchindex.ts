// Einstellung „Wortteile für die letzten N Jahre“ (Für Techniker → Suchindex): reine Texte und Prüfungen, ohne React,
// testbar mit node --test. Sidecar: suchindex_routes.py. Ältere Quellen stehen nur im kleineren Wortindex und werden nach
// ganzen Wörtern gefunden. Gewählt wird aus einer Liste, nicht getippt (Fremdprobe, Befund 28).

export type SuchindexStand = {
  wortteile_jahre: number; quellen: number; mit_wortteilen: number; nur_woerter: number; groesse_mb: number | null;
  umgestuft?: number; verdichtet?: boolean;
};

export const MAX_JAHRE = 100;

const zahl = (wert: number) => wert.toLocaleString("de-DE");

/** Die Auswahl: Wie weit zurück Wortteile gelten. Ein Wert, der nicht in der Liste steht (aus früheren Fassungen), kommt
 * dazu, damit die Auswahl immer zeigt, was gilt. */
export function jahreAuswahl(aktuell: number): Array<{ jahre: number; text: string }> {
  const werte = [0, 1, 2, 3, 5, 10];
  if (!werte.includes(aktuell) && Number.isInteger(aktuell) && aktuell > 0 && aktuell <= MAX_JAHRE) werte.push(aktuell);
  return werte.sort((a, b) => a - b).map(jahre => ({ jahre, text: jahre === 0 ? "in allen Quellen"
    : jahre === 1 ? "in den Quellen des letzten Jahres" : `in den Quellen der letzten ${zahl(jahre)} Jahre` }));
}

/** „1 Quelle“, „1.200 Quellen“. */
export function quellen(anzahl: number): string {
  return `${zahl(anzahl)} ${anzahl === 1 ? "Quelle" : "Quellen"}`;
}

/** Größe für Menschen: „unbekannt“, „unter 1 MB“, „210 MB“, „1,4 GB“. */
export function groesseText(mb: number | null): string {
  if (mb === null) return "unbekannt";
  if (mb < 1) return "unter 1 MB";
  if (mb < 1000) return `${zahl(Math.round(mb))} MB`;
  return `${(mb / 1024).toLocaleString("de-DE", {maximumFractionDigits: 1})} GB`;
}

/** Ein Satz über den Stand: wie viele Quellen Wortteile haben und wie groß der Index ist. */
export function standText(stand: SuchindexStand): string {
  const platz = `Der Suchindex belegt ${groesseText(stand.groesse_mb)}.`;
  if (stand.wortteile_jahre === 0) {
    if (stand.quellen === 0) return `Noch keine Quellen; jede neue wird nach Wortteilen durchsucht. ${platz}`;
    if (stand.quellen === 1) return `Die eine Quelle wird nach Wortteilen durchsucht. ${platz}`;
    return `Alle ${quellen(stand.quellen)} werden nach Wortteilen durchsucht. ${platz}`;
  }
  const wird = (anzahl: number) => anzahl === 1 ? "wird" : "werden";
  return `${quellen(stand.mit_wortteilen)} ${wird(stand.mit_wortteilen)} nach Wortteilen durchsucht, ${zahl(stand.nur_woerter)} ältere nur nach ganzen Wörtern. ${platz}`;
}

/** Die Rückmeldung nach dem Umbau: was geschah. Was es brachte, steht im Stand darüber. */
export function ergebnisText(stand: SuchindexStand): string {
  const bewegt = stand.umgestuft ?? 0;
  const wie = bewegt === 0 ? "Es musste nichts umgestellt werden." : `${quellen(bewegt)} ${bewegt === 1 ? "wurde" : "wurden"} umgestellt.`;
  return `Gespeichert. ${wie}`;
}
