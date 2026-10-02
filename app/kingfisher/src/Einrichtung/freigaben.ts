// Reine Logik des Schritts „Freigaben“ (ohne React, testbar mit node --test). Fremdprobe 3, Befund 4: Sobald man
// etwas angefasst hat, heißt der Knopf „Weiter“ (und der Schritt gilt als erledigt, nicht als übersprungen). Wer das
// Wetter einschaltet, aber keinen Ort wählen konnte, liest das in einem Satz, statt es später still aus vorzufinden.

export type FreigabeId = "meetings" | "wetter" | "fahrzeiten";

/** An, aus, oder `null`, solange der Stand nicht gelesen werden konnte. */
export type FreigabenAn = Record<FreigabeId, boolean | null>;

export type FreigabenStand = {
  an: FreigabenAn;
  /** Hat der Mensch in diesem Schritt etwas geändert? Dann ist er erledigt, auch wenn am Ende alles aus ist. */
  angefasst: boolean;
  /** Der Schalter „Wetter“ wurde eingeschaltet; an ist das Wetter erst mit einem gewählten Ort. */
  wetterGewuenscht: boolean;
};

export type FreigabenEreignis =
  /** Der Stand vom Sidecar (beim Öffnen und nach dem Zuklappen einer Zeile). */
  | {art: "gelesen"; an: FreigabenAn}
  /** Eine Einstellung wurde gespeichert; `an`, wenn ihr neuer Stand bekannt ist. */
  | {art: "geaendert"; id: FreigabeId; an?: boolean}
  /** Der Schalter des Wetters wurde umgelegt (mit Ort speichert er sofort, ohne Ort öffnet er die Ortssuche). */
  | {art: "wetter_wunsch"; an: boolean};

export const FREIGABEN_START: FreigabenStand = {
  an: {meetings: null, wetter: null, fahrzeiten: null}, angefasst: false, wetterGewuenscht: false,
};

export function freigabenWeiter(stand: FreigabenStand, ereignis: FreigabenEreignis): FreigabenStand {
  switch (ereignis.art) {
    case "gelesen": return {...stand, an: ereignis.an};
    case "geaendert": return {...stand, angefasst: true,
      an: ereignis.an === undefined ? stand.an : {...stand.an, [ereignis.id]: ereignis.an}};
    case "wetter_wunsch": return {...stand, angefasst: true, wetterGewuenscht: ereignis.an};
  }
}

/** „Weiter“ statt „Überspringen“: etwas ist an, oder der Mensch hat in diesem Schritt etwas geändert. */
export const freigabenErledigt = (stand: FreigabenStand) =>
  stand.angefasst || Object.values(stand.an).some(wert => wert === true);

export const WETTER_OHNE_ORT = "Das Wetter ist noch aus, weil noch kein Ort gewählt ist.";

/** Der eine Satz, wenn der Schalter des Wetters an sein soll, es aber ohne Ort nicht sein kann. */
export const wetterHinweis = (stand: FreigabenStand): string | null =>
  stand.wetterGewuenscht && stand.an.wetter !== true ? WETTER_OHNE_ORT : null;
