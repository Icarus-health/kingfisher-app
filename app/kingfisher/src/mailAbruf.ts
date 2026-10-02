// „Mails regelmäßig abrufen“ (Für Techniker → Zeitplan und Hintergrund): reine Texte und Auswahl, ohne React, testbar mit
// node --test. Früher stand dort „Automatische Quellenaufnahme“, „Bestandsaufnahme“, „Posteingang (INBOX)“ und ein
// Zahlenfeld „Abstand in Minuten“ (Fremdprobe, Befund 12). Die Technik dahinter ist dieselbe (`PUT /api/v1/schedule`),
// nur Wörter und Bedienelemente sind neu: ein Schalter und eine Auswahl.

/** Wörter, die vorher dort standen und nicht wiederkommen sollen (Test und Browserprobe suchen danach). */
export const ALTE_WOERTER: readonly string[] = [
  "Automatische Quellenaufnahme", "Bestandsaufnahme", "Mailbereiche prüfen", "Posteingang (INBOX)",
  "Aufnahmestand aktualisieren", "Abstand in Minuten", "Mailbereich", "Mailbestand",
];

/** Vorgabe: alle 30 Minuten, damit eine Bitte vom Morgen im Briefing desselben Vormittags steht (Fremdprobe 3,
 * Befund 13; vorher alle vier Stunden). Dieselbe Vorgabe wie im Sidecar (`config.VORGABE_ABSTAND_MINUTEN`). */
export const VORGABE_MINUTEN = 30;

const NAMEN: Record<number, string> = { 30: "alle 30 Minuten", 60: "jede Stunde", 240: "alle vier Stunden", 1440: "täglich" };

/** Wie oft, in Worten: „jede Stunde“, „alle vier Stunden“, „täglich“, sonst „alle 30 Minuten“ bzw. „alle 8 Stunden“. */
export function abstandText(minuten: number): string {
  if (NAMEN[minuten]) return NAMEN[minuten];
  if (minuten % 60 === 0) return `alle ${minuten / 60} Stunden`;
  return `alle ${minuten} Minuten`;
}

/** Die Auswahl; ein früher gespeicherter Wert außerhalb der Vorgaben bleibt sichtbar, damit sie zeigt, was gilt. */
export function abstandAuswahl(aktuell: number): Array<{ minuten: number; text: string }> {
  const werte = [30, 60, 240, 1440];
  if (Number.isInteger(aktuell) && aktuell >= 15 && !werte.includes(aktuell)) werte.push(aktuell);
  return werte.sort((a, b) => a - b).map(minuten => ({ minuten, text: abstandText(minuten) }));
}

/** Ein Satz, was gerade gilt. `postfaecher` sind die Namen der Postfächer, die abgerufen werden. */
export function abrufSatz(an: boolean, minuten: number, postfaecher: string[]): string {
  if (!postfaecher.length) return "Verbinde zuerst ein Postfach unter Zugänge; dann kann Kingfisher deine Mails regelmäßig abrufen.";
  if (!an) return "Aus. Kingfisher liest neue Mails nur, wenn du es in der Einrichtung oder hier anstößt.";
  const wer = postfaecher.length === 1 ? postfaecher[0] : `${postfaecher.length} Postfächern`;
  return `An. Kingfisher ruft die Mails aus ${wer} ${abstandText(minuten)} ab.`;
}

/** Ordnernamen, wie der Nutzer sie kennt: „INBOX“ heißt Posteingang. */
export function ordnerName(ordner: string): string {
  return ordner.toUpperCase() === "INBOX" ? "Posteingang" : ordner;
}
