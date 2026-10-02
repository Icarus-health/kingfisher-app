// Wie der Assistent ein Postfach nennt (ohne React, testbar mit node --test). „Die Mails von example.org“ klang nach
// Mails *von* der Firma example.org; gemeint ist das eigene Postfach, also steht seine Adresse da (Fremdprobe 3, Befund 5).

/** „dein Postfach lena@example.org“; ohne Adresse der Name des Kontos. */
export function deinPostfach(label: string, adresse?: string | null): string {
  const wer = adresse?.trim();
  return wer && wer.includes("@") ? `dein Postfach ${wer}` : `dein Postfach „${label}“`;
}

/** Die Frage vor dem ersten Einlesen; Pausieren ist Alltag und steht auf Heute, nicht unter „Für Techniker“. */
export const einlesenFrage = (label: string, adresse?: string | null) =>
  `Soll Kingfisher ${deinPostfach(label, adresse)} jetzt einlesen? Es liest Posteingang, Gesendetes und Archiv, ohne Spam ` +
  "und Papierkorb. Alles bleibt auf diesem Rechner. Anhalten kannst du es jederzeit auf Heute mit „Pausieren“.";
