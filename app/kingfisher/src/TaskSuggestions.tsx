import { useEffect, useRef, useState } from "react";
import { api, type Project, type Task, type TaskCandidate } from "./api";
import { ProfileSource } from "./ProfileSource";

export function TaskSuggestions({projects, onAccepted, initiallyExpanded = false}: {projects: Project[]; onAccepted: (task: Task) => void; initiallyExpanded?: boolean}) {
  const requestVersion = useRef(0);
  const [items, setItems] = useState<TaskCandidate[]>([]);
  const [error, setError] = useState(false);
  const [revision, setRevision] = useState(0);
  const [expanded, setExpanded] = useState(initiallyExpanded);
  const [notice, setNotice] = useState("");
  useEffect(() => {
    let active = true;
    const refresh = () => { const version = ++requestVersion.current; api.taskCandidates().then(result => {if (active && version === requestVersion.current) {setItems(result); setError(false);}}).catch(() => {if (active && version === requestVersion.current) setError(true);}); };
    refresh();
    window.addEventListener("focus", refresh);
    return () => {active = false; window.removeEventListener("focus", refresh);};
  }, [revision]);
  if (!items.length && !error && !notice) return null;
  return <section className="task-source" aria-label="Erkannte Aufgaben und Zusagen">
    {items.length > 0 && <><h2><button type="button" className="secondary-action" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>Zur Prüfung · {items.length}</button></h2><p>In deinen Quellen erkannt. Erst deine Bestätigung macht daraus eine Aufgabe.</p></>}
    {notice && <p role="status">{notice}</p>}
    {error && <p role="alert">Vorschläge sind gerade nicht erreichbar. <button type="button" onClick={() => setRevision(value => value + 1)}>Erneut laden</button></p>}
    {expanded && items.map(item => <Suggestion key={item.id} item={item} projects={projects} onDone={task => {
      requestVersion.current++;
      setItems(current => current.filter(candidate => candidate.id !== item.id));
      setNotice(task ? "Aufgabe gespeichert." : "Vorschlag verworfen.");
      setRevision(value => value + 1);
      if (task) onAccepted(task);
    }} />)}
  </section>;
}

function Suggestion({item, projects, onDone}: {item: TaskCandidate; projects: Project[]; onDone: (task?: Task) => void}) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState(item.statement);
  const [project, setProject] = useState("");
  // Eine Frist aus einer privaten Mail bringt ihr Datum mit (akten_arten.py); geändert werden kann es trotzdem.
  const [due, setDue] = useState(item.temporal_status === "recent" && item.valid_until ? item.valid_until.slice(0, 10) : "");
  const [waiting, setWaiting] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function save(accept: boolean) {
    if (busy) return;
    setBusy(true); setError("");
    try {
      if (accept) {
        const task = await api.acceptTaskCandidate(item.id, {title: title.trim(), project_id: project || null,
          due: due ? new Date(`${due}T00:00:00`).toISOString() : null, waiting_for: waiting.trim() || null});
        onDone(task);
      } else { await api.rejectTaskCandidate(item.id); onDone(); }
    } catch (failure) {
      setError(failure instanceof Error && failure.message === "HTTP 409"
        ? "Dieser Vorschlag ist nicht mehr verfügbar oder seine Quelle wurde ausgeschlossen. Bitte die Aufgabenansicht neu laden."
        : "Die Änderung konnte nicht gespeichert werden. Deine Eingaben bleiben erhalten. Bitte erneut versuchen.");
    } finally {setBusy(false);}
  }
  return <article className="mail-task-form">
    <h3>{item.statement}</h3>
    <p>{item.temporal_reason || 'Zeitliche Einordnung bitte prüfen.'}</p>
    <p>Quelldatum: {item.received_at ? new Date(item.received_at).toLocaleString('de-DE', {dateStyle:'medium', timeStyle:'short'}) : 'unbekannt'}
      {item.recorded_at && <> · Erfasst: {new Date(item.recorded_at).toLocaleString('de-DE', {dateStyle:'medium', timeStyle:'short'})}</>}</p>
    {item.followup_episode_id && <div><p>Weitere Nachricht im Verlauf:</p><ProfileSource kind="episode" id={item.followup_episode_id} allowIgnore={false} /></div>}
    {item.evidence.map(evidence => <div key={evidence.episode_id}><blockquote>{evidence.quote}</blockquote><ProfileSource kind="episode" id={evidence.episode_id} allowIgnore={false} /></div>)}
    {!open ? <div><button className="secondary-action" type="button" onClick={() => setOpen(true)}>Aufgabe prüfen</button><button className="secondary-action" type="button" disabled={busy} onClick={() => void save(false)}>Verwerfen</button></div> :
      <form onSubmit={event => {event.preventDefault(); void save(true);}}>
        <fieldset className="task-suggestion-fields" disabled={busy}><label>Aufgabe<input value={title} onChange={event => setTitle(event.target.value)} required maxLength={4096} /></label>
          <div className="mail-task-form-fields"><label>Projekt<select value={project} onChange={event => setProject(event.target.value)}><option value="">Ohne Projekt</option>{projects.filter(value => value.open).map(value => <option key={value.id} value={value.id}>{value.name}</option>)}</select></label>
          <label>Fällig am<input type="date" value={due} onChange={event => setDue(event.target.value)} /></label>
          <label>Warte auf (optional)<input value={waiting} onChange={event => setWaiting(event.target.value)} maxLength={1024} /></label></div>
          <div className="task-suggestion-actions"><button className="primary-action" type="submit" disabled={!title.trim()}>Aufgabe festhalten</button>
          <button className="secondary-action" type="button" onClick={() => setOpen(false)}>Abbrechen</button></div>
        </fieldset>
      </form>}
    {error && <p role="alert">{error}</p>}
  </article>;
}
