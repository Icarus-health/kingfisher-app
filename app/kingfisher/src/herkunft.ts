// Woher eine Quelle stammt, in Worten oder als Kennung für Techniker (Fremdprobe 3, Befund 9). Reine Logik, testbar.
export type Provenienz = {source_type?: string | null; source_ref?: string | null};

/** Was vorne stehen darf: nur Herkünfte, die ein Mensch versteht. Sonst `null`. */
export function herkunftLesbar(provenienz?: Provenienz | null): string | null {
  if (provenienz?.source_type === "manual_correction") return "Deine Berichtigung";
  if (provenienz?.source_type === "chat" && provenienz.source_ref) return "Dein Gespräch mit Kingfisher";
  return null;
}

/** Die technische Kennung (`calendar:…`, `mail:…`) für „Für Techniker“; `null`, wenn vorne schon alles steht. */
export function herkunftKennung(provenienz?: Provenienz | null): string | null {
  if (!provenienz?.source_ref || herkunftLesbar(provenienz)) return null;
  return provenienz.source_ref;
}
