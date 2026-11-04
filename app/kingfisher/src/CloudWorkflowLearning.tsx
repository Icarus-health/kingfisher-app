import { useEffect, useRef, useState } from "react";
import { ApiError, request, type MistralSourceBudget } from "./api";
import { budgetNotice, formatBudgetUsd } from "./cloud-budget";
import { listenForCloudAccessChange } from "./cloudAccessEvents";

type Area = "mail" | "planning" | "analysis";
type Job = {
  id: string; state: "running" | "complete" | "failed" | "cancelled" | "interrupted";
  result: { status?: string; proposal_id?: string; count?: number; reused?: boolean; synthesis?: { provider: "mistral"; model: string } } | null; message?: string;
};
type Status = {
  provider: "mistral"; model: string; available: boolean; budget: MistralSourceBudget;
  job: Job | null; candidates: Record<Area, number>;
};
type Preview = {
  preview_id: string; available: boolean; model: string; budget: MistralSourceBudget;
  payload: { corrections: Array<{ id: string; request: string; correction: string }>; existing: Record<string, unknown>[] };
  max_requests: number; expires_at: number;
};
const AREAS: Record<Area, string> = { mail: "E-Mails", planning: "Planung", analysis: "Analysen" };
const apiPath = "/api/v1/procedure-learning";
const failure = (error: unknown, fallback: string) => error instanceof ApiError && error.detail ? error.detail : fallback;
const sameBudget = (first: MistralSourceBudget, second: MistralSourceBudget) => first.budget_id === second.budget_id
  && first.revision === second.revision && first.price_id === second.price_id;

