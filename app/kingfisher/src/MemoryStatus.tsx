import { useEffect, useRef, useState } from "react";
import { api, type MemoryAutomation, type MemoryCoverage, type MemoryTimeline } from "./api";
import { ProfileSource } from "./ProfileSource";
import { navigate } from "./ui";
import { FUNDE_SATZ, pruefSatz, sortiertGerade, sortierStand, sortierWirkung } from "./verarbeitung";
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

function WorkingMemoryProgress({progress, enabled, wartet}: {progress: NonNullable<MemoryCoverage["working_memory_progress"]>; enabled: boolean; wartet: boolean}) {
  const {total, done, remaining, retry, skipped, estimate_seconds: estimate} = progress;
  if (total === 0) return null;
  const status = remaining === 0 ? skipped ? "Das Sortieren ist abgeschlossen; einige Quellen konnten nicht sortiert werden." : "Alle Quellen sind sortiert."
    : wartet ? "Der Rest wird sortiert, sobald das Sprachmodell auf diesem Rechner bereit ist."
    : !enabled ? "Das automatische Sortieren ist pausiert. Der Rest wird sortiert, sobald es wieder läuft."
    : estimate ? `Noch etwa ${roughDuration(estimate)}, solange die App geöffnet ist.`
    : "Die Restzeit wird nach den ersten Durchgängen geschätzt.";
  return <div className="memory-progress">
    <p><strong>{done} von {total} Quellen automatisch sortiert.</strong> {FUNDE_SATZ}</p>
    <progress max={total} value={done + skipped} aria-label="Fortschritt des Sortierens">{Math.round((done + skipped) / total * 100)} %</progress>
    <p role="status">{status}</p>
    {retry || skipped ? <p className="memory-status-note">{retry ? `${retry} werden erneut versucht. ` : ""}{skipped ? `${skipped} lassen sich nicht sortieren (zu umfangreich, unvollständig oder von dir verworfen).` : ""}</p> : null}
  </div>;
}

