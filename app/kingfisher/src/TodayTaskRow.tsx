import {useEffect, useRef, useState} from 'react';
import {api, type Attention, type Task} from './api';
import {TaskRow} from './TaskRow';
import {zeigeHinweis} from './grundlage';
import {erledigtHinweis} from './aufgabenHinweis';

/** Was Heute von einer Aufgabe weiß, wenn der Sidecar sie (älterer Stand) nicht mitliefert: Kennung und Titel. */
export function aufgabeAusPunkt(item: Attention): Task {
  if (item.task && item.task.id === item.source_ref) return item.task;
  return {id: item.source_ref ?? item.id, title: item.title, status: 'open', created_at: '', due: null, notes: null, tags: [],
    project_id: item.project_id ?? null, wartet_auf: null, wartet_seit: null, wartet_tage: null, overdue: false};
}

/**
 * Eine Aufgabe unter „Braucht dich“ (V1): dieselbe Zeile wie in der Aufgabenliste (`TaskRow`, compact). Der Kreis
 * erledigt sofort und füllt sich; die ganze Zeile öffnet die Aufgabe (`onOpen`). Erledigt antwortet der Hinweis unten
 * mit „Rückgängig“ (V4); was nicht bestätigt wurde, sagt die Zeile darunter. `onChanged` lädt Heute neu. Projekt und „Warte auf …“ stehen in der geöffneten Aufgabe, nicht in der Zeile.
 */
export function TodayTaskRow({item, onChanged, onOpen}: {item: Attention; onChanged: () => void; onOpen: () => void}) {
  const [busy, setBusy] = useState(false);
  const [erledigt, setErledigt] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef(false);
  const alive = useRef(true);
  useEffect(() => {alive.current = true; return () => {alive.current = false;};}, []);
  const task = aufgabeAusPunkt(item);
  const waiting = item.source === 'wartet' || Boolean(task.wartet_auf);
  async function erledigen() {
    if (pending.current || erledigt) return;
    pending.current = true; setBusy(true); setError('');
    try {
      await api.completeTask(task.id);
      if (alive.current) setErledigt(true);
      onChanged();
      zeigeHinweis(erledigtHinweis(task, async () => {
        await api.reopenTask(task.id);
        if (alive.current) setErledigt(false);
        onChanged();
      }));
    } catch {if (alive.current) setError('Nicht erledigt: Die Änderung wurde nicht bestätigt. Bitte erneut versuchen.');}
    finally {pending.current = false; if (alive.current) setBusy(false);}
  }
  const keine = async () => false;
  return <div className="today-task">
    <TaskRow compact ohneAktionen task={erledigt ? {...task, status: 'done'} : task} view={waiting ? 'waiting' : 'mine'}
      completing={busy || erledigt} onComplete={() => void erledigen()} onOpen={onOpen} projects={[]}
      projektName={item.project_name} hinweis={item.action === 'Verlauf prüfen' ? 'Verlauf ungeprüft' : undefined}
      onProjectChange={() => undefined} onWait={() => undefined} onEdit={keine} />
    {error && <p className="today-task-fehler" role="alert">{error}</p>}
  </div>;
}
