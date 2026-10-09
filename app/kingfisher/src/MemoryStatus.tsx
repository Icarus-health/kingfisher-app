import { useEffect, useRef, useState } from "react";
import { api, type MemoryAutomation, type MemoryCoverage, type MemoryTimeline } from "./api";
import { ProfileSource } from "./ProfileSource";
import { navigate } from "./ui";
import { FUNDE_SATZ, pruefSatz, sortiertGerade, sortierStand, sortierWirkung } from "./verarbeitung";
import { newestSourceMonth, timelineDateValues, type TimelineBasis } from "./memoryStatusDates";
import "./MemoryStatus.css";

const labels: Record<string, string> = {source_received: "Quelle aufgenommen", accepted: "Aussage bestätigt", superseded: "Stand ersetzt", retracted: "Aussage widerrufen", disputed: "Grundlage entzogen"};
const date = (value: string) => new Date(value).toLocaleString("de-DE", {dateStyle: "medium", timeStyle: "short"});

// Restzeit in Worten, grob gerundet: Eine Minute Genauigkeit wäre vorgetäuscht.
export function roughDuration(seconds: number): string {
  if (seconds < 90) return "weniger als zwei Minuten";
  const minutes = Math.round(seconds / 60);
  if (minutes < 90) return `${Math.max(2, Math.round(minutes / 5) * 5 || minutes)} Minuten`;
  const hours = seconds / 3600;
  if (hours < 36) return `${Math.round(hours)} Stunden`;
  return `${Math.round(hours / 24)} Tage`;
}

function WorkingMemoryProgress({progress, enabled, wartet, stale = false, pauseReason}: {progress: NonNullable<MemoryCoverage["working_memory_progress"]>; enabled: boolean; wartet: boolean; stale?: boolean; pauseReason?: string | null}) {
  const {total, done, remaining, retry, skipped, estimate_seconds: estimate} = progress;
  if (total === 0) return null;
  const status = stale ? "Der aktuelle Fortschritt ist nicht erreichbar. Die Zahlen zeigen den letzten bekannten Stand."
    : remaining === 0 ? skipped ? "Das Sortieren ist abgeschlossen; einige Quellen konnten nicht sortiert werden." : "Alle Quellen sind sortiert."
    : pauseReason && enabled ? pauseReason
    : wartet ? "Der Rest wird sortiert, sobald das Sprachmodell auf diesem Rechner bereit ist."
    : !enabled ? "Das automatische Sortieren ist pausiert. Der Rest wird sortiert, sobald es wieder läuft."
    : estimate ? `Noch etwa ${roughDuration(estimate)}, solange die App geöffnet ist.`
    : "Die Restzeit wird nach den ersten Durchgängen geschätzt.";
  return <div className="memory-progress">
    <p><strong>{done} von {total} Quellen {stale ? "beim letzten Abruf sortiert" : "automatisch sortiert"}.</strong> {FUNDE_SATZ}</p>
    <progress max={total} value={done + skipped} aria-label={stale ? "Letzter bekannter Fortschritt des Sortierens" : "Fortschritt des Sortierens"}>{Math.round((done + skipped) / total * 100)} %</progress>
    <p role="status">{status}</p>
    {retry || skipped ? <p className="memory-status-note">{retry ? stale || pauseReason ? `${retry} erneute Versuche vorgemerkt. ` : `${retry} werden erneut versucht. ` : ""}{skipped ? `${skipped} lassen sich nicht sortieren (zu umfangreich, unvollständig oder von dir verworfen).` : ""}</p> : null}
  </div>;
}

