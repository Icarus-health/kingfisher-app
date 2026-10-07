import {useState, type FormEvent} from "react";
import {type Task as LocalTask, type Project} from "./api";
import {icon} from "./ui";
import {TaskSource} from "./TaskSource";
import {TaskHistory} from "./TaskHistory";
import {endOfTaskDay, localTaskDay as dateInput} from "./taskWorkflow";

function dueLabel(value: string | null) {
  if (!value) return "Ohne Termin";
  const date = new Date(value);
  const today = new Date();
  const start = (item: Date) => new Date(item.getFullYear(), item.getMonth(), item.getDate()).getTime();
  const days = Math.round((start(date) - start(today)) / 86_400_000);
  if (days === 0) return "Heute";
  if (days === 1) return "Morgen";
  if (days === -1) return "Gestern";
  return new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "short" }).format(date).replace(".", "");
}

export function TaskRow({ task, view, completing, onComplete, onWait, projects, onProjectChange, onEdit, projectDisabled = false }: { task: LocalTask; view: "mine" | "waiting" | "done"; completing: boolean; onComplete: () => void; onWait: (name?: string) => void; projects: Project[]; projectDisabled?: boolean; onProjectChange: (id: string) => void; onEdit: (data: {title?: string; due?: string | null; notes?: string | null}) => Promise<boolean> }) {
  const [waitingForm, setWaitingForm] = useState(false);
  const [waitingName, setWaitingName] = useState("");
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(task.title);
  const [editDue, setEditDue] = useState(dateInput(task.due));
  const [editNotes, setEditNotes] = useState(task.notes ?? "");
  const complete = task.status === "done";
  const canComplete = ((view === "mine" || view === "waiting") && task.status === "open") || (view === "done" && complete);
  function beginEdit() {
    setEditTitle(task.title);
    setEditDue(dateInput(task.due));
    setEditNotes(task.notes ?? "");
    setEditing(true);
  }
  async function saveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editTitle.trim()) return;
    const changes: {title?: string; due?: string | null; notes?: string | null} = {};
    if (editTitle.trim() !== task.title) changes.title = editTitle.trim();
    if (editDue !== dateInput(task.due)) changes.due = editDue ? endOfTaskDay(editDue) : null;
    if (editNotes !== (task.notes ?? "")) changes.notes = editNotes.trim() || null;
    if (Object.keys(changes).length === 0 || await onEdit(changes)) setEditing(false);
  }
  return <article className={`task-row ${complete ? "done" : ""}`}>
    <button aria-label={complete ? `${task.title} wieder öffnen` : `${task.title} erledigen`} title={complete ? "Wieder öffnen" : "Erledigen"} className="task-check" disabled={!canComplete || completing} onClick={onComplete} type="button">{complete ? <img src={icon("check", "Outline")} alt="" /> : null}</button>
    <div className="task-copy">{editing ? <form className="task-create task-edit" onSubmit={saveEdit}>
      <label>Aufgabe<input autoFocus required value={editTitle} onChange={event => setEditTitle(event.target.value)} /></label>
      <label>Fällig am <small>(optional)</small><input type="date" value={editDue} onChange={event => setEditDue(event.target.value)} /></label>
      <label>Notiz <small>(optional)</small><textarea value={editNotes} onChange={event => setEditNotes(event.target.value)} rows={2} /></label>
      <div><button className="secondary-action" disabled={completing} onClick={() => setEditing(false)} type="button">Abbrechen</button><button className="primary-action" disabled={completing || !editTitle.trim()} type="submit">Änderungen speichern</button></div>
    </form> : <><strong>{task.title}</strong>{view === "waiting" && task.wartet_auf ? <small>Wartet auf {task.wartet_auf}</small> : null}{task.notes ? <small title={task.notes}>Notiz: {task.notes}</small> : null}<select aria-label={`Projekt für ${task.title}`} value={task.project_id ?? ""} disabled={completing || projectDisabled} onChange={event => onProjectChange(event.target.value)}><option value="">Ohne Projekt</option>{task.project_id && !projects.some(project => project.id === task.project_id) ? <option value={task.project_id}>Projekt nicht verfügbar</option> : null}{projects.map(project => <option key={project.id} value={project.id}>{project.name}{!project.open ? " (geschlossen)" : ""}</option>)}</select><button className="secondary-action" type="button" disabled={completing} onClick={beginEdit}>Bearbeiten</button>{task.provenance?.source_ref?.startsWith("episode:") && <TaskSource taskId={task.id} />}<TaskHistory taskId={task.id} revision={JSON.stringify([task.title, task.due, task.notes, task.status, task.project_id, task.wartet_auf])} /></>}</div>
    {view !== "done" && <div className="task-wait-control">
      {view === "waiting" ? <button type="button" disabled={completing} onClick={() => onWait()}>Zurück zu mir</button> : waitingForm ? <form onSubmit={event => { event.preventDefault(); if (waitingName.trim()) onWait(waitingName.trim()); }}>
        <label>Warte auf<input value={waitingName} onChange={event => setWaitingName(event.target.value)} required maxLength={200} placeholder="Name" /></label>
        <small>Nur lokal vermerken; keine Nachricht senden.</small>
        <button type="submit" disabled={completing || !waitingName.trim()}>Speichern</button><button type="button" onClick={() => setWaitingForm(false)}>Abbrechen</button>
      </form> : <button type="button" onClick={() => setWaitingForm(true)}>Warte auf …</button>}
    </div>}
    <time className={task.overdue ? "overdue" : ""} dateTime={task.due ?? undefined}>{dueLabel(task.due)}</time>
  </article>;
}
