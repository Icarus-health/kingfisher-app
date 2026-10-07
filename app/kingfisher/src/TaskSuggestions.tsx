import { useEffect, useRef, useState } from "react";
import { api, ApiError, type Project, type Task, type TaskCandidate, type TaskCandidatePage } from "./api";
import { ProfileSource } from "./ProfileSource";
import { generationForTaskPage, isVisibleTaskPage, type TaskTemporalFilter } from "./taskSuggestionsView";

const PAGE_SIZE = 25;
type TemporalFilter = TaskTemporalFilter;
type PresentedTaskPage = TaskCandidatePage & {temporal: TemporalFilter};
type SuggestionDraft = {open: boolean; title: string; project: string; due: string; waiting: string};

function initialDraft(item: TaskCandidate): SuggestionDraft {
  return {open: false, title: item.statement, project: "",
    due: item.temporal_status === "recent" && item.valid_until ? item.valid_until.slice(0, 10) : "", waiting: ""};
}

export function TaskSuggestions({projects, onAccepted, initiallyExpanded = false}: {projects: Project[]; onAccepted: (task: Task) => void; initiallyExpanded?: boolean}) {
  const requestVersion = useRef(0);
  const [page, setPage] = useState<PresentedTaskPage | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);
  const [revision, setRevision] = useState(0);
  const [expanded, setExpanded] = useState(initiallyExpanded);
  const [notice, setNotice] = useState("");
  const [offset, setOffset] = useState(0);
  const [temporal, setTemporal] = useState<TemporalFilter>("all");
  const [drafts, setDrafts] = useState<Record<string, SuggestionDraft>>({});
  const generations = useRef<Record<TemporalFilter, string | undefined>>({all: undefined, recent: undefined, review: undefined});
  useEffect(() => {
    let active = true;
    const refresh = () => {
      const version = ++requestVersion.current;
      setLoading(true);
      api.taskCandidatePage(PAGE_SIZE, offset, temporal, generationForTaskPage(offset, generations.current[temporal])).then(result => {
        if (!active || version !== requestVersion.current) return;
        if (offset === 0) generations.current[temporal] = result.generation;
        setPage({...result, temporal});
        setError(false);
        if (offset > 0 && result.items.length === 0) {
          const clamped = result.total > 0 ? Math.floor((result.total - 1) / PAGE_SIZE) * PAGE_SIZE : 0;
          if (clamped < offset) setOffset(clamped);
        }
      }).catch(failure => {
        if (!active || version !== requestVersion.current) return;
        if (failure instanceof ApiError && failure.status === 409) {
          generations.current[temporal] = undefined;
          setPage(null);
          setError(false);
          setNotice("Die Prüfliste hat sich geändert. Ich lade die erste Seite neu.");
          setOffset(0);
          if (offset === 0) setRevision(value => value + 1);
          return;
        }
        setError(true);
      }).finally(() => {
        if (active && version === requestVersion.current) setLoading(false);
      });
    };
    refresh();
    window.addEventListener("focus", refresh);
    return () => {active = false; window.removeEventListener("focus", refresh);};
  }, [revision, offset, temporal]);
  const visiblePage = isVisibleTaskPage(page, offset, temporal, loading, error) ? page : null;
  if (!page && !error && !notice && !initiallyExpanded) return null;
  if (visiblePage?.total === 0 && temporal === "all" && !error && !notice && !initiallyExpanded) return null;
  function changeDraft(item: TaskCandidate, patch: Partial<SuggestionDraft>) {
    setDrafts(current => ({...current, [item.id]: {...(current[item.id] ?? initialDraft(item)), ...patch}}));
  }
  return <section className="task-source" aria-label="Erkannte Aufgaben und Zusagen">
    <h2><button type="button" className="secondary-action" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>{expanded ? "Prüfung schließen" : "Zur Prüfung"}{visiblePage ? ` · ${visiblePage.total}` : ""}</button></h2>
    <p>In deinen Quellen erkannt. Erst deine Bestätigung macht daraus eine Aufgabe.</p>
    {notice && <p role="status">{notice}</p>}
    {error && <p role="alert">Vorschläge sind gerade nicht erreichbar. <button type="button" onClick={() => setRevision(value => value + 1)}>Erneut laden</button></p>}
    {expanded && <>
      <div className="task-suggestion-actions">
        <label>Zeitraum<select value={temporal} onChange={event => {setNotice(""); setTemporal(event.target.value as TemporalFilter); setOffset(0);}}>
          <option value="all">Alle Vorschläge</option><option value="recent">Zeitnah</option><option value="review">Zeitlich prüfen</option>
        </select></label>
        <span>{visiblePage ? `${visiblePage.total ? offset + 1 : 0}–${Math.min(offset + visiblePage.items.length, visiblePage.total)} von ${visiblePage.total}` : error ? "Vorschläge gerade nicht erreichbar" : "Vorschläge werden geladen …"}</span>
        <button type="button" className="secondary-action" disabled={loading || !visiblePage || offset === 0} onClick={() => setOffset(value => Math.max(0, value - PAGE_SIZE))}>Vorherige</button>
        <button type="button" className="secondary-action" disabled={loading || !visiblePage?.has_more} onClick={() => setOffset(value => value + PAGE_SIZE)}>Weitere</button>
      </div>
      {loading && !visiblePage && <p role="status">Vorschläge werden geladen …</p>}
      {visiblePage?.total === 0 && <p>Für diesen Zeitraum gibt es keine offenen Vorschläge.</p>}
      {visiblePage?.items.map(item => <Suggestion key={item.id} item={item} draft={drafts[item.id] ?? initialDraft(item)} onDraftChange={patch => changeDraft(item, patch)} projects={projects} onDone={task => {
        requestVersion.current++;
        setDrafts(current => {const next = {...current}; delete next[item.id]; return next;});
        setPage(current => current ? {...current, items: current.items.filter(candidate => candidate.id !== item.id), total: Math.max(0, current.total - 1)} : current);
        generations.current[temporal] = undefined;
        setLoading(true);
        setOffset(0);
        setNotice(task ? "Aufgabe gespeichert." : "Vorschlag verworfen.");
        setRevision(value => value + 1);
        if (task) onAccepted(task);
      }} />)}
    </>}
  </section>;
}

