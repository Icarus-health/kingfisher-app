import {useRef, useState, type FormEvent} from "react";
import {type Task as LocalTask, type Project} from "./api";
import {icon} from "./ui";
import {TaskSource} from "./TaskSource";
import {TaskHistory} from "./TaskHistory";
import {endOfTaskDay, localTaskDay as dateInput} from "./taskWorkflow";
import {localReminderInput, reminderEditChanges, reminderLabel, tomorrowAtNine} from "./reminderDates";
import {postSatz} from "./aufgabenPost";
import {dueLabel} from "./taskWorkspaceModel";

/**
 * Eine Aufgabe. In der Liste (`compact`) zeigt die Zeile die Aufgabe, nicht die Bedienung: Kreis, Titel, darunter
 * leise in einer Zeile Projekt (nur wenn gesetzt), Wartet auf und Wiedervorlage, rechts die Fälligkeit. Die ganze Zeile
 * öffnet die Aufgabe. Projekt und „Warte auf …“ erscheinen bei Zeiger oder Tastaturfokus in der Zeile; auf schmalen
 * Fenstern und ohne Zeiger stehen sie in der geöffneten Aufgabe. Im Detail (nicht `compact`, auch auf Heute) stehen
 * Titel, eine Zeile mit Fälligkeit und Zuordnung, die Notiz und darunter die Aktionen.
 */