export function MemoryStatus() {
  const today = new Date();
  const [month, setMonth] = useState(`${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`);
  const [coverage, setCoverage] = useState<MemoryCoverage | null>(null);
  const [automation, setAutomation] = useState<MemoryAutomation | null>(null);
  const [timeline, setTimeline] = useState<MemoryTimeline | null>(null);
  const [error, setError] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const generation = useRef(0);
  const loadingMore = useRef(false);
  const [paging, setPaging] = useState(false);
  const [pageError, setPageError] = useState(false);
  const [automationBusy, setAutomationBusy] = useState(false);
  const [automationError, setAutomationError] = useState("");
  useEffect(() => {
    generation.current += 1;
    loadingMore.current = false; setPaging(false); setPageError(false);
    let active = true;
    setError(false); setTimeline(null);
    const [year, m] = month.split("-").map(Number);
    if (!Number.isInteger(year) || year < 100 || year > 9999 || !m || m > 12) { setError(true); return; }
    const start = new Date(year, m - 1, 1).toISOString();
    const end = new Date(year, m, 1).toISOString();
    Promise.all([api.memoryCoverage(), api.memoryTimeline(start, end)])
      .then(([c, t]) => { if (active) { setCoverage(c); setTimeline(t); setAutomation(c.automation ?? null); } })
      .catch(() => { if (active) setError(true); });
    return () => { active = false; generation.current += 1; };
  }, [month, refresh]);

  async function older() {
    if (!timeline?.next_cursor || loadingMore.current) return;
    const current = generation.current;
    loadingMore.current = true; setPaging(true); setPageError(false);
    try {
      const next = await api.memoryTimeline(timeline.start, timeline.end, timeline.next_cursor);
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
          setCoverage(current);
          setAutomation(current.automation ?? null);
        } catch { /* Der Bestätigungsfehler bleibt sichtbar. */ }
        return;
      }
      setAutomation(next);
      // Zahlen und Restzeit gleich mit nachladen; der Stand oben gilt schon.
      api.memoryCoverage().then(current => setCoverage(current)).catch(() => undefined);
    } finally { setAutomationBusy(false); }
  }

  return <section className="memory-status" aria-label="Verarbeitung und Verlauf">
    <header><div><p className="eyebrow">GEDÄCHTNIS</p><h1>Verarbeitung & Verlauf</h1></div><button type="button" onClick={() => setRefresh(x => x + 1)}>Aktualisieren</button></header>
    {error ? <p role="alert">Der Gedächtnisstand konnte nicht geladen werden. Bitte erneut aktualisieren.</p> : !timeline || !coverage || !automation ? <p role="status">Gedächtnisstand wird geladen …</p> : <>
      <section className="memory-status-card"><h2>Was wurde geprüft?</h2>
        <p>{coverage.total_sources === 0 ? "Noch keine Nachrichten oder Dokumente aufgenommen." : `${coverage.total_sources} Nachrichten und Dokumente sind aufgenommen.`}</p>
        {/* Derselbe Stand wie „Automatisches Sortieren“ darunter, damit nach dem Klick nicht „pausiert“ neben „An“ steht (Befund 12). */}
        {coverage.working_memory_progress ? <WorkingMemoryProgress progress={coverage.working_memory_progress} enabled={sortiertGerade(automation)} wartet={automation.requested && !sortiertGerade(automation)} /> : null}
        <p className="memory-status-pruefung">{pruefSatz(coverage.counts)}</p>
        {coverage.truncated ? <p>Die Aufteilung zeigt die neuesten {coverage.sampled_sources} Quellen.</p> : null}
        <section aria-label="Automatisches Sortieren">
          <h3>Automatisches Sortieren</h3>
          <p>{sortierStand(automation)}</p>
          <p>{sortierWirkung(automation)}</p>
          {automationError ? <p role="alert">{automationError}</p> : null}
          <div className="memory-status-automation-actions">
            {automation.state === "legacy_active" ? <>
              <button type="button" disabled={automationBusy} onClick={() => void setAutomaticClassification(true)}>{automationBusy ? "Wird gespeichert …" : "Lokal absichern"}</button>
              <button type="button" disabled={automationBusy} onClick={() => void setAutomaticClassification(false)}>Automatik pausieren</button>
            </> : <button type="button" disabled={automationBusy || (!automation.requested && automation.state !== "paused")} onClick={() => void setAutomaticClassification(!automation.requested)}>{automationBusy ? "Wird gespeichert …" : automation.requested ? "Automatisches Sortieren pausieren" : "Automatisches Sortieren einschalten"}</button>}
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
      <section className="memory-status-card"><div className="memory-status-timeline-heading"><h2>Verlauf</h2><label>Monat <input aria-label="Monat im Gedächtnisverlauf" type="month" value={month} onChange={e => { if (e.target.value) setMonth(e.target.value); }} /></label></div>
        <p className="memory-status-note">Wann etwas aufgenommen oder entschieden wurde. Das Datum der Quelle kann älter sein.</p>
        {timeline.items.length ? <ol>{timeline.items.map(item => <li key={item.id}><small>{date(item.recorded_at)} · {labels[item.kind] ?? "Gedächtnisänderung"}</small><p>{item.title}</p>{item.occurred_at && new Date(item.occurred_at).getTime() !== new Date(item.recorded_at).getTime() ? <small>Bezug der Quelle/Aussage: {date(item.occurred_at)}</small> : null}{item.episode_id ? <ProfileSource kind="episode" id={item.episode_id} onChange={() => setRefresh(x => x + 1)} /> : null}</li>)}</ol> : <p>Auf dieser Seite sind keine zugänglichen Einträge erfasst.</p>}
        {pageError ? <p role="alert">Weitere Einträge konnten nicht geladen werden. Bitte erneut versuchen.</p> : null}
        {timeline.next_cursor ? <button type="button" disabled={paging} onClick={() => void older()}>{paging ? "Wird geladen …" : "Ältere Einträge anzeigen"}</button> : null}
        <p className="memory-status-note">Je Seite bis zu 100 Einträge. „Aktualisieren“ zeigt wieder die neuesten.</p>
      </section>
    </>}
  </section>;
}
