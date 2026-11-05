import {useEffect,useRef,useState} from 'react';
import {Zeile} from './grundlage';
import {api,type Task,type TaskListView} from './api';
import {TaskPager,initialTaskPage,type TaskPageState} from './taskPager';
import {projectBoardViews, projectColumns} from './taskWorkspaceModel';
import {responsibilityLabel} from './taskResponsibilityModel';

export function ProjectBoard({projectId,revision,onTask}: {projectId:string; revision:number; onTask:(task:Task)=>void}) {
  return <section className="workspace-board" aria-label="Projektboard">
    {projectBoardViews.map(({view, label})=><BoardColumn key={view} view={view} label={label} projectId={projectId} revision={revision} onTask={onTask}/>)}
  </section>;
}

function BoardColumn({view,label,projectId,revision,onTask}: {view:TaskListView;label:string;projectId:string;revision:number;onTask:(task:Task)=>void}) {
  const [page,setPage]=useState<TaskPageState>(initialTaskPage);
  const pager=useRef<TaskPager|null>(null);
  if(!pager.current) pager.current=new TaskPager((s,c)=>api.tasks(s.view,s.projectId,{q:s.q,cursor:c}),setPage);
  useEffect(()=>{void pager.current!.select({view,projectId,q:''});return()=>pager.current!.cancel();},[view,projectId,revision]);
  const key=JSON.stringify({view,projectId,q:''});
  const tasks=page.selectionKey===key ? page.tasks : null;
  const items = projectColumns(tasks ?? []).find(column => column.view === view)?.items ?? [];
  // Eine Spalte ist eine Gruppe: klein der Name mit Zahl, darunter eine Fläche mit ganzen, klickbaren Zeilen.
  return <section className="workspace-board-column g-gruppe" aria-label={label}><h3 className="g-gruppe-titel">{label} {tasks && page.total > 0 && <small>{page.total}</small>}</h3>
    {page.loading && <p className="workspace-board-satz" role="status">Wird geladen …</p>}{page.error && <p className="workspace-board-satz" role="alert">{page.error} <button type="button" className="text-action" onClick={()=>void pager.current!.refresh()}>Erneut laden</button></p>}
    {items.length > 0 && <div className="g-flaeche">{items.map(task=><Zeile key={task.id} className="workspace-board-task" onClick={()=>onTask(task)} titel={task.title} neben={[`Zuständigkeit: ${responsibilityLabel(task.responsibility)}`, task.wartet_auf && `Wartet auf ${task.wartet_auf}`].filter(Boolean).join(' · ')} wert={task.due ? new Date(task.due).toLocaleDateString('de-DE', {day: 'numeric', month: 'short'}) : undefined} wertZeit={task.due ?? undefined} />)}</div>}
    {tasks?.length===0 && <p className="workspace-board-satz">Keine Aufgaben</p>}
    {tasks && (page.canNext || page.canPrevious) && <p className="workspace-board-satz">{tasks.length} von {page.total} · Seite {page.page}</p>}
    {(page.canNext||page.canPrevious) && <nav className="workspace-board-seiten" aria-label={`${label}: Seiten`}><button type="button" className="g-knopf-getoent g-kompakt" disabled={!page.canPrevious} onClick={()=>void pager.current!.previous()}>Zurück</button><button type="button" className="g-knopf-getoent g-kompakt" disabled={!page.canNext} onClick={()=>void pager.current!.next()}>Weitere</button></nav>}
  </section>;
}
