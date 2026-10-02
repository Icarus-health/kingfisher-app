import {useCallback, useEffect, useRef, useState} from "react";
import { pruefRolleOhneModell } from "./pruefHinweis";
import { ausstattungSatz, type AusstattungQuelle } from "./system";
import {api, ApiError, type ModelPullState, type ModelRecommendation as Recommendation, type ModelRecommendationRow} from "./api";
import {ModelRolesExpert} from "./ModelRolesExpert";
import {actionLabel, allConfirmation, describePull, isRunning, orchesterZeile, pendingRoles, pullPercent, statusLabel, watchPull} from "./modelSetup";
import "./ModelRecommendation.css";

type Confirm = {kind: "one"; rolle: string} | {kind: "all"} | null;
type Run = {rolle: string; titel: string; state: ModelPullState | null};

const deviceLine = (data: Recommendation) => {
  const {chip, arbeitsspeicher_gb: gb, bekannt} = data.geraet;
  // Ohne Bericht eines Helfers misst Kingfisher selbst; im Container ist das eine Untergrenze (Befund 10). Derselbe Satz
  // wie unter „Gerät und lokale Modelle“ (Fremdprobe 2, Befund 27).
  const quelle = (data.geraet.quelle ?? (bekannt ? "bericht" : "unbekannt")) as AusstattungQuelle;
  return (bekannt || quelle !== "unbekannt" ? ausstattungSatz({ chip, gb, quelle }) : null)
    ?? "Die Ausstattung ließ sich nicht ermitteln. Es gilt eine kleine Vorauswahl, die auf jedem Rechner läuft.";
};

const failure = (error: unknown) => error instanceof ApiError && error.detail ? error.detail
  : "Kingfisher ist gerade nicht erreichbar. Bitte in einem Moment erneut versuchen.";

