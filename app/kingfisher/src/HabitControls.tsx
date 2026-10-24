import { useEffect, useState } from "react";
import { api } from "./api";
import { ProfileSource } from "./ProfileSource";

type Habit = { id: string; label: string; target_per_week: number; week_start: string; week_end: string; checkins: number; observed_days: string[]; checkin_records: Array<{episode_id: string; day: string}> };
type Evidence = { episode_id: string; quote: string; digest: string };
type Learning = { id: string; statement: string; rationale: string; state: string; evidence: Evidence[]; claim?: { id: string; statement: string; status: string } | null };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...init, credentials: "include", headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json() as Promise<T>;
}

const today = () => new Date().toISOString().slice(0, 10);

export function HabitControls({initiallyOpen = false}: {initiallyOpen?: boolean}) {
  const [habits, setHabits] = useState<Habit[]>([]); const [learning, setLearning] = useState<Learning[]>([]);
  const [label, setLabel] = useState(""); const [target, setTarget] = useState(3); const [day, setDay] = useState(today());
  const [open, setOpen] = useState(initiallyOpen); const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [notice, setNotice] = useState("");
  async function refresh() { const [h, l] = await Promise.all([request<{items: Habit[]}>("/api/v1/habits"), request<{items: Learning[]}>("/api/v1/learning")]); setHabits(h.items); setLearning(l.items); }
  useEffect(() => { void refresh().catch(() => setError("Gewohnheiten sind gerade nicht erreichbar.")); }, []);
  async function run(action: () => Promise<unknown>, message: string) { if (busy) return; setBusy(true); setError(""); try { await action(); await refresh(); setNotice(message); } catch { setError("Die Änderung konnte nicht gespeichert werden. Bitte erneut versuchen."); } finally { setBusy(false); } }
  // Gewohnheiten und Lernen als ein Aufklapper: darin die Gewohnheiten als Zeilen einer Fläche (Woche, Check-ins mit
  // Quelle und Rückgängig), darunter leise das Formular für eine neue und die Lernbeobachtungen mit Belegen.
  const beobachtungen = learning.filter(item => item.state === "pending" || item.state === "accepted");
  return <section className="decision-controls habit-controls" aria-label="Gewohnheiten und Lernen"><details className="g-aufklapper habit-aufklapper" open={open} onToggle={event => setOpen(event.currentTarget.open)}><summary><span className="g-aufklapper-titel">Gewohnheiten & Lernen</span>{habits.length ? <span className="g-aufklapper-neben">{habits.length}</span> : null}</summary>
    <div className="habit-inhalt">
    {habits.length > 0 && <div className="decision-list">{habits.map(habit => <article className="decision-row habit-row" key={habit.id}><div className="decision-row-main"><p className="decision-statement">{habit.label}</p><p>{habit.checkins} von {habit.target_per_week} Tagen diese Woche</p>{habit.checkin_records.map(record => <div className="habit-checkin" key={record.episode_id}><span>{record.day}</span><ProfileSource kind="episode" id={record.episode_id} allowIgnore={false} /><button className="text-action" disabled={busy} onClick={() => void run(() => request(`/api/v1/habits/checkins/${record.episode_id}/retract`, { method: "POST" }), "Check-in zurückgenommen.")}>Rückgängig</button></div>)}<form className="habit-checkin-form" onSubmit={event => { event.preventDefault(); void run(() => request(`/api/v1/habits/${habit.id}/checkins`, { method: "POST", body: JSON.stringify({ day }) }), "Check-in gespeichert."); }}><label>Tag <input type="date" value={day} min="2000-01-01" max={today()} onChange={event => setDay(event.target.value)} /></label><span>UTC</span><button className="secondary-action g-kompakt" disabled={busy || day > today()}>Check-in</button><button type="button" className="text-action" disabled={busy} onClick={() => void run(() => request(`/api/v1/habits/${habit.id}/retract`, { method: "POST" }), "Gewohnheit widerrufen.")}>Widerrufen</button></form></div></article>)}</div>}
    <form className="decision-create-form habit-neu" onSubmit={event => { event.preventDefault(); void run(() => request("/api/v1/habits", { method: "POST", body: JSON.stringify({ label: label.trim(), target_per_week: target }) }).then(() => setLabel("")), "Gewohnheit gespeichert."); }}>
      <label>Neue Gewohnheit<input value={label} onChange={event => setLabel(event.target.value)} required maxLength={4000} placeholder="Etwa: Spaziergang" /></label><label>Tage pro Woche<select value={target} onChange={event => setTarget(Number(event.target.value))}>{[1,2,3,4,5,6,7].map(value => <option key={value} value={value}>{value}</option>)}</select></label><button className="secondary-action" disabled={busy || !label.trim()}>Gewohnheit festhalten</button>
    </form>
    <p className="habit-fussnote">Von dir festgelegte Gewohnheiten. Fehlende Tage sind kein Beweis, dass etwas nicht stattgefunden hat.</p>
    {beobachtungen.length > 0 && <div className="decision-list">{beobachtungen.map(item => <article className="decision-row" key={item.id}><div className="decision-row-main"><p className="decision-statement">{item.statement}</p><p>{item.rationale}</p>{item.state === "accepted" && <p role="status">{item.claim?.status === "active" ? "Von dir bestätigt" : "Nicht mehr als gültiges Wissen verwendbar"}</p>}{item.claim?.status === "active" && <button className="text-action" disabled={busy} onClick={() => void run(() => api.retractClaim(item.claim!.id, "Lernbeobachtung vom Nutzer zurückgenommen."), "Bestätigung zurückgenommen.")}>Bestätigung zurücknehmen</button>}<details><summary>Belege ansehen</summary>{item.evidence.map(evidence => <div key={evidence.episode_id}><blockquote>{evidence.quote}</blockquote><ProfileSource kind="episode" id={evidence.episode_id} onChange={() => { void refresh().catch(() => setError("Aktueller Stand konnte nicht geladen werden.")); }} /></div>)}</details>{item.state === "pending" && <div className="goal-aktionen"><button className="secondary-action g-kompakt" disabled={busy} onClick={() => void run(() => request(`/api/v1/learning/${item.id}/accept`, { method: "POST" }), "Lernvorschlag übernommen.")}>Übernehmen</button><button className="text-action" disabled={busy} onClick={() => void run(() => request(`/api/v1/learning/${item.id}/reject`, { method: "POST" }), "Lernvorschlag verworfen.")}>Verwerfen</button></div>}</div></article>)}</div>}
    <div className="habit-fuss"><button className="g-knopf-schlicht" disabled={busy} onClick={() => void run(() => request("/api/v1/learning/scan", { method: "POST" }), "Beobachtungen geprüft.")}>Beobachtungen prüfen</button>
    {notice && <p role="status">{notice}</p>}{error && <p className="decision-controls-error" role="alert">{error} <button type="button" className="text-action" onClick={() => { void refresh().catch(() => setError("Gewohnheiten sind gerade nicht erreichbar.")); }}>Erneut laden</button></p>}</div>
    </div>
  </details></section>;
}
