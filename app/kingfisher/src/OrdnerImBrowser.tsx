import {useEffect, useState, type FormEvent} from "react";
import {api, ApiError, type OrdnerOrte, type OrdnerPrefix, type Unterordner} from "./api";
import {OHNE_ORTE, ortText, ortZusatz} from "./ordnerWahl";

/**
 * Ein Auswahldialog im Browser (Fremdprobe 2, Befund 30): vom Benutzerordner aus durch die Unterordner klicken, statt
 * einen Pfad zu tippen. Gezeigt werden nur Namen von Ordnern; freigegeben wird erst mit „Diesen Ordner verwenden“.
 */
function OrdnerDurchsehen({prefix, arbeitet, beiWahl}: {prefix: OrdnerPrefix; arbeitet: boolean; beiWahl: (pfad: string) => void}) {
  const [stand, setStand] = useState<Unterordner | null>(null);
  const [fehler, setFehler] = useState("");
  async function oeffnen(pfad: string) {
    setFehler("");
    try { setStand(await api.unterordner(prefix, pfad)); }
    catch (problem) { setFehler(problem instanceof ApiError && problem.detail ? problem.detail : "Der Ordner ließ sich gerade nicht öffnen."); }
  }
  useEffect(() => { void oeffnen(""); }, [prefix]);  // eslint-disable-line react-hooks/exhaustive-deps
  return <div className="ordner-durchsehen" role="group" aria-label="Ordner auswählen">
    {stand ? <>
      <p className="ordner-hier"><strong>{stand.pfad ? stand.name : "Wo liegt der Ordner?"}</strong></p>
      <ul className="ordner-liste" aria-label="Unterordner">
        {stand.oben !== null ? <li><button type="button" className="text-action" disabled={arbeitet} onClick={() => void oeffnen(stand.oben ?? "")}>Eine Ebene höher</button></li> : null}
        {stand.ordner.map(ordner => <li key={ordner.pfad}><button type="button" className="ordner-eintrag" disabled={arbeitet} onClick={() => void oeffnen(ordner.pfad)}><span aria-hidden="true" className="ordner-pfeil">▸ </span>{ordner.name}</button></li>)}
        {!stand.ordner.length ? <li className="source-hint">Hier liegen keine weiteren Ordner.</li> : null}
      </ul>
      {stand.pfad ? <button type="button" className="primary-action" disabled={arbeitet} onClick={() => beiWahl(stand.pfad)}>Diesen Ordner verwenden</button> : null}
    </> : !fehler ? <p role="status">Wird geladen …</p> : null}
    {fehler ? <p role="alert" className="settings-error am-knopf">{fehler}</p> : null}
  </div>;
}

/**
 * Ordner wählen ohne Mac-Helfer (Fremdprobe, Befund 6): bekannte Orte zum Anklicken, „Anderen Ordner auswählen …“ zum
 * Durchklicken wie in einem Auswahldialog (Fremdprobe 2, Befund 30) und, eingeklappt für Techniker, ein Feld für einen
 * Pfad, den Kingfisher vorher prüft. Freigegeben wird nur, was hier angeklickt wird; die Antwort ist ein Satz.
 */
export function OrdnerImBrowser({prefix, beiGewaehlt}: {prefix: OrdnerPrefix; beiGewaehlt: (satz: string) => void}) {
  const [orte, setOrte] = useState<OrdnerOrte | null>(null);
  const [pfad, setPfad] = useState("");
  const [durchsehen, setDurchsehen] = useState(false);
  const [arbeitet, setArbeitet] = useState(false);
  const [fehler, setFehler] = useState("");
  const feldId = prefix === "/api/v1/transcript-sync" ? "ordner-pfad-mitschriften" : "ordner-pfad-dokumente";
  useEffect(() => {
    let aktiv = true;
    api.ordnerOrte(prefix).then(daten => { if (aktiv) setOrte(daten); })
      .catch(() => { if (aktiv) setFehler("Die Orte konnten gerade nicht geladen werden."); });
    return () => { aktiv = false; };
  }, [prefix]);

  async function waehlen(wahl: {pfad?: string; vorgabe?: boolean}) {
    if (arbeitet) return;
    setArbeitet(true); setFehler("");
    try { beiGewaehlt((await api.ordnerLokal(prefix, wahl)).satz); setPfad(""); }
    catch (problem) { setFehler(problem instanceof ApiError && problem.detail ? problem.detail : "Der Ordner konnte gerade nicht freigegeben werden. Bitte versuche es noch einmal."); }
    finally { setArbeitet(false); }
  }
  function eigener(event: FormEvent) {
    event.preventDefault();
    if (pfad.trim()) void waehlen({pfad: pfad.trim()});
  }

  return <div className="ordner-im-browser">
    <p>Kingfisher liest nur den Ordner, den du hier auswählst.</p>
    {!orte && !fehler ? <p role="status">Wird geladen …</p> : null}
    {orte && orte.orte.length ? <ul className="ordner-orte" aria-label="Ordner zum Auswählen">
      {orte.orte.map(ort => <li key={ort.pfad}>
        <button type="button" className={ort.vorgabe ? "primary-action" : "secondary-action"} disabled={arbeitet}
          onClick={() => void waehlen(ort.vorgabe ? {vorgabe: true} : {pfad: ort.pfad})}>{ortText(ort)}</button>
        {ortZusatz(ort) ? <small>{ortZusatz(ort)}</small> : null}
      </li>)}
    </ul> : null}
    {orte && !orte.orte.length ? <p className="source-hint" role="status">{OHNE_ORTE}</p> : null}
    {orte && orte.cloud_hinweis ? <p className="source-hint">{orte.cloud_hinweis}</p> : null}
    {!durchsehen ? <button type="button" className="secondary-action" disabled={arbeitet} onClick={() => setDurchsehen(true)}>Anderen Ordner auswählen …</button>
      : <OrdnerDurchsehen prefix={prefix} arbeitet={arbeitet} beiWahl={gewaehlt => void waehlen({pfad: gewaehlt})} />}
    <details className="ordner-eigener">
      <summary>Für Techniker: Pfad eintippen</summary>
      <form onSubmit={eigener}>
        <label htmlFor={feldId}>Pfad des Ordners</label>
        <div><input id={feldId} value={pfad} placeholder="~/Documents/Mitschriften" disabled={arbeitet} onChange={event => setPfad(event.target.value)} />
          <button type="submit" className="secondary-action" disabled={arbeitet || !pfad.trim()}>Diesen Pfad verwenden</button></div>
      </form>
    </details>
    {arbeitet ? <p role="status" className="source-hint">Kingfisher prüft den Ordner und liest ihn …</p> : null}
    {fehler ? <p role="alert" className="settings-error am-knopf">{fehler}</p> : null}
  </div>;
}
