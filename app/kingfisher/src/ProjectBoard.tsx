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
  return <div className="workspace-board-column"><h3>{column.label} {tasks && page.total > 0 && <small>{page.total}</small>}</h3>
    {page.loading && <p role="status">Wird geladen …</p>}{page.error && <p role="alert">{page.error}<button onClick={()=>void pager.current!.refresh()}>Erneut laden</button></p>}
    {column.items.map(task=><button key={task.id} className="workspace-board-task" type="button" onClick={()=>onTask(task)}><strong>{task.title}</strong>{task.wartet_auf && <span>Wartet auf {task.wartet_auf}</span>}{task.due && <time dateTime={task.due}>{new Date(task.due).toLocaleDateString('de-DE')}</time>}</button>)}
    {tasks?.length===0 && <p>Keine Aufgaben</p>}
    {tasks && (page.canNext || page.canPrevious) && <small>{tasks.length} von {page.total} · Seite {page.page}</small>}
    {(page.canNext||page.canPrevious) && <nav aria-label={`${column.label}: Seiten`}><button disabled={!page.canPrevious} onClick={()=>void pager.current!.previous()}>Zurück</button><button disabled={!page.canNext} onClick={()=>void pager.current!.next()}>Weitere</button></nav>}
  </div>;
}
