import {useCallback, useEffect, useState} from "react";
import {api, type AutostartStand} from "../api";
import {autostartMeldung} from "./autostart";

/**
 * „Beim Anmelden starten“: ein Schalter, nicht vorausgewählt. Er schreibt nur die Antwort; eingerichtet wird auf dem
 * Rechner von einem Helfer (Mac: Launch Agent). Dieselbe Wahl im Assistenten und unter Einstellungen → Was Kingfisher darf.
 */
export function AutostartWahl({beiAenderung, titel, satz}: {beiAenderung?: (stand: AutostartStand) => void; titel?: string; satz?: string}) {
  const [stand, setStand] = useState<AutostartStand | null>(null);
  const [fehler, setFehler] = useState("");
  const [arbeitet, setArbeitet] = useState(false);

  const lesen = useCallback(async () => {
    try {
      const neu = await api.autostart();
      setStand(neu); beiAenderung?.(neu);
    } catch {
      setFehler("Der Stand konnte gerade nicht gelesen werden.");
    }
  }, [beiAenderung]);

  // Ob ein Helfer da ist und ob er die Datei angelegt hat, zeigt sich erst nach ein paar Sekunden.
  useEffect(() => {
    void lesen();
    const takt = window.setInterval(() => { if (document.visibilityState === "visible") void lesen(); }, 5000);
    return () => window.clearInterval(takt);
  }, [lesen]);

  async function setzen(an: boolean) {
    setArbeitet(true); setFehler("");
    try {
      const neu = await api.autostartSetzen(an);
      setStand(neu); beiAenderung?.(neu);
    } catch {
      setFehler("Das konnte gerade nicht gespeichert werden. Bitte versuche es noch einmal.");
    } finally {
      setArbeitet(false);
    }
  }

  return <div className="autostart-wahl">
    <label className="autostart-schalter">
      <input type="checkbox" role="switch" checked={stand?.gewuenscht === true} disabled={!stand || !stand.verfuegbar || arbeitet}
        onChange={event => void setzen(event.target.checked)} />
      {satz ? <span><strong>{titel ?? "Beim Anmelden starten"}</strong><small>{satz}</small></span> : <span>{titel ?? "Beim Anmelden starten"}</span>}
    </label>
    <p role="status" className="autostart-meldung">{autostartMeldung(stand)}</p>
    {fehler ? <p role="alert" className="settings-error">{fehler}</p> : null}
  </div>;
}
