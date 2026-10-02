// Kleine reine Hilfen für „In die Akte übernehmen“; ohne React, damit sie sich ohne Browser testen lassen.
import type { UebernehmenErgebnis, UebernehmenSatz, UebernehmenVorschlag } from "./api";

/** Nur Antworten in Sätzen lassen sich übernehmen: keine Rückfragen, kein Zitatmodus ohne Sätze. */
export function uebernehmbar(nachricht: { role: string; status: string; metadata?: { context?: { satzantwort?: { saetze?: unknown[] }; clarification_choices?: unknown[]; clarification_date?: boolean } } }): boolean {
  if (nachricht.role !== "assistant" || nachricht.status !== "complete") return false;
  const kontext = nachricht.metadata?.context;
  if (kontext?.clarification_choices?.length || kontext?.clarification_date) return false;
  return Boolean(kontext?.satzantwort?.saetze?.length);
}

/** Die Vorgabe der Auswahl: alle Sätze, die nichts gegen sich haben (kein Hinweis, nicht schon in der Akte, nicht schon vorgeschlagen). */
export function vorgabeWahl(saetze: UebernehmenSatz[], bisher: UebernehmenVorschlag[] = []): number[] {
  const vorhanden = new Set(bisher.map(v => v.statement));
  return saetze.filter(s => s.vorgabe && !vorhanden.has(s.text)).map(s => s.nr);
}

/** „1 Satz“ / „3 Sätze“. */
export function saetzeText(anzahl: number): string {
  return anzahl === 1 ? "1 Satz" : `${anzahl} Sätze`;
}

/** Was nach dem Vorschlagen ohne Karte zu sagen ist: ein Satz steht schon in der Akte, liegt schon vor oder ging schief. */
export function ergebnisText(e: UebernehmenErgebnis): string {
  if (e.status === "steht_schon") return "Steht schon in der Akte.";
  if (e.status === "liegt_vor") return "Liegt schon zur Entscheidung vor.";
  if (e.status === "fehler") return e.grund || "Das ließ sich nicht vorschlagen.";
  return "Vorgeschlagen.";
}

/** Der Satz über den Vorschlägen: „Vorgeschlagen.“ oder, wenn nichts Neues entstand, der Grund. */
export function vorgeschlagenText(ergebnisse: UebernehmenErgebnis[]): string {
  const neu = ergebnisse.filter(e => e.status === "vorgeschlagen").length;
  if (neu > 0) return "Vorgeschlagen.";
  if (ergebnisse.length > 0 && ergebnisse.every(e => e.status === "steht_schon")) return "Steht schon in der Akte.";
  if (ergebnisse.some(e => e.status === "liegt_vor")) return "Liegt schon zur Entscheidung vor.";
  return "Nichts vorgeschlagen.";
}
