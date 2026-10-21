// Ton je Kreis (Paket B5): unter „Kingfisher und du“ je bestätigtem Kreis eine Zeile mit dem Vorschlag aus den gesendeten
// Mails an seine Personen, dazu „Übernehmen“ und „Nicht übernehmen“ und die Belege zum Aufklappen. Eine Regel entsteht
// erst mit dem Klick (sidecar: mail_style.py, Scope `kreis:<kreis>`).
import { useEffect, useState } from "react";
import { api, ApiError } from "./api";
import { ProfileSource } from "./ProfileSource";
import { belegeTitel, kreisTonSatz, type KreisTonStand } from "./stilprofil";
import "./Kreis.css";

function fehlerText(e: unknown, sonst: string): string {
  return e instanceof ApiError && e.detail ? e.detail : sonst;
}

export function KreisTon() {
  const [kreise, setKreise] = useState<KreisTonStand[] | null>(null);
  const [fehler, setFehler] = useState("");
  const [meldung, setMeldung] = useState("");
  const [arbeitet, setArbeitet] = useState(false);
  const [runde, setRunde] = useState(0);

  useEffect(() => {
    let aktiv = true;
    api.stilKreise().then(daten => { if (aktiv) setKreise(daten.kreise); })
      .catch(e => { if (aktiv) setFehler(fehlerText(e, "Der Ton je Kreis ließ sich gerade nicht laden.")); });
    return () => { aktiv = false; };
  }, [runde]);

  async function tun(aktion: () => Promise<KreisTonStand>, satz: string) {
    setArbeitet(true); setFehler(""); setMeldung("");
    try { await aktion(); setMeldung(satz); setRunde(r => r + 1); }
    catch (e) { setFehler(fehlerText(e, "Das ließ sich gerade nicht speichern. Bitte noch einmal versuchen.")); setRunde(r => r + 1); }
    finally { setArbeitet(false); }
  }

  if (fehler && !kreise) return <p role="alert" className="kreis-fehler">{fehler}</p>;
  if (!kreise) return <p className="source-hint">Wird gelesen …</p>;
  return <div className="kreis-stand stil-kreise">
    {kreise.map(stand => <div key={stand.kreis} className="stil-kreis">
      <p className="source-hint">{kreisTonSatz(stand)}</p>
      {stand.proposal ? <div className="kreis-wahlen">
        <button type="button" className="primary-action" disabled={arbeitet}
          onClick={() => void tun(() => api.stilKreisUebernehmen(stand.kreis, stand.proposal!.rules, stand.proposal!.evidence_ids),
            `Übernommen. Entwürfe an ${stand.kreis_text} folgen jetzt diesem Ton; eine Regel je Person geht vor.`)}>Übernehmen</button>
        <button type="button" className="secondary-action" disabled={arbeitet}
          onClick={() => void tun(() => api.stilKreisAblehnen(stand.kreis, stand.proposal!.evidence_ids),
            "Nicht übernommen. Kommt eine neue gesendete Mail dazu, fragt Kingfisher wieder.")}>Nicht übernehmen</button>
      </div> : null}
      {stand.profile ? <div className="kreis-wahlen">
        <button type="button" className="chronik-mehr" disabled={arbeitet}
          onClick={() => void tun(() => api.stilKreisZurueck(stand.kreis), `Zurückgenommen. Für ${stand.kreis_text} gilt keine eigene Regel mehr.`)}>Regel zurücknehmen</button>
      </div> : null}
      {stand.gesendete.length ? <details className="quiet-details stil-belege">
        <summary>{belegeTitel(stand.gesendete.length)}</summary>
        {stand.gesendete.map(beleg => <article key={beleg.id} className="stil-beleg">
          <strong>{beleg.title || "(Ohne Betreff)"}</strong>
          <p>{beleg.text}</p>
          <ProfileSource kind="episode" id={beleg.id} label="Mail öffnen" readOnly />
        </article>)}
      </details> : null}
    </div>)}
    {meldung ? <p role="status" className="kreis-ok">{meldung}</p> : null}
    {fehler ? <p role="alert" className="kreis-fehler">{fehler}</p> : null}
  </div>;
}
