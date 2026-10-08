import { FormEvent, useEffect, useState } from "react";
import { ProfileSource } from "./ProfileSource";

type Goal = { id: string; statement: string };
export type WorldSource = {
  id: string; url: string; label: string; topics: string[]; enabled: boolean;
  episode_id: string | null; last_success: string | null; error: string | null;
  fetched_url?: string | null; source_sha256?: string | null;
  truncated: boolean; status: string; matched_goals?: Goal[];
};
type WorldPayload = { items: WorldSource[] };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "same-origin", ...init,
    headers: { ...(init?.body ? { "content-type": "application/json" } : {}), ...init?.headers },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json() as Promise<T>;
}

function sourceStatus(source: WorldSource) {
  return ({disabled: "Deaktiviert", stale: "Veraltet – bitte aktualisieren", ignored: "Ausgeschlossen", pending: "Noch nicht abgerufen", ok: "Innerhalb der letzten 24 Stunden abgerufen"} as Record<string, string>)[source.status] || "Status unbekannt";
}

function freshness(value: string | null) {
  return value ? `Abgerufen ${new Date(value).toLocaleString("de-DE")}` : "Noch nicht abgerufen";
}

export function WorldControls({ initiallyOpen = false }: { initiallyOpen?: boolean }) {
  const [payload, setPayload] = useState<WorldPayload | null>(null);
  const [label, setLabel] = useState("");
  const [url, setUrl] = useState("");
  const [topics, setTopics] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [open, setOpen] = useState(initiallyOpen);
  const load = async () => {
    setError(false);
    try { setPayload(await request<WorldPayload>("/api/v1/world")); } catch { setError(true); }
  };
  useEffect(() => { void load(); }, []);
  async function add(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (!url.trim().toLowerCase().startsWith("https://")) { setError(true); return; }
    setBusy(true); setError(false);
    try {
      await request<WorldSource>("/api/v1/world", { method: "POST", body: JSON.stringify({
        url: url.trim(), label: label.trim(), topics: topics.split(",").map(item => item.trim()).filter(Boolean),
      }) });
      setLabel(""); setUrl(""); setTopics(""); await load();
    } catch { setError(true); } finally { setBusy(false); }
  }
  async function mutate(source: WorldSource, action: "refresh" | "disable") {
    if (busy) return;
    setBusy(true); setError(false);
    try { await request(`/api/v1/world/${encodeURIComponent(source.id)}/${action}`, { method: "POST" }); await load(); }
    catch { setError(true); } finally { setBusy(false); }
  }
  return <details className="profile-card" open={open} onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>Aktuelle Quellen</summary>
    <p>Du wählst öffentliche Quellen aus. Automatische Abrufe laufen nur mit aktiviertem Zeitplan, solange Kingfisher läuft. Ohne Zeitplan kannst du hier manuell abrufen.</p><p>Der Abrufzeitpunkt zeigt, wann Kingfisher die Seite gelesen hat. Ein Veröffentlichungsdatum wird nicht übernommen; angezeigt wird ausschließlich der Abrufzeitpunkt. Der Auszug bleibt ein Quellenbericht und bestätigt keine persönliche Angabe.</p>
    <form className="decision-create-form" onSubmit={add} aria-label="Öffentliche Quelle hinzufügen">
      <label>Bezeichnung<input value={label} onChange={event => setLabel(event.target.value)} required maxLength={200} /></label>
      <label>HTTPS-Adresse<input type="url" value={url} onChange={event => setUrl(event.target.value)} placeholder="https://…" required /></label>
      <label>Themen, getrennt durch Komma<input value={topics} onChange={event => setTopics(event.target.value)} /></label>
      <button className="primary-action" disabled={busy} type="submit">Quelle hinzufügen</button>
    </form>
    {!payload && !error ? <p role="status">Quellen werden geladen …</p> : null}
    {payload?.items.length === 0 ? <p>Noch keine von dir ausgewählten Quellen.</p> : null}
    {payload?.items.map(source => <article className="identity-source-row" key={source.id}>
      <h3>{source.label}</h3>
      <p>{freshness(source.last_success)} · {sourceStatus(source)}</p>
      <a href={source.url} target="_blank" rel="noopener noreferrer">Eingetragene Adresse öffnen</a>
      {source.fetched_url || source.source_sha256 ? <details style={{overflowWrap: "anywhere"}}><summary>Herkunft und Version des Auszugs</summary>
        {source.fetched_url && source.fetched_url !== source.url ? <p>Endgültige Abrufadresse: <a href={source.fetched_url} target="_blank" rel="noopener noreferrer">{source.fetched_url}</a></p> : null}
        {source.source_sha256 ? <p>Textversion (SHA-256): <code>{source.source_sha256}</code></p> : null}
      </details> : null}
      {source.matched_goals?.length ? <p>Themenüberschneidung mit einem Ziel (nur ein Hinweis): {source.matched_goals.map(goal => goal.statement).join(", ")}</p> : <p>Von dir ausgewählte öffentliche Quelle</p>}
      {source.truncated && <p>Gespeicherter Auszug: maximal 12.000 Zeichen.</p>}{source.episode_id ? <ProfileSource kind="episode" id={source.episode_id} allowIgnore={false} /> : null}
      {source.error ? <p role="alert">Die Quelle konnte nicht aktualisiert werden. <button type="button" disabled={busy} onClick={() => void mutate(source, "refresh")}>Erneut versuchen</button></p> : null}
      {source.enabled ? <><button className="secondary-action" type="button" disabled={busy} onClick={() => void mutate(source, "refresh")}>Jetzt abrufen</button><button className="secondary-action" type="button" disabled={busy} onClick={() => void mutate(source, "disable")}>Deaktivieren</button></> : null}
    </article>)}
    {error ? <p role="alert">Die Quellen konnten nicht geladen oder geändert werden. <button type="button" disabled={busy} onClick={() => void load()}>Erneut versuchen</button></p> : null}
  </details>;
}

export function WorldRadar() {
  const [items, setItems] = useState<WorldSource[]>([]);
  useEffect(() => { let active = true; request<WorldPayload>("/api/v1/world").then(result => { if (active) setItems(result.items.filter(item => item.enabled && item.status !== "ignored" && !!item.episode_id && !!item.matched_goals?.length)); }).catch(() => { if (active) setItems([]); }); return () => { active = false; }; }, []);
  if (!items.length) return null;
  return <section aria-label="Öffentliche Quellen mit Themenüberschneidung" className="profile-card"><h2>Quellen mit möglicher Themenüberschneidung</h2>{items.map(source => <article key={source.id}><strong>{source.label}</strong><p>{freshness(source.last_success)} · {sourceStatus(source)}</p><a href={source.url} target="_blank" rel="noopener noreferrer">Eingetragene Adresse öffnen</a><p>Themenüberschneidung mit einem Ziel (nur ein Hinweis): {source.matched_goals?.map(goal => goal.statement).join(" · ")}</p>{source.truncated && <p>Gespeicherter Auszug: maximal 12.000 Zeichen.</p>}{source.episode_id ? <ProfileSource kind="episode" id={source.episode_id} allowIgnore={false} /> : null}</article>)}</section>;
}