export function SemanticMemoryProgress({progress, stale = false}: {progress: NonNullable<MemoryCoverage["semantic_index"]>; stale?: boolean}) {
  const {status, total, indexed, pending, failed, source_pending: sources, pause_reason: paused} = progress;
  const knownCounts = total !== null && indexed !== null;
  const model = (progress.model_name || progress.model_key)?.replace(/:[a-f0-9]{64}$/i, "").replace(/[@|].*$/, "").trim();
  const complete = !stale && status === "indexed" && knownCounts && total > 0 && indexed === total && pending === 0 && failed === 0 && sources === 0 && !paused;
  const explanation = stale ? "Der aktuelle Stand ist gerade nicht erreichbar. Die Zahlen zeigen den letzten bekannten Stand."
    : status === "disabled" ? "Die Bedeutungssuche ist ausgeschaltet."
    : paused ? paused
    : status === "unavailable" ? progress.identity_checked_at === null ? "Das lokale Suchmodell und der Suchindex wurden noch nicht geprüft. Der Stand wird automatisch erneut geprüft." : "Die Bedeutungssuche ist gerade nicht bereit. Der Stand wird automatisch erneut geprüft."
    : complete ? "Die bisher sortierten Abschnitte sind für die Bedeutungssuche vorbereitet."
    : total === 0 ? "Sobald sortierte Abschnitte vorliegen, werden sie für die Bedeutungssuche vorbereitet."
    : pending ? "Weitere Abschnitte werden im Hintergrund vorbereitet."
    : sources && knownCounts && indexed === total && failed === 0 ? "Die bisher sortierten Abschnitte sind vorbereitet. Weitere Quellen werden noch sortiert."
    : "Der Vorbereitungsstand wird automatisch erneut geprüft.";
  return <section className="memory-progress memory-semantic-progress" aria-label="Vorbereitung der Bedeutungssuche">
    <h3>Für Bedeutungssuche vorbereitet</h3>
    <p><strong>{knownCounts ? `${indexed} von ${total} ${total === 1 ? "Abschnitt" : "Abschnitten"}` : "Abschnittszahl noch nicht verfügbar"}</strong>{stale ? " · letzter bekannter Stand" : ""}</p>
    {knownCounts && total > 0 && status !== "disabled" ? <progress max={total} value={indexed} aria-label={stale ? "Letzter bekannter Fortschritt der Bedeutungssuche" : "Fortschritt der Vorbereitung zur Bedeutungssuche"}>{Math.round(indexed / total * 100)} %</progress> : null}
    <p role="status">{explanation}</p>
    {status !== "disabled" ? <>
      {pending !== null && pending > 0 ? <p className="memory-status-note">{pending} Abschnitte stehen noch aus.{failed ? ` Bei ${failed} Abschnitten ist ein Versuch fehlgeschlagen; sie werden erneut versucht.` : ""}</p>
        : failed !== null && failed > 0 ? <p className="memory-status-note">Bei {failed} Abschnitten ist ein Versuch fehlgeschlagen; sie werden erneut versucht.</p> : null}
      {sources !== null && sources > 0 ? <p className="memory-status-note">{sources} {sources === 1 ? "Quelle wird" : "Quellen werden"} noch sortiert; daraus können weitere Abschnitte entstehen.</p> : null}
    </> : null}
    <p className="memory-status-note">Die Bedeutungssuche findet auch inhaltlich ähnliche Stellen. Das Sortieren der Quellen ist ein eigener Schritt.{model ? ` Suchmodell: ${model}.` : ""}</p>
    {progress.updated_at !== null ? <p className="memory-status-note">Vorbereitungsstand vom {date(new Date(progress.updated_at * 1000).toISOString())}.</p> : null}
  </section>;
}

