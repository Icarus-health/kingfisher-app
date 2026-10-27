export function cloudAccessSaveBody(apiKey: string, model: string): {api_key?: string; model: string} {
  const key = apiKey.trim();
  return key ? {api_key: key, model: model.trim()} : {model: model.trim()};
}

/** „Anderes Modell“ in der Liste: dann das Feld für den Namen (für Techniker). */
export const ANDERES_MODELL = "__anderes__";

/** Was im Feld „Modell“ steht, bevor jemand etwas wählt: das gespeicherte, sonst das empfohlene (das erste der Liste). */
export function vorbelegtesModell(provider: {model: string; modelle?: Array<{id: string}>}): string {
  return provider.model.trim() || provider.modelle?.[0]?.id || "";
}

/** Der Wert der Liste: das Modell, wenn es dort steht, sonst „Anderes Modell“. */
export function listenWert(modell: string, modelle: Array<{id: string}> | undefined): string {
  return modelle?.some(eintrag => eintrag.id === modell) ? modell : ANDERES_MODELL;
}
