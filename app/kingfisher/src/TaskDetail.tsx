import {useEffect, useRef, useState} from 'react';
import {api, type Project, type Task} from './api';
import {TaskRow} from './TaskRow';
import {navigate} from './ui';
import {zeigeHinweis, zitat, type HinweisDaten} from './grundlage';
import {erledigtHinweis, POST_ZURUECK, verworfenHinweis, wartetHinweis, wiederOffenHinweis, zurueckZuMirHinweis} from './aufgabenHinweis';

/** Exact lookup also works when a task is outside the current list/filter. */
export function TaskDetail({taskId, onChanged, editing = false}: {taskId: string; onChanged: () => void; editing?: boolean}) {
  const [task, setTask] = useState<Task | null>(null);
  const [goalStatement, setGoalStatement] = useState<string | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectsFailed, setProjectsFailed] = useState(false);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectRevision, setProjectRevision] = useState(0);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const alive = useRef(true);
  const lifecycle = useRef(0);
  useEffect(() => {
    lifecycle.current++;
    alive.current = true;
    pending.current = false; setBusy(false);
    let active = true;
    setTask(null); setError('');
    api.task(taskId).then(value => {if (active) setTask(value);}).catch(() => {
      if (active) setError('Diese Aufgabe ist nicht verfügbar. Sie wurde möglicherweise entfernt.');
    });
    return () => {active = false; alive.current = false; lifecycle.current++;};
  }, [taskId, revision]);
  useEffect(() => {
    let active = true;
    if (!task?.goal_id) {setGoalStatement(null); return () => {active = false;};}
    setGoalStatement(null);
    api.goalHistory(task.goal_id).then(history => {
      if (active) setGoalStatement(history.find(item => item.id === task.goal_id)?.statement ?? "Zielangabe nicht mehr verfügbar");
    }).catch(() => {
      if (active) setGoalStatement("Zielangabe nicht verfügbar");
    });
    return () => {active = false;};
  }, [task?.goal_id]);
  useEffect(() => {
    let active = true;
    setProjectsLoading(true); setProjectsFailed(false);
    api.projects().then(value => {if (active) setProjects(value);})
      .catch(() => {if (active) setProjectsFailed(true);})
      .finally(() => {if (active) setProjectsLoading(false);});
    return () => {active = false;};
  }, [projectRevision]);
  async function change(operation: () => Promise<Task>) {
    if (pending.current) return false;
    const version = lifecycle.current;
    pending.current = true; setBusy(true); setError('');
    try {
      const value = await operation();
      if (alive.current && version === lifecycle.current) {setTask(value); onChanged();}
      return true;
    } catch {
      if (alive.current && version === lifecycle.current) setError('Die Änderung wurde nicht bestätigt. Deine Eingaben bleiben erhalten. Bitte erneut versuchen.');
      return false;
    } finally {if (version === lifecycle.current) {pending.current = false; if (alive.current) setBusy(false);}}
  }
  // Jede Änderung antwortet mit dem Hinweis unten; dessen „Rückgängig“ geht über die Gegenroute und wirft, wenn sie
  // nicht bestätigt wurde (dann sagt der Hinweis es).
  async function mitHinweis(operation: () => Promise<Task>, hinweis: HinweisDaten) {
    const wegZurueck = hinweis.rueckgaengig;
    const daten = wegZurueck ? {...hinweis, rueckgaengig: async () => { if (!await wegZurueck()) throw new Error('nicht bestätigt'); }} : hinweis;
    if (await change(operation)) zeigeHinweis(daten);
  }
  return <div className="task-detail">
    {new URLSearchParams(window.location.search).get('from')==='memory'&&<button type="button" className="text-action" onClick={()=>window.history.back()}>Zur vorherigen Gedächtnisansicht</button>}
    {!task && !error && <p className="task-detail-satz" role="status">Aufgabe wird geladen …</p>}
    {error && <p className="task-detail-satz task-detail-fehler" role="alert">{error}{!task && <> <button type="button" className="text-action" onClick={() => setRevision(value => value + 1)}>Erneut laden</button></>}</p>}
    {task?.goal_id && <p className="task-goal-link"><strong>Zielbezug:</strong> {goalStatement ?? "Ziel wird geladen …"}</p>}
    {projectsFailed && <p className="task-detail-satz" role="status">Projekte konnten nicht geladen werden. Die Projektzuordnung bleibt erhalten. <button type="button" className="text-action" disabled={busy} onClick={() => setProjectRevision(value => value + 1)}>Projekte erneut laden</button></p>}
    {task?.status === "dropped" && <div className="task-detail-verworfen"><p>Diese Aufgabe wurde verworfen: {task.title}</p><button type="button" className="secondary-action" disabled={busy} onClick={()=>void mitHinweis(()=>api.reopenTask(task.id), {text: `${zitat(task.title)} ist wieder offen.`, rueckgaengig: () => change(() => api.dropTask(task.id)), danach: `${zitat(task.title)} verworfen.`})}>Aufgabe wieder aufnehmen</button></div>}
    {task && task.status !== "dropped" && <TaskRow task={task} view={task.status === 'done' ? 'done' : task.wartet_auf ? 'waiting' : 'mine'} completing={busy}
      projects={projects} projectDisabled={projectsFailed || projectsLoading} onProjectChange={id => {void change(() => api.assignTaskProject(task.id, id || null));}}
      onEdit={data => change(() => api.editTask(task.id, data))}
      onWait={name => {void mitHinweis(() => name ? api.waitTask(task.id, name) : api.unwaitTask(task.id), name
        ? wartetHinweis(task, name, () => change(() => api.unwaitTask(task.id)))
        : zurueckZuMirHinweis(task, task.wartet_auf, vorher => change(() => api.waitTask(task.id, vorher))));}}
      onComplete={() => {void mitHinweis(() => task.status === 'done' ? api.reopenTask(task.id) : api.completeTask(task.id), task.status === 'done'
        ? wiederOffenHinweis(task, () => change(() => api.completeTask(task.id)))
        : erledigtHinweis(task, () => change(() => api.reopenTask(task.id))));}}
      onRueckgaengig={() => {void mitHinweis(() => api.taskRueckgaengig(task.id), {text: POST_ZURUECK});}} startEditing={editing} />}
    {/* Seltenes steht unter der Aufgabe, nicht davor: erst die Sache, dann der Weg weg von ihr. */}
    {task && (task.project_id || task.status === 'open') && <p className="task-detail-more">
      {task.project_id&&<button type="button" className="text-action" onClick={()=>navigate(`/memory/projects/${encodeURIComponent(task.project_id!)}?${new URLSearchParams({return_to:'/memory?tab=projects'})}`)}>Projekt im Gedächtnis öffnen</button>}
      {task.status==='open'&&<button type="button" className="text-action" disabled={busy} onClick={()=>void mitHinweis(()=>api.dropTask(task.id), verworfenHinweis(task, () => change(() => api.reopenTask(task.id))))}>Aufgabe verwerfen</button>}
    </p>}
  </div>;
}
