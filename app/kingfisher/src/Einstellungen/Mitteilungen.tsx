import { useEffect, useState } from "react";
import { Schalter } from "../grundlage";
import { api, ApiError, type MitteilungenEinstellung } from "../api";
import { UHRZEIT_VORGABE, mitteilungenSchalter, uhrzeitGueltig, wochenSatz } from "../mitteilungenSchalter";
import { fuerSystem } from "../system";
import { useSystem } from "../useSystem";
import { SCHALTER } from "./gliederung";

// „Mitteilungen auf dem {Rechner}“: Vorgabe aus, weil es eine Erlaubnis des Systems braucht. Mit dem Schalter kommt
// morgens eine Mitteilung mit dem, was heute zählt, dazu höchstens zwei dringende (sidecar: mitteilungen.py). Darunter
// die Uhrzeit und der Satz, an dem Etappe 5 gemessen wird: wie viele Mitteilungen diese Woche und wie viele davon der
// Mensch für überflüssig hielt. Fehlt die Erlaubnis, steht da, wo man sie gibt.
const fehlerText = (e: unknown) => e instanceof ApiError && e.detail ? e.detail : "Das konnte nicht gespeichert werden. Bitte erneut versuchen.";

export function Mitteilungen() {
  const system = useSystem();
  const [stand, setStand] = useState<MitteilungenEinstellung | null>(null);
  const [uhrzeit, setUhrzeit] = useState(UHRZEIT_VORGABE);
  const [arbeitet, setArbeitet] = useState(false);
  const [fehler, setFehler] = useState("");
  const [gespeichert, setGespeichert] = useState("");

  useEffect(() => {
    let aktiv = true;
    api.mitteilungen().then(daten => { if (aktiv) { setStand(daten); setUhrzeit(daten.morgens); } })
      .catch(() => { if (aktiv) setFehler("Die Einstellung konnte nicht geladen werden."); });
    return () => { aktiv = false; };
  }, []);

  async function speichern(body: { an?: boolean; morgens?: string }, text: string) {
    setArbeitet(true); setFehler(""); setGespeichert("");
    try {
      const neu = await api.mitteilungenSetzen(body);
      setStand(neu); setUhrzeit(neu.morgens); setGespeichert(text);
    } catch (e) { setFehler(fehlerText(e)); }
    finally { setArbeitet(false); }
  }

  const titel = fuerSystem(SCHALTER.mitteilungen.titel, system);
  const schalter = stand ? mitteilungenSchalter(stand, system) : null;
  return <section className="darf-zeile" aria-label={titel}>
    {!stand || !schalter ? <p>{fehler || "Wird geladen …"}</p> : <>
      <Schalter titel={titel} satz={SCHALTER.mitteilungen.verlaesst} an={schalter.an} deaktiviert={arbeitet || schalter.gesperrt}
        onWechsel={an => void speichern({ an },
          an ? "Kingfisher meldet sich jetzt von sich aus. Jede Mitteilung lässt sich als überflüssig melden." : "Kingfisher meldet sich nicht mehr von sich aus.")} />
      {schalter.hinweis && <p className="source-hint" role="status">{schalter.hinweis}</p>}
      {stand.an && <form className="mitteilungen-uhrzeit" onSubmit={event => {
        event.preventDefault();
        if (uhrzeitGueltig(uhrzeit) && uhrzeit !== stand.morgens) void speichern({ morgens: uhrzeit }, `Die Morgenmitteilung kommt ab ${uhrzeit} Uhr.`);
      }}>
        <label htmlFor="mitteilungen-morgens">Wann morgens?</label>
        <div>
          <input id="mitteilungen-morgens" type="time" value={uhrzeit} min="00:00" max="20:59" step={60} disabled={arbeitet}
            onChange={event => setUhrzeit(event.target.value)} />
          <button type="submit" className="secondary-action" disabled={arbeitet || !uhrzeitGueltig(uhrzeit) || uhrzeit === stand.morgens}>Uhrzeit speichern</button>
        </div>
        {!uhrzeitGueltig(uhrzeit) && <p className="source-hint" role="status">Bitte eine Uhrzeit vor 21:00 Uhr.</p>}
      </form>}
      <p className="source-hint" role="status" data-testid="mitteilungen-woche">{wochenSatz(stand.woche)}</p>
    </>}
    {gespeichert && <p role="status" className="source-hint">{gespeichert}</p>}
    {fehler && stand && <p role="alert" className="settings-error">{fehler}</p>}
  </section>;
}
