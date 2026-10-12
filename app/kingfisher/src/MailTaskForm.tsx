import { FormEvent, useEffect, useRef, useState } from "react";
import { api, ApiError, type Project, type Task } from "./api";
import { endOfTaskDay, explicitDeadline, taskHref } from "./taskWorkflow";
import { navigate } from "./ui";

type MailTaskFormProps = {
  uid: string;
  subject: string;
  expectedSourceDigest: string | null;
  initialSuggestion?: { title: string; quote: string; source_digest: string };
  onTaskFormProtected?: (protectedState: boolean) => void;
};

function newRequestId(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  // Older native WebKit still supplies cryptographic random bytes.
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}

function pendingRequestId(uid: string): string {
  const key = `kingfisher:mail-task-request:${encodeURIComponent(uid)}`;
  const previous = localStorage.getItem(key);
  if (previous) {
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(previous)) {
      throw new Error('Die gespeicherte Auftragskennung ist ungültig.');
    }
    return previous;
  }
  const id = newRequestId();
  // Store only UID/opaque identity, never mail text or task fields. Persist
  // before sending so reopening after an uncertain response retains identity.
  localStorage.setItem(key, id);
  return id;
}

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
  const [retryReviewed, setRetryReviewed] = useState(false);
  const userChanged = useRef(false);
  const saveAttempt = useRef<{id: string | null; inFlight: boolean; succeeded: boolean}>({id: null, inFlight: false, succeeded: false});

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
    if (!trimmedTitle || saving || saved || saveAttempt.current.inFlight || saveAttempt.current.succeeded) return;
    if (!sourceDigest || sourceDigest !== expectedSourceDigest) {
      setError("Die gelesene Mailfassung konnte nicht bestätigt werden. Bitte die Nachricht neu öffnen und deine Eingaben mit dem Original abgleichen.");
      return;
    }
    protectSuggestion();
    setSaving(true);
    setError(null);
    setRetryReviewed(false);
    try {
      // Keep this identity after failure, including edits after an uncertain
      // response. The server rejects rebinding an already committed request.
      saveAttempt.current.id ??= pendingRequestId(uid);
      saveAttempt.current.inFlight = true;
      const task = await api.addMailTask(uid, {
        request_id: saveAttempt.current.id,
        title: trimmedTitle,
        project_id: projectId || null,
        due: endOfTaskDay(due),
        waiting_for: waitingFor.trim() || null,
        source_digest: sourceDigest,
        ...(sourceQuote ? { source_quote: sourceQuote } : {}),
      });
      saveAttempt.current.succeeded = true;
      setSaved(task);
      try {
        const key = `kingfisher:mail-task-request:${encodeURIComponent(uid)}`;
        if (localStorage.getItem(key) === saveAttempt.current.id) localStorage.removeItem(key);
      } catch { /* Retaining a confirmed identity is safe; never retry as new. */ }
    } catch (failure) {
      setError(!saveAttempt.current.inFlight
        ? "Der Speicherauftrag konnte nicht vorbereitet werden. Bitte Eingaben und lokalen Speicher prüfen. Es wurde keine Aufgabe gesendet."
        : failure instanceof ApiError && failure.status === 409
        ? "Quelle oder Eingaben passen nicht mehr zum Speicherauftrag. Bitte zuerst die vorhandenen Aufgaben und die Original-Mail prüfen. Deine Eingaben bleiben erhalten."
        : "Die Speicherbestätigung fehlt. Du kannst mit denselben Eingaben erneut versuchen; dabei wird höchstens eine Aufgabe angelegt. Vor dem Schließen bitte die vorhandenen Aufgaben prüfen.");
    } finally {
      saveAttempt.current.inFlight = false;
      setSaving(false);
    }
  }

  function prepareNewRequest() {
    if (!retryReviewed || saving || saved || saveAttempt.current.inFlight) return;
    try {
      const key = `kingfisher:mail-task-request:${encodeURIComponent(uid)}`;
      const pending = localStorage.getItem(key);
      if (pending && pending !== saveAttempt.current.id) {
        setError('Eine andere Speicherung ist noch ungeklärt. Bitte zuerst die Aufgaben prüfen.');
        return;
      }
      localStorage.removeItem(key);
      saveAttempt.current = {id: null, inFlight: false, succeeded: false};
      setRetryReviewed(false);
      setError(null);
      // Keep the reviewed digest and all visible fields. No automatic save or
      // silent source rebinding; the next submit still checks the original.
    } catch {
      setError('Der neue Speicherauftrag konnte nicht vorbereitet werden. Bitte den lokalen Speicher prüfen. Es wurde keine Aufgabe gesendet.');
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
      {error ? <div className="mail-reader-error" role="alert">
        <p>{error} <a href="/vorhaben?view=mine" onClick={(event) => {event.preventDefault(); navigate('/vorhaben?view=mine');}}>Aufgaben prüfen</a></p>
        <label className="mail-task-retry-review"><input id="mail-task-request-reviewed" type="checkbox" checked={retryReviewed} disabled={saving} onChange={(event) => setRetryReviewed(event.target.checked)} /> Ich habe die vorhandenen Aufgaben geprüft und möchte bewusst einen neuen Auftrag vorbereiten.</label>
        <button id="mail-task-new-request" type="button" className="mail-reader-secondary" disabled={!retryReviewed || saving} onClick={prepareNewRequest}>Neuen Auftrag vorbereiten</button>
      </div> : null}
      {saved ? <p className="mail-task-form-success" role="status">Aufgabe festgehalten. <a href={successPath} onClick={(event) => { event.preventDefault(); navigate(successPath); }}>Aufgabe ansehen</a></p> : null}
    </form>
    </> : null}
  </section>;
}
