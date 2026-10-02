import {useEffect, useState} from "react";
import {ApiError, api} from "./api";
import {ergebnisText, jahreAuswahl, standText, type SuchindexStand} from "./suchindex";
import "./WeltSettings.css";

// Für Techniker → Suchindex: wie genau Kingfisher alte Quellen durchsucht und wie viel Platz das kostet. Die Vorgabe (0)
// durchsucht alles nach Wortteilen; wer Platz sparen will, wählt die letzten Jahre (sidecar: suchindex_routes.py). Eine
// Auswahl statt eines Zahlenfelds; die Wahl gilt sofort und lässt sich ebenso zurückstellen.

export function SuchindexSettings({active}: {active: boolean}) {
  const [stand, setStand] = useState<SuchindexStand | null>(null);
  const [arbeitet, setArbeitet] = useState(false);
  const [fehler, setFehler] = useState("");
  const [gespeichert, setGespeichert] = useState("");

  useEffect(() => {
    if (!active) return;
    let aktiv = true;
    api.suchindex().then(daten => { if (aktiv) setStand(daten); })
      .catch(() => { if (aktiv) setFehler("Der Stand des Suchindex konnte nicht geladen werden."); });
    return () => { aktiv = false; };
  }, [active]);

  async function speichern(jahre: number) {
    if (stand === null || jahre === stand.wortteile_jahre) return;
    setArbeitet(true); setFehler(""); setGespeichert("");
    try {
      const neu = await api.suchindexSetzen(jahre);
      setStand(neu); setGespeichert(ergebnisText(neu));
    } catch (e) {
      setFehler(e instanceof ApiError && e.detail ? e.detail : "Das konnte nicht umgestellt werden. Die Suche funktioniert weiter wie zuvor.");
    } finally { setArbeitet(false); }
  }

  return <section className="source-section welt-abschnitt" aria-label="Suchindex">
    <h2>Suche in alten Quellen</h2>
    <p>Kingfisher findet in neuen Quellen auch Wortteile („Rechnung“ in „Stromrechnung“). Das braucht viel Platz. Für ältere Quellen
      reicht oft die Suche nach ganzen Wörtern.</p>
    {!stand ? <p>{fehler || "Wird geladen …"}</p> : <>
      <div className="welt-suche">
        <label htmlFor="suchindex-jahre">Wortteile suchen</label>
        <div>
          <select id="suchindex-jahre" value={stand.wortteile_jahre} disabled={arbeitet} aria-describedby="suchindex-stand"
            onChange={event => void speichern(Number(event.target.value))}>
            {jahreAuswahl(stand.wortteile_jahre).map(eintrag => <option key={eintrag.jahre} value={eintrag.jahre}>{eintrag.text}</option>)}
          </select>
        </div>
      </div>
      {arbeitet && <p className="source-hint" role="status">Der Suchindex wird umgebaut. Bei vielen Quellen kann das einige Minuten dauern; die Suche funktioniert währenddessen weiter.</p>}
      <p id="suchindex-stand" className="source-hint">{standText(stand)}</p>
    </>}
    {gespeichert && <p role="status" className="source-hint suchindex-ergebnis">{gespeichert}</p>}
    {fehler && stand && <p role="alert" className="partial-error">{fehler}</p>}
  </section>;
}