export function TaskRow({ task, view, completing, onComplete, onWait, projects, onProjectChange, onEdit, projectDisabled = false, compact = false, onOpen, onRueckgaengig, startEditing = false, showProjectName = true }: { task: LocalTask; view: "mine" | "waiting" | "done"; completing: boolean; onComplete: () => void; onWait: (name?: string) => void; projects: Project[]; projectDisabled?: boolean; compact?: boolean; onOpen?: () => void; onProjectChange: (id: string) => void; onEdit: (data: {title?: string; due?: string | null; notes?: string | null; remind_at?: string | null; expected_remind_at?: string | null}) => Promise<boolean>; onRueckgaengig?: () => void; startEditing?: boolean; showProjectName?: boolean }) {
  const remindAt = (task as LocalTask & {remind_at?: string | null; expected_remind_at?: string | null}).remind_at ?? null;
  const [waitingForm, setWaitingForm] = useState(false);
  const [waitingName, setWaitingName] = useState("");
  const [editing, setEditing] = useState(startEditing && !compact);
  const [focusTitle, setFocusTitle] = useState(false);
  const [editTitle, setEditTitle] = useState(task.title);
  const [editDue, setEditDue] = useState(dateInput(task.due));
  const [editRemindAt, setEditRemindAt] = useState(localReminderInput(remindAt));
  const editOriginalReminder = useRef(remindAt);
  const [editNotes, setEditNotes] = useState(task.notes ?? "");
  const [reminderError, setReminderError] = useState("");
  const complete = task.status === "done";
  // Aufgaben folgen der Post: Was die eigene Mail erledigt oder zurückgeholt hat, steht mit Grund da, mit „Rückgängig“.
  const postZeile = postSatz(task);
  const canComplete = ((view === "mine" || view === "waiting") && task.status === "open") || (view === "done" && complete);
  const projectName = task.project_id ? projects.find(project => project.id === task.project_id)?.name : undefined;
  function beginEdit() {
    setEditTitle(task.title);
    setEditDue(dateInput(task.due));
    setEditRemindAt(localReminderInput(remindAt));
    editOriginalReminder.current = remindAt;
    setEditNotes(task.notes ?? "");
    setReminderError("");
    setFocusTitle(true);
    setEditing(true);
  }
  async function saveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editTitle.trim()) return;
    const changes: {title?: string; due?: string | null; notes?: string | null; remind_at?: string | null; expected_remind_at?: string | null} = {};
    if (editTitle.trim() !== task.title) changes.title = editTitle.trim();
    if (editDue !== dateInput(task.due)) changes.due = editDue ? endOfTaskDay(editDue) : null;
    try {Object.assign(changes, reminderEditChanges(editOriginalReminder.current, editRemindAt));}
    catch (error) { setReminderError(error instanceof Error ? error.message : "Bitte Datum und Uhrzeit prüfen."); return; }
    if (editNotes !== (task.notes ?? "")) changes.notes = editNotes.trim() || null;
    if (Object.keys(changes).length === 0 || await onEdit(changes)) setEditing(false);
  }
  const actions = <div className="task-row-actions">
    {!compact && !editing ? <button className="secondary-action" type="button" disabled={completing} onClick={beginEdit}>Bearbeiten</button> : null}
    {view !== "done" && <div className="task-wait-control">
      {view === "waiting" ? <button type="button" disabled={completing} onClick={() => onWait()}>Zurück zu mir</button> : waitingForm ? <form onSubmit={event => { event.preventDefault(); if (waitingName.trim()) onWait(waitingName.trim()); }}>
        <label>Warte auf<input autoFocus value={waitingName} onChange={event => setWaitingName(event.target.value)} required maxLength={200} placeholder="Name" /></label>
        <small>Nur lokal vermerken; keine Nachricht senden.</small>
        <button type="submit" disabled={completing || !waitingName.trim()}>Speichern</button><button type="button" onClick={() => setWaitingForm(false)}>Abbrechen</button>
      </form> : <button type="button" onClick={() => setWaitingForm(true)}>Warte auf …</button>}
    </div>}
    <select aria-label={`Projekt für ${task.title}`} value={task.project_id ?? ""} disabled={completing || projectDisabled} onChange={event => onProjectChange(event.target.value)}><option value="">Ohne Projekt</option>{task.project_id && !projects.some(project => project.id === task.project_id) ? <option value={task.project_id}>Projekt nicht verfügbar</option> : null}{projects.filter(project => project.open || project.id === task.project_id).map(project => <option disabled={!project.open}  key={project.id} value={project.id}>{project.name}{!project.open ? " (geschlossen)" : ""}</option>)}</select>
  </div>;
  // Eine leise Zeile unter dem Titel statt mehrerer: Projekt (nur wenn gesetzt), Wartet auf, Wiedervorlage. Im Detail
  // steht die Fälligkeit vorne, in der Liste rechts.
  const meta = [
    !compact && task.due ? <time key="due" className={task.overdue ? "overdue" : ""} dateTime={task.due}>{dueLabel(task.due)}</time> : null,
    (!compact || showProjectName) && projectName ? <span key="project" className="task-project">{projectName}</span> : null,
    (view === "waiting" || !compact) && task.wartet_auf ? <span key="waiting">Wartet auf {task.wartet_auf}</span> : null,
    remindAt ? <span key="remind">Wiedervorlage {reminderLabel(remindAt)}</span> : null,
  ].filter(Boolean);
  return <article className={`task-row${compact ? " compact" : " task-row-detail"}${complete ? " done" : ""}${waitingForm ? " task-row-open" : ""}`}>
    <button aria-label={complete ? `${task.title} wieder öffnen` : `${task.title} erledigen`} title={complete ? "Wieder öffnen" : "Erledigen"} className="task-check" disabled={!canComplete || completing} onClick={onComplete} type="button">{complete ? <img src={icon("check", "Outline")} alt="" /> : null}</button>
    <div className="task-copy">{editing ? <form className="task-create task-edit" onSubmit={saveEdit}>
      <label className="task-edit-title">Aufgabe<input autoFocus={focusTitle} required value={editTitle} onChange={event => setEditTitle(event.target.value)} /></label>
      <label>Fällig am<input type="date" value={editDue} onChange={event => setEditDue(event.target.value)} /></label>
      <div className="task-edit-reminder"><label>Wieder vorlegen am<input type="datetime-local" step="60" value={editRemindAt} onChange={event => {setEditRemindAt(event.target.value); setReminderError("");}} /></label>
      <div className="task-reminder-edit-actions"><button type="button" className="text-action" onClick={() => {setEditRemindAt(localReminderInput(tomorrowAtNine())); setReminderError("");}}>Morgen 09:00</button>{editRemindAt ? <button type="button" className="text-action" onClick={() => {setEditRemindAt(""); setReminderError("");}}>Wiedervorlage löschen</button> : null}</div></div>
      {reminderError && <p className="partial-error" role="alert">{reminderError}</p>}
      <label className="task-edit-notes">Notiz<textarea value={editNotes} onChange={event => setEditNotes(event.target.value)} rows={2} /></label>
      <div className="task-edit-actions"><button className="secondary-action" disabled={completing} onClick={() => setEditing(false)} type="button">Abbrechen</button><button className="primary-action" disabled={completing || !editTitle.trim()} type="submit">Speichern</button></div>
    </form> : <>{onOpen ? <button className="task-title-link" type="button" title="Öffnen und bearbeiten" onClick={onOpen}>{task.title}</button> : <strong>{task.title}</strong>}{meta.length ? <small className="task-meta">{meta}</small> : null}{postZeile ? <small className="task-post" role="status">{postZeile}{onRueckgaengig ? <> <button type="button" className="text-action" disabled={completing} onClick={onRueckgaengig}>Rückgängig</button></> : null}</small> : null}{!compact && task.notes ? <p className="task-notiz">{task.notes}</p> : null}</>}
      {!compact && actions}
      {!compact && !editing && task.provenance?.source_ref?.startsWith("episode:") && <TaskSource taskId={task.id} />}{!compact && !editing && <TaskHistory taskId={task.id} revision={JSON.stringify([task.title, task.due, remindAt, task.notes, task.status, task.project_id, task.wartet_auf])} />}</div>
    {compact && actions}
    {compact && task.due ? <time className={task.overdue ? "overdue" : ""} dateTime={task.due}>{dueLabel(task.due)}</time> : null}
  </article>;
}
