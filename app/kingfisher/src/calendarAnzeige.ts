// Anzeige im Kalender (Paket P4): ruhige, gut lesbare Zeitangaben. Nur Darstellung, keine Kalenderlogik.

type Termin = {start: string | null; end: string | null; all_day: boolean};

const gueltig = (wert: string | null | undefined) => {
  if (!wert) return null;
  const d = new Date(wert);
  return Number.isNaN(d.getTime()) ? null : d;
};
const gleicherTag = (a: Date, b: Date) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
const uhr = (d: Date) => d.toLocaleTimeString("de-DE", {hour: "2-digit", minute: "2-digit"});
const tagLang = (d: Date) => d.toLocaleDateString("de-DE", {weekday: "long", day: "numeric", month: "long", year: "numeric"});
const tagKurz = (d: Date) => d.toLocaleDateString("de-DE", {weekday: "short", day: "numeric", month: "short"});

/** Ganztägig in der Anzeige: als ganztägig geliefert oder von Mitternacht über den ganzen Tag (manche Kalender liefern
 * Geburtstage als 00:00–23:59). Solche Termine stehen in der Ganztagszeile statt als Block über das ganze Raster. */
export function ganztaegig(termin: Termin): boolean {
  if (termin.all_day) return true;
  const start = gueltig(termin.start), ende = gueltig(termin.end);
  if (!start || !ende || start.getHours() !== 0 || start.getMinutes() !== 0) return false;
  return ende.getTime() - start.getTime() >= (23 * 60 + 59) * 60000;
}

/** Wann ein Termin ist, in einer Zeile: „Mittwoch, 9. September 2026 · 10:00–11:00“. Ganztägig zählt das Ende wie im
 * Kalenderformat als ersten Tag danach; gezeigt wird der letzte Tag des Termins, damit niemand einen Tag zu viel liest. */
export function terminZeit(termin: Termin): string {
  const start = gueltig(termin.start), ende = gueltig(termin.end);
  if (!start) return "Beginn unbekannt";
  if (ganztaegig(termin)) {
    // Endet der Termin um Mitternacht (so liefern Kalender „ganztägig“), ist der Vortag sein letzter Tag.
    const umMitternacht = ende && ende.getHours() === 0 && ende.getMinutes() === 0;
    const letzter = ende ? new Date(ende.getFullYear(), ende.getMonth(), ende.getDate() - (umMitternacht ? 1 : 0)) : null;
    return letzter && letzter > start && !gleicherTag(letzter, start)
      ? `Ganztägig · ${tagLang(start)} bis ${tagLang(letzter)}`
      : `Ganztägig · ${tagLang(start)}`;
  }
  if (!ende) return `${tagLang(start)} · ${uhr(start)}`;
  if (gleicherTag(start, ende)) return `${tagLang(start)} · ${uhr(start)}–${uhr(ende)}`;
  return `${tagKurz(start)}, ${uhr(start)} – ${tagKurz(ende)}, ${uhr(ende)}`;
}

/** Termine nach Tagen ordnen (Listenansicht): je Tag eine Überschrift, darin die Termine in ihrer Reihenfolge. */
export function nachTagen<T extends {start: string | null}>(termine: readonly T[]): Array<{tag: Date | null; termine: T[]}> {
  const gruppen: Array<{tag: Date | null; termine: T[]}> = [];
  for (const termin of termine) {
    const start = gueltig(termin.start);
    const tag = start ? new Date(start.getFullYear(), start.getMonth(), start.getDate()) : null;
    const letzte = gruppen.at(-1);
    if (letzte && (letzte.tag?.getTime() ?? null) === (tag?.getTime() ?? null)) letzte.termine.push(termin);
    else gruppen.push({tag, termine: [termin]});
  }
  return gruppen;
}
