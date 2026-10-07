import {useEffect, useRef, useState} from 'react';
import {api, type Project, type Task} from './api';
import {TaskRow} from './TaskRow';

/** Exact lookup also works when a task is outside the current list/filter. */
export function TaskDetail({taskId, onChanged}: {taskId: string; onChanged: () => void}) {
  const [task, setTask] = useState<Task | null>(null);
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
  return <div className="task-detail">
    {!task && !error && <p role="status">Aufgabe wird geladen …</p>}
    {error && <p role="alert">{error}{!task && <button type="button" onClick={() => setRevision(value => value + 1)}>Erneut laden</button>}</p>}
    {projectsFailed && <p role="status">Projekte konnten nicht geladen werden. Die Projektzuordnung bleibt erhalten. <button type="button" disabled={busy} onClick={() => setProjectRevision(value => value + 1)}>Projekte erneut laden</button></p>}
    {task?.status === "dropped" && <p>Diese Aufgabe wurde verworfen: {task.title}</p>}
    {task && task.status !== "dropped" && <TaskRow task={task} view={task.status === 'done' ? 'done' : task.wartet_auf ? 'waiting' : 'mine'} completing={busy}
      projects={projects} projectDisabled={projectsFailed || projectsLoading} onProjectChange={id => {void change(() => api.assignTaskProject(task.id, id || null));}}
      onEdit={data => change(() => api.editTask(task.id, data))}
      onWait={name => {void change(() => name ? api.waitTask(task.id, name) : api.unwaitTask(task.id));}}
      onComplete={() => {void change(() => task.status === 'done' ? api.reopenTask(task.id) : api.completeTask(task.id));}} />}
  </div>;
}
