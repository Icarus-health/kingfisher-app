import { useEffect, useState } from "react";
import { api } from "./api";
import { ProfileSource } from "./ProfileSource";

type Page = Awaited<ReturnType<typeof api.uploadedDocuments>>;
export function DocumentSources() {
  const [page, setPage] = useState<Page | null>(null);
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    let loading = false;
    setPage(null); setError(false); setSelected(null);
    async function refresh() {
      if (loading) return;
      loading = true;
      try {
        const result = await api.uploadedDocuments(offset);
        if (active) {setPage(result); setError(false);}
      } catch {if (active) setError(true);}
      finally {loading = false;}
    }
    void refresh();
    const timer = window.setInterval(() => {if (!document.hidden) void refresh();}, 5000);
    return () => {active = false; window.clearInterval(timer);};
  }, [offset, revision]);
  async function ignore(id: string) {
    if (busy) return;
    setBusy(true);setError(false);
    try {await api.ignoreSource(id);setRevision(value => value + 1);}
    catch {setError(true);}
    finally {setBusy(false);}
  }
  return <section aria-label="Aufgenommene Dateien">
    <h3>Aufgenommene Dateien</h3>
    {!page && !error && <p role="status">Dateiliste wird geladen …</p>}
    {page && page.items.length === 0 && <p>Noch keine aufgenommenen Dateien auf dieser Seite.</p>}
    {page?.items.map(item => <article key={`${item.id}:${item.state}`} className="identity-source-row">
      <h4>{item.title}</h4><p>{new Date(item.recorded_at).toLocaleString("de-DE")} · {item.state === "ignored" ? "Ausgeschlossen" : "Gespeicherte Quelle"}</p>
      {item.memory_status && <p role="status">{item.memory_status.label}</p>}
      <ProfileSource kind="episode" id={item.id} allowIgnore={false} onChange={() => setRevision(value => value + 1)} />
      {item.project_id && <p><a href={`/memory/projects/${encodeURIComponent(item.project_id)}`}>Projektakte öffnen</a></p>}
      {item.state !== "ignored" && <button className="secondary-action" type="button" disabled={busy} onClick={() => setSelected(item.id)}>Quelle ausschließen</button>}
      {selected === item.id && <div role="group" aria-label="Quelle ausschließen"><p>Diese Quelle wird nicht weiter als Beleg verwendet. Daraus bestätigtes und davon abhängiges Wissen wird als fraglich markiert. Der gespeicherte Inhalt bleibt im Verlauf erhalten.</p>
        <button type="button" className="primary-action" disabled={busy} onClick={() => void ignore(item.id)}>Ausschluss bestätigen</button>
        <button type="button" className="secondary-action" disabled={busy} onClick={() => setSelected(null)}>Abbrechen</button>
      </div>}
    </article>)}
    {(offset > 0 || page?.next_offset != null) && <div><button className="secondary-action" disabled={offset === 0 || busy || !page} onClick={() => setOffset(value => Math.max(0, value - 50))} type="button">Vorherige Dateien</button><button className="secondary-action" disabled={page?.next_offset == null || busy} onClick={() => {if (page?.next_offset != null) setOffset(page.next_offset);}} type="button">Weitere Dateien</button></div>}
    {error && <p role="alert">Die Dateiliste oder Änderung konnte nicht geladen werden. <button type="button" disabled={busy} onClick={() => setRevision(value => value + 1)}>Erneut versuchen</button></p>}
  </section>;
}
