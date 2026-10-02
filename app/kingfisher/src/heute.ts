// Kleine reine Hilfen für Heute und das Briefing (Fremdprobe 2, Befund 10); ohne React, damit `node --test` sie prüft.

/** Was im Zähler einer Kachel steht: die Zahl, oder nichts, wenn es nichts gibt. Eine Signalfarbe für „0“ ruft ohne Grund. */
export function zaehlerText(anzahl: number): string | null {
  return Number.isFinite(anzahl) && anzahl > 0 ? String(anzahl) : null;
}

/** Welche Aussagen über ein Postfach Heute zeigt: die, die erklären, warum keine Mails dastehen (leer, noch nicht
 * abgerufen, angehalten, Fehler). Was gerade gelesen wird, steht in „Kingfisher lernt gerade“; ein gelesenes Postfach
 * zeigt seine Mails selbst (Fremdprobe 2, Befund 17). */
export function postfachAufHeute(zustand: string): boolean {
  return zustand === "leer" || zustand === "nicht_abgerufen" || zustand === "pausiert" || zustand === "fehler";
}

/**
 * Was nach „Aktualisieren“ unter „Nachrichten“ steht (Fremdprobe 2, Befund 18): wann abgerufen wurde und ob etwas
 * Neues kam. `vorher` ist die Liste vor dem Klick (null beim ersten Laden: dann kein Satz).
 */
export function aktualisiertSatz(vorher: string[] | null, nachher: string[], uhrzeit: string): string | null {
  if (vorher === null) return null;
  if (!nachher.length) return `Gerade abgerufen um ${uhrzeit}: Der Posteingang ist leer.`;
  const bekannt = new Set(vorher);
  const neu = nachher.filter(id => !bekannt.has(id)).length;
  if (neu === 0) return `Gerade abgerufen um ${uhrzeit}, nichts Neues.`;
  return `Gerade abgerufen um ${uhrzeit}: ${neu === 1 ? "eine neue Nachricht" : `${neu} neue Nachrichten`}.`;
}
