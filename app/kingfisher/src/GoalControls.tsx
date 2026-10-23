import { useEffect, useRef, useState, type FormEvent } from "react";
import { GoalHistory } from "./GoalHistory";
import { api, ApiError } from "./api";
import {TaskSaveAttempt, TaskSavePreparationError, goalTaskRequestKey, TASK_SAVE_UNCONFIRMED, TASK_SAVE_PENDING} from './taskSaveAttempt';
import {TaskRetryReview} from './TaskRetryReview';
import { taskHref } from "./taskWorkflow";
import { Leer } from "./grundlage";

type Goal = Awaited<ReturnType<typeof api.goals>>["items"][number];
export function GoalControls() {
  const [goals, setGoals] = useState<Goal[] | null>(null);
  const [completed, setCompleted] = useState<Awaited<ReturnType<typeof api.goals>>["completed"]>([]);
  const [closing, setClosing] = useState<Goal | null>(null);
  const [outcome, setOutcome] = useState<"achieved" | "stopped">("achieved");
  const [note, setNote] = useState("");
  const [editing, setEditing] = useState<Goal | "new" | null>(null);
  const [statement, setStatement] = useState("");
  const [topics, setTopics] = useState("");
  const [confirming, setConfirming] = useState<string | null>(null);
  const [nextStepGoal, setNextStepGoal] = useState<Goal | null>(null);
  const [nextStepTitle, setNextStepTitle] = useState("");
  const [nextStepBusy, setNextStepBusy] = useState(false);
  const [nextStepError, setNextStepError] = useState("");
  const [nextStepReviewed, setNextStepReviewed] = useState(false);
  const nextStepSave = useRef(new TaskSaveAttempt());
  const [createdTask, setCreatedTask] = useState<Awaited<ReturnType<typeof api.addTask>> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {let active = true;setError(false);api.goals().then(result => {if (active) {setGoals(result.items);setCompleted(result.completed ?? []);}}).catch(() => {if (active) setError(true);});return () => {active = false;};}, [revision]);
  function edit(goal: Goal | "new") {setClosing(null);setEditing(goal);setStatement(goal === "new" ? "" : goal.satz);setTopics(goal === "new" ? "" : goal.marken.join(", "));setConfirming(null);}
  async function run(action: () => Promise<unknown>) {
    if (busy) return;
    setBusy(true);setError(false);
    try {await action();setClosing(null);setEditing(null);setConfirming(null);setRevision(value => value + 1);}
    catch {setError(true);}
    finally {setBusy(false);}
  }
  async function saveNextStep(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const attempt = nextStepSave.current;
    if (!nextStepGoal || nextStepBusy || attempt.inFlight || attempt.succeeded || !nextStepTitle.trim()) return;
    setNextStepBusy(true); setNextStepError(""); setNextStepReviewed(false);
    try {
      const task = await attempt.save({title: nextStepTitle.trim(), goal_id: nextStepGoal.id}, api.addTask);
      if (!task) return;
      setCreatedTask(task); setNextStepGoal(null); setNextStepTitle("");
    } catch (cause) {setNextStepError(cause instanceof TaskSavePreparationError ? `${cause.message} Es wurde keine Aufgabe gesendet.` : cause instanceof ApiError && cause.status === 409 ? (cause.detail ?? TASK_SAVE_UNCONFIRMED) : TASK_SAVE_UNCONFIRMED);}
    finally { setNextStepBusy(false); }
  }
  function openNextStep(goal: Goal) {
    if (nextStepSave.current.inFlight) return;
    nextStepSave.current = new TaskSaveAttempt(undefined, goalTaskRequestKey(goal.id));
    setNextStepGoal(goal); setNextStepTitle(""); setNextStepReviewed(false); setCreatedTask(null);
    try {setNextStepError(nextStepSave.current.restore() ? TASK_SAVE_PENDING : "");}
    catch (cause) {setNextStepError(`${cause instanceof Error ? cause.message : 'Der lokale Speicher ist nicht verfügbar.'} Es wurde keine Aufgabe gesendet.`);}
  }
  function prepareNewNextStepRequest() {
    if (!nextStepReviewed || nextStepBusy || nextStepSave.current.inFlight) return;
    try {nextStepSave.current.resetAfterReview(); setNextStepReviewed(false); setNextStepError("");}
    catch {setNextStepError('Der neue Speicherauftrag konnte nicht vorbereitet werden. Bitte den lokalen Speicher und andere offene Aufgabenfenster prüfen. Es wurde keine Aufgabe gesendet.');}
  }
  // Ziele als Gruppe: klein die Überschrift, rechts „Ziel festhalten“ (der eine gefüllte Knopf, solange kein Formular
  // offen ist); je Ziel eine Zeile mit dem Satz, einer leisen Zeile zu Themen und Aktivität und leisen Aktionen.
  const formularOffen = Boolean(editing || closing || nextStepGoal);
  return <section className="decision-controls goal-controls" aria-label="Persönliche Ziele">
    <div className="decision-controls-heading"><h2 className="goal-titel">Was dir wichtig ist</h2>{!editing && <button className={formularOffen ? "secondary-action" : "primary-action"} disabled={busy} onClick={() => edit("new")} type="button">Ziel festhalten</button>}</div>
    {editing && <form className="decision-create-form" aria-label="Ziel festhalten" onSubmit={event => {event.preventDefault();void run(() => api.saveGoal(statement.trim(), [...new Set(topics.split(",").map(item => item.trim()).filter(Boolean))], editing === "new" ? undefined : editing.id));}}>
      <label>Ziel<textarea aria-label="Ziel" autoFocus required maxLength={4000} disabled={busy} value={statement} onChange={event => setStatement(event.target.value)} /></label>
      <label>Themen, mit Komma getrennt<input disabled={busy} value={topics} maxLength={500} onChange={event => setTopics(event.target.value)} /></label>
      <p>Gemeinsame Themen können Hinweise auf passende Aktivitäten liefern. Sie beweisen keinen Fortschritt.</p>
      <div className="decision-form-actions"><button className="g-knopf-schlicht" disabled={busy} onClick={() => setEditing(null)} type="button">Abbrechen</button><button className="primary-action" disabled={busy || !statement.trim()} type="submit">{editing === "new" ? "Ziel festhalten" : "Korrektur bestätigen"}</button></div>
    </form>}
    {closing && <form className="decision-create-form" aria-label="Ziel abschließen" onSubmit={event => {event.preventDefault();void run(() => api.finishGoal(closing.id, outcome, note));}}>
      <p className="goal-formular-satz">{closing.satz}</p>
      <label>Abschluss<select aria-label="Abschluss" disabled={busy} value={outcome} onChange={event => setOutcome(event.target.value as "achieved" | "stopped")}><option value="achieved">Erreicht</option><option value="stopped">Nicht mehr verfolgen</option></select></label>
      <label>Notiz<textarea disabled={busy} maxLength={4000} value={note} onChange={event => setNote(event.target.value)} /></label>
      <p>Das Ziel bleibt im Verlauf erhalten und erscheint nicht mehr als offen.</p>
      <div className="decision-form-actions"><button className="g-knopf-schlicht" disabled={busy} onClick={() => setClosing(null)} type="button">Abbrechen</button><button className="primary-action" disabled={busy} type="submit">Abschluss speichern</button></div>
    </form>}
    {!goals && !error && <p className="decision-muted" role="status">Ziele werden geladen …</p>}
    {goals?.length === 0 && !editing && <Leer className="decision-leer" zeichen="check" satz={completed.length ? "Kein offenes Ziel." : "Noch kein Ziel festgehalten."} />}
    {goals && goals.length > 0 && <div className="decision-list">{goals.map(goal => <article className="decision-row goal-row" key={goal.id}><div className="decision-row-main"><p className="decision-statement">{goal.satz}</p>
      <p className="goal-stand">{goal.marken.length > 0 && <span>{goal.marken.join(", ")}</span>}<span>{goal.beurteilbar ? <>{goal.letzte_regung ? `Letzte passende Aktivität: ${new Date(goal.letzte_regung).toLocaleDateString("de-DE")}` : "Noch keine passende Aktivität erfasst."}{goal.woran ? ` · ${goal.woran}` : ""}{goal.schlaeft ? ` Seit ${goal.tage_still} Tagen kein passender Eintrag – bitte selbst zuordnen.` : ""}</> : "Noch keine ausreichende Zuordnung zu Aktivitäten."}</span></p>
      {nextStepGoal?.id === goal.id ? <form className="decision-create-form goal-schritt" aria-label={`Nächsten Schritt zu ${goal.satz}`} onSubmit={saveNextStep}>
        <label>Nächster Schritt<input autoFocus required maxLength={4096} disabled={nextStepBusy} value={nextStepTitle} onChange={event => setNextStepTitle(event.target.value)} placeholder="Was möchtest du als Nächstes tun?" /></label>
        {nextStepError && <p className="goal-fehler" role="alert">{nextStepError}</p>}
        {nextStepError && <TaskRetryReview reviewed={nextStepReviewed} busy={nextStepBusy} onReviewed={setNextStepReviewed} onPrepareNew={prepareNewNextStepRequest} />}
        <div className="decision-form-actions"><button type="button" className="g-knopf-schlicht" disabled={nextStepBusy} onClick={() => setNextStepGoal(null)}>Abbrechen</button><button type="submit" className="primary-action" disabled={nextStepBusy || !nextStepTitle.trim()}>Aufgabe speichern</button></div>
      </form> : null}
      {createdTask?.goal_id === goal.id && <p className="goal-gespeichert" role="status">Nächster Schritt gespeichert: <a href={taskHref(createdTask)}>Aufgabe öffnen</a></p>}
      <div className="goal-aktionen">{nextStepGoal?.id !== goal.id && <button className="secondary-action g-kompakt" disabled={busy || nextStepBusy} type="button" onClick={() => openNextStep(goal)}>Nächsten Schritt festhalten</button>}
      <button className="text-action" disabled={busy} onClick={() => {setClosing(goal);setEditing(null);setConfirming(null);setOutcome("achieved");setNote("");}} type="button">Abschließen</button>
      <button className="text-action" disabled={busy} onClick={() => edit(goal)} type="button">Korrigieren</button>
      <button className="text-action" disabled={busy} onClick={() => setConfirming(goal.id)} type="button">Widerrufen</button></div>
      {confirming === goal.id && <div className="goal-rueckfrage" role="group" aria-label="Zielangabe widerrufen"><p>War diese Zielangabe falsch? Der Widerruf bleibt nachvollziehbar. Er bedeutet nicht, dass das Ziel erreicht wurde.</p><button className="secondary-action decision-confirm g-kompakt" disabled={busy} onClick={() => void run(() => api.retractGoal(goal.id))} type="button">Widerruf bestätigen</button><button className="text-action" disabled={busy} onClick={() => setConfirming(null)} type="button">Abbrechen</button></div>}
      <GoalHistory key={`${goal.id}:${revision}`} id={goal.id} />
    </div></article>)}</div>}
    {completed.length > 0 && <details className="g-aufklapper goal-abgeschlossen"><summary><span className="g-aufklapper-titel">Abgeschlossene Ziele</span><span className="g-aufklapper-neben">{completed.length}</span></summary><div className="decision-list">{completed.map(goal => <article className="decision-row" key={goal.id}><div className="decision-row-main"><p className="decision-statement">{goal.statement}</p><p>{goal.outcome === "achieved" ? "Erreicht" : "Nicht mehr verfolgt"} · {new Date(goal.recorded_at).toLocaleDateString("de-DE")}</p>{goal.note && <p>{goal.note}</p>}<div className="goal-aktionen"><button className="text-action" disabled={busy} onClick={() => void run(() => api.reopenGoal(goal.id))} type="button">Wieder aufnehmen</button></div><GoalHistory key={`${goal.id}:${revision}`} id={goal.id} /></div></article>)}</div></details>}
    {error && <p className="decision-controls-error" role="alert">Die Ziele konnten nicht geladen oder gespeichert werden. <button type="button" className="text-action" disabled={busy} onClick={() => setRevision(value => value + 1)}>Erneut laden</button></p>}
  </section>;
}
