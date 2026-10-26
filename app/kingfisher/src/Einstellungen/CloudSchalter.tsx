import { useEffect, useRef, useState } from "react";
import { Schalter } from "../grundlage";
import { api, ApiError, type CloudProtokollEintrag, type ModelRoles, type ModelRoleState } from "../api";
import { listenForCloudAccessChange } from "../cloudAccessEvents";
import { SCHALTER, zustimmungCloud } from "./gliederung";

// „Cloud für Fragen und Antworten nutzen“: ein Schalter für die zwei Aufgaben, die ein Cloudanbieter übernehmen darf
// (Fragen verstehen, Antworten formulieren). Alles andere bleibt auf diesem Rechner, auch mit diesem Schalter an
// (sidecar: model_roles.py, `cloud_moeglich`). Aus ist die Vorgabe und mit einem Klick wieder erreicht; Einschalten
// braucht die ausdrückliche Zustimmung in einem Satz. Die feine Wahl je Aufgabe steht hinter „Für Techniker“.
//
// Persona-Prüfung, Paket D: Der Schalter steht erst nach der Zustimmung auf „an“ (D5); bis dahin sagt eine Zeile, dass
// die Cloud noch aus ist. Die Zustimmung nennt den Anbieter mit Land und Region (D4). Ausschalten gilt sofort: Der
// Schalter steht beim Klick auf „aus“, der Sidecar schreibt den Widerruf, ohne auf eine laufende Antwort zu warten (D1).
// Darunter, aufklappbar, was wann an welchen Anbieter ging, ohne Inhalte (Kleinpunkt b).

