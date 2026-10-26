import { Segmente } from "./grundlage";
import { kontenApi } from "./kontenApi";
import { filterOptionen, gueltigeWahl, passtZuBereich, type Konten } from "./kontenBereiche";

/**
 * Der Filter „Alle · Arbeit · Privat · …“ für Kalender und Aufgaben (Paket K). Er steht nur da, wenn mindestens zwei
 * Bereiche einem Postfach oder Kalender zugeordnet sind; die Wahl merkt sich jede Seite für sich (`gemerkteWahl`). Ohne
 * Antwort des Sidecars gibt es keinen Filter, und alles bleibt sichtbar.
 *
 * Bewusst ohne eigene Hooks: Die Seiten halten Wahl und Konten mit ihren eigenen `useState`/`useEffect` (ihre Tests
 * ersetzen die React-Hooks je Datei).
 */
export function bereichFilter(konten: Konten | null, wahl: string, waehle: (wahl: string) => void) {
  const optionen = filterOptionen(konten);
  const gilt = gueltigeWahl(wahl, optionen);
  const segmente = optionen.length
    ? <Segmente kompakt label="Bereich" className="bereich-filter" optionen={optionen} wert={gilt} onWahl={waehle} /> : null;
  return { wahl: gilt, passt: (eintrag: { bereich?: string | null }) => passtZuBereich(eintrag, gilt), segmente };
}

/** Liest die Konten einmal für den Filter; gibt das Aufräumen für `useEffect` zurück. */
export function kontenFuerFilter(setzen: (konten: Konten) => void): () => void {
  let aktiv = true;
  kontenApi.konten().then(antwort => { if (aktiv) setzen(antwort); }).catch(() => { /* ohne Filter */ });
  return () => { aktiv = false; };
}
