import {herkunftKennung, herkunftLesbar, type Provenienz} from "./herkunft";

/**
 * Woher eine Quelle stammt. Vorne nur, was ein Mensch lesen kann („Deine Berichtigung“); eine technische Kennung wie
 * `calendar:calendar-38d1…:probe-1@attrappe` steht eingeklappt unter „Für Techniker“ (Fremdprobe 3, Befund 9).
 */
export function Herkunft({provenance, klein = false}: {provenance?: Provenienz | null; klein?: boolean}) {
  const lesbar = herkunftLesbar(provenance);
  if (lesbar) return klein ? <small>Herkunft: {lesbar}</small> : <p>Herkunft: {lesbar}</p>;
  const kennung = herkunftKennung(provenance);
  return kennung ? <details className="quelle-technik"><summary>Für Techniker</summary><p>Herkunft: {kennung}</p></details> : null;
}
