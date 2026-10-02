import "./MailFilterSettings.css";
import { useEffect, useRef, useState } from "react";

type Pending = { id: string; account_id: string; uid: string; sender: string; subject: string; preview: string; category: string; reason: string };
type FilterState = { ai_enabled: boolean; block_newsletters: boolean; allowed: string[]; blocked: string[]; revision: number; pending: Pending[] };
type ReviewBody = { subject: string; sender: string; body: string; truncated?: boolean };

const reasons: Record<string, string> = {
  content_incomplete: "Mailinhalt ist für die automatische KI-Prüfung zu lang oder unvollständig",
  spam_header: "Spam-Markierung im Mailkopf",
  newsletter: "Newsletter erkannt",
  blocked: "Absender steht auf der Sperrliste",
  ai_spam: "Lokale KI erkennt möglichen Spam",
  ai_newsletter: "Lokale KI erkennt einen Newsletter",
  ai_unclear: "Lokale KI konnte die Mail nicht sicher sortieren",
  ai_unavailable: "Lokale KI war nicht verfügbar",
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { credentials: "same-origin", ...init, headers: { ...(init?.body ? { "content-type": "application/json" } : {}), ...init?.headers } });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json() as Promise<T>;
}

function rules(values: string[]) { return values.join("\n"); }
function parseRules(value: string) { return [...new Set(value.split("\n").map(item => item.trim()).filter(Boolean))]; }

