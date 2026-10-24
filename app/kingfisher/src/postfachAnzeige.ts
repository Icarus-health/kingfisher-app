// Anzeige im Postfach (Paket P4): Datum rechts in der Zeile wie in Apple Mail. Nur Darstellung, keine Logik.

const tag = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();

/** Datum rechts in der Postfachzeile: heute die Uhrzeit, gestern „Gestern“, in der letzten Woche der Wochentag, sonst
 * das kurze Datum. Unlesbar oder fehlend: „Ohne Datum“. */
export function postfachDatum(wert: string | null | undefined, jetzt: Date = new Date()): string {
  if (!wert) return "Ohne Datum";
  const d = new Date(wert);
  if (Number.isNaN(d.getTime())) return "Ohne Datum";
  const tage = Math.round((tag(jetzt) - tag(d)) / 86400000);
  if (tage === 0) return d.toLocaleTimeString("de-DE", {hour: "2-digit", minute: "2-digit"});
  if (tage === 1) return "Gestern";
  if (tage > 1 && tage < 7) return d.toLocaleDateString("de-DE", {weekday: "long"});
  return d.toLocaleDateString("de-DE", {day: "2-digit", month: "2-digit", year: "2-digit"});
}