/** Preview is local; only the explicitly consented start may use the provider. */
export function CloudWorkflowLearning({ onProposed, refreshKey = 0 }: { onProposed: () => void; refreshKey?: number }) {
  const [opened, setOpened] = useState(false);
  const [area, setArea] = useState<Area>("mail");
  const [status, setStatus] = useState<Status | null>(null);
  const [verified, setVerified] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [consent, setConsent] = useState(false);
  const [expired, setExpired] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const mounted = useRef(false);
  const working = useRef(false);
  const readVersion = useRef(0);
  const previewVersion = useRef(0);
  const notified = useRef<string | null>(null);
  const notify = useRef(onProposed); notify.current = onProposed;

  function invalidatePreview() {
    previewVersion.current++;
    setPreview(null); setConsent(false); setExpired(false);
  }
  function observeJob(job: Job | null) {
    if (job?.state === "running") setOpened(true);
    if (job?.state === "complete") {
      const projection = `${job.id}:${job.result?.status}:${job.result?.proposal_id || ""}`;
      const withdrawn = job.result?.status === "changed" && notified.current?.startsWith(`${job.id}:`);
      if ((job.result?.proposal_id || withdrawn) && notified.current !== projection) {
        notified.current = projection;
        notify.current();
      }
    }
  }
  async function loadStatus() {
    if (working.current) return;
    const version = ++readVersion.current;
    try {
      const next = await request<Status>(`${apiPath}/status`);
      if (mounted.current && version === readVersion.current) {
        setStatus(next); setVerified(true); observeJob(next.job);
      }
    } catch {
      if (mounted.current && version === readVersion.current) {
        setVerified(false); setError("Der Arbeitsstand konnte nicht geladen werden. Bitte erneut laden.");
      }
    }
  }
  useEffect(() => {
    mounted.current = true;
    invalidatePreview();
    void loadStatus();
    const refresh = () => { invalidatePreview(); void loadStatus(); };
    const stop = listenForCloudAccessChange(refresh);
    window.addEventListener("focus", refresh);
    return () => { mounted.current = false; readVersion.current++; previewVersion.current++; stop(); window.removeEventListener("focus", refresh); };
  }, [refreshKey]);
  useEffect(() => {
    if (status?.job?.state !== "running") return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => { await loadStatus(); if (!cancelled) timer = setTimeout(poll, 2000); };
    timer = setTimeout(poll, 2000);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [status?.job?.id, status?.job?.state]);
  useEffect(() => {
    if (!preview) return;
    const timer = setTimeout(() => { setExpired(true); setConsent(false); }, Math.max(0, preview.expires_at * 1000 - Date.now()));
    return () => clearTimeout(timer);
  }, [preview]);

  async function action(work: () => Promise<void>) {
    if (working.current) return;
    working.current = true; readVersion.current++; setBusy(true); setError("");
    try { await work(); }
    catch (error) { if (mounted.current) setError(failure(error, "Die Prüfung konnte nicht bestätigt werden. Bitte den Arbeitsstand erneut laden.")); }
    finally {
      working.current = false;
      if (mounted.current) { setBusy(false); void loadStatus(); }
    }
  }
  function prepare() {
    if (working.current || status?.job?.state === "running") return;
    invalidatePreview();
    const version = previewVersion.current;
    void action(async () => {
      const next = await request<Preview>(`${apiPath}/preview`, { method: "POST", body: JSON.stringify({ area }) });
      if (mounted.current && version === previewVersion.current) {
        setPreview(next); setExpired(next.expires_at * 1000 <= Date.now());
      }
    });
  }
  const job = status?.job;
  const running = job?.state === "running";
  const budget = status?.budget;
  const current = Boolean(preview && budget && sameBudget(preview.budget, budget));
  const canStart = Boolean(verified && status?.available && budget?.ready && preview?.available && preview.budget.ready
    && current && preview.payload.corrections.length && consent && !expired && !busy && !running);
  function start() {
    if (!canStart || !preview || preview.expires_at * 1000 <= Date.now()) return;
    const previewId = preview.preview_id;
    // Consume local consent before sending: a timeout never silently retries a start.
    invalidatePreview();
    void action(async () => {
      const next = await request<{ job: Job }>(`${apiPath}/start`, { method: "POST", body: JSON.stringify({ preview_id: previewId, consent: true }) });
      if (mounted.current) { setStatus(value => value ? { ...value, job: next.job } : value); observeJob(next.job); }
    });
  }
  return <details className="quiet-details cloud-workflow-learning" open={opened} onToggle={event => {
    if (event.target === event.currentTarget) setOpened(event.currentTarget.open);
  }}>
    <summary>Mit Mistral prüfen (optional){running ? " · läuft" : ""}</summary>
    <p className="source-hint">Aus ausdrücklich markierten Arbeitskorrekturen einen Ablauf vorschlagen lassen. Vorschau und Auswahl bleiben lokal.</p>
    <div className="source-form"><label>Bereich für die Prüfung<select value={area} disabled={busy || running} onChange={event => { invalidatePreview(); setArea(event.target.value as Area); }}>
      {Object.entries(AREAS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
    </select></label></div>
    {status ? <p className="source-hint">{status.candidates[area] > 0 ? `${status.candidates[area]} passende Arbeitskorrekturen für eine neue Prüfung.` : "Aktuell keine passenden Arbeitskorrekturen für eine neue Prüfung."}</p> : <p role="status">Arbeitsstand wird gelesen …</p>}
    {budget ? <p className="source-hint">Quellen und Abläufe teilen ein Gesamtlimit: {formatBudgetUsd(budget.remaining_microusd, true)} verfügbar von {formatBudgetUsd(budget.cap_microusd)}.</p> : null}
    {budget && !budget.ready ? <p role="status">{budgetNotice(budget)}</p> : null}
    <p className="source-hint"><a href="/settings#ki">Mistral-Zugang und gemeinsames Kostenlimit verwalten</a></p>
    <button type="button" className="secondary-action" disabled={busy || running || !verified || !status?.candidates[area]} onClick={prepare}>Vorschau ansehen</button>
    {preview ? <div className="cloud-workflow-preview">
      <h4>Diese Daten würden übertragen</h4>
      <p className="source-hint">Noch nichts an Mistral gesendet. Keine vollständigen Mails, Antworten oder Anhänge werden ergänzt.</p>
      <ol>{preview.payload.corrections.map(item => <li key={item.id}>
        <p><strong>Auftrag:</strong> {item.request}</p><p><strong>Deine Korrektur:</strong> {item.correction}</p>
      </li>)}</ol>
      <details className="quiet-details"><summary>Mitgesendete Katalogangaben ({preview.payload.existing.length})</summary>
        {preview.payload.existing.length ? <pre>{JSON.stringify(preview.payload.existing, null, 2)}</pre> : <p>Keine vorhandenen Ablaufangaben.</p>}
      </details>
      <p className="source-hint">Mistral Small 4 · {preview.model} · höchstens {preview.max_requests} kostenpflichtige Aufrufe innerhalb desselben Gesamtlimits für Quellen und Abläufe.</p>
      <label className="cloud-workflow-consent"><input type="checkbox" checked={consent} disabled={busy || expired || !current} onChange={event => setConsent(event.target.checked)} />
        <span>Ich erlaube, die gezeigten Aufträge, Korrekturen und Katalogangaben einmalig an Mistral am EU/EFTA-Endpunkt zu senden und dafür höchstens {preview.max_requests} kostenpflichtige Aufrufe im gemeinsamen Kostenlimit zu verwenden.</span>
      </label>
      <p className="source-hint">Das Kostenlimit allein gibt keine Daten frei. Neue Vorschläge bleiben bis zu deiner Prüfung und Übernahme inaktiv.</p>
      {!preview.available || !status?.available ? <p role="status">Für den Start zuerst den Mistral-Zugang einrichten.</p> : null}
      {expired ? <p role="status">Die Vorschau ist abgelaufen. Bitte eine neue Vorschau ansehen.</p> : !current ? <p role="status">Der Kostenstand hat sich geändert. Bitte eine neue Vorschau ansehen.</p> : null}
      <button type="button" className="primary-action" disabled={!canStart} onClick={start}>Mit Mistral prüfen</button>
    </div> : null}
    {job ? <div className="cloud-workflow-progress" role="status" aria-live="polite">
      {running ? <><p>Prüfung läuft …</p><progress aria-label="Ablaufprüfung läuft" />
        <p className="source-hint">Abbrechen verhindert weitere Aufrufe und die Ergebnisübernahme. Bereits entstandene Kosten bleiben bestehen.</p>
        <button type="button" className="secondary-action" disabled={busy} onClick={() => void action(async () => {
          const next = await request<Status>(`${apiPath}/revoke`, { method: "POST", body: JSON.stringify({ job_id: job.id }) });
          if (mounted.current) { setStatus(next); setVerified(true); }
        })}>Prüfung abbrechen</button></>
        : job.state === "complete" ? job.result?.status === "changed" ? <p>Die Grundlage hat sich verändert. Der vorhandene Vorschlag ist nicht mehr verwendbar. Bitte die Korrekturen prüfen und eine neue Vorschau erstellen.</p>
          : job.result?.proposal_id ? <>
            {job.result.reused ? <p>Ein vorhandener Ablauf wurde wiedergefunden.</p> : null}
            <p>{job.result.status === "active" ? "Der zugehörige Ablauf ist übernommen und kann bei passenden Anfragen verwendet werden."
              : job.result.status === "dismissed" ? "Der zugehörige Ablauf wird nicht verwendet (nicht übernommen oder zurückgenommen)."
              : job.result.reused ? "Den aktuellen Stand und die Übernahme prüfst du in der Bibliothek."
              : "Ein Ablauf wurde als Vorschlag gespeichert. Den aktuellen Stand und die Übernahme prüfst du in der Bibliothek."}</p>
            {job.result.synthesis?.provider === "mistral" ? <p className="source-hint">Mit Mistral entworfen · lokal gespeichert.</p> : null}
          </>
          : job.result?.status === "no_pattern" ? <p>Kein neuer Ablaufvorschlag. Aus diesen Korrekturen wurde kein geeigneter neuer Ablauf abgeleitet.</p>
          : <p>Die Prüfung ist beendet. Bitte den aktuellen Stand in der Bibliothek prüfen.</p>
        : job.state === "cancelled" ? <p>Prüfung abgebrochen. Bereits entstandene Kosten bleiben bestehen.</p>
        : job.state === "interrupted" ? <p>Prüfung unterbrochen. Sie wird nicht automatisch erneut gestartet. Bitte den Kostenstand prüfen und bei Bedarf eine neue Vorschau erstellen.</p>
        : <p>{job.message || "Die Prüfung konnte nicht abgeschlossen werden. Bitte eine neue Vorschau erstellen."}</p>}
    </div> : null}
    {busy ? <p role="status">Arbeitsgang wird vorbereitet …</p> : null}
    {error ? <p role="alert">{error} <button type="button" className="g-knopf-schlicht" disabled={busy} onClick={() => { setError(""); void loadStatus(); }}>Stand erneut laden</button></p> : null}
  </details>;
}
