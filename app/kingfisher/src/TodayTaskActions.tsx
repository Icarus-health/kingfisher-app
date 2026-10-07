import {useEffect, useRef, useState} from 'react';
import {api, type Attention} from './api';
import {taskHref} from './taskWorkflow';
import {TaskDetail} from './TaskDetail';

export function TodayTaskActions({item, onChanged}: {item: Attention; onChanged: () => void}) {
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const pending = useRef(false);
  const alive = useRef(true);
  useEffect(() => {alive.current = true; return () => {alive.current = false;};}, []);
  const id = item.source_ref!;
  const waiting = item.source === 'wartet';
  async function act() {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError('');
    try {
      if (waiting) await api.unwaitTask(id);
      else await api.completeTask(id);
      if (alive.current) {setNotice(waiting ? 'Die Aufgabe liegt wieder bei dir.' : 'Aufgabe erledigt.'); onChanged();}
    } catch {if (alive.current) setError('Die Änderung wurde nicht bestätigt. Bitte erneut versuchen.');}
    finally {pending.current = false; if (alive.current) setBusy(false);}
  }
  return <div className="today-task-actions">
    <div className="task-suggestion-actions">
      <button className="today-action" type="button" disabled={busy || Boolean(notice) || expanded} onClick={() => void act()}>{busy ? 'Wird gespeichert …' : waiting ? 'Zurück zu mir' : 'Erledigen'}</button>
      <button className="today-text-link" type="button" disabled={busy} aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>{expanded ? 'Bearbeitung schließen' : 'Hier bearbeiten'}</button>
      <a className="today-text-link" href={taskHref({id, wartet_auf: waiting ? 'waiting' : null, project_id: item.project_id})}>Aufgabe öffnen →</a>
    </div>
    {notice && <p role="status">{notice}</p>}
    {error && <p role="alert">{error}</p>}
    {expanded && <TaskDetail taskId={id} onChanged={onChanged} />}
  </div>;
}
