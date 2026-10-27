// Nach dem Seitenwechsel weiß man, wo man ist (Persona-Prüfung, Paket B, B2, 27.10.2026): das Modell ohne Browser.
//
// Bis 1.0.29 hieß jede Seite „Kingfisher“, und nach jedem Wechsel lag der Fokus auf `body`: Ein Vorleser sagte nichts an,
// und der nächste Tab begann wieder oben in der Seitenleiste. Jetzt trägt jede Seite ihren Namen im Fenstertitel
// („Aufgaben – Kingfisher“, im Gespräch „Wurde die Frist … – Gespräche – Kingfisher“), und nach einem Wechsel, bei dem
// der Fokus verloren ging, steht er auf der Hauptüberschrift der neuen Seite (`tabindex=-1`, kein neuer Tab-Halt). Der
// Vorleser sagt sie an; Tab führt von dort in den Inhalt. Wer schon etwas fokussiert hat (das Eingabefeld im Gespräch),
// behält es.

export const MARKE = "Kingfisher";

/** Bereich je Pfad; `einzeln`: Die Seite zeigt einen Gegenstand, dessen Name (die Überschrift) vorne steht. */
const BEREICHE: Array<[RegExp, string, boolean]> = [
  [/^\/today\/?$/, "Heute", false],
  [/^\/conversations\/[^/]+$/, "Gespräche", true],
  [/^\/conversations\/?$/, "Gespräche", false],
  [/^\/vorhaben\/?$/, "Aufgaben", false],
  [/^\/memory\/(?:people|projects|akte|registry)\/[^/]+$/, "Gedächtnis", true],
  [/^\/memory\/?$/, "Gedächtnis", false],
  [/^\/nachrichten\/?$/, "Nachrichten", false],
  [/^\/calendar\/?$/, "Kalender", false],
  [/^\/settings\/?$/, "Einstellungen", false],
  [/^\/review\/?$/, "Prüfen und entscheiden", false],
  [/^\/wellbeing\/?$/, "Gesundheit", false],
  [/^\/world\/?$/, "Öffentliches Wissen", false],
  [/^\/development\/?$/, "Persönliche Entwicklung", false],
  [/^\/willkommen\/?$/, "Willkommen", false],
];

/** Der Fenstertitel einer Seite: „Bereich – Kingfisher“, bei einem einzelnen Gegenstand „Name – Bereich – Kingfisher“. */
export function seitenTitel(pfad: string, ueberschrift?: string | null): string {
  const treffer = BEREICHE.find(([muster]) => muster.test(pfad));
  if (!treffer) return MARKE;
  const [, bereich, einzeln] = treffer;
  const name = (ueberschrift ?? "").replace(/\s+/g, " ").trim();
  return einzeln && name && name !== bereich ? `${kuerzen(name)} – ${bereich} – ${MARKE}` : `${bereich} – ${MARKE}`;
}

function kuerzen(text: string, laenge = 60) {
  return text.length <= laenge ? text : `${text.slice(0, laenge - 1).trimEnd()}…`;
}

type Knoten = { isConnected: boolean; closest?(selektor: string): unknown };

/**
 * Wohin der Fokus nach einem Seitenwechsel gehört: `true`, wenn er verloren ging (auf `body`, an einem entfernten
 * Element oder auf der ganzen Seite, wohin der Hinweis ihn ersatzweise stellt) und die Überschrift ihn nehmen soll; `false`,
 * wenn die neue Seite schon etwas fokussiert hat.
 */
export function fokusVerloren(aktiv: Knoten | null, body: unknown, seite: unknown): boolean {
  return !aktiv || aktiv === body || !aktiv.isConnected || aktiv === seite;
}

/** Hat sich die Seite gewechselt? Nur der Pfad zählt: Ansicht, Filter und Anker (`?view=`, `#zugaenge`) bleiben auf ihr. */
export function seiteGewechselt(vorher: string | null, jetzt: string): boolean {
  return vorher !== null && vorher !== jetzt;
}