function Suggestion({item, draft, onDraftChange, projects, onDone}: {item: TaskCandidate; draft: SuggestionDraft; onDraftChange: (patch: Partial<SuggestionDraft>) => void; projects: Project[]; onDone: (task?: Task) => void}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function save(accept: boolean) {
    if (busy) return;
    setBusy(true); setError("");
    try {
      if (accept) {
        const task = await api.acceptTaskCandidate(item.id, {title: draft.title.trim(), project_id: draft.project || null,
          due: draft.due ? new Date(`${draft.due}T00:00:00`).toISOString() : null, waiting_for: draft.waiting.trim() || null});
        onDone(task);
      } else { await api.rejectTaskCandidate(item.id); onDone(); }
    } catch (failure) {
      setError(failure instanceof Error && failure.message === "HTTP 409"
        ? "Dieser Vorschlag ist nicht mehr verfügbar oder seine Quelle wurde ausgeschlossen. Bitte die Aufgabenansicht neu laden."
        : "Die Änderung konnte nicht gespeichert werden. Deine Eingaben bleiben erhalten. Bitte erneut versuchen.");
    } finally {setBusy(false);}
  }
  return <article className="mail-task-form">
    <h3>{item.statement}</h3>
    <p>{item.temporal_reason || 'Zeitliche Einordnung bitte prüfen.'}</p>
    <p>Quelldatum: {item.received_at ? new Date(item.received_at).toLocaleString('de-DE', {dateStyle:'medium', timeStyle:'short'}) : 'unbekannt'}
      {item.recorded_at && <> · Erfasst: {new Date(item.recorded_at).toLocaleString('de-DE', {dateStyle:'medium', timeStyle:'short'})}</>}</p>
    {item.followup_episode_id && <div><p>Weitere Nachricht im Verlauf:</p><ProfileSource kind="episode" id={item.followup_episode_id} allowIgnore={false} /></div>}
    {item.evidence.map(evidence => <div key={evidence.episode_id}><blockquote>{evidence.quote}</blockquote><ProfileSource kind="episode" id={evidence.episode_id} allowIgnore={false} /></div>)}
    {!draft.open ? <div><button className="secondary-action" type="button" onClick={() => onDraftChange({open: true})}>Aufgabe prüfen</button><button className="secondary-action" type="button" disabled={busy} onClick={() => void save(false)}>Verwerfen</button></div> :
      <form onSubmit={event => {event.preventDefault(); void save(true);}}>
        <fieldset className="task-suggestion-fields" disabled={busy}><label>Aufgabe<input value={draft.title} onChange={event => onDraftChange({title: event.target.value})} required maxLength={4096} /></label>
          <div className="mail-task-form-fields"><label>Projekt<select value={draft.project} onChange={event => onDraftChange({project: event.target.value})}><option value="">Ohne Projekt</option>{projects.filter(value => value.open).map(value => <option key={value.id} value={value.id}>{value.name}</option>)}</select></label>
          <label>Fällig am<input type="date" value={draft.due} onChange={event => onDraftChange({due: event.target.value})} /></label>
          <label>Warte auf (optional)<input value={draft.waiting} onChange={event => onDraftChange({waiting: event.target.value})} maxLength={1024} /></label></div>
          <div className="task-suggestion-actions"><button className="primary-action" type="submit" disabled={!draft.title.trim()}>Aufgabe festhalten</button>
          <button className="secondary-action" type="button" onClick={() => onDraftChange({open: false})}>Abbrechen</button></div>
        </fieldset>
      </form>}
    {error && <p role="alert">{error}</p>}
  </article>;
}