export function MemoryStatus() {
  const today = new Date();
  const [month, setMonth] = useState(`${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`);
  const [basis, setBasis] = useState<TimelineBasis>("source");
  const [coverage, setCoverage] = useState<MemoryCoverage | null>(null);
  const [automation, setAutomation] = useState<MemoryAutomation | null>(null);
  const [timeline, setTimeline] = useState<MemoryTimeline | null>(null);
  const [coverageError, setCoverageError] = useState(false);
  const [coverageRefreshError, setCoverageRefreshError] = useState(false);
  const [timelineError, setTimelineError] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const generation = useRef(0);
  const loadingMore = useRef(false);
  const [paging, setPaging] = useState(false);
  const [pageError, setPageError] = useState(false);
  const [automationBusy, setAutomationBusy] = useState(false);
  const [automationError, setAutomationError] = useState("");
  const latestSourceMonth = newestSourceMonth(coverage?.source_dates?.latest);
  const undatedSources = coverage?.source_dates?.undated ?? 0;
  function adoptCoverage(current: MemoryCoverage) {
    setCoverage(current);
    setAutomation(current.automation ?? null);
    setCoverageError(false);
    setCoverageRefreshError(false);
  }
  useEffect(() => {
    let active = true;
    let inFlight = false;
    const loadCoverage = async () => {
      if (!active || document.visibilityState !== "visible" || inFlight) return;
      inFlight = true;
      try {
        const current = await api.memoryCoverage();
        if (active) {
          adoptCoverage(current);
        }
      } catch {
        if (active) {
          setCoverageError(true);
          setCoverageRefreshError(true);
        }
      } finally { inFlight = false; }
    };
    const onVisibilityChange = () => { if (document.visibilityState === "visible") void loadCoverage(); };
    void loadCoverage();
    const interval = window.setInterval(() => void loadCoverage(), 15000);
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      active = false;
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [refresh]);

  useEffect(() => {
    generation.current += 1;
    loadingMore.current = false; setPaging(false); setPageError(false);
    let active = true;
    setTimelineError(false); setTimeline(null);
    const [year, m] = month.split("-").map(Number);
    if (!Number.isInteger(year) || year < 100 || year > 9999 || !m || m > 12) { setTimelineError(true); return; }
    const start = new Date(year, m - 1, 1).toISOString();
    const end = new Date(year, m, 1).toISOString();
    api.memoryTimeline(start, end, undefined, basis)
      .then(result => { if (active) setTimeline(result); })
      .catch(() => { if (active) setTimelineError(true); });
    return () => { active = false; generation.current += 1; };
  }, [month, basis, refresh]);

  async function older() {
    if (!timeline?.next_cursor || loadingMore.current) return;
    const current = generation.current;
    loadingMore.current = true; setPaging(true); setPageError(false);
    try {
      const next = await api.memoryTimeline(timeline.start, timeline.end, timeline.next_cursor, basis);
      if (current === generation.current) setTimeline(next);
    } catch {
      if (current === generation.current) setPageError(true);
    } finally {
      if (current === generation.current) { loadingMore.current = false; setPaging(false); }
    }
  }

  async function setAutomaticClassification(enabled: boolean) {
    if (automationBusy) return;
    setAutomationBusy(true); setAutomationError("");
    try {
      let next: MemoryAutomation;
      try {
        next = await api.setMemoryAutomation(enabled);
      } catch {
        setAutomationError("Die Änderung konnte nicht bestätigt werden. Bitte aktualisiere den Stand, bevor du es erneut versuchst.");
        try {
          const current = await api.memoryCoverage();
          adoptCoverage(current);
        } catch { setCoverageRefreshError(true); }
        return;
      }
      setAutomation(next);
      // Zahlen und Restzeit gleich mit nachladen; der Stand oben gilt schon.
      api.memoryCoverage().then(adoptCoverage).catch(() => setCoverageRefreshError(true));
    } finally { setAutomationBusy(false); }
  }

  return <section className="memory-status" aria-label="Verarbeitung und Verlauf">
    <header><div><p className="eyebrow">GEDÄCHTNIS</p><h1>Verarbeitung & Verlauf</h1></div><button type="button" onClick={() => setRefresh(x => x + 1)}>Aktualisieren</button></header>
    {coverageError && !coverage ? <p role="alert">Der Gedächtnisstand konnte nicht geladen werden. Bitte erneut aktualisieren.</p> : !coverage || !automation ? <p role="status">Gedächtnisstand wird geladen …</p> : <>
      <section className="memory-status-card"><h2>Was wurde geprüft?</h2>
        <p>{coverage.total_sources === 0 ? "Noch keine Nachrichten oder Dokumente aufgenommen." : `${coverage.total_sources} Nachrichten und Dokumente sind aufgenommen.`}</p>
        {/* Derselbe Stand wie „Automatisches Sortieren“ darunter, damit nach dem Klick nicht „pausiert“ neben „An“ steht (Befund 12). */}
        {coverage.working_memory_progress ? <WorkingMemoryProgress progress={coverage.working_memory_progress} enabled={automation.requested || automation.state === "active" || automation.state === "legacy_active"} wartet={automation.requested && !sortiertGerade(automation)} stale={coverageRefreshError} pauseReason={automation.execution_pause_reason} /> : null}
        {coverage.semantic_index ? <SemanticMemoryProgress progress={coverage.semantic_index} stale={coverageRefreshError} /> : null}
        <p className="memory-status-pruefung">{coverageRefreshError ? "Die Prüfzahlen stammen aus dem letzten Abruf; der aktuelle Prüfstand ist nicht bestätigt." : pruefSatz(coverage.counts, sortiertGerade(automation))}</p>
        {coverage.truncated ? <p>Die Aufteilung zeigt die neuesten {coverage.sampled_sources} Quellen.</p> : null}
        {coverageRefreshError ? <p className="memory-status-error" role="status">Der Fortschritt konnte gerade nicht aktualisiert werden. Angezeigt wird der letzte bekannte Stand.</p> : null}
        <section aria-label="Automatisches Sortieren">
          <h3>Automatisches Sortieren</h3>
          <p>{coverageRefreshError ? "Der aktuelle Automatikstand konnte nicht geprüft werden. Bitte aktualisiere den Stand." : sortierStand(automation)}</p>
          <p>{coverageRefreshError ? "Beim Sortieren entstehen Vorschläge mit Quellen. Die aktuelle Freigabe und der Fortschritt sind gerade nicht bestätigt." : sortierWirkung(automation)}</p>
          {automationError ? <p role="alert">{automationError}</p> : null}
          <div className="memory-status-automation-actions">
            {automation.state === "legacy_active" ? <>
              <button type="button" disabled={automationBusy || coverageRefreshError} onClick={() => void setAutomaticClassification(true)}>{automationBusy ? "Wird gespeichert …" : "Lokal absichern"}</button>
              <button type="button" disabled={automationBusy || coverageRefreshError} onClick={() => void setAutomaticClassification(false)}>Automatik pausieren</button>
            </> : <button type="button" disabled={automationBusy || coverageRefreshError || (!automation.requested && automation.state !== "paused")} onClick={() => void setAutomaticClassification(!automation.requested)}>{automationBusy ? "Wird gespeichert …" : automation.requested ? "Automatisches Sortieren pausieren" : "Automatisches Sortieren einschalten"}</button>}
            {automation.state === "model_missing" || automation.state === "wrong_model" || automation.state === "cloud_ueber_ollama" || automation.state === "local_model_unavailable" ? <button type="button" onClick={() => navigate("/settings#technik-modelle")}>Lokales Modell prüfen</button> : null}
          </div>
        </section>
        <details><summary>Was bedeutet dieser Stand?</summary><p>{coverage.scope}</p><p>{coverage.detail}</p><p>Erkannte Aufgaben bleiben Vorschläge, bis du sie übernimmst.</p></details>
        {/* Die Zahlen je Prüfstand und das Modell nur für Techniker (Fremdprobe 2, Befund 16). */}
        <details className="memory-status-technik"><summary>Für Techniker</summary>
          {automation.model ? <p>Modell für das Sortieren: {automation.model}</p> : null}
          <p>Ein separat eingeschalteter Mailfilter bleibt vom Sortieren unabhängig.</p>
          <dl>{([["completed", "Prüflauf durchgeführt"], ["pending", "Noch zu prüfen"], ["partial", "Teilweise geprüft"], ["running", "In Bearbeitung"], ["failed", "Prüfung fehlgeschlagen"], ["excluded", "Von der Prüfung ausgeschlossen"]] as const).map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{coverage.counts[key]}</dd></div>)}</dl>
        </details>
      </section>
      <section className="memory-status-card"><div className="memory-status-timeline-heading"><h2>{basis === "source" ? "Quellengeschichte" : "Änderungen am Gedächtnis"}</h2><label>Monat <input aria-label="Monat im Gedächtnisverlauf" type="month" value={month} onChange={e => { if (e.target.value) setMonth(e.target.value); }} /></label></div>
        <div className="memory-status-timeline-controls" role="group" aria-label="Zeitachse auswählen">
          <button type="button" aria-pressed={basis === "source"} onClick={() => setBasis("source")}>Quellengeschichte</button>
          <button type="button" aria-pressed={basis === "recorded"} onClick={() => setBasis("recorded")}>Änderungen am Gedächtnis</button>
          {basis === "source" && latestSourceMonth && month !== latestSourceMonth
            ? <button type="button" onClick={() => setMonth(latestSourceMonth)}>Zum neuesten Quellmonat ({latestSourceMonth})</button>
            : null}
        </div>
        {basis === "source" ? <>
          <p className="memory-status-note">Hier stehen Originalquellen nach ihrem Quelldatum. Die Erfassungszeit bleibt separat sichtbar.</p>
          {undatedSources > 0 ? <p className="memory-status-note">{undatedSources} {undatedSources === 1 ? "Quelle hat kein verlässliches Quelldatum und erscheint deshalb" : "Quellen haben kein verlässliches Quelldatum und erscheinen deshalb"} in keinem Quellmonat. Das Erfassungsdatum wird nicht als Quelldatum eingesetzt.</p> : null}
        </> : <p className="memory-status-note">Wann Aussagen bestätigt, ersetzt oder widerrufen wurden. Das Datum der Quelle steht darunter, wenn es bekannt ist.</p>}
        {timelineError ? <p role="alert">Die Zeitachse konnte nicht geladen werden. Bitte erneut aktualisieren.</p> : !timeline || timeline.basis !== basis ? <p role="status">Zeitachse wird geladen …</p> : timeline.items.length ? <ol>{timeline.items.map(item => {
          const dates = timelineDateValues(item, basis);
          const mainDate = dates.main ? date(dates.main) : "Quelldatum unbekannt";
          return <li key={item.id}>
            <small>{basis === "source" ? `Quelle vom ${mainDate}` : `${date(item.recorded_at)} · ${labels[item.kind] ?? "Gedächtnisänderung"}`}</small>
            <p>{item.title}</p>
            {basis === "source" ? <small>Erfasst am {date(item.recorded_at)}</small>
              : dates.secondary && new Date(dates.secondary).getTime() !== new Date(dates.main ?? "").getTime() ? <small>Quelldatum: {date(dates.secondary)}</small> : null}
            {item.episode_id ? <ProfileSource kind="episode" id={item.episode_id} onChange={() => setRefresh(x => x + 1)} /> : null}
          </li>;
        })}</ol> : <p>Für diesen Monat gibt es keine zugänglichen Einträge.</p>}
        {pageError ? <p role="alert">Weitere Einträge konnten nicht geladen werden. Bitte erneut versuchen.</p> : null}
        {timeline?.basis === basis && timeline.next_cursor ? <button type="button" disabled={paging} onClick={() => void older()}>{paging ? "Wird geladen …" : "Ältere Einträge anzeigen"}</button> : null}
        <p className="memory-status-note">Je Seite bis zu 100 Einträge. „Aktualisieren“ zeigt wieder die neuesten.</p>
      </section>
    </>}
  </section>;
}
