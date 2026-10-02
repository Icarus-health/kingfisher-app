import { useEffect, useState } from "react";
import { api } from "./api";

type History = Awaited<ReturnType<typeof api.taskHistory>>;
const labels: Record<string, string> = {
  created: "Aufgabe angelegt", from_suggestion: "Vorschlag als Aufgabe übernommen",
  completed: "Als erledigt markiert", dropped: "Fallengelassen", reopened: "Wieder geöffnet",
  waiting_for: "Wartestatus geändert", returned: "Zurück zu mir", project_assigned: "Projektzuordnung geändert",
  edited: "Details bearbeitet",
  preexisting_snapshot: "Bereits vorhandener Stand erfasst",
};
export function TaskHistory({ taskId, revision }: { taskId: string; revision: string }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<History | null>(null);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!open) return;
    let active = true;
    setData(null); setError(false);
    api.taskHistory(taskId).then(value => { if (active) setData(value); })
      .catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [taskId, revision, open, retry]);
  return <div className="task-source">
    <button type="button" className="secondary-action" aria-expanded={open} onClick={() => setOpen(value => !value)}>{open ? "Verlauf schließen" : "Verlauf öffnen"}</button>
    {open && <section aria-label="Aufgabenverlauf">
      <h3>Aufgabenverlauf</h3>
      {error ? <p role="alert">Der Verlauf ist gerade nicht erreichbar. <button type="button" onClick={() => setRetry(value => value + 1)}>Erneut versuchen</button></p> : !data ? <p role="status">Verlauf wird geladen …</p> : <>
        <p>{data.scope}</p>
        {data.items.length === 0 && <p>Keine Änderungen aufgezeichnet.</p>}
        <ol>{data.items.map(event => <li key={event.sequence}>
          <strong>{labels[event.kind] ?? "Aufgabenänderung"}</strong>
          <p>Aufgezeichnet: {new Date(event.recorded_at).toLocaleString("de-DE")}</p>
          {event.kind === "preexisting_snapshot" && <p>Frühere Änderungen sind nicht bekannt. Dieser Eintrag rekonstruiert keine Vergangenheit.</p>}
          {event.after.wartet_auf && event.before?.wartet_auf !== event.after.wartet_auf && <p>Wartet auf: {event.after.wartet_auf}</p>}
        </li>)}</ol>
        {data.truncated && <p>Die neuesten 100 Änderungen werden angezeigt.</p>}
      </>}
    </section>}
  </div>;
}
