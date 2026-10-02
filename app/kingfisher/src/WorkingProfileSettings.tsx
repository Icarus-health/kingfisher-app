import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, type WorkingProfile } from "./api";

const FIELDS = {answer_length: "Antwortlänge", address: "Anrede", emoji: "Emojis"};
const VALUES: Record<string, Record<string, string>> = {answer_length: {short: "Kurz", detailed: "Ausführlich"}, address: {du: "Du", sie: "Sie"}, emoji: {yes: "Erlaubt", no: "Ohne Emojis"}};
const AREAS: Record<string, string> = {"": "Allgemein", analysis: "Analysen", mail: "E-Mails", planning: "Planung"};

export function WorkingProfileSettings() {
  const [area, setArea] = useState("");
  const [field, setField] = useState("answer_length");
  const [value, setValue] = useState("short");
  const [data, setData] = useState<WorkingProfile | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [attempt, setAttempt] = useState(0);
  const generation = useRef(0);
  useEffect(() => {
    const current = ++generation.current;
    setData(null); setError("");
    api.workingProfile(area).then(result => {if (current === generation.current) setData(result);})
      .catch(() => {if (current === generation.current) setError("Arbeitsvorlieben konnten nicht geladen werden.");});
    return () => {generation.current++;};
  }, [area, attempt]);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await api.saveWorkingPreference({key: field, value, scope: area ? "task" : "global", scope_key: area || null});
      setData(await api.workingProfile(area));
      setMessage("Arbeitsvorliebe gespeichert. Sie gilt ab der nächsten passenden Antwort.");
    } catch {setError("Speichern konnte nicht bestätigt werden. Bitte neu laden und den Stand prüfen.");}
    finally {setBusy(false);}
  }
  async function retract(id: string) {
    if (busy) return; setBusy(true); setError(""); setMessage("");
    try {
      await api.retractWorkingPreference(id);
      setData(await api.workingProfile(area));
      setMessage("Arbeitsvorliebe widerrufen. Eine allgemeinere Regel kann wieder gelten.");
    } catch {setError("Widerruf konnte nicht bestätigt werden. Bitte neu laden und den Stand prüfen.");}
    finally {setBusy(false);}
  }
  return <section className="source-section compact-model" aria-label="Arbeitsvorlieben">
    <div className="compact-integration-heading"><div><h2>Arbeitsvorlieben</h2></div></div>
    <p className="source-hint">Hier bestätigst du deine Regeln selbst. Aufgabenbezogene Vorlieben gelten nur für die erkannte Aufgabe. Eine aktuelle Bitte wie „diesmal kurz“ gilt nur für diese Antwort. Belegantworten behalten den Wortlaut der Quelle.</p>
    <form className="source-form" onSubmit={save}>
      <label>Bereich<select disabled={busy} value={area} onChange={e => {setArea(e.target.value); setMessage("");}}>{Object.entries(AREAS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <label>Vorliebe<select disabled={busy} value={field} onChange={e => {setField(e.target.value); setValue(Object.keys(VALUES[e.target.value])[0]);}}>{Object.entries(FIELDS).map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <label>Auswahl<select disabled={busy} value={value} onChange={e => setValue(e.target.value)}>{Object.entries(VALUES[field]).map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <div className="source-form-actions"><button className="primary-action" disabled={busy || !data} type="submit">Vorliebe speichern</button></div>
    </form>
    {error && <p role="alert">{error} <button type="button" disabled={busy} onClick={() => setAttempt(attempt + 1)}>Neu laden</button></p>}
    <p role="status">{message || (!data && !error ? "Arbeitsvorlieben werden geladen …" : "")}</p>
    {data && <>
      <h3>Für diesen Bereich wirksam</h3>
      {Object.keys(data.effective.rules).length ? <ul>{Object.entries(data.effective.rules).map(([key,v]) => <li key={key}>{FIELDS[key as keyof typeof FIELDS]}: {VALUES[key]?.[v] || v}</li>)}</ul> : <p>Keine bestätigte Regel für diesen Bereich.</p>}
      {data.effective.conflicts.length > 0 && <p role="alert">Widersprüchliche Regeln werden ausgesetzt: {data.effective.conflicts.map(key => FIELDS[key as keyof typeof FIELDS]).join(", ")}. Speichere deine gewünschte Auswahl erneut.</p>}
      <h3>Gespeicherte Regeln und Herkunft</h3>
      {data.items.length === 0 ? <p>Noch keine Arbeitsvorlieben gespeichert.</p> : <ul>{data.items.map(item => <li key={item.id}><p>{item.statement}<br/><small>{item.provenance.source_type === "user_stated" ? "Von dir ausdrücklich bestätigt" : "Weitere Herkunft"} · {item.status === "active" ? "Gespeichert" : item.status === "retracted" ? "Widerrufen" : item.status === "superseded" ? "Ersetzt" : item.status}{item.expires_at ? ` · Gültig bis ${new Date(item.expires_at).toLocaleString("de-DE")}` : ""}</small></p>{item.status === "active" && <button className="secondary-action" disabled={busy} type="button" onClick={() => retract(item.id)}>Widerrufen</button>}</li>)}</ul>}
    </>}
  </section>;
}
