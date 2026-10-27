// Konten und Bereiche (Paket K, docs/66-automatik.md): reine Logik ohne React, testbar mit node --test.
// Der Sidecar bestimmt Bereich, Vorschlag und Stand (`bereiche.py`, `konten_routes.py`); hier steht nur, wie die
// Oberfläche daraus Sätze, Segmente und Filter macht.

export type Bereich = { id: string; name: string; eigen: boolean };
export type KontoVorschlag = { bereich: string; grund: string };
export type KontoStand = { satz: string; art: "gut" | "laeuft" | "fehler"; verweis: string | null };
export type Konto = {
  id: string;
  name: string;
  adresse: string;
  /** Nur beim Kalender: caldav, ical, google, microsoft oder mac. */
  art?: string;
  umbenennbar?: boolean;
  bereich: string | null;
  vorschlag: KontoVorschlag | null;
  stand: KontoStand | null;
};
export type Konten = {
  bereiche: Bereich[];
  /** Bereiche, die mindestens ein Konto trägt; ab zwei gibt es den Filter in Kalender und Aufgaben. */
  in_gebrauch: string[];
  postfaecher: Konto[];
  kalender: Konto[];
  ausgeblendet: string[];
};

export const ALLE = "alle";

export const bereichName = (konten: Pick<Konten, "bereiche"> | null, id: string | null | undefined) =>
  (id && konten?.bereiche.find(b => b.id === id)?.name) || "";

/** „Vorschlag: Privat. gmail.com ist ein Anbieter für private Adressen.“ */
export function vorschlagSatz(konten: Pick<Konten, "bereiche">, konto: Pick<Konto, "vorschlag">): string {
  if (!konto.vorschlag) return "";
  return `Vorschlag: ${bereichName(konten, konto.vorschlag.bereich) || konto.vorschlag.bereich}. ${konto.vorschlag.grund}`;
}

/** Alle offenen Vorschläge als eine Zuordnung, für „Alle Vorschläge übernehmen“; und der Weg zurück. */
export function offeneVorschlaege(konten: Konten | null): Record<string, string> {
  const zuordnung: Record<string, string> = {};
  for (const konto of [...(konten?.postfaecher ?? []), ...(konten?.kalender ?? [])])
    if (!konto.bereich && konto.vorschlag) zuordnung[konto.id] = konto.vorschlag.bereich;
  return zuordnung;
}
export const zurueckZuOhne = (zuordnung: Record<string, string>): Record<string, null> =>
  Object.fromEntries(Object.keys(zuordnung).map(id => [id, null]));

/** Was unter dem Namen eines Kalenders steht. */
export function kalenderNeben(konto: Pick<Konto, "art" | "adresse">): string {
  const art = konto.art === "ical" ? "Kalender-Abo" : konto.art === "google" ? "Google · nur lesen"
    : konto.art === "microsoft" ? "Microsoft · nur lesen" : konto.art === "mac" ? "Mac-Kalender"
    : "Mit Benutzername und Passwort";
  return konto.adresse ? `${konto.adresse} · ${art}` : art;
}

/** Die Segmente „Alle · Arbeit · Privat · …“ – leer, solange höchstens ein Bereich vorkommt (dann gibt es keinen Filter). */
export function filterOptionen(konten: Pick<Konten, "bereiche" | "in_gebrauch"> | null): Array<{ wert: string; titel: string }> {
  if (!konten || konten.in_gebrauch.length < 2) return [];
  return [{ wert: ALLE, titel: "Alle" },
    ...konten.in_gebrauch.map(id => ({ wert: id, titel: bereichName(konten, id) || id }))];
}

/** Eine gemerkte Wahl gilt nur, wenn es sie noch gibt; sonst „Alle“. */
export function gueltigeWahl(wahl: string | null | undefined, optionen: Array<{ wert: string }>): string {
  return wahl && optionen.some(o => o.wert === wahl) ? wahl : ALLE;
}

/** Passt ein Eintrag (Termin, Aufgabe) zur Wahl? Bei „Alle“ immer; sonst nur mit genau diesem Bereich. */
export const passtZuBereich = (eintrag: { bereich?: string | null }, wahl: string) =>
  wahl === ALLE || eintrag.bereich === wahl;

const SCHLUESSEL = (seite: string) => `kingfisher-bereich-${seite}`;

/** Die gemerkte Wahl einer Seite; ohne Browser-Speicher (privates Fenster) einfach „Alle“. */
export function gemerkteWahl(seite: string, speicher: Pick<Storage, "getItem"> | null = globalThis.localStorage ?? null): string {
  try { return speicher?.getItem(SCHLUESSEL(seite)) || ALLE; } catch { return ALLE; }
}
export function merkeWahl(seite: string, wahl: string, speicher: Pick<Storage, "setItem"> | null = globalThis.localStorage ?? null) {
  try { speicher?.setItem(SCHLUESSEL(seite), wahl); } catch { /* Die Wahl gilt dann nur bis zum Neuladen. */ }
}

/** Der Hinweis nach dem Umbenennen und nach einer Bereichswahl, je mit Rückgängig (docs/16-gestaltung.md). */
export const umbenanntText = (name: string) => `Umbenannt in „${name}“.`;
// „Privat gehört jetzt zu Privat.“ stand da, wenn ein Kalender so heißt wie sein Bereich (Paket S, Befund 6): Der Name
// steht in Anführungszeichen, der Bereich heißt „Bereich“.
export function bereichText(konten: Pick<Konten, "bereiche">, name: string, bereich: string | null): string {
  return bereich ? `„${name}“ gehört jetzt zum Bereich ${bereichName(konten, bereich) || bereich}.` : `„${name}“ hat keinen Bereich mehr.`;
}
export const alleUebernommenText = (anzahl: number) =>
  anzahl === 1 ? "Ein Vorschlag übernommen." : `${anzahl} Vorschläge übernommen.`;

/** Ein neuer Name ist gültig, wenn er nicht leer und nicht unverändert ist. */
export const neuerName = (eingabe: string, bisher: string) => {
  const name = eingabe.trim().replace(/\s+/g, " ");
  return name && name !== bisher ? name : null;
};
