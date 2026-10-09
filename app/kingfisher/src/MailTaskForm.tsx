import { FormEvent, useEffect, useRef, useState } from "react";
import { api, type Project, type Task } from "./api";
import { endOfTaskDay, explicitDeadline, taskHref } from "./taskWorkflow";
import { navigate } from "./ui";

type MailTaskFormProps = {
  uid: string;
  subject: string;
  expectedSourceDigest: string | null;
  initialSuggestion?: { title: string; quote: string; source_digest: string };
  onTaskFormProtected?: (protectedState: boolean) => void;
};

export function MailTaskForm({ uid, subject, expectedSourceDigest, initialSuggestion, onTaskFormProtected }: MailTaskFormProps) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState(subject || "(Ohne Betreff)");
  const [projectId, setProjectId] = useState("");
  const [due, setDue] = useState("");
  const [waitingFor, setWaitingFor] = useState("");
  const [sourceQuote, setSourceQuote] = useState<string | null>(null);
  const [sourceDigest, setSourceDigest] = useState<string | null>(expectedSourceDigest);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectsError, setProjectsError] = useState(false);
  const [saving, setSaving] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [suggestions, setSuggestions] = useState<Array<{ title: string; quote: string }>>([]);
  const [suggestionsSourceDigest, setSuggestionsSourceDigest] = useState<string | null>(null);
  const [suggestionsDetail, setSuggestionsDetail] = useState<string | null>(null);
  const [suggestionsUnavailable, setSuggestionsUnavailable] = useState(false);
  const [saved, setSaved] = useState<Task | null>(null);
  const [error, setError] = useState<string | null>(null);
  const userChanged = useRef(false);

  function protectSuggestion() {
    if (userChanged.current) return;
    userChanged.current = true;
    onTaskFormProtected?.(true);
  }

  useEffect(() => {
    if (!initialSuggestion || initialSuggestion.source_digest !== expectedSourceDigest || userChanged.current || saved) return;
    setOpen(true);
    setTitle(initialSuggestion.title);
    setSourceQuote(initialSuggestion.quote);
    setSourceDigest(initialSuggestion.source_digest);
  }, [initialSuggestion, expectedSourceDigest, saved]);

  useEffect(() => {
    let active = true;
    api.projects().then((items) => {
      if (active) setProjects(items.filter((project) => project.open));
    }).catch(() => {
      if (active) setProjectsError(true);
    });
    return () => { active = false; };
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const trimmedTitle = title.trim();
    if (!trimmedTitle || saving || saved) return;
    if (!sourceDigest || sourceDigest !== expectedSourceDigest) {
      setError("Die gelesene Mailfassung konnte nicht bestätigt werden. Bitte die Nachricht neu öffnen und deine Eingaben mit dem Original abgleichen.");
      return;
    }
    protectSuggestion();
    setSaving(true);
    setError(null);
    try {
      const task = await api.addMailTask(uid, {
        title: trimmedTitle,
        project_id: projectId || null,
        due: endOfTaskDay(due),
        waiting_for: waitingFor.trim() || null,
        source_digest: sourceDigest,
        ...(sourceQuote ? { source_quote: sourceQuote } : {}),
      });
      setSaved(task);
    } catch {
      setError("Die Aufgabe konnte nicht festgehalten werden. Falls sich die Nachricht geändert hat, bitte schließen und erneut prüfen. Deine Eingaben bleiben hier erhalten.");
    } finally {
      setSaving(false);
    }
  }

  async function suggestTasks() {
    if (suggesting || saving || saved) return;
    setSuggesting(true);
    setSuggestions([]);
    setSuggestionsSourceDigest(null);
    setSuggestionsDetail(null);
    setSuggestionsUnavailable(false);
    setError(null);
    try {
      const result = await api.taskSuggestions(uid);
      setSuggestions(result.items);
      setSuggestionsSourceDigest(result.source_digest);
      const detail = result.detail || (result.items.length === 0 ? "Es wurden keine passenden Aufgaben vorgeschlagen." : null);
      setSuggestionsDetail(result.items.length === 0 && result.available ? "Keine belegbaren Aufgabenvorschläge gefunden. Du kannst selbst eine Aufgabe eingeben." : detail);
      setSuggestionsUnavailable(!result.available);
    } catch {
      setSuggestionsDetail("Die Vorschläge konnten nicht erstellt werden. Bitte Modellverbindung und Nachricht prüfen und erneut versuchen.");
      setSuggestionsUnavailable(true);
    } finally {
      setSuggesting(false);
    }
  }

  function useSuggestion(suggestion: { title: string; quote: string }) {
    protectSuggestion();
    setTitle(suggestion.title);
    setSourceQuote(suggestion.quote);
    setSourceDigest(suggestionsSourceDigest);
  }

  const successPath = saved ? taskHref(saved) : "/vorhaben?view=mine";
  const suggestedDay = sourceQuote ? explicitDeadline(sourceQuote) : null;

  return <section className="mail-task-form" aria-label="Aufgabe aus Nachricht festhalten">
    {!open ? <button className="mail-reader-secondary" onClick={() => setOpen(true)} type="button">Als Aufgabe festhalten</button> : null}
    {open ? <>
    <div className="mail-task-form-heading">
      <div>
        <p className="mail-reader-eyebrow">Nächster Schritt</p>
        <h2>Als Aufgabe festhalten</h2>
      </div>
      <p className="mail-reader-status">Die Original-Mail bleibt als Quelle erhalten. Es wird nichts versendet.</p>
    </div>
    <form onSubmit={submit}>
      <label htmlFor="mail-task-title">Aufgabe</label>
      <input disabled={saving || Boolean(saved)} id="mail-task-title" onChange={(event) => { protectSuggestion(); setTitle(event.target.value); }} value={title} />
      {sourceQuote && <p className="mail-reader-status">Übernommene Textstelle: „{sourceQuote}“</p>}
      {!initialSuggestion && <div className="mail-task-suggestions">
        <button className="mail-reader-secondary" disabled={suggesting || saving || Boolean(saved)} onClick={suggestTasks} type="button">
          {suggesting ? "Aufgaben werden vorgeschlagen …" : "Aufgaben vorschlagen"}
        </button>
        {suggestionsUnavailable ? <p className="mail-reader-status" role="status">{suggestionsDetail || "Für diese Nachricht konnten keine Aufgaben vorgeschlagen werden."}</p> : null}
        {!suggesting && !suggestionsUnavailable && suggestions.length === 0 && suggestionsDetail ? <p className="mail-reader-status" role="status">{suggestionsDetail}</p> : null}
        {suggestions.length > 0 ? <div className="mail-task-suggestions-list" aria-label="Vorgeschlagene Aufgaben">
          {suggestions.map((suggestion, index) => <article className="mail-task-suggestion" key={`${suggestion.title}-${index}`}>
            <div>
              <p className="mail-task-suggestion-title">{suggestion.title}</p>
              <p className="mail-task-suggestion-quote">„{suggestion.quote}“</p>
            </div>
            <button className="mail-reader-secondary" disabled={saving || Boolean(saved)} onClick={() => useSuggestion(suggestion)} type="button">In Aufgabe übernehmen</button>
          </article>)}
        </div> : null}
      </div>}
      {suggestedDay && !due && !saved && <p className="mail-reader-status">In der Textstelle steht ein mögliches Datum. Bitte den Zusammenhang prüfen. <button type="button" className="mail-reader-secondary" disabled={saving} onClick={() => {protectSuggestion(); setDue(suggestedDay);}}>Datum aus Text übernehmen: {suggestedDay.split('-').reverse().join('.')}</button></p>}
      <div className="mail-task-form-fields">
        <label htmlFor="mail-task-project">Projekt <select disabled={saving || Boolean(saved)} id="mail-task-project" aria-label="Projekt" onChange={(event) => { protectSuggestion(); setProjectId(event.target.value); }} value={projectId}>
          <option value="">Keinem Projekt zuordnen</option>
          {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
        </select></label>
        <label htmlFor="mail-task-due">Fällig am (optional) <input aria-describedby="mail-task-due-hint" disabled={saving || Boolean(saved)} id="mail-task-due" onChange={(event) => { protectSuggestion(); setDue(event.target.value); }} type="date" value={due} />
          <span className="mail-reader-status" id="mail-task-due-hint">{due ? "Dieser Tag wird bis 23:59 Uhr als Fälligkeit gespeichert. Eine ausdrücklich genannte Uhrzeit bitte separat prüfen." : "Kein Datum festgelegt. Die Aufgabe wird ohne Termin gespeichert."}</span>
        </label>
        <label htmlFor="mail-task-waiting">Warten auf <input disabled={saving || Boolean(saved)} id="mail-task-waiting" onChange={(event) => { protectSuggestion(); setWaitingFor(event.target.value); }} placeholder="Optional, z. B. Anna Müller" value={waitingFor} /></label>
      </div>
      <div className="mail-task-form-footer">
        <span className="mail-reader-status">{projectsError ? "Projekte konnten gerade nicht geladen werden." : "Nur lokal in Kingfisher festgehalten."}</span>
        <button className="mail-reader-primary" disabled={saving || Boolean(saved) || !title.trim()} type="submit">{saving ? "Wird festgehalten …" : saved ? "Aufgabe festgehalten" : "Aufgabe festhalten"}</button>
      </div>
      {error ? <p className="mail-reader-error" role="alert">{error}</p> : null}
      {saved ? <p className="mail-task-form-success" role="status">Aufgabe festgehalten. <a href={successPath} onClick={(event) => { event.preventDefault(); navigate(successPath); }}>Aufgabe ansehen</a></p> : null}
    </form>
    </> : null}
  </section>;
}
