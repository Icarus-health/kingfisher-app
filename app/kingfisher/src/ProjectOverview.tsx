import {useEffect, useState} from 'react';
import {api, type ProjectTaskOverview, type Task} from './api';
import './ProjectOverview.css';

type View = 'mine' | 'waiting' | 'done';
function dateLabel(value: string | null) {
  if (!value) return 'Ohne Termin';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Termin nicht lesbar' : date.toLocaleString('de-DE', {day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'});
}

export function ProjectOverview({projectId, revision, onView, onTask}: {
  projectId: string; revision: number;
  onView: (view: View) => void; onTask: (id: string, view: View) => void;
}) {
  const [result,setResult] = useState<ProjectTaskOverview | null>(null);
  const [error,setError] = useState('');
  useEffect(() => {
    let active = true;
    setResult(null); setError('');
    if (projectId) api.projectOverview(projectId).then(value => {
      if (active) setResult(value);
    }).catch(() => {if(active) setError('Der Projektüberblick ist gerade nicht erreichbar.');});
    return () => {active=false;};
  }, [projectId,revision]);
  if (!projectId) return null;
  const data = result?.project_id === projectId ? result : null;
  function preview(tasks: Task[], view: 'mine' | 'waiting') {
    return <ul>{tasks.map(task => <li key={task.id}>
      <button type="button" className="project-task-link" onClick={() => onTask(task.id,view)}>{task.title}</button>
      {view === 'waiting' && <small>Bei {task.wartet_auf}{task.wartet_tage !== null ? ` · seit ${task.wartet_tage} Tagen` : ''}</small>}
      <time className={task.overdue ? 'overdue' : ''} dateTime={task.due ?? undefined}>{dateLabel(task.due)}</time>
    </li>)}</ul>;
  }
  return <section className="project-overview" aria-label="Projektüberblick">
    {/* Kein eigener Knopf zum Aktualisieren: Der Überblick lädt nach jeder Änderung in der Liste neu (`revision`). */}
    <header><h2>Projekt auf einen Blick</h2></header>
    {error ? <p role="alert">{error}</p> : !data ? <p role="status">Projektüberblick wird geladen …</p> : <>
      <div className="project-counts">
        <button type="button" onClick={()=>onView('mine')}><strong>{data.counts.mine}</strong>Meine offenen Aufgaben{(data.counts.overdue > 0 || data.counts.undated > 0) && <small>{[data.counts.overdue ? `${data.counts.overdue} überfällig` : '', data.counts.undated ? `${data.counts.undated} ohne Termin` : ''].filter(Boolean).join(' · ')}</small>}</button>
        <button type="button" onClick={()=>onView('waiting')}><strong>{data.counts.waiting}</strong>Warte auf andere</button>
        <button type="button" onClick={()=>onView('done')}><strong>{data.counts.done}</strong>Erledigte Aufgaben{data.counts.dropped > 0 && <small>{data.counts.dropped} verworfen</small>}</button>
      </div>
      <details className="quiet-details"><summary>Nächste Schritte & Projektstand</summary><div className="project-next">
        <div><h3>Nächste eigene Aufgaben</h3><p className="project-overview-help">Früheste Fristen zuerst · bis zu drei Aufgaben</p>{data.next_tasks.length ? preview(data.next_tasks,'mine') : <p>Keine eigenen offenen Aufgaben.</p>}</div>
        <div><h3>Wartende Punkte</h3><p className="project-overview-help">Am längsten wartende zuerst · bis zu drei Aufgaben</p>{data.waiting_tasks.length ? preview(data.waiting_tasks,'waiting') : <p>Keine wartenden Aufgaben.</p>}</div>
      </div>
      <p className="project-overview-help">Gesamter Projektbestand · unabhängig von der Listensuche · Stand: <time dateTime={data.as_of}>{dateLabel(data.as_of)}</time></p></details>
    </>}
  </section>;
}
