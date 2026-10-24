import {useEffect,useRef,useState} from 'react';
import {api,type Task} from './api';
import {TaskPager,initialTaskPage,type TaskPageState} from './taskPager';
import {projectColumns} from './taskWorkspaceModel';

export function ProjectBoard({projectId,revision,onTask}: {projectId:string; revision:number; onTask:(task:Task)=>void}) {
  return <section className="workspace-board" aria-label="Projektboard">
    {(['mine','waiting','done'] as const).map(view=><BoardColumn key={view} view={view} projectId={projectId} revision={revision} onTask={onTask}/>)}
  </section>;
}

function BoardColumn({view,projectId,revision,onTask}: {view:'mine'|'waiting'|'done';projectId:string;revision:number;onTask:(task:Task)=>void}) {
  const [page,setPage]=useState<TaskPageState>(initialTaskPage);
  const pager=useRef<TaskPager|null>(null);
  if(!pager.current) pager.current=new TaskPager((s,c)=>api.tasks(s.view,s.projectId,{q:s.q,cursor:c}),setPage);
  useEffect(()=>{void pager.current!.select({view,projectId,q:''});return()=>pager.current!.cancel();},[view,projectId,revision]);
  const key=JSON.stringify({view,projectId,q:''});
  const tasks=page.selectionKey===key ? page.tasks : null;
  const index=view==='mine'?0:view==='waiting'?1:2;
  const column=projectColumns(tasks??[])[index];
  // Eine Spalte ist eine Gruppe: klein der Name mit Zahl, darunter eine Fläche mit ganzen, klickbaren Zeilen.
  return <section className="workspace-board-column g-gruppe" aria-label={column.label}><h3 className="g-gruppe-titel">{column.label} {tasks && page.total > 0 && <small>{page.total}</small>}</h3>
    {page.loading && <p className="workspace-board-satz" role="status">Wird geladen …</p>}{page.error && <p className="workspace-board-satz" role="alert">{page.error} <button type="button" className="text-action" onClick={()=>void pager.current!.refresh()}>Erneut laden</button></p>}
    {column.items.length > 0 && <div className="g-flaeche">{column.items.map(task=><button key={task.id} className="workspace-board-task g-zeile" type="button" onClick={()=>onTask(task)}><span className="g-zeile-text"><span className="g-zeile-titel">{task.title}</span>{task.wartet_auf && <span className="g-zeile-neben">Wartet auf {task.wartet_auf}</span>}</span>{task.due && <time className="g-zeile-wert" dateTime={task.due}>{new Date(task.due).toLocaleDateString('de-DE', {day: 'numeric', month: 'short'})}</time>}</button>)}</div>}
    {tasks?.length===0 && <p className="workspace-board-satz">Keine Aufgaben</p>}
    {tasks && (page.canNext || page.canPrevious) && <p className="workspace-board-satz">{tasks.length} von {page.total} · Seite {page.page}</p>}
    {(page.canNext||page.canPrevious) && <nav className="workspace-board-seiten" aria-label={`${column.label}: Seiten`}><button type="button" className="g-knopf-getoent g-kompakt" disabled={!page.canPrevious} onClick={()=>void pager.current!.previous()}>Zurück</button><button type="button" className="g-knopf-getoent g-kompakt" disabled={!page.canNext} onClick={()=>void pager.current!.next()}>Weitere</button></nav>}
  </section>;
}
