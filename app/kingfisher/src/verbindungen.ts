// Wohin „Verbindungen prüfen“ führt: direkt in den Bereich der Einstellungen, der betroffen ist (Befund 30).
// Reine Logik, testbar mit node --test. Die Einstellungen lesen den Bereich aus dem Adressteil (`#zugaenge`, docs/47).

// Reihenfolge = Vorrang. Als Objekte, nicht als Paare: `scripts/check_asset_manifest.py` liest `["…", "…"]` als Icon.
const BEREICH_ZUR_QUELLE: ReadonlyArray<{quelle: string; bereich: string}> = [
  {quelle: "mail", bereich: "zugaenge"}, {quelle: "calendar", bereich: "zugaenge"}, {quelle: "weather", bereich: "darf"}];

/** Die Adresse für „Verbindungen prüfen“: der erste betroffene Bereich (Post und Kalender vor Wetter), sonst die Zugänge. */
export function verbindungenPruefen(ausfaelle: ReadonlyArray<{section: string}>): string {
  const betroffen = new Set(ausfaelle.map(ausfall => ausfall.section));
  const treffer = BEREICH_ZUR_QUELLE.find(eintrag => betroffen.has(eintrag.quelle));
  return `/settings#${treffer ? treffer.bereich : "zugaenge"}`;
}
