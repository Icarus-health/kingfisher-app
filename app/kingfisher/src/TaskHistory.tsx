import { useEffect, useState } from "react";
import { api } from "./api";
import { reminderLabel } from "./reminderDates";

type History = Awaited<ReturnType<typeof api.taskHistory>>;
const labels: Record<string, string> = {
  created: "Aufgabe angelegt", from_suggestion: "Vorschlag als Aufgabe übernommen",
  completed: "Als erledigt markiert", user_confirmed_completion: "Erledigung ausdrücklich bestätigt",
  dropped: "Fallengelassen", reopened: "Wieder geöffnet",
  post_completed: "Erledigung mit Mailbezug erfasst", post_undone: "Änderung durch die Post zurückgenommen",
  waiting_for: "Wartestatus geändert", returned: "Zurück zu mir", project_assigned: "Projektzuordnung geändert",
  edited: "Details bearbeitet",
  reminder_changed: "Wiedervorlage geändert", remind_at_changed: "Wiedervorlage geändert",
  preexisting_snapshot: "Bereits vorhandener Stand erfasst",
};
export function TaskHistory({ taskId, revision, sequence }: { taskId: string; revision: string; sequence?: string }) {
  const [open, setOpen] = useState(Boolean(sequence));
  const [showRecent, setShowRecent] = useState(false);
  const selected = showRecent ? undefined : sequence;
  const [data, setData] = useState<History | null>(null);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!open) return;
    let active = true;
    setData(null); setError(false);
    api.taskHistory(taskId, selected).then(value => { if (active) setData(value); })
      .catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [taskId, revision, open, retry, selected]);
  return <div className="task-source">
    <button type="button" className="task-aufklapper" aria-expanded={open} onClick={() => setOpen(value => !value)}>Verlauf</button>
    {open && <section aria-label="Aufgabenverlauf">
      {sequence && <button type="button" className="text-action" onClick={() => setShowRecent(value => !value)}>{showRecent ? "Verknüpften Eintrag ansehen" : "Neueste Änderungen ansehen"}</button>}
      {error ? <p role="alert">Der Verlauf ist gerade nicht erreichbar. <button type="button" onClick={() => setRetry(value => value + 1)}>Erneut versuchen</button></p> : !data ? <p role="status">Verlauf wird geladen …</p> : <>
        <p>{data.scope}</p>
        {data.items.length === 0 && <p>Keine Änderungen aufgezeichnet.</p>}
        <ol>{data.items.map(event => <li key={event.sequence}>
          {(() => {
            const before = event.before as (typeof event.before & {remind_at?: string | null}) | null;
            const after = event.after as typeof event.after & {remind_at?: string | null};
            const hasReminder = Boolean((before && Object.hasOwn(before, "remind_at")) || Object.hasOwn(after, "remind_at"));
            const changed = hasReminder && before?.remind_at !== after.remind_at;
            return <><strong>{changed ? "Wiedervorlage geändert" : labels[event.kind] ?? "Aufgabenänderung"}</strong>
              {changed && <p>Wieder vorlegen: {after.remind_at ? reminderLabel(after.remind_at) : "keine Wiedervorlage"}</p>}</>;
          })()}
          <p>Aufgezeichnet: {new Date(event.recorded_at).toLocaleString("de-DE")}</p>
          {event.kind === "preexisting_snapshot" && <p>Frühere Änderungen sind nicht bekannt. Dieser Eintrag rekonstruiert keine Vergangenheit.</p>}
          {event.after.wartet_auf && event.before?.wartet_auf !== event.after.wartet_auf && <p>Wartet auf: {event.after.wartet_auf}</p>}
        </li>)}</ol>
        {data.truncated && <p>Die neuesten 100 Änderungen werden angezeigt.</p>}
      </>}
    </section>}
  </div>;
}
