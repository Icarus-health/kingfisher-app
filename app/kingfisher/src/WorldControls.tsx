import { FormEvent, useEffect, useState } from "react";
import { ProfileSource } from "./ProfileSource";
import { Gruppe, Leer } from "./grundlage";

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
  if (!response.ok) throw Object.assign(new Error("Anfrage fehlgeschlagen"),{status:response.status});
  return response.json() as Promise<T>;
}

function sourceStatus(source: WorldSource) {
  return ({disabled: "Deaktiviert", stale: "Veraltet – bitte aktualisieren", ignored: "Ausgeschlossen", pending: "Noch nicht abgerufen", ok: "Innerhalb der letzten 24 Stunden abgerufen"} as Record<string, string>)[source.status] || "Status unbekannt";
}

function freshness(value: string | null) {
  return value ? `Abgerufen ${new Date(value).toLocaleString("de-DE")}` : "Noch nicht abgerufen";
}

export function WorldControls({ initiallyOpen = false, seite = false }: { initiallyOpen?: boolean; seite?: boolean }) {
  const [payload, setPayload] = useState<WorldPayload | null>(null);
  const [label, setLabel] = useState("");
  const [url, setUrl] = useState("");
  const [topics, setTopics] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reloadOffered,setReloadOffered] = useState(true);
  const [open, setOpen] = useState(initiallyOpen);
  const load = async () => {
    setError("");
    setReloadOffered(true);
    try { setPayload(await request<WorldPayload>("/api/v1/world")); } catch { setError("Die Quellenliste konnte nicht geladen werden. Bitte erneut laden."); }
  };
  useEffect(() => { void load(); }, []);
  async function add(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setReloadOffered(false);
    if (!url.trim().toLowerCase().startsWith("https://")) { setError("Bitte eine öffentliche HTTPS-Adresse eingeben. Deine Eingabe bleibt erhalten."); return; }
    setBusy(true); setError("");
    try {
      await request<WorldSource>("/api/v1/world", { method: "POST", body: JSON.stringify({
        url: url.trim(), label: label.trim(), topics: topics.split(",").map(item => item.trim()).filter(Boolean),
      }) });
      setLabel(""); setUrl(""); setTopics(""); await load();
    } catch (failure) {
      const status=(failure as {status?:number}).status;
      setError(status===400 || status===422 ? "Bitte Bezeichnung, öffentliche HTTPS-Adresse und Themen prüfen (höchstens 10, je 80 Zeichen). Prüfe auch, ob diese Quelle bereits in der Liste steht. Deine Eingabe bleibt erhalten."
        : status===409 ? "Die Quelle konnte nicht bestätigt werden. Bitte zuerst die vorhandene Quellenliste prüfen. Deine Eingabe bleibt erhalten."
        : "Die Quelle wurde nicht bestätigt. Deine Eingabe bleibt erhalten; bitte erneut hinzufügen.");
    } finally { setBusy(false); }
  }
  async function mutate(source: WorldSource, action: "refresh" | "disable") {
    if (busy) return;
    setBusy(true); setError("");
    try { await request(`/api/v1/world/${encodeURIComponent(source.id)}/${action}`, { method: "POST" }); await load(); }
    catch { setReloadOffered(true);setError("Die Änderung wurde nicht bestätigt. Lade die Quellenliste neu, bevor du erneut handelst."); } finally { setBusy(false); }
  }
  // Ein Satz, der zusichert, was mit dem Auszug geschieht und was nicht; sonst keine Erklärprosa.
  const hinweis = "Abrufe laufen nur mit Zeitplan, solange Kingfisher läuft. Angezeigt wird die Abrufzeit; ein Veröffentlichungsdatum wird nicht übernommen. Der Auszug bleibt ein Quellenbericht und bestätigt keine persönliche Angabe.";
  const formular = <form className="decision-create-form welt-formular" onSubmit={add} aria-label="Öffentliche Quelle hinzufügen">
      <label>Bezeichnung<input value={label} onChange={event => setLabel(event.target.value)} required maxLength={200} /></label>
      <label>HTTPS-Adresse<input type="url" value={url} onChange={event => setUrl(event.target.value)} placeholder="https://…" required /></label>
      <label>Themen, getrennt durch Komma<input value={topics} onChange={event => setTopics(event.target.value)} /></label>
      <button className="primary-action" disabled={busy} type="submit">Quelle hinzufügen</button>
    </form>;
  const liste = <>
    {!payload && !error ? <p role="status">Quellen werden geladen …</p> : null}
    {payload?.items.length === 0 ? (seite ? <Leer zeichen="search" satz="Noch keine von dir ausgewählten Quellen." /> : <p>Noch keine von dir ausgewählten Quellen.</p>) : null}
    {payload?.items.map(source => <article className="identity-source-row" key={source.id}>
      <h3>{source.label}</h3>
      <p>{!source.last_success&&source.status==="pending"?"Noch nicht abgerufen":`${freshness(source.last_success)} · ${sourceStatus(source)}`}</p>
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
    {error ? <p role="alert">{error}{reloadOffered && <> <button type="button" disabled={busy} onClick={() => void load()}>Liste neu laden</button></>}</p> : null}
  </>;
  // Auf der eigenen Seite zwei Gruppen (neue Quelle, deine Quellen); in den Einstellungen bleibt der Aufklapper.
  if (seite) return <div className="welt-seite">
    <Gruppe titel="Neue Quelle" frei fussnote={hinweis}>{formular}</Gruppe>
    <Gruppe titel="Deine Quellen" frei>{liste}</Gruppe>
  </div>;
  return <details className="profile-card" open={open} onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>Aktuelle Quellen</summary>
    <p>{hinweis}</p>
    {formular}
    {liste}
  </details>;
}

export function WorldRadar() {
  const [items, setItems] = useState<WorldSource[]>([]);
  useEffect(() => { let active = true; request<WorldPayload>("/api/v1/world").then(result => { if (active) setItems(result.items.filter(item => item.enabled && item.status !== "ignored" && !!item.episode_id && !!item.matched_goals?.length)); }).catch(() => { if (active) setItems([]); }); return () => { active = false; }; }, []);
  if (!items.length) return null;
  return <section aria-label="Öffentliche Quellen mit Themenüberschneidung" className="profile-card"><h2>Quellen mit möglicher Themenüberschneidung</h2>{items.map(source => <article key={source.id}><strong>{source.label}</strong><p>{freshness(source.last_success)} · {sourceStatus(source)}</p><a href={source.url} target="_blank" rel="noopener noreferrer">Eingetragene Adresse öffnen</a><p>Themenüberschneidung mit einem Ziel (nur ein Hinweis): {source.matched_goals?.map(goal => goal.statement).join(" · ")}</p>{source.truncated && <p>Gespeicherter Auszug: maximal 12.000 Zeichen.</p>}{source.episode_id ? <ProfileSource kind="episode" id={source.episode_id} allowIgnore={false} /> : null}</article>)}</section>;
}
