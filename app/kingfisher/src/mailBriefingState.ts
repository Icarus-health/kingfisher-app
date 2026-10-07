export function mailBriefingFailure(status?: number): string {
  if (status === 429) return "Eine lokale Auswertung läuft noch. Bitte kurz warten und erneut versuchen. Das Original ist unten verfügbar.";
  return "Die Auszüge konnten gerade nicht ausgewählt werden.";
}
