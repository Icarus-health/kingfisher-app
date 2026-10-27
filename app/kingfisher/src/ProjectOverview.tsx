import {useEffect, useState} from 'react';
import {Zeile} from './grundlage';
import {api, type ProjectTaskOverview, type Task} from './api';
import './ProjectOverview.css';

type View = 'mine' | 'waiting' | 'done';
function dateLabel(value: string | null) {
  if (!value) return 'Ohne Termin';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Termin nicht lesbar' : date.toLocaleString('de-DE', {day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'});
}

export function ProjectOverview({projectId, bereich = '', revision, onView, onTask}: {
  projectId: string; bereich?: string; revision: number;
  onView: (view: View) => void; onTask: (id: string, view: View) => void;
}) {
  const [result,setResult] = useState<ProjectTaskOverview | null>(null);
  const [error,setError] = useState('');
  useEffect(() => {
    let active = true;
    setResult(null); setError('');
    // Mit dem Bereich der Liste: dieselbe Auswahl wie darunter (Paket Z1).
    if (projectId) api.projectOverview(projectId, bereich).then(value => {
      if (active) setResult(value);
    }).catch(() => {if(active) setError('Der Projektüberblick ist gerade nicht erreichbar.');});
    return () => {active=false;};
  }, [projectId,revision,bereich]);
  if (!projectId) return null;
  const data = result?.project_id === projectId ? result : null;
  function preview(tasks: Task[], view: 'mine' | 'waiting') {
    // Jede Aufgabe eine ganze, klickbare Zeile (Baustein-Klassen g-zeile), rechts die Fälligkeit.
    return <div className="g-flaeche">{tasks.map(task => <Zeile key={task.id} className="project-task-link" onClick={() => onTask(task.id,view)} titel={task.title}
      neben={view === 'waiting' ? `Bei ${task.wartet_auf}${task.wartet_tage !== null ? ` · seit ${task.wartet_tage} Tagen` : ''}` : undefined}
      wert={dateLabel(task.due)} wertZeit={task.due ?? ''} wertKlasse={task.overdue ? 'overdue' : undefined} />)}</div>;
  }
  // Projekt auf einen Blick: drei Kacheln (offen, wartet, erledigt), jede öffnet die passende Liste; darunter leise die
  // nächsten Schritte. Die Zahlen gelten für das ganze Projekt, unabhängig von der Suche.
  return <section className="project-overview" aria-label="Projekt auf einen Blick">
    {/* Kein eigener Knopf zum Aktualisieren: Der Überblick lädt nach jeder Änderung in der Liste neu (`revision`). */}
    {error ? <p className="project-overview-satz" role="alert">{error}</p> : !data ? <p className="project-overview-satz" role="status">Projektüberblick wird geladen …</p> : <>
      <div className="project-counts">
        <button type="button" onClick={()=>onView('mine')}><strong>{data.counts.mine}</strong>Offen{(data.counts.overdue > 0 || data.counts.undated > 0) && <small>{[data.counts.overdue ? `${data.counts.overdue} überfällig` : '', data.counts.undated ? `${data.counts.undated} ohne Termin` : ''].filter(Boolean).join(' · ')}</small>}</button>
        <button type="button" onClick={()=>onView('waiting')}><strong>{data.counts.waiting}</strong>Wartet</button>
        <button type="button" onClick={()=>onView('done')}><strong>{data.counts.done}</strong>Erledigt{data.counts.dropped > 0 && <small>{data.counts.dropped} verworfen</small>}</button>
      </div>
      <details className="g-aufklapper project-next-details"><summary><span className="g-aufklapper-titel">Nächste Schritte</span></summary><div className="project-next">
        <div><h3>Als Nächstes</h3>{data.next_tasks.length ? preview(data.next_tasks,'mine') : <p>Keine eigenen offenen Aufgaben.</p>}</div>
        <div><h3>Wartet</h3>{data.waiting_tasks.length ? preview(data.waiting_tasks,'waiting') : <p>Keine wartenden Aufgaben.</p>}</div>
      </div>
      <p className="project-overview-help">Je bis zu drei, früheste Frist und längste Wartezeit zuerst · ganzes Projekt, unabhängig von der Suche · Stand <time dateTime={data.as_of}>{dateLabel(data.as_of)}</time></p></details>
    </>}
  </section>;
}
