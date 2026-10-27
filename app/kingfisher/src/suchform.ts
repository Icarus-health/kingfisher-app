// Suchen nach Namen ohne Rücksicht auf die Schreibweise der Umlaute (Persona-Prüfung, Befund A7): „Müller“ findet
// „Mueller“ und umgekehrt, ebenso ä/ae, ö/oe, ü/ue und ß/ss; „Muller“ findet „Müller“ (ohne Umlautpunkte).
// Verglichen werden zwei Formen: die Umschrift (ä → ae) und die Grundform ohne Punkte (ä → a).

function umschrift(text: string): string {
  return text.toLocaleLowerCase("de").replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss");
}

function grundform(text: string): string {
  return text.toLocaleLowerCase("de").replace(/ß/g, "ss").normalize("NFD").replace(/\p{M}/gu, "");
}

/** Die Wörter einer Suche, klein geschrieben. */
export function suchbegriffe(suche: string): string[] {
  return suche.trim().toLocaleLowerCase("de").split(/\s+/).filter(Boolean);
}

/** Enthält `text` den Begriff, in welcher Schreibweise der Umlaute auch immer? */
export function enthaeltBegriff(text: string, begriff: string): boolean {
  return umschrift(text).includes(umschrift(begriff)) || grundform(text).includes(grundform(begriff));
}

/** Passen alle Wörter der Suche? Leere Suche passt immer. */
export function passtSuche(text: string, suche: string): boolean {
  return suchbegriffe(suche).every(begriff => enthaeltBegriff(text, begriff));
}
