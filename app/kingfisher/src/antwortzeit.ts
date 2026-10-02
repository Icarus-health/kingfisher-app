// Reine Logik der Antwortzeit (ohne React, testbar mit node --test): die Zeile unter der Antwort, der Satz mit der
// Ursache bei einer langsamen Antwort und die Zeilen des Protokolls. Die Zahlen misst der Sidecar (zeitmessung.py).
import type {AntwortZeiten, AntwortZeitenProtokoll} from "./api";

/** Ab wann eine Antwort „langsam“ heißt und die Zeile eine Ursache nennt. Gleich dem Ziel der Messlatte (8 s im Median). */
export const LANGSAM_S = 8;

type Abschnitt = Exclude<keyof AntwortZeiten, "gesamt">;

/** Beschriftung in der Zeile unter der Antwort, in der Reihenfolge des Weges. */
const KURZ: Array<[Abschnitt, string]> = [
  ["frage", "Frage"], ["suche", "Suche"], ["antwort_modell", "Auswahl"], ["saetze_modell", "Sätze"], ["satzpruefung", "Prüfung"],
  ["pruefung_modell", "Prüfmodell"],
];

/** Die Ursache als Satz, so wie ein Mensch es sagen würde. */
const URSACHE: Record<Abschnitt, (s: string) => string> = {
  saetze_modell: s => `Der zweite Modellaufruf für die Sätze brauchte ${s} s.`,
  antwort_modell: s => `Der erste Modellaufruf, der die Quellen auswählt, brauchte ${s} s.`,
  frage: s => `Das Verstehen der Frage brauchte ${s} s.`,
  suche: s => `Die Suche in deinen Quellen brauchte ${s} s.`,
  satzpruefung: s => `Die Prüfung der Sätze brauchte ${s} s.`,
  pruefung_modell: s => `Das Prüfmodell brauchte für die Sätze ${s} s.`,
};

/** Sekunden für Menschen: unter 10 mit einer Stelle und Komma, darüber ganz. */
export function sekunden(wert: number) {
  const rund = wert < 9.95 ? Math.round(wert * 10) / 10 : Math.round(wert);
  return rund.toLocaleString("de-DE", {minimumFractionDigits: rund < 10 ? 1 : 0, maximumFractionDigits: rund < 10 ? 1 : 0});
}

const zahl = (wert: unknown): wert is number => typeof wert === "number" && Number.isFinite(wert) && wert >= 0;

/** Gibt es Zeiten, die sich zeigen lassen? Sonst zeigt die Oberfläche nichts (ältere Antworten haben keine). */
export function gueltigeZeiten(roh: unknown): AntwortZeiten | null {
  if (typeof roh !== "object" || roh === null || !zahl((roh as AntwortZeiten).gesamt)) return null;
  return roh as AntwortZeiten;
}

/** „3,2 s · Suche 0,3 · Sätze 2,1“: die Gesamtzeit, dann die Teile, die mindestens eine Zehntelsekunde brauchten. */
export function zeitZeile(zeiten: AntwortZeiten) {
  const teile = KURZ.filter(([name]) => zahl(zeiten[name]) && zeiten[name]! >= 0.05).map(([name, text]) => `${text} ${sekunden(zeiten[name]!)}`);
  return [`${sekunden(zeiten.gesamt)} s`, ...teile].join(" · ");
}

/** Bei einer langsamen Antwort ein Satz mit der Ursache; sonst null. Der größte Teil zählt, wenn er die Zeit prägt. */
export function ursacheSatz(zeiten: AntwortZeiten) {
  if (!(zeiten.gesamt > LANGSAM_S)) return null;
  let groesster: Abschnitt | null = null;
  for (const [name] of KURZ) if (zahl(zeiten[name]) && (groesster === null || zeiten[name]! > zeiten[groesster]!)) groesster = name;
  if (groesster === null || zeiten[groesster]! < zeiten.gesamt * 0.4) return "Die Zeit verteilt sich auf mehrere Schritte.";
  const satz = URSACHE[groesster](sekunden(zeiten[groesster]!));
  return groesster === "saetze_modell" ? `${satz} Unter Einstellungen, Lokale KI, lassen sich die Sätze ausschalten.` : satz;
}

/** Zeilen des Protokolls: nur Abschnitte, die gemessen wurden. */
export function protokollZeilen(protokoll: AntwortZeitenProtokoll) {
  const titel: Array<[keyof AntwortZeiten, string]> = [
    ["frage", "Frage verstehen"], ["suche", "Suche"], ["antwort_modell", "Antwortmodell: Quellen auswählen"],
    ["saetze_modell", "Sätze formulieren"], ["satzpruefung", "Sätze prüfen"], ["pruefung_modell", "Prüfmodell"],
    ["gesamt", "Antwort insgesamt"],
  ];
  return titel.flatMap(([name, text]) => {
    const wert = protokoll.abschnitte[name];
    return wert ? [{name, titel: text, median: sekunden(wert.median), p90: sekunden(wert.p90), anzahl: wert.anzahl}] : [];
  });
}

/** Der eine Satz über dem Protokoll: im Ziel oder nicht, in Worten. */
export function protokollSatz(protokoll: AntwortZeitenProtokoll) {
  const gesamt = protokoll.abschnitte.gesamt;
  if (!gesamt) return "Noch keine gemessene Antwort. Nach den ersten Fragen an das Gedächtnis steht hier, wie lange sie brauchen.";
  const ziel = `${sekunden(protokoll.ziel_s)} s`;
  const stand = gesamt.median <= protokoll.ziel_s ? `Typisch sind ${sekunden(gesamt.median)} s (Median), das ist im Ziel von ${ziel}.`
    : `Typisch sind ${sekunden(gesamt.median)} s (Median), das ist über dem Ziel von ${ziel}.`;
  return `${stand} Neun von zehn Antworten kamen in höchstens ${sekunden(gesamt.p90)} s. Gezählt sind die letzten ${gesamt.anzahl} Antworten.`;
}
