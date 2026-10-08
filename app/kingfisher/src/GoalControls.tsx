import { useEffect, useState, type FormEvent } from "react";
import { GoalHistory } from "./GoalHistory";
import { api } from "./api";
import { taskHref } from "./taskWorkflow";

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
  const [nextStepError, setNextStepError] = useState(false);
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
    if (!nextStepGoal || nextStepBusy || !nextStepTitle.trim()) return;
    setNextStepBusy(true); setNextStepError(false);
    try {
      const task = await api.addTask({title: nextStepTitle.trim(), goal_id: nextStepGoal.id});
      setCreatedTask(task); setNextStepGoal(null); setNextStepTitle("");
    } catch { setNextStepError(true); }
    finally { setNextStepBusy(false); }
  }
  return <section className="decision-controls" aria-label="Persönliche Ziele">
    <div className="decision-controls-heading"><div><h2>Was dir wichtig ist</h2><p>Deine ausdrücklich festgehaltenen Ziele.</p></div><button className="secondary-action" disabled={busy} onClick={() => edit("new")} type="button">+ Ziel</button></div>
    {editing && <form className="decision-create-form" aria-label="Ziel festhalten" onSubmit={event => {event.preventDefault();void run(() => api.saveGoal(statement.trim(), [...new Set(topics.split(",").map(item => item.trim()).filter(Boolean))], editing === "new" ? undefined : editing.id));}}>
      <label>Ziel<textarea aria-label="Ziel" required maxLength={4000} disabled={busy} value={statement} onChange={event => setStatement(event.target.value)} /></label>
      <label>Themen (optional, mit Komma trennen)<input disabled={busy} value={topics} maxLength={500} onChange={event => setTopics(event.target.value)} /></label>
      <p>Gemeinsame Themen können Hinweise auf passende Aktivitäten liefern. Sie beweisen keinen Fortschritt.</p>
      <div className="decision-form-actions"><button className="secondary-action" disabled={busy} onClick={() => setEditing(null)} type="button">Abbrechen</button><button className="primary-action" disabled={busy || !statement.trim()} type="submit">{editing === "new" ? "Ziel festhalten" : "Korrektur bestätigen"}</button></div>
    </form>}
    {closing && <form className="decision-create-form" aria-label="Ziel abschließen" onSubmit={event => {event.preventDefault();void run(() => api.finishGoal(closing.id, outcome, note));}}>
      <p>{closing.satz}</p>
      <label>Abschluss<select aria-label="Abschluss" disabled={busy} value={outcome} onChange={event => setOutcome(event.target.value as "achieved" | "stopped")}><option value="achieved">Erreicht</option><option value="stopped">Nicht mehr verfolgen</option></select></label>
      <label>Notiz (optional)<textarea disabled={busy} maxLength={4000} value={note} onChange={event => setNote(event.target.value)} /></label>
      <p>Das Ziel bleibt im Verlauf erhalten und erscheint nicht mehr als offen.</p>
      <div className="decision-form-actions"><button className="secondary-action" disabled={busy} onClick={() => setClosing(null)} type="button">Abbrechen</button><button className="primary-action" disabled={busy} type="submit">Abschluss speichern</button></div>
    </form>}
    {!goals && !error && <p role="status">Ziele werden geladen …</p>}
    {goals?.length === 0 && <p>{completed.length ? "Kein offenes Ziel." : "Noch kein Ziel festgehalten."}</p>}
    <div className="decision-list">{goals?.map(goal => <article className="decision-row" key={goal.id}><div className="decision-row-main"><p className="decision-statement">{goal.satz}</p>
      <GoalHistory key={`${goal.id}:${revision}`} id={goal.id} />
      {goal.marken.length > 0 && <p>Themen: {goal.marken.join(", ")}</p>}
      {goal.beurteilbar ? <p>{goal.letzte_regung ? `Letzte passende Aktivität: ${new Date(goal.letzte_regung).toLocaleDateString("de-DE")}` : "Noch keine passende Aktivität erfasst."}{goal.woran ? ` · ${goal.woran}` : ""}{goal.schlaeft ? ` Seit ${goal.tage_still} Tagen kein passender Eintrag – bitte selbst zuordnen.` : ""}</p> : <p>Noch keine ausreichende Zuordnung zu Aktivitäten.</p>}
      {nextStepGoal?.id === goal.id ? <form className="decision-create-form" aria-label={`Nächsten Schritt zu ${goal.satz}`} onSubmit={saveNextStep}>
        <label>Nächster Schritt<input autoFocus required maxLength={4096} disabled={nextStepBusy} value={nextStepTitle} onChange={event => setNextStepTitle(event.target.value)} placeholder="Was möchtest du als Nächstes tun?" /></label>
        {nextStepError && <p role="alert">Die Aufgabe konnte nicht mit diesem Ziel verknüpft werden. Das Ziel ist möglicherweise nicht mehr offen. Bitte neu laden.</p>}
        <div className="decision-form-actions"><button type="button" className="text-action" disabled={nextStepBusy} onClick={() => setNextStepGoal(null)}>Abbrechen</button><button type="submit" className="primary-action" disabled={nextStepBusy || !nextStepTitle.trim()}>Aufgabe speichern</button></div>
      </form> : <button className="secondary-action" disabled={busy || nextStepBusy} type="button" onClick={() => {setNextStepGoal(goal);setNextStepTitle("");setNextStepError(false);setCreatedTask(null);}}>Nächsten Schritt festhalten</button>}
      {createdTask?.goal_id === goal.id && <p role="status">Nächster Schritt gespeichert: <a href={taskHref(createdTask)}>Aufgabe öffnen</a></p>}
      <div className="decision-form-actions"><button className="secondary-action" disabled={busy} onClick={() => {setClosing(goal);setEditing(null);setConfirming(null);setOutcome("achieved");setNote("");}} type="button">Ziel abschließen</button>
      <button className="secondary-action" disabled={busy} onClick={() => edit(goal)} type="button">Ziel korrigieren</button>
      <button className="text-action" disabled={busy} onClick={() => setConfirming(goal.id)} type="button">Angabe widerrufen</button></div>
      {confirming === goal.id && <div role="group" aria-label="Zielangabe widerrufen"><p>War diese Zielangabe falsch? Der Widerruf bleibt nachvollziehbar. Er bedeutet nicht, dass das Ziel erreicht wurde.</p><button className="secondary-action" disabled={busy} onClick={() => void run(() => api.retractGoal(goal.id))} type="button">Widerruf bestätigen</button><button className="text-action" disabled={busy} onClick={() => setConfirming(null)} type="button">Abbrechen</button></div>}
    </div></article>)}</div>
    {completed.length > 0 && <details><summary>Abgeschlossene Ziele ({completed.length})</summary><div className="decision-list">{completed.map(goal => <article className="decision-row" key={goal.id}><div className="decision-row-main"><p className="decision-statement">{goal.statement}</p><p>{goal.outcome === "achieved" ? "Erreicht" : "Nicht mehr verfolgt"} · {new Date(goal.recorded_at).toLocaleDateString("de-DE")}</p>{goal.note && <p>{goal.note}</p>}<GoalHistory key={`${goal.id}:${revision}`} id={goal.id} /><button className="secondary-action" disabled={busy} onClick={() => void run(() => api.reopenGoal(goal.id))} type="button">Wieder aufnehmen</button></div></article>)}</div></details>}
    {error && <p role="alert">Die Ziele konnten nicht geladen oder gespeichert werden. <button type="button" disabled={busy} onClick={() => setRevision(value => value + 1)}>Erneut laden</button></p>}
  </section>;
}
