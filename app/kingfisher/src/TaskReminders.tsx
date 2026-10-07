import {useCallback, useEffect, useRef, useState} from "react";
import {api, type Task} from "./api";
import {taskHref} from "./taskWorkflow";
import {reminderLabel, tomorrowAtNine} from "./reminderDates";

type ReminderTask = Task;
const reminderApi = api;

/** A bounded, independently refreshed list; completing a reminder never completes its task. */
export function TaskReminders({active = true, onChanged}: {active?: boolean; onChanged?: () => void}) {
  const [items, setItems] = useState<ReminderTask[] | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [message, setMessage] = useState("");
  const [workingId, setWorkingId] = useState("");
  const pending = useRef(false);
  const version = useRef(0);
  const lifecycle = useRef(0);
  const activeRef = useRef(false);

  const load = useCallback(async () => {
    const current = ++version.current;
    setItems(null); setTruncated(false); setError(""); setLoading(true);
    try {
      const response = await reminderApi.taskReminders(100);
      if (!activeRef.current || current !== version.current) return;
      setItems(response.items.filter(task => Boolean(task.remind_at)));
      setTruncated(response.truncated);
    } catch {
      if (activeRef.current && current === version.current) setError("Die Wiedervorlagen konnten gerade nicht geladen werden.");
    } finally {
      if (activeRef.current && current === version.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!active) return;
    let mounted = true;
    activeRef.current = true;
    lifecycle.current++;
    void load();
    const refreshOnReturn = () => {
      if (mounted && !document.hidden && !pending.current) void load();
    };
    const visible = () => { if (!document.hidden) refreshOnReturn(); };
    window.addEventListener("focus", refreshOnReturn);
    document.addEventListener("visibilitychange", visible);
    const timer = window.setInterval(refreshOnReturn, 60_000);
    return () => {
      mounted = false; activeRef.current = false;
      lifecycle.current++; version.current++;
      window.removeEventListener("focus", refreshOnReturn);
      document.removeEventListener("visibilitychange", visible);
      window.clearInterval(timer);
    };
  }, [active, load]);

  async function update(task: ReminderTask, remindAt: string | null, action: "close" | "tomorrow") {
    if (!activeRef.current || pending.current) return;
    pending.current = true;
    const currentLife = lifecycle.current;
    version.current++;
    setWorkingId(task.id); setActionError(""); setMessage(""); setError("");
    try {
      await reminderApi.editTask(task.id, {remind_at: remindAt, expected_remind_at: task.remind_at ?? null});
      if (!activeRef.current || currentLife !== lifecycle.current) return;
      setItems(previous => (previous ?? []).filter(item => item.id !== task.id));
      setMessage(action === "close" ? `Wiedervorlage für „${task.title}“ abgeschlossen. Die Aufgabe bleibt unverändert.`
        : `„${task.title}“ wird morgen um 09:00 Uhr wieder vorgelegt.`);
      onChanged?.();
    } catch {
      if (activeRef.current && currentLife === lifecycle.current) {
        setActionError("Die Wiedervorlage wurde nicht bestätigt. Bitte erneut laden und den aktuellen Stand prüfen.");
        void load();
      }
    } finally {
      pending.current = false;
      if (activeRef.current && currentLife === lifecycle.current) setWorkingId("");
    }
  }

  if (!active) return null;
  const visibleItems = (items ?? []).slice(0, expanded ? 100 : 5);
  return <section className="source-section task-reminders" aria-label="Wiedervorlagen">
    <div className="memory-questions-kopf"><div><h2>Wiedervorlagen</h2><p>Aufgaben, die du dir für später vorgemerkt hast.</p></div>
      {items && items.length > 5 && <button type="button" className="text-action" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>{expanded ? "Weniger anzeigen" : `Alle ${items.length} anzeigen`}</button>}
    </div>
    {loading && <p role="status">Wiedervorlagen werden geladen …</p>}
    {error && <p role="alert">{error} <button type="button" className="text-action" onClick={() => void load()}>Erneut laden</button></p>}
    {items?.length === 0 && !error && !loading && <p role="status">Keine offenen Wiedervorlagen.</p>}
    {visibleItems.length > 0 && <ul className="befunde-liste" aria-label="Vorgemerkte Aufgaben">
      {visibleItems.map(task => <li className="befund task-reminder" key={task.id}>
        <div><strong>{task.title}</strong><small>Wieder vorlegen: {reminderLabel(task.remind_at)}</small></div>
        <a className="text-action" href={taskHref(task)}>Aufgabe öffnen</a>
        <div className="befund-aktionen">
          <button type="button" className="secondary-action" disabled={workingId !== ""} onClick={() => void update(task, null, "close")}>Wiedervorlage abschließen</button>
          <button type="button" className="text-action" disabled={workingId !== ""} onClick={() => void update(task, tomorrowAtNine(), "tomorrow")}>Morgen 09:00</button>
        </div>
      </li>)}
    </ul>}
    {items && items.length > 5 && !expanded && <button type="button" className="text-action" onClick={() => setExpanded(true)}>Weitere {items.length - 5} anzeigen</button>}
    {truncated && <p className="task-notice" role="note">Nicht alle Wiedervorlagen sind sichtbar: Die Anzeige ist auf 100 begrenzt.</p>}
    {message && <p className="source-hint" role="status">{message}</p>}
    {actionError && <p className="partial-error" role="alert">{actionError} <button type="button" className="text-action" onClick={() => void load()}>Erneut laden</button></p>}
  </section>;
}
