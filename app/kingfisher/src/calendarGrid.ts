// Der Monat als Raster mit einem Tab-Halt (Persona-Prüfung, Paket B, B5, 27.10.2026): das Modell ohne Browser.
//
// Bis 1.0.29 war jeder Tag ein eigener Tab-Halt, dazu jeder Termin: Im Oktober rund 45 Tab-Stopps, ohne Pfeiltasten. Am
// Handy waren die Termine 6 × 6 px große Punkte, die man trotzdem antippen sollte. Jetzt ist der Monat ein Raster
// (`role=grid`) mit einem Tab-Halt auf dem gewählten Tag; Pfeiltasten wandern von Tag zu Tag, Pos1/Ende zum Anfang und
// Ende der Woche, Bild auf/ab einen Monat. Jeder Tag ist beschriftet („Dienstag, 27. Oktober, 2 Termine, heute“) und als
// ganze Fläche das Ziel; die Termine stehen in der Liste darunter, Enter öffnet sie. Die Punkte sind nur noch Zeichen.

const tag = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const plus = (d: Date, n: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);

/** Ein Tag im Raster als Schlüssel (für `data-tag`): JJJJ-MM-TT. */
export function tagSchluessel(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Die Wochen eines Monats, Montag zuerst; `null` für die Felder vor dem 1. und nach dem letzten Tag. */
export function monatsWochen(jahr: number, monat: number): Array<Array<Date | null>> {
  const erster = new Date(jahr, monat, 1);
  const vorne = (erster.getDay() + 6) % 7;
  const tage = new Date(jahr, monat + 1, 0).getDate();
  const felder: Array<Date | null> = [...Array.from({ length: vorne }, () => null),
    ...Array.from({ length: tage }, (_, i) => new Date(jahr, monat, i + 1))];
  while (felder.length % 7) felder.push(null);
  return Array.from({ length: felder.length / 7 }, (_, w) => felder.slice(w * 7, w * 7 + 7));
}

/** Wohin eine Taste im Raster führt; `null`, wenn sie dort nichts tut. */
export function tagNachTaste(taste: string, d: Date): Date | null {
  const t = tag(d);
  const wochentag = (t.getDay() + 6) % 7;
  switch (taste) {
    case "ArrowLeft": return plus(t, -1);
    case "ArrowRight": return plus(t, 1);
    case "ArrowUp": return plus(t, -7);
    case "ArrowDown": return plus(t, 7);
    case "Home": return plus(t, -wochentag);
    case "End": return plus(t, 6 - wochentag);
    case "PageUp": case "PageDown": {
      const richtung = taste === "PageUp" ? -1 : 1;
      const letzter = new Date(t.getFullYear(), t.getMonth() + richtung + 1, 0).getDate();
      return new Date(t.getFullYear(), t.getMonth() + richtung, Math.min(t.getDate(), letzter));
    }
    default: return null;
  }
}

/** Der Name eines Tages für Vorleser: Wochentag, Datum, Zahl der Termine, „heute“. */
export function tagBeschriftung(d: Date, termine: number, heute: Date): string {
  const datum = d.toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" });
  const zahl = termine === 0 ? "keine Termine" : termine === 1 ? "1 Termin" : `${termine} Termine`;
  return `${datum}, ${zahl}${tagSchluessel(d) === tagSchluessel(heute) ? ", heute" : ""}`;
}

/** Welcher Tag eines Monats den einen Tab-Halt trägt: der gewählte, sonst der erste. */
export function tabTag(jahr: number, monat: number, gewaehlt: Date): Date {
  return gewaehlt.getFullYear() === jahr && gewaehlt.getMonth() === monat ? tag(gewaehlt) : new Date(jahr, monat, 1);
}
