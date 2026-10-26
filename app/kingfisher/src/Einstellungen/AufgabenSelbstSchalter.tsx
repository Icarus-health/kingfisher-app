import { useEffect, useState } from "react";
import { Schalter } from "../grundlage";
import { api } from "../api";
import { SCHALTER } from "./gliederung";

// „Aufgaben aus Mails selbst anlegen“ (docs/66-automatik.md): Vorgabe an. Eindeutige Bitten an dich und deine Zusagen
// aus neuen Mails legt Kingfisher selbst als Aufgabe an, jede mit „Rückgängig“; aus, bleiben sie Vorschläge. Der Sidecar
// hält die Wahl (`aufgaben_von_selbst_routes.py`); hier nur der Schalter und die Antwort darauf.
export function AufgabenSelbstSchalter() {
  const [an, setAn] = useState<boolean | null>(null);
  const [arbeitet, setArbeitet] = useState(false);
  const [fehler, setFehler] = useState("");
  const [gespeichert, setGespeichert] = useState("");

  useEffect(() => {
    let aktiv = true;
    api.aufgabenVonSelbst().then(daten => { if (aktiv) setAn(daten.an); })
      .catch(() => { if (aktiv) setFehler("Die Einstellung konnte nicht geladen werden."); });
    return () => { aktiv = false; };
  }, []);

  async function wechseln(neu: boolean) {
    setArbeitet(true); setFehler(""); setGespeichert("");
    try {
      const daten = await api.aufgabenVonSelbstSetzen(neu);
      setAn(daten.an);
      setGespeichert(daten.an ? "Eindeutige Bitten und Zusagen aus neuen Mails werden ab jetzt Aufgaben." : "Erkannte Aufgaben bleiben ab jetzt Vorschläge, bis du sie übernimmst.");
    } catch { setFehler("Das konnte nicht gespeichert werden. Bitte erneut versuchen."); }
    finally { setArbeitet(false); }
  }

  return <section className="darf-zeile" aria-label={SCHALTER.aufgaben_selbst.titel}>
    {an === null ? <p>{fehler || "Wird geladen …"}</p>
      : <Schalter titel={SCHALTER.aufgaben_selbst.titel} satz={SCHALTER.aufgaben_selbst.verlaesst} an={an} deaktiviert={arbeitet}
          onWechsel={neu => void wechseln(neu)} />}
    {gespeichert && <p role="status" className="source-hint">{gespeichert}</p>}
    {fehler && an !== null && <p role="alert" className="settings-error">{fehler}</p>}
  </section>;
}
