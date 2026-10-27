// Die fertige Antwort im Gespräch wird angesagt (Persona-Prüfung, Paket B, B1, 27.10.2026): ohne React, testbar.
//
// Bis 1.0.29 sagte ein Vorleser „Kingfisher antwortet …“ und dann nichts mehr: Die Antwort erschien still, der Fokus lag
// auf `body`. Jetzt sagt der Ort für Ansagen (grundlage/ansage.ts) den Anfang der fertigen Antwort einmal an, höflich,
// in ein bis zwei Sätzen; den Rest liest man mit dem Vorleser an der Antwort selbst. Den Zwischenstand liest er nicht
// Wort für Wort vor: Er sagt nur die Schritte („Sucht in deinen Quellen …“), die Antwort kommt am Stück.
import type { Message } from "./api";

/** So viel vom Anfang, etwa zwei kurze Sätze: genug, um zu wissen, ob es passt. */
export const ANSAGE_ZEICHEN = 220;

/** Markdown und Belegnummern weg, damit der Vorleser keine Sternchen und „[1]“ vorliest. */
export function klartext(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/\[\d+(?:\s*[,–-]\s*\d+)*\]/g, "")
    .replace(/^\s{0,3}(?:#{1,6}|[-*+]|\d+\.)\s+/gm, "")
    .replace(/[*_`~>|]+/g, "")
    .replace(/\s+([.,;:!?])/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

/** Der Anfang eines Texts: ganze Sätze bis etwa `grenze` Zeichen; ist schon der erste länger, am Wort gekürzt. */
export function anfang(text: string, grenze = ANSAGE_ZEICHEN): string {
  if (text.length <= grenze) return text;
  const saetze = text.match(/[^.!?…]+[.!?…]+(?=\s|$)/g) ?? [];
  let aus = "";
  for (const satz of saetze) {
    if ((aus + satz).length > grenze) break;
    aus += satz;
  }
  if (aus.trim()) return aus.trim();
  const schnitt = text.slice(0, grenze);
  return `${schnitt.slice(0, Math.max(schnitt.lastIndexOf(" "), grenze / 2)).trimEnd()} …`;
}

type Antwort = Pick<Message, "role" | "content" | "status"> & { metadata?: Message["metadata"] };

/** Was angesagt wird, wenn die Antwort fertig ist; `null`, wenn die letzte Nachricht keine Antwort ist. */
export function antwortAnsage(nachrichten: ReadonlyArray<Antwort> | null | undefined): string | null {
  const letzte = nachrichten?.[nachrichten.length - 1];
  if (!letzte || letzte.role !== "assistant") return null;
  if (letzte.status === "error") return "Die Antwort ist fehlgeschlagen. Unter der Nachricht steht „Wiederholen“.";
  const saetze = letzte.metadata?.context?.satzantwort?.saetze?.map(s => s.text).join(" ");
  const text = klartext(saetze && saetze.trim() ? saetze : letzte.content ?? "");
  const rueckfrage = Boolean(letzte.metadata?.context?.clarification_choices?.length || letzte.metadata?.context?.clarification_date);
  if (!text) return "Kingfisher hat geantwortet.";
  return `${rueckfrage ? "Kingfisher fragt zurück" : "Kingfisher antwortet"}: ${anfang(text)}`;
}