/** „26.10., 14:03“: kurz genug für eine Zeile im Protokoll. */
function zeitKurz(iso: string): string {
  const zeit = new Date(iso);
  if (Number.isNaN(zeit.getTime())) return "";
  return zeit.toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

/** Was an die Cloud ging: lädt erst beim Aufklappen, ohne Inhalte, neueste zuerst. */
export function CloudProtokoll() {
  const [eintraege, setEintraege] = useState<CloudProtokollEintrag[] | null>(null);
  const [fehler, setFehler] = useState(false);
  function laden() {
    setFehler(false);
    api.cloudProtokoll().then(daten => setEintraege(daten.eintraege)).catch(() => setFehler(true));
  }
  return <details className="quiet-details cloud-protokoll" onToggle={event => { if ((event.target as HTMLDetailsElement).open) laden(); }}>
    <summary>{SCHALTER.cloud.protokoll}</summary>
    {fehler ? <p className="source-hint" role="status">Das Protokoll konnte gerade nicht gelesen werden.</p>
      : eintraege === null ? <p className="source-hint">Wird geladen …</p>
      : eintraege.length === 0 ? <p className="source-hint">In den letzten 30 Tagen ist nichts an einen Cloudanbieter gegangen.</p>
      : <ul className="cloud-protokoll-liste" aria-label={SCHALTER.cloud.protokoll}>
        {eintraege.map((e, index) => <li key={`${e.zeit}-${index}`}><span className="cloud-protokoll-zeit">{zeitKurz(e.zeit)}</span> {e.satz}</li>)}
      </ul>}
    <p className="source-hint">Nur Zeit, Anbieter und wofür; was gesendet wurde, steht hier nicht. Letzte 30 Tage, höchstens 30 Anfragen.</p>
  </details>;
}

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
  // Beim Ausschalten steht der Schalter sofort auf „aus“, auch bevor der Sidecar antwortet (D1).
  const [widerrufen, setWiderrufen] = useState(false);
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
  const an = inCloud.length > 0 && !widerrufen;
  const mitSchluessel = rollen ? rollen.anbieter.filter(a => a.schluessel_da && a.standardmodell.trim()) : [];
  const gewaehlt = anbieter || (mitSchluessel.length === 1 ? mitSchluessel[0].id : "");
  const gewaehltDaten = rollen?.anbieter.find(a => a.id === gewaehlt) ?? null;
  const anbieterName = (id: string) => rollen?.anbieter.find(a => a.id === id)?.wohin ?? rollen?.anbieter.find(a => a.id === id)?.label ?? id;

  async function ausschalten() {
    setWiderrufen(true); setArbeitet(true); setFehler(""); setFrage(false);
    setHinweis("Ausgeschaltet. Ab jetzt geht keine Frage mehr an die Cloud, auch nicht aus einer Antwort, die gerade läuft.");
    const version = loadVersion.current;
    try {
      // Beide Aufgaben zugleich: Der Widerruf soll nicht auf den ersten warten.
      const staende = await Promise.all(inCloud.map(aufgabe => api.saveModelRole(aufgabe.rolle, { cloud: false })));
      if (version !== loadVersion.current) return;
      if (staende.length) setRollen(staende[staende.length - 1]);
      setWiderrufen(false);
    } catch (e) {
      if (version === loadVersion.current) { setWiderrufen(false); setHinweis(""); setFehler(fehlerText(e)); }
    }
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
      setHinweis(`Fragen und Antworten laufen jetzt über ${anbieterName(gewaehlt)}. Mit einem Klick auf den Schalter ist das sofort wieder aus.`);
    } catch (e) { if (version === loadVersion.current) setFehler(fehlerText(e)); }
    finally { setArbeitet(false); }
  }

  function umschalten(neu: boolean) {
    setHinweis(""); setFehler("");
    if (!neu) { void ausschalten(); return; }
    setAnbieter(""); setZugestimmt(false); setFrage(true);
  }

  return <section className="darf-zeile" id="darf-cloud" aria-label={SCHALTER.cloud.titel}>
    {geladenFehler ? <p role="alert" className="settings-error">Der Stand konnte gerade nicht gelesen werden.</p> : !rollen ? <p>Wird geladen …</p> : aufgaben.length === 0 ? null : <>
      <Schalter className="welt-schalter" titel={SCHALTER.cloud.titel} satz={SCHALTER.cloud.verlaesst} an={an} deaktiviert={arbeitet} onWechsel={umschalten} />
      {an && <p className="source-hint" role="status">Fragen und Antworten laufen über {anbieterName(inCloud[0].wahl.anbieter)}.</p>}
      {frage && !an && mitSchluessel.length > 0 && <p className="source-hint cloud-wartet" role="status">{SCHALTER.cloud.wartet}</p>}
      {frage && !an && (mitSchluessel.length === 0
        ? <div className="darf-frage" role="group" aria-label="Cloud einschalten">
          <p>Dafür braucht es einen gespeicherten Zugang und ein Modell. Richte beides unter <a href="#ki">KI &amp; Modelle</a> ein. Bis dahin bleibt alles auf diesem Rechner.</p>
          <button type="button" className="secondary-action" onClick={() => setFrage(false)}>Verstanden</button>
        </div>
        : <div className="darf-frage" role="group" aria-label="Cloud einschalten">
          {mitSchluessel.length > 1 && <label>Anbieter
            <select value={gewaehlt} onChange={event => { setAnbieter(event.target.value); setZugestimmt(false); }}>
              <option value="">Bitte wählen</option>
              {mitSchluessel.map(a => <option key={a.id} value={a.id}>{a.label}</option>)}
            </select></label>}
          {gewaehltDaten ? <label className="model-consent"><input type="checkbox" checked={zugestimmt} onChange={event => setZugestimmt(event.target.checked)} />
            <span>{zustimmungCloud(gewaehltDaten)}</span></label>
            : <p className="source-hint">{zustimmungCloud(null)}</p>}
          <div className="darf-frage-knoepfe">
            <button type="button" className="primary-action" disabled={arbeitet || !gewaehlt || !zugestimmt} onClick={() => void einschalten()}>Cloud einschalten</button>
            <button type="button" className="secondary-action" onClick={() => setFrage(false)}>Abbrechen</button>
          </div>
        </div>)}
    </>}
    {hinweis && <p role="status" className="source-hint">{hinweis}</p>}
    {fehler && <p role="alert" className="settings-error">{fehler}</p>}
    {rollen && aufgaben.length > 0 ? <CloudProtokoll /> : null}
  </section>;
}
