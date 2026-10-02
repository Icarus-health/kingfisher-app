import { useEffect, useMemo, useState } from "react";
import { OrdnerImBrowser } from "./OrdnerImBrowser";
import { ordnerWeg } from "./ordnerWahl";
import { ProfileSource } from "./ProfileSource";

type FolderFile = { id: string; filename: string; state: string };
type FolderSyncState = {
  enabled: boolean;
  generation: number;
  root_id: string | null;
  folder: string | null;
  seen_at: string | null;
  synced_at: string | null;
  last_run: null | { recorded: number; duplicates: number; changed: number; removed: number; errors: string[] };
  files: FolderFile[];
  running: boolean;
  lokal?: boolean;
  helfer?: boolean;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...init,
    headers: { ...(init?.body ? { "content-type": "application/json" } : {}), ...init?.headers },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json() as Promise<T>;
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString("de-DE") : "Noch nicht ausgeführt";
}

function workerState(data: FolderSyncState) {
  // Im Browser gewählt: Kingfisher liest selbst; ein Helfer wird nicht gebraucht (Befund 6).
  if (data.lokal) return data.running ? "Kingfisher liest diesen Ordner etwa einmal pro Minute." : "Kingfisher hat den Ordner seit ein paar Minuten nicht gelesen.";
  if (!data.root_id && !data.helfer) return "Noch kein Ordner gewählt.";
  if (!data.root_id || !data.seen_at) return "Ordnerhelfer nicht verbunden";
  const seen = Date.parse(data.seen_at);
  if (!Number.isFinite(seen) || Date.now() - seen > 120_000) return "Ordnerhelfer derzeit nicht erreichbar";
  return "Ordnerhelfer verbunden";
}

export function FolderSyncSettings() {
  const [data, setData] = useState<FolderSyncState | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [satz, setSatz] = useState("");
  const [andererOrdner, setAndererOrdner] = useState(false);
  const load = async () => {
    setLoading(true); setError(false);
    try { setData(await request<FolderSyncState>("/api/v1/folder-sync")); } catch { setError(true); } finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (!expanded || busy) return;
    let active = true;
    const timer = window.setInterval(() => {
      void request<FolderSyncState>("/api/v1/folder-sync")
        .then(next => { if (active) { setData(next); setError(false); } })
        .catch(() => { if (active) setError(true); });
    }, 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, [expanded, busy]);
  const worker = useMemo(() => data ? workerState(data) : "", [data]);
  async function setEnabled(enabled: boolean) {
    if (busy) return;
    setBusy(true); setError(false);
    try { setData(await request<FolderSyncState>("/api/v1/folder-sync", { method: "PUT", body: JSON.stringify({ enabled }) })); }
    catch { setError(true); } finally { setBusy(false); }
  }
  async function run() {
    if (busy) return;
    setBusy(true); setError(false);
    try { await request("/api/v1/folder-sync/run", { method: "POST", body: "{}" }); await load(); }
    catch { setError(true); } finally { setBusy(false); }
  }
  return <details className="profile-card" onToggle={event => setExpanded(event.currentTarget.open)}>
    <summary>Dokumente automatisch aufnehmen</summary>
    <p>Lege Dokumente in diesen Ordner. Kingfisher prüft ihn einmal pro Minute und übernimmt Text, DOCX, PDF, SRT und VTT. Mitschriften aus Meetings gehören in den Ordner unter „Meetings“; dort werden sie einem Termin zugeordnet.</p>
    <p>Du kannst die Aufnahme jederzeit pausieren. Bisherige Belege bleiben erhalten; entfernte Dateien werden nach einer vollständigen Prüfung nicht mehr als aktuelles Wissen verwendet.</p>
    {loading ? <p role="status">Ordneraufnahme wird geladen …</p> : null}
    {data ? <>
      <p><strong>Ordner:</strong> {data.folder || "Noch kein Ordner ausgewählt"}</p>
      <p role="status"><strong>{worker}</strong></p>
      {ordnerWeg(data) === "browser" && (!data.root_id || andererOrdner)
        ? <OrdnerImBrowser prefix="/api/v1/folder-sync" beiGewaehlt={text => { setSatz(text); setAndererOrdner(false); void load(); }} /> : null}
      {ordnerWeg(data) === "browser" && data.root_id && !andererOrdner
        ? <button className="secondary-action" type="button" disabled={busy} onClick={() => setAndererOrdner(true)}>Anderen Ordner wählen …</button> : null}
      {satz ? <p role="status">{satz}</p> : null}
      <p>{data.synced_at ? `Letzter erfolgreicher Lauf: ${formatDate(data.synced_at)}` : "Noch kein erfolgreicher Lauf"}</p>
      {data.last_run ? <p>{data.last_run.recorded} aufgenommen · {data.last_run.duplicates} unverändert · {data.last_run.changed} geändert · {data.last_run.removed} entfernt</p> : null}
      {data.last_run?.errors.length ? <p role="alert">{data.last_run.errors.join(" ")}</p> : null}
      <button className="primary-action" type="button" disabled={busy || !data.root_id} onClick={() => void setEnabled(!data.enabled)}>{data.enabled ? "Ordneraufnahme pausieren" : "Ordneraufnahme aktivieren"}</button>
      <button className="secondary-action" type="button" disabled={busy || !data.enabled} onClick={() => void run()}>Jetzt prüfen</button>
      {data.files.length ? <section aria-label="Aufgenommene Dateien"><h3>Aufgenommene Dateien</h3>{data.files.map(file => <article className="identity-source-row" key={file.id}><strong>{file.filename}</strong><p>{file.state === "ignored" ? "Nicht mehr verwendet" : "Aufgenommen"}</p><ProfileSource kind="episode" id={file.id} /></article>)}</section> : <p>Noch keine Dateien aus diesem Ordner aufgenommen.</p>}
    </> : null}
    {error ? <p role="alert">Die Ordneraufnahme konnte nicht geladen oder geändert werden. <button type="button" disabled={busy} onClick={() => void load()}>Erneut versuchen</button></p> : null}
  </details>;
}
