// Kleine reine Hilfen des Rückkanals für Fehler; ohne React, damit sie sich ohne Browser testen lassen.

/** Die Arten einer Meldung, in der Reihenfolge der Auswahl. Dieselben Kennungen kennt der Sidecar (rueckmeldung.py). */
export const ARTEN = [
  { id: "falsch", text: "Falsch" },
  { id: "unvollstaendig", text: "Unvollständig" },
  { id: "veraltet", text: "Veraltet" },
  { id: "zu_langsam", text: "Zu langsam" },
  { id: "sonstiges", text: "Etwas anderes" },
] as const;

/** Ein Text auf höchstens `max` Zeichen, am Wortende gekürzt, mit Auslassungszeichen. */
export function kurz(text: string, max = 90): string {
  const glatt = text.replace(/\s+/g, " ").trim();
  if (glatt.length <= max) return glatt;
  const schnitt = glatt.slice(0, max - 1);
  const leer = schnitt.lastIndexOf(" ");
  return `${(leer > max / 2 ? schnitt.slice(0, leer) : schnitt).trimEnd()}…`;
}

/** „3 Meldungen, 2 offen.“ oder „Noch keine Meldungen.“ */
export function zaehlSatz(z: { gesamt: number; offen: number }): string {
  if (z.gesamt === 0) return "Noch keine Meldungen.";
  const meldungen = z.gesamt === 1 ? "1 Meldung" : `${z.gesamt} Meldungen`;
  return z.offen === 0 ? `${meldungen}, alle erledigt.` : `${meldungen}, ${z.offen} offen.`;
}

/** Was nach „Melden“ dasteht: was mit der Meldung geschieht, in Alltagssprache (Fremdprobe 2, Befund 12). Ohne
 * „Prüffrage“ und „wer Kingfisher verbessert“; das steht nur unter „Für Techniker“ (Fremdprobe 3, Befund 11). Dahinter
 * folgt der Verweis auf die Liste unter Einstellungen → Für Techniker → Rückmeldungen. */
export const GEMELDET = "Gemerkt. Kingfisher soll diesen Fehler nicht wieder machen. Die Meldung bleibt auf diesem Rechner und ändert nichts an deinem Gedächtnis. Du findest sie unter";

type Nachricht = { role: string; status: string; metadata?: { memory_candidate_id?: unknown; systemhinweis?: unknown; context?: { clarification_choices?: unknown[]; clarification_date?: boolean } } };

/** Ein Hinweis des Programms, keine Antwort: etwa „Ich habe einen Gedächtnisvorschlag vorbereitet …“ (Befund 14). */
export function systemhinweis(nachricht: Nachricht): boolean {
  return Boolean(nachricht.metadata?.memory_candidate_id || nachricht.metadata?.systemhinweis);
}

/** Nur Antworten lassen sich melden: keine Rückfragen nach einer Auswahl oder einem Datum, keine Hinweise des Programms. */
export function meldbar(nachricht: Nachricht): boolean {
  if (nachricht.role !== "assistant" || nachricht.status !== "complete" || systemhinweis(nachricht)) return false;
  const kontext = nachricht.metadata?.context;
  return !(kontext?.clarification_choices?.length || kontext?.clarification_date);
}
