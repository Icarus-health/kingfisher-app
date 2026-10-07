import { useEffect, useRef, useState } from "react";
import { api, ApiError, type ModelRoles, type ModelRoleState } from "../api";
import { listenForCloudAccessChange } from "../cloudAccessEvents";
import { SCHALTER } from "./gliederung";

// „Cloud für Fragen und Antworten nutzen“: ein Schalter für die zwei Aufgaben, die ein Cloudanbieter übernehmen darf
// (Fragen verstehen, Antworten formulieren). Alles andere bleibt auf diesem Rechner, auch mit diesem Schalter an
// (sidecar: model_roles.py, `cloud_moeglich`). Aus ist die Vorgabe und mit einem Klick wieder erreicht; Einschalten
// braucht die ausdrückliche Zustimmung in einem Satz. Die feine Wahl je Aufgabe steht hinter „Für Techniker“.

const AUFGABEN: Record<string, true> = { frage: true, antwort: true };
const fehlerText = (e: unknown) => e instanceof ApiError && e.detail ? e.detail : "Das konnte nicht gespeichert werden. Bitte erneut versuchen.";

export function CloudSchalter() {
  const [rollen, setRollen] = useState<ModelRoles | null>(null);
  const [geladenFehler, setGeladenFehler] = useState(false);
  const [frage, setFrage] = useState(false);
  const [anbieter, setAnbieter] = useState("");
  const [zugestimmt, setZugestimmt] = useState(false);
  const [arbeitet, setArbeitet] = useState(false);
  const [fehler, setFehler] = useState("");
  const [hinweis, setHinweis] = useState("");
  const loadVersion = useRef(0);

  useEffect(() => {
    let aktiv = true;
    async function load() {
      const version = ++loadVersion.current;
      try {
        const daten = await api.modelRoles();
        if (aktiv && version === loadVersion.current) { setRollen(daten); setGeladenFehler(false); }
      } catch {
        if (aktiv && version === loadVersion.current) setGeladenFehler(true);
      }
    }
    const cloudAccessChanged = () => {
      setFrage(false); setAnbieter(""); setZugestimmt(false);
      setFehler(""); setHinweis(""); setRollen(null); setGeladenFehler(false);
      void load();
    };
    void load();
    const unsubscribe = listenForCloudAccessChange(cloudAccessChanged);
    return () => { aktiv = false; loadVersion.current++; unsubscribe(); };
  }, []);

  const aufgaben: ModelRoleState[] = rollen ? rollen.rollen.filter(r => r.rolle in AUFGABEN && r.cloud_moeglich) : [];
  const inCloud = aufgaben.filter(r => r.wirksam.quelle === "cloud");
  const an = inCloud.length > 0;
  const mitSchluessel = rollen ? rollen.anbieter.filter(a => a.schluessel_da && a.standardmodell.trim()) : [];
  const gewaehlt = anbieter || (mitSchluessel.length === 1 ? mitSchluessel[0].id : "");
  const anbieterName = (id: string) => rollen?.anbieter.find(a => a.id === id)?.label ?? id;

  async function ausschalten() {
    setArbeitet(true); setFehler(""); setHinweis(""); setFrage(false);
    const version = loadVersion.current;
    try {
      let stand = rollen as ModelRoles;
      for (const aufgabe of inCloud) {
        if (version !== loadVersion.current) return;
        stand = await api.saveModelRole(aufgabe.rolle, { cloud: false });
      }
      if (version !== loadVersion.current) return;
      setRollen(stand);
      setHinweis("Fragen und Antworten bleiben wieder auf diesem Rechner.");
    } catch (e) { if (version === loadVersion.current) setFehler(fehlerText(e)); }
    finally { setArbeitet(false); }
  }

  async function einschalten() {
    if (!gewaehlt || !zugestimmt) return;
    setArbeitet(true); setFehler(""); setHinweis("");
    const version = loadVersion.current;
    try {
      let stand = rollen as ModelRoles;
      for (const aufgabe of aufgaben) {
        if (version !== loadVersion.current) return;
        stand = await api.saveModelRole(aufgabe.rolle, { cloud: true, anbieter: gewaehlt, einwilligung: true });
      }
      if (version !== loadVersion.current) return;
      setRollen(stand); setFrage(false); setZugestimmt(false);
      setHinweis(`Fragen und Antworten laufen jetzt über ${anbieterName(gewaehlt)}. Mit einem Klick auf den Schalter ist das wieder aus.`);
    } catch (e) { if (version === loadVersion.current) setFehler(fehlerText(e)); }
    finally { setArbeitet(false); }
  }

  function umschalten(neu: boolean) {
    setHinweis(""); setFehler("");
    if (!neu) { void ausschalten(); return; }
    setAnbieter(""); setZugestimmt(false); setFrage(true);
  }

  return <section className="darf-zeile" aria-label={SCHALTER.cloud.titel}>
    {geladenFehler ? <p role="alert" className="settings-error">Der Stand konnte gerade nicht gelesen werden.</p> : !rollen ? <p>Wird geladen …</p> : aufgaben.length === 0 ? null : <>
      <label className="welt-schalter"><input type="checkbox" role="switch" checked={an || frage} disabled={arbeitet}
        onChange={event => umschalten(event.target.checked)} />
        <span><strong>{SCHALTER.cloud.titel}</strong><small>{SCHALTER.cloud.verlaesst}</small></span></label>
      {an && <p className="source-hint" role="status">Fragen und Antworten laufen über {anbieterName(inCloud[0].wahl.anbieter)}.</p>}
      {frage && !an && (mitSchluessel.length === 0
        ? <div className="darf-frage" role="group" aria-label="Cloud einschalten">
          <p>Dafür braucht es einen gespeicherten Zugang und ein Modell. Richte beides unter <a href="#ki">KI &amp; Modelle</a> ein. Bis dahin bleibt alles auf diesem Rechner.</p>
          <button type="button" className="secondary-action" onClick={() => setFrage(false)}>Verstanden</button>
        </div>
        : <div className="darf-frage" role="group" aria-label="Cloud einschalten">
          {mitSchluessel.length > 1 && <label>Anbieter
            <select value={gewaehlt} onChange={event => setAnbieter(event.target.value)}>
              <option value="">Bitte wählen</option>
              {mitSchluessel.map(a => <option key={a.id} value={a.id}>{a.label}</option>)}
            </select></label>}
          <label className="model-consent"><input type="checkbox" checked={zugestimmt} onChange={event => setZugestimmt(event.target.checked)} />
            <span>{SCHALTER.cloud.zustimmung}</span></label>
          <div className="darf-frage-knoepfe">
            <button type="button" className="primary-action" disabled={arbeitet || !gewaehlt || !zugestimmt} onClick={() => void einschalten()}>Cloud einschalten</button>
            <button type="button" className="secondary-action" onClick={() => setFrage(false)}>Abbrechen</button>
          </div>
        </div>)}
    </>}
    {hinweis && <p role="status" className="source-hint">{hinweis}</p>}
    {fehler && <p role="alert" className="settings-error">{fehler}</p>}
  </section>;
}
