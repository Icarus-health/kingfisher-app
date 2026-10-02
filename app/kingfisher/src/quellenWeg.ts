// Reine Logik der Quellenverweise unter einer belegten Gedächtnisantwort (ohne React, testbar mit node --test).
// Der Sidecar liefert je Quelle einen Satz in Alltagssprache und die Kennungen als Datenfeld (`context.quellen`,
// `quellenhinweis.py`). Hier wird entschieden, wohin der eine Klick führt.

export type BelegQuelle = {
  nummer: number;
  text: string;
  art: string;
  assertion_id: string;
  episode_id: string;
  source_ref?: string | null;
  occurred_at?: string | null;
  recorded_at?: string | null;
  conversation_id?: string;
  message_id?: string;
};

export type QuellenWeg =
  | { art: "nachricht"; nachricht: string }
  | { art: "gespraech"; pfad: string; nachricht: string }
  | { art: "quelle"; episode: string };

/** Wohin „Quelle öffnen“ führt: zur Nachricht in diesem Gespräch, in ein anderes Gespräch oder in die Quellenansicht. */
export function quellenWeg(quelle: BelegQuelle, gespraech: string): QuellenWeg {
  if (quelle.art === "chat" && quelle.conversation_id && quelle.message_id) {
    if (quelle.conversation_id === gespraech) return { art: "nachricht", nachricht: quelle.message_id };
    return { art: "gespraech", pfad: `/conversations/${encodeURIComponent(quelle.conversation_id)}#message-${encodeURIComponent(quelle.message_id)}`, nachricht: quelle.message_id };
  }
  return { art: "quelle", episode: quelle.episode_id };
}

/** Die Nachricht, die die Adresse anspringen soll (`#message-…`), sonst null. */
export function nachrichtAusAdresse(hash: string): string | null {
  const treffer = /^#message-([^#?&/]+)$/.exec(hash);
  return treffer ? decodeURIComponent(treffer[1]) : null;
}

/** Was „Für Techniker“ je Quelle zeigt: Claim und Quellenkennung, sonst nirgends sichtbar. */
export function technikZeile(quelle: BelegQuelle): string {
  return `[${quelle.nummer}] ${quelle.assertion_id} · ${quelle.source_ref || quelle.episode_id}`;
}

/** Nur wohlgeformte Einträge; ein beschädigtes Datenfeld zeigt nichts statt eines kaputten Knopfs. */
export function gueltigeQuellen(wert: unknown): BelegQuelle[] {
  if (!Array.isArray(wert)) return [];
  return wert.filter((q): q is BelegQuelle => typeof q === "object" && q !== null
    && typeof q.nummer === "number" && typeof q.text === "string" && q.text.length > 0
    && typeof q.episode_id === "string" && typeof q.assertion_id === "string" && typeof q.art === "string");
}
