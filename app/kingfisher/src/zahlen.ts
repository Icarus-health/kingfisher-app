// Eine Zahl je Begriff (Persona-Prüfung, Paket Z1, 27.10.2026). Heute sagte „Ein Punkt braucht dich“, Aufgaben
// „2 Aufgaben brauchen dich heute“; über einer leeren Liste stand „1“, unter Zugänge „2 Kalender verbunden“ über drei
// Zeilen. Gezählt wird im Sidecar (`zaehlung.py`); hier steht nur, wie jede Anzeige dieselbe Zahl in denselben Satz
// setzt. Reine Logik ohne React, geprüft in `tests/eine-zahl.test.mjs`.

export type BrauchtDich = { aufgaben: number; weitere: number };
export type HeuteZahlen = BrauchtDich & { gezeigt: number; gesamt: number };

const zahl = (wert: unknown) => (typeof wert === "number" && Number.isFinite(wert) && wert > 0 ? Math.floor(wert) : 0);

/** Der eine Satz zu „braucht dich heute“: auf Heute über allem, unter „Aufgaben“ (dort ohne weitere Punkte). */
export function brauchtDichSatz({ aufgaben, weitere }: BrauchtDich): string {
  const a = zahl(aufgaben), w = zahl(weitere);
  if (!a && !w) return "Dein Überblick ist da.";
  if (!w) return a === 1 ? "Eine Aufgabe braucht dich heute." : `${a} Aufgaben brauchen dich heute.`;
  if (!a) return w === 1 ? "Ein Punkt braucht dich." : `${w} Punkte brauchen dich.`;
  return `${a === 1 ? "Eine Aufgabe" : `${a} Aufgaben`} und ${w === 1 ? "ein weiterer Punkt" : `${w} weitere Punkte`} brauchen dich heute.`;
}

type Zeile = { anzahl?: number | null };

/** Die Zahlen auf Heute: was der Sidecar ganz gezählt hat (`braucht_dich`), und wofür die gezeigten Zeilen stehen
 * („Heute sind 3 Aufgaben fällig.“ steht für drei). Ohne Zählung (ältere Antwort, Bildschirmvorlage) die Zeilen. */
export function heuteZahlen(briefing: { braucht_dich?: Partial<BrauchtDich> | null; needs_you: Zeile[] }): HeuteZahlen {
  const gezeigt = briefing.needs_you.reduce((summe, zeile) => summe + (zahl(zeile.anzahl) || 1), 0);
  const gezaehlt = briefing.braucht_dich;
  if (!gezaehlt) return { aufgaben: 0, weitere: gezeigt, gezeigt, gesamt: gezeigt };
  const aufgaben = zahl(gezaehlt.aufgaben), weitere = zahl(gezaehlt.weitere);
  return { aufgaben, weitere, gezeigt: Math.min(gezeigt, aufgaben + weitere), gesamt: aufgaben + weitere };
}

/** Die leise Zahl neben „Braucht dich“: die ganze Zahl, oder „3 von 22“, wenn Heute nur das Wichtigste zeigt. */
export function brauchtDichZaehler({ gezeigt, gesamt }: Pick<HeuteZahlen, "gezeigt" | "gesamt">): string | null {
  if (!(gesamt > 0)) return null;
  return gezeigt >= gesamt ? String(gesamt) : `${gezeigt} von ${gesamt}`;
}

type KalenderQuelle = { id: string };
type KalenderKonto = { id: string; art?: string };

/** Die Zeilen unter „Kalender“ in Zugänge: eingetragene Kalender und die Mac-Kalender, die Kingfisher liest. Die Zahl
 * „N Kalender verbunden“ ist die Länge dieser Liste, nicht nur die der eingetragenen. */
export function kalenderZeilen<Q extends KalenderQuelle, K extends KalenderKonto>(
  overview: { calendar_sources?: Q[] } | null, konten: { kalender: K[] } | null,
): Array<{ id: string; quelle?: Q; konto?: K }> {
  const eingetragen = (overview?.calendar_sources ?? []).map(quelle => ({ id: quelle.id, quelle, konto: konten?.kalender.find(k => k.id === quelle.id) }));
  const mac = (konten?.kalender ?? []).filter(k => k.art === "mac" && !eingetragen.some(e => e.id === k.id)).map(konto => ({ id: konto.id, konto }));
  return [...eingetragen, ...mac];
}

/** Liegen Termine des Zeitraums (im gewählten Bereich) nur in ausgeblendeten Kalendern, sagt der Kalender das, statt
 * „keine Termine“, und bietet an, genau diese Kalender wieder einzublenden. Sonst null. */
export function ausgeblendetLage<T>({ termine, quellen, ausgeblendet, passt, quelleVon }: {
  termine: T[]; quellen: Array<{ id: string; label: string }>; ausgeblendet: Set<string>;
  passt: (termin: T) => boolean; quelleVon: (termin: T) => string | string[];
}): { anzahl: number; kalender: Array<{ id: string; label: string }>; satz: string; knopf: string } | null {
  if (!ausgeblendet.size) return null;
  const ids = new Set<string>();
  let anzahl = 0;
  for (const termin of termine) {
    if (!passt(termin)) continue;
    const von = ([] as string[]).concat(quelleVon(termin));
    if (!von.length || von.some(id => !ausgeblendet.has(id))) continue;
    anzahl += 1;
    for (const id of von) ids.add(id);
  }
  if (!anzahl) return null;
  const kalender = quellen.filter(q => ids.has(q.id));
  const namen = kalender.map(k => k.label).join(", ");
  const wer = kalender.length === 1 ? "einem ausgeblendeten Kalender" : "ausgeblendeten Kalendern";
  const satz = `${anzahl === 1 ? "Ein Termin" : `${anzahl} Termine`} in diesem Zeitraum ${anzahl === 1 ? "liegt" : "liegen"} in ${wer}${namen ? `: ${namen}` : ""}.`;
  const knopf = kalender.length <= 1 ? "Einblenden" : kalender.length === 2 ? "Beide einblenden" : "Alle einblenden";
  return { anzahl, kalender, satz, knopf };
}