/** „Für diesen Rechner empfohlen“: je Aufgabe ein Modell, ein Klick richtet es ein. Vorauswahl, keine Messung. */
export function ModelRecommendation({beiFertig}: {beiFertig?: () => void} = {}) {
  const [data, setData] = useState<Recommendation | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [confirm, setConfirm] = useState<Confirm>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [note, setNote] = useState<{ok: boolean; text: string} | null>(null);
  const alive = useRef(true);

  const load = useCallback(async () => {
    try { const next = await api.modelRecommendation(); if (alive.current) { setData(next); setLoadError(false); } }
    catch { if (alive.current) setLoadError(true); }
  }, []);

  // Ein Ladevorgang, der schon läuft (etwa nach dem Neuladen der Seite), wird weiter angezeigt.
  useEffect(() => {
    alive.current = true;
    void load();
    api.currentModelPull().then(({aktuell}) => {
      if (aktuell && isRunning(aktuell) && alive.current) void follow(aktuell.rolle, aktuell);
    }).catch(() => undefined);
    return () => { alive.current = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  async function follow(rolle: string, first: ModelPullState): Promise<ModelPullState | null> {
    const titel = data?.rollen.find(row => row.rolle === rolle)?.titel ?? "Modell";
    setRun({rolle, titel, state: first});
    const last = await watchPull({read: () => api.modelPull(first.id), onState: state => setRun({rolle, titel, state}), isStopped: () => !alive.current});
    return last;
  }

  // Richtet die Rollen nacheinander ein und hält bei der ersten Fehlermeldung an; der Grund bleibt sichtbar.
  async function setUp(roles: string[]) {
    setConfirm(null); setNote(null);
    for (const rolle of roles) {
      const row = data?.rollen.find(item => item.rolle === rolle);
      try {
        const started = await api.startModelPull(rolle);
        const last = await follow(rolle, started);
        if (!alive.current) return;
        if (last === null) { setNote({ok: false, text: "Der Fortschritt ist gerade nicht abrufbar. Das Laden läuft weiter; öffne diese Seite später erneut."}); return; }
        if (last.phase === "fehler") return;
      } catch (error) {
        if (alive.current) { setRun(null); setNote({ok: false, text: `${row?.titel ?? "Modell"}: ${failure(error)}`}); }
        return;
      }
    }
    if (!alive.current) return;
    setRun(null);
    setNote({ok: true, text: roles.length === 1 ? "Eingerichtet und geprüft." : "Alles eingerichtet und geprüft."});
    await load();
    beiFertig?.();
  }

  const busy = run !== null && (run.state === null || isRunning(run.state));
  const rows = data?.rollen ?? [];
  const pending = pendingRoles(rows);
  const failed = run?.state?.phase === "fehler";
  const percent = run?.state ? pullPercent(run.state) : null;

  function ask(row: ModelRecommendationRow) {
    // Was schon installiert ist, wird nur übernommen; dazu braucht es keine Rückfrage.
    if (row.status === "installiert") void setUp([row.rolle]);
    else setConfirm({kind: "one", rolle: row.rolle});
  }

  return <section className="source-section model-recommendation" aria-label="Für diesen Rechner empfohlen">
    <div className="compact-integration-heading"><div><h2>Für diesen Rechner empfohlen</h2>
      <p>{data ? deviceLine(data) : loadError ? "Empfehlung gerade nicht erreichbar" : "Wird geladen …"}</p></div></div>
    {loadError && !data ? <p role="alert">Die Empfehlung konnte nicht geladen werden. <button className="secondary-action" type="button" onClick={() => void load()}>Erneut versuchen</button></p> : null}
    {data && !data.ollama.erreichbar ? <p className="source-hint" role="status">Ollama antwortet nicht. Starte Ollama auf diesem Rechner; danach kannst du hier einrichten.
      {" "}<button className="secondary-action" type="button" disabled={busy} onClick={() => void load()}>Erneut prüfen</button></p> : null}
    {data ? <ul className="model-rec-list">
      {rows.map(row => {
        const action = actionLabel(row.status);
        return <li key={row.rolle} className="model-rec-row">
          <div className="model-rec-text">
            <strong>{row.titel}</strong>
            <span className="model-rec-model">{row.empfohlen.name}</span>
            <p>{row.empfohlen.begruendung}</p>
            {row.orchester_hinweis ? <p>{row.orchester_hinweis}</p> : null}
            {pruefRolleOhneModell(row) ? <p>{pruefRolleOhneModell(row)}</p> : null}
            {!row.empfohlen.passt ? <p className="model-rec-warn">Dieses Modell passt vermutlich nicht in den Arbeitsspeicher.</p> : null}
            {row.blockiert ? <p className="model-rec-warn" role="status">{row.blockiert}</p> : null}
          </div>
          <span className={`model-rec-status is-${row.status}`}>{statusLabel(row.status)}</span>
          {action ? <button className="secondary-action" type="button" disabled={busy || !data.ollama.erreichbar}
            aria-label={`${row.titel}: ${action}`} onClick={() => ask(row)}>{action}</button> : <span className="model-rec-spacer" />}
          {confirm?.kind === "one" && confirm.rolle === row.rolle ? <div className="model-rec-confirm" role="group" aria-label="Bestätigung">
            <p>{row.empfohlen.bestaetigung}</p>
            <button className="primary-action" type="button" onClick={() => void setUp([row.rolle])}>Laden und einrichten</button>
            <button className="secondary-action" type="button" onClick={() => setConfirm(null)}>Abbrechen</button>
          </div> : null}
        </li>;
      })}
    </ul> : null}
    {data?.orchester ? <div className="model-rec-total" aria-label="Was alle Modelle zusammen brauchen">
      <p>{orchesterZeile(data.orchester)}</p>
      {data.orchester.hinweise.map(text => <p key={text} className="model-rec-warn" role="status">{text}</p>)}
    </div> : null}
    {data?.ollama.cloud_ueber_ollama?.length ? <p className="source-hint model-rec-meta" role="status">Läuft in Ollamas Cloud, nicht auf diesem Rechner: {data.ollama.cloud_ueber_ollama.join(", ")}. Die Anfragen gehen über Ollama an dessen Server in den USA. Diese Modelle werden hier nicht als lokale Vorauswahl angeboten.</p> : null}
    {data && pending.length > 1 && confirm?.kind !== "all" ? <div className="source-form-actions">
      <button className="primary-action" type="button" disabled={busy || !data.ollama.erreichbar} onClick={() => setConfirm({kind: "all"})}>Alles einrichten</button></div> : null}
    {data && confirm?.kind === "all" ? <div className="model-rec-confirm" role="group" aria-label="Bestätigung">
      <p>{allConfirmation(rows.filter(row => pending.includes(row.rolle)))}</p>
      <button className="primary-action" type="button" onClick={() => void setUp(pending)}>Laden und einrichten</button>
      <button className="secondary-action" type="button" onClick={() => setConfirm(null)}>Abbrechen</button>
    </div> : null}
    {run?.state ? <div className={`model-rec-progress${failed ? " is-failed" : ""}`} role={failed ? "alert" : "status"} aria-live="polite">
      <strong>{run.titel}</strong>
      {!failed && isRunning(run.state) ? <progress max={100} value={percent ?? undefined} aria-label={`Fortschritt ${run.titel}`} /> : null}
      <p>{describePull(run.state)}</p>
      {failed ? <button className="secondary-action" type="button" onClick={() => void setUp([run.rolle])}>Erneut versuchen</button> : null}
    </div> : null}
    {note ? <p className="model-rec-note" role={note.ok ? "status" : "alert"}>{note.text}</p> : null}
    {data ? <p className="source-hint">{data.hinweis} Stand der Empfehlungen: {new Date(data.stand).toLocaleDateString("de-DE")}. Es wird nichts ohne deine Bestätigung geladen, und es werden keine deiner Inhalte gesendet.</p> : null}
    {data ? <details className="model-rec-expert"><summary>Für Fortgeschrittene: Modell je Aufgabe wählen</summary>
      <ModelRolesExpert installed={data.ollama.installiert} rows={rows} onChanged={() => void load()} /></details> : null}
  </section>;
}
