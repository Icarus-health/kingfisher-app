// Worauf sich eine Antwort im Gespräch stützt (Fremdprobe 2, Befund 13). Reine Logik ohne React, testbar mit node --test.
//
// Unter jeder Antwort steht sichtbar, ob sie belegt ist: die lesbaren Quellenhinweise (`context.quellen`, mit einem Klick
// zur Quelle), die Quellen einer Antwort aus Rohquellen (`context.source_links`), die Sätze mit ihrem Weg nach unten
// (`context.satzantwort`), oder deutlich „ohne Beleg“. Hinweise des Programms und Rückfragen tragen nichts davon.
import { gueltigeQuellen } from "./quellenWeg.ts";
import { systemhinweis } from "./rueckmeldung.ts";

type Nachricht = {
  role: string; status: string;
  metadata?: { memory_candidate_id?: unknown; systemhinweis?: unknown; context?: {
    quellen?: unknown; source_links?: unknown[]; satzantwort?: unknown;
    clarification_choices?: unknown[]; clarification_date?: boolean } };
};

export type BelegStand =
  | { art: "quellen"; anzahl: number }
  | { art: "quellenlinks"; anzahl: number }
  | { art: "saetze" }
  | { art: "ohne" }
  | { art: "keiner" };

/** Der Satz unter einer Antwort ohne Beleg. */
export const OHNE_BELEG = "Ohne Beleg: Diese Antwort stützt sich auf keine Quelle aus deinem Gedächtnis.";
/** Die Überschrift über den Quellen einer belegten Antwort. */
export const GESTUETZT_AUF = "Gestützt auf";

export function belegStand(nachricht: Nachricht): BelegStand {
  if (nachricht.role !== "assistant" || nachricht.status !== "complete" || systemhinweis(nachricht)) return { art: "keiner" };
  const kontext = nachricht.metadata?.context;
  if (kontext?.clarification_choices?.length || kontext?.clarification_date) return { art: "keiner" };
  if (kontext?.satzantwort) return { art: "saetze" };
  const quellen = gueltigeQuellen(kontext?.quellen);
  if (quellen.length) return { art: "quellen", anzahl: quellen.length };
  if (kontext?.source_links?.length) return { art: "quellenlinks", anzahl: kontext.source_links.length };
  return { art: "ohne" };
}

/**
 * Der Satz der linken Spalte, wenn dort keine Aussage steht. Er darf einer belegten Antwort nicht widersprechen: Stützt
 * sich eine Antwort im Gespräch auf Quellen, sagt er das und wo es steht.
 */
export function kontextLeerSatz(nachrichten: Nachricht[]): string {
  const belegt = nachrichten.map(belegStand).filter(stand => stand.art === "quellen" || stand.art === "quellenlinks" || stand.art === "saetze");
  if (!belegt.length) return "In diesem Gespräch hat Kingfisher noch nichts aus deinem Gedächtnis verwendet.";
  return belegt.length === 1
    ? "Eine Antwort in diesem Gespräch stützt sich auf dein Gedächtnis; worauf, steht unter der Antwort."
    : `${belegt.length} Antworten in diesem Gespräch stützen sich auf dein Gedächtnis; worauf, steht unter jeder Antwort.`;
}
