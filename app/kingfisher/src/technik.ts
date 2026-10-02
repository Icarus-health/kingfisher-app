// Sätze unter „Für Techniker“ ohne Widerspruch (Fremdprobe 2, Befunde 27 bis 29). Reine Logik, testbar mit node --test.

/** „1 gespeichertes Dokument“, „12 gespeicherte Dokumente“, „Mindestens 50 gespeicherte Dokumente“. */
export function dokumenteSatz(anzahl: number, mindestens = false): string {
  const text = anzahl === 1 ? "1 gespeichertes Dokument" : `${anzahl} gespeicherte Dokumente`;
  return mindestens ? `Mindestens ${text}` : text;
}

/**
 * Ob beim regelmäßigen Abruf ein Modell Kosten verursachen kann. Nur wenn ein Modell außerhalb dieses Rechners gerufen
 * werden kann, steht eine Warnung da, und dann welches (`kosten_modell` aus `GET /api/v1/schedule`).
 */
export function kostenSatz(mitModell: boolean, kostenModell: string | null | undefined): string {
  if (!mitModell) return "Dabei wird kein Sprachmodell gerufen.";
  if (kostenModell) return `Dabei kann ${kostenModell} gerufen werden; dieses Modell läuft nicht auf diesem Rechner und kann Kosten verursachen.`;
  return "Dabei arbeitet nur ein Sprachmodell auf diesem Rechner; das kostet nichts.";
}

/**
 * Eine Zeile unter „Was zuletzt lief“: bei Erfolg, was getan wurde; bei einem Fehler der Grund, nie „Fehler · Nichts zu
 * tun.“ (Befund 29). Ein Fehler ohne Grund sagt das ehrlich.
 */
export function laufZeile(name: string, ok: boolean, detail: string): string {
  const text = detail.trim();
  if (ok) return `${name}: ${text || "erledigt"}`;
  if (!text || /^nichts zu tun\.?$/i.test(text)) return `${name}: Fehler ohne genannten Grund. Der nächste Lauf versucht es erneut.`;
  return `${name}: ${/^fehler/i.test(text) ? text : `Fehler: ${text}`}`;
}
