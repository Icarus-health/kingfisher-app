import { useEffect, useRef, useState } from "react";
import { api, type AufgabenVonSelbstHeute } from "./api";
import { zeigeHinweis } from "./grundlage";
import { ANLAGE_WIEDER, ANLAGE_ZURUECK, heuteSatz, heuteZurueck } from "./aufgabenVonSelbst";

// Aufgaben von selbst auf Heute (docs/66-automatik.md): eine ruhige Zeile „3 Aufgaben aus der Post angelegt. Ansehen ·
// Rückgängig“, nicht jede einzeln. „Rückgängig“ nimmt alle noch offenen von heute zurück, der Hinweis unten holt sie mit
// seinem „Rückgängig“ wieder. Nichts davon ist ein Fakt im Bestand; der Sidecar entscheidet (`aufgaben_von_selbst.py`).

/** Nimmt eine selbst angelegte Aufgabe zurück und sagt es im Hinweis, mit „Rückgängig“ (stellt sie wieder her). */
export async function anlageZuruecknehmen(taskId: string, nachher: () => void, fehler: (satz: string) => void, wieder: () => void = nachher) {
  try {
    await api.aufgabeVonSelbstZuruecknehmen(taskId);
    nachher();
    zeigeHinweis({ text: ANLAGE_ZURUECK, danach: ANLAGE_WIEDER,
      rueckgaengig: async () => { await api.aufgabeVonSelbstWiederherstellen(taskId); wieder(); } });
  } catch {
    fehler("Das ließ sich gerade nicht zurücknehmen. Bitte erneut versuchen.");
  }
}

export function AufgabenVonSelbstZeile({ onChanged }: { onChanged?: () => void }) {
  const [heute, setHeute] = useState<AufgabenVonSelbstHeute | null>(null);
  const [arbeitet, setArbeitet] = useState(false);
  const [fehler, setFehler] = useState("");
  const version = useRef(0);

  function laden() {
    const eigene = ++version.current;
    api.aufgabenVonSelbstHeute().then(daten => { if (eigene === version.current) setHeute(daten); }).catch(() => undefined);
  }
  useEffect(() => { laden(); window.addEventListener("focus", laden); return () => { version.current++; window.removeEventListener("focus", laden); }; }, []);

  const satz = heuteSatz(heute);
  const offen = heuteZurueck(heute);
  if (!satz) return null;

  async function zuruecknehmen() {
    if (arbeitet || !offen.length) return;
    setArbeitet(true); setFehler("");
    try {
      const antwort = await api.aufgabenVonSelbstZuruecknehmen(offen);
      laden(); onChanged?.();
      zeigeHinweis({ text: `${antwort.satz} Kingfisher legt sie nicht wieder an.`, danach: "Die Aufgaben sind wieder da.",
        rueckgaengig: async () => { await api.aufgabenVonSelbstWiederherstellen(offen); laden(); onChanged?.(); } });
    } catch {
      setFehler("Das ließ sich gerade nicht zurücknehmen. Bitte erneut versuchen.");
    } finally {
      setArbeitet(false);
    }
  }

  return <p className="today-notice today-von-selbst" role="status">
    {satz} <a href="/vorhaben?view=mine">Ansehen</a>
    {offen.length ? <><span aria-hidden="true"> · </span><button type="button" className="text-action" disabled={arbeitet} onClick={() => void zuruecknehmen()}>Rückgängig</button></> : null}
    {fehler ? <span className="today-von-selbst-fehler" role="alert"> {fehler}</span> : null}
  </p>;
}