export function MailFilterSettings() {
  const [state, setState] = useState<FilterState | null>(null);
  const [allowed, setAllowed] = useState("");
  const [blocked, setBlocked] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [notice, setNotice] = useState("");
  const [revision, setRevision] = useState(0);
  const requestVersion = useRef(0);
  const initialized = useRef(false);
  const [inspection, setInspection] = useState<Record<string, ReviewBody>>({});
  const [inspectionOpen, setInspectionOpen] = useState<string | null>(null);
  const [inspectionBusy, setInspectionBusy] = useState<string | null>(null);
  const [inspectionError, setInspectionError] = useState<string | null>(null);
  async function load() {
    const version = ++requestVersion.current;
    setError(false);
    try {
      const next = await request<FilterState>("/api/v1/mail-filter");
      if (version !== requestVersion.current) return;
      setState(next);
      if (!initialized.current) { setAllowed(rules(next.allowed)); setBlocked(rules(next.blocked)); initialized.current = true; }
    } catch { if (version === requestVersion.current) setError(true); }
  }
  useEffect(() => { void load(); }, [revision]);
  async function save() {
    if (!state || busy) return;
    setBusy(true); setError(false); setNotice(""); const version = ++requestVersion.current;
    try { const next = await request<FilterState>("/api/v1/mail-filter", { method: "PUT", body: JSON.stringify({ ai_enabled: state.ai_enabled, block_newsletters: state.block_newsletters, allowed: parseRules(allowed), blocked: parseRules(blocked) }) }); if (version !== requestVersion.current) return; setState(next); setAllowed(rules(next.allowed)); setBlocked(rules(next.blocked)); initialized.current = true; setNotice("Mailfilter gespeichert."); }
    catch { setError(true); } finally { setBusy(false); }
  }
  async function toggle(field: "ai_enabled" | "block_newsletters") {
    if (!state || busy) return;
    setBusy(true); setError(false); setNotice(""); const version = ++requestVersion.current;
    try { const next = await request<FilterState>("/api/v1/mail-filter", { method: "PUT", body: JSON.stringify({ ai_enabled: field === "ai_enabled" ? !state.ai_enabled : state.ai_enabled, block_newsletters: field === "block_newsletters" ? !state.block_newsletters : state.block_newsletters, allowed: state.allowed, blocked: state.blocked }) }); if (version !== requestVersion.current) return; setState(next); }
    catch { setError(true); } finally { setBusy(false); }
  }
  async function review(id: string, action: "include" | "exclude") {
    if (busy) return;
    setBusy(true); setError(false); const version = ++requestVersion.current;
    try { const next = await request<FilterState>(`/api/v1/mail-filter/review/${encodeURIComponent(id)}`, { method: "POST", body: JSON.stringify({ action }) }); if (version !== requestVersion.current) return; setState(next); }
    catch { setError(true); } finally { setBusy(false); }
  }
  async function inspect(id: string) {
    if (inspectionBusy === id) return;
    if (inspection[id]) { setInspectionOpen(open => open === id ? null : id); return; }
    setInspectionOpen(id); setInspectionBusy(id); setInspectionError(null);
    try { const body = await request<ReviewBody>(`/api/v1/mail-filter/review/${encodeURIComponent(id)}`); setInspection(current => ({ ...current, [id]: body })); }
    catch { setInspectionError(id); }
    finally { setInspectionBusy(null); }
  }
  return <section className="source-section mail-filter-settings" aria-label="Mailfilter">
    <details><summary>Mailfilter für automatische Quellenaufnahme</summary>
      <p>Der Filter gilt nur für die automatische Aufnahme. Dein normaler Posteingang zeigt weiterhin alle Mails; bestehende Quellen bleiben unverändert.</p>
      {!state && !error ? <p role="status">Mailfilter wird geladen …</p> : null}
      {state ? <>
        <label className="mail-sync-check"><input type="checkbox" disabled={busy} checked={state.block_newsletters} onChange={() => void toggle("block_newsletters")} />Newsletter automatisch zurückhalten</label>
        <label className="mail-sync-check"><input type="checkbox" disabled={busy} checked={state.ai_enabled} onChange={() => void toggle("ai_enabled")} />Optionale lokale KI-Unterstützung einschalten</label>
        <p>Die lokale KI ist standardmäßig aus. Unsichere oder lange Mails bleiben zur Prüfung liegen. Es gibt keinen Cloud-Fallback.</p>
        <label className="mail-filter-rule">Erlaubte Absender (E-Mail oder @Domain, eine Regel pro Zeile)<textarea disabled={busy} value={allowed} onChange={event => setAllowed(event.target.value)} /></label>
        <label className="mail-filter-rule">Gesperrte Absender (E-Mail oder @Domain, eine Regel pro Zeile)<textarea disabled={busy} value={blocked} onChange={event => setBlocked(event.target.value)} /></label>
        <button className="secondary-action" type="button" disabled={busy} onClick={() => void save()}>Filter speichern</button>
        {state.pending.length ? <section aria-label="Zur Prüfung zurückgehaltene Mails"><h3>Zur Prüfung zurückgehalten ({state.pending.length}/500)</h3><p>Bei 500 offenen Mails pausiert die Aufnahme bis zur nächsten Prüfung.</p>{state.pending.map(item => <article className="identity-source-row" key={item.id}><strong>{item.sender}</strong><p>{item.subject}</p><p>{item.preview}</p><p>{reasons[item.reason] ?? "Automatische Filterung"}</p><button className="secondary-action" type="button" disabled={busy || inspectionBusy === item.id} onClick={() => void inspect(item.id)}>{inspectionOpen === item.id ? "Mailinhalt ausblenden" : "Mailinhalt anzeigen"}</button>{inspectionBusy === item.id ? <p role="status">Mailinhalt wird geladen …</p> : null}{inspectionError === item.id ? <p role="alert">Der Mailinhalt konnte nicht geladen werden. <button type="button" onClick={() => void inspect(item.id)}>Erneut versuchen</button></p> : null}{inspectionOpen === item.id && inspection[item.id] ? <section aria-label="Mailinhalt"><p><strong>{inspection[item.id].sender}</strong></p><p>{inspection[item.id].subject}</p><div className="mail-filter-body">{inspection[item.id].body}</div>{inspection[item.id].truncated ? <p role="status">Der angezeigte Mailinhalt wurde aus Sicherheitsgründen begrenzt.</p> : null}</section> : null}<button className="primary-action" type="button" disabled={busy} onClick={() => void review(item.id, "include")}>Als Quelle aufnehmen</button><button className="secondary-action" type="button" disabled={busy} onClick={() => void review(item.id, "exclude")}>Nicht aufnehmen</button></article>)}</section> : <p>Keine zurückgehaltenen Mails.</p>}
      </> : null}
      <button className="text-action" type="button" disabled={busy} onClick={() => void load()}>Prüfbereich aktualisieren</button>
      {notice ? <p role="status">{notice}</p> : null}
      {error ? <p role="alert">Der Mailfilter konnte nicht geladen oder gespeichert werden. <button type="button" disabled={busy} onClick={() => setRevision(value => value + 1)}>Erneut versuchen</button></p> : null}
    </details>
  </section>;
}
