import { useEffect, useRef, useState } from "react";
import { api, ApiError, type Project, type Task, type TaskCandidate, type TaskCandidatePage } from "./api";
import { candidateDeadline, localTaskDay } from "./taskWorkflow";
import { ProfileSource } from "./ProfileSource";
import { generationForTaskPage, isVisibleTaskPage, type TaskTemporalFilter } from "./taskSuggestionsView";
import {DetailPanel} from './DetailPanel';

const PAGE_SIZE = 25;
type TemporalFilter = TaskTemporalFilter;
type PresentedTaskPage = TaskCandidatePage & {temporal: TemporalFilter};
type SuggestionDraft = {open: boolean; title: string; project: string; newProject: string; due: string; waiting: string};

function initialDraft(item: TaskCandidate): SuggestionDraft {
  return {open: false, title: item.statement, project: item.project_suggestion?.project_id ?? "", newProject: item.project_suggestion?.new_project_name ?? "",
    due: item.temporal_status === "recent" && item.valid_until ? localTaskDay(item.valid_until) : "", waiting: ""};
}

function deadlineText(item: TaskCandidate, day: string) {
  if (!day) return 'Ohne Frist';
  try { const value = candidateDeadline(item, day); return value ? `Frist ${new Date(value).toLocaleString('de-DE', {dateStyle:'medium',timeStyle:'short'})}` : 'Ohne Frist'; }
  catch { return 'Frist prüfen'; }
}

/**
 * „Zur Prüfung“: in den Quellen erkannte Aufgaben. Der Reiter auf der Aufgabenseite ist der Schalter; er erscheint nur,
 * wenn etwas zu prüfen ist (`onTotal` meldet die Zahl). Ist nichts offen, zeigt die Komponente nichts.
 */
export function TaskSuggestions({projects, onAccepted, onPreview, onTotal}: {projects: Project[]; onAccepted: (task: Task) => void; onPreview?:()=>void; onTotal?: (total: number) => void}) {
  const requestVersion = useRef(0);
  const [page, setPage] = useState<PresentedTaskPage | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);
  const [revision, setRevision] = useState(0);
  const reportTotal = useRef(onTotal);
  reportTotal.current = onTotal;
  const [notice, setNotice] = useState("");
  const [offset, setOffset] = useState(0);
  const [temporal, setTemporal] = useState<TemporalFilter>("all");
  const [drafts, setDrafts] = useState<Record<string, SuggestionDraft>>({});
  const [selected,setSelected]=useState<string[]>([]);
  const [batchPreview,setBatchPreview]=useState<Array<{item:TaskCandidate;draft:SuggestionDraft}>|null>(null);
  const [batchBusy,setBatchBusy]=useState(false);
  const batchPending=useRef(false);
  const [batchResults,setBatchResults]=useState<Array<{id:string;title:string;ok:boolean}>>([]);
  useEffect(()=>{setSelected([]);setBatchPreview(null);},[offset,temporal]);
  const generations = useRef<Record<TemporalFilter, string | undefined>>({all: undefined, recent: undefined, review: undefined});
  useEffect(() => {
    let active = true;
    const refresh = () => {
      const version = ++requestVersion.current;
      setLoading(true);
      api.taskCandidatePage(PAGE_SIZE, offset, temporal, generationForTaskPage(offset, generations.current[temporal])).then(result => {
        if (!active || version !== requestVersion.current) return;
        if (offset === 0) generations.current[temporal] = result.generation;
        if (temporal === "all") reportTotal.current?.(result.total);
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
  if (!page && !error && !notice) return null;
  if (visiblePage?.total === 0 && temporal === "all" && !error && !notice) return null;
  function changeDraft(item: TaskCandidate, patch: Partial<SuggestionDraft>) {
    setBatchPreview(null);
    setDrafts(current => ({...current, [item.id]: {...(current[item.id] ?? initialDraft(item)), ...patch}}));
  }
  async function acceptBatch(){
    if(!batchPreview||batchPending.current)return;
    batchPending.current=true;setBatchBusy(true);setBatchResults([]);
    const results:Array<{id:string;title:string;ok:boolean}>=[];
    let lastTask:Task|null=null;
    for(const {item,draft} of batchPreview){
      try{const task=await api.acceptTaskCandidate(item.id,{title:draft.title.trim(),project_id:draft.project||null,new_project_name:draft.newProject.trim()||null,due:candidateDeadline(item,draft.due),waiting_for:draft.waiting.trim()||null});results.push({id:item.id,title:draft.title,ok:true});lastTask=task;}
      catch{results.push({id:item.id,title:draft.title,ok:false});}
      setBatchResults([...results]);
    }
    setSelected([]);setBatchPreview(null);generations.current[temporal]=undefined;setOffset(0);setRevision(n=>n+1);setBatchBusy(false);batchPending.current=false;
    if(lastTask)onAccepted(lastTask);
  }
  return <section className="task-source" aria-label="Erkannte Aufgaben und Zusagen">
    <p>In deinen Quellen erkannt. Erst deine Bestätigung macht daraus eine Aufgabe.</p>
    {notice && <p role="status">{notice}</p>}
    {error && <p role="alert">Vorschläge sind gerade nicht erreichbar. <button type="button" onClick={() => setRevision(value => value + 1)}>Erneut laden</button></p>}
    {visiblePage && selected.length > 0 && <div className="task-suggestion-actions"><button className="secondary-action" type="button" disabled={batchBusy||!selected.length} onClick={()=>{onPreview?.();setBatchPreview(visiblePage.items.filter(item=>selected.includes(item.id)).map(item=>({item,draft:{...(drafts[item.id]??initialDraft(item))}})));}}>Auswahl prüfen ({selected.length})</button><small>Auswahl gilt für diese Seite; jede Übernahme prüft ihre Quelle erneut.</small></div>}
    {batchResults.length>0&&<ul aria-label="Ergebnisse der Aufgabenübernahme">{batchResults.map(result=><li key={result.id}>{result.title}: {result.ok?'Aufgabe und Zuordnung gespeichert.':'Nicht bestätigt. Bitte Quelle und Eingaben erneut prüfen; eine Wiederholung legt keine zweite Aufgabe an.'}</li>)}</ul>}
    {batchPreview&&<DetailPanel title="Ausgewählte Vorschläge" onClose={()=>{if(!batchBusy)setBatchPreview(null);}}><p>Diese sichtbaren Angaben werden gemeinsam übernommen. Unklare oder historische Quellen bleiben ausdrücklich zu prüfen.</p>{batchPreview.map(({item,draft})=><article key={item.id}><h3>{draft.title}</h3><p>{draft.newProject?`Neues Projekt: ${draft.newProject}`:projects.find(p=>p.id===draft.project)?.name??'Ohne Projekt'} · {deadlineText(item,draft.due)}{draft.waiting&&` · Warte auf ${draft.waiting}`}</p><p>{item.temporal_reason}</p>{item.evidence.map(e=><blockquote key={e.episode_id}>{e.quote}</blockquote>)}</article>)}<button type="button" className="primary-action" disabled={batchBusy} onClick={()=>void acceptBatch()}>{batchBusy?'Wird einzeln übernommen …':'Diese Angaben übernehmen'}</button></DetailPanel>}
    <div className="task-suggestion-actions">
      <label>Zeitraum<select value={temporal} onChange={event => {setNotice(""); setTemporal(event.target.value as TemporalFilter); setOffset(0);}}>
        <option value="all">Alle Vorschläge</option><option value="recent">Zeitnah</option><option value="review">Zeitlich prüfen</option>
      </select></label>
      {visiblePage && (offset > 0 || visiblePage.has_more) ? <span>{`${visiblePage.total ? offset + 1 : 0}–${Math.min(offset + visiblePage.items.length, visiblePage.total)} von ${visiblePage.total}`}</span> : null}
      {(offset > 0 || visiblePage?.has_more) && <button type="button" className="secondary-action" disabled={loading || !visiblePage || offset === 0} onClick={() => setOffset(value => Math.max(0, value - PAGE_SIZE))}>Vorherige</button>}
      {(offset > 0 || visiblePage?.has_more) && <button type="button" className="secondary-action" disabled={loading || !visiblePage?.has_more} onClick={() => setOffset(value => value + PAGE_SIZE)}>Weitere</button>}
    </div>
    {loading && !visiblePage && <p role="status">Vorschläge werden geladen …</p>}
    {visiblePage?.total === 0 && temporal !== "all" && <p>Für diesen Zeitraum gibt es keine offenen Vorschläge.</p>}
    {visiblePage?.items.map(item => <Suggestion key={item.id} item={item} disabled={batchBusy} selected={selected.includes(item.id)} onSelected={value=>{setBatchPreview(null);setSelected(ids=>value?[...new Set([...ids,item.id])]:ids.filter(id=>id!==item.id));}} draft={drafts[item.id] ?? initialDraft(item)} onDraftChange={patch => changeDraft(item, patch)} projects={projects} onDone={task => {
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
  </section>;
}

function Suggestion({item, draft, onDraftChange, projects, onDone,selected,onSelected,disabled=false}: {item: TaskCandidate; draft: SuggestionDraft; onDraftChange: (patch: Partial<SuggestionDraft>) => void; projects: Project[]; onDone: (task?: Task) => void;selected:boolean;onSelected:(value:boolean)=>void;disabled?:boolean}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function save(accept: boolean) {
    if (busy||disabled) return;
    setBusy(true); setError("");
    try {
      if (accept) {
        const task = await api.acceptTaskCandidate(item.id, {title: draft.title.trim(), project_id: draft.project || null, new_project_name: draft.newProject.trim() || null,
          due: candidateDeadline(item, draft.due), waiting_for: draft.waiting.trim() || null});
        onDone(task);
      } else { await api.rejectTaskCandidate(item.id); onDone(); }
    } catch (failure) {
      setError(failure instanceof Error && failure.message === "HTTP 409"
        ? "Dieser Vorschlag ist nicht mehr verfügbar oder seine Quelle wurde ausgeschlossen. Bitte die Aufgabenansicht neu laden."
        : "Die Änderung konnte nicht gespeichert werden. Deine Eingaben bleiben erhalten. Bitte erneut versuchen.");
    } finally {setBusy(false);}
  }
  return <article className="mail-task-form">
    <label><input aria-label="Für gemeinsame Übernahme auswählen" type="checkbox" checked={selected} disabled={busy||disabled} onChange={event=>onSelected(event.target.checked)}/>Auswählen</label>
    <h3>{draft.title}</h3>
    <p>Übernahme: {draft.newProject ? `Neues Projekt „${draft.newProject}“` : draft.project ? `Projekt „${projects.find(p=>p.id===draft.project)?.name ?? 'nicht verfügbar'}“` : 'Ohne Projekt'}
      {' · '}{deadlineText(item,draft.due)}{draft.waiting && ` · Warte auf ${draft.waiting}`}</p>
    <span className="suggestion-time-badge">{item.temporal_status === 'recent' ? 'Vorschlag · noch unbestätigt' : ['old','history'].includes(item.temporal_status ?? '') ? 'Historisch · Aktualität prüfen' : 'Zeitliche Einordnung prüfen'}</span>
    <details className="quiet-details suggestion-evidence" open={draft.open || undefined}><summary>Quelle & Begründung</summary>
    <p>{item.temporal_reason || 'Zeitliche Einordnung bitte prüfen.'}</p>
    <p>Quelldatum: {item.received_at ? new Date(item.received_at).toLocaleString('de-DE', {dateStyle:'medium', timeStyle:'short'}) : 'unbekannt'}
      {item.recorded_at && <> · Erfasst: {new Date(item.recorded_at).toLocaleString('de-DE', {dateStyle:'medium', timeStyle:'short'})}</>}</p>
    {item.followup_episode_id && <div><p>Weitere Nachricht im Verlauf:</p><ProfileSource kind="episode" id={item.followup_episode_id} allowIgnore={false} /></div>}
    {item.evidence.map(evidence => <div key={evidence.episode_id}><blockquote>{evidence.quote}</blockquote><ProfileSource kind="episode" id={evidence.episode_id} allowIgnore={false} /></div>)}
    {item.project_suggestion && <p className="workspace-project-hint">Projektvorschlag: <strong>{item.project_suggestion.name}</strong> · {item.project_suggestion.reason}</p>}
    </details>
    {!draft.open ? <div className="task-suggestion-actions"><button className="secondary-action" type="button" disabled={busy} onClick={()=>void save(true)}>Aufgabe{draft.project || draft.newProject ? " und Projekt" : ""} übernehmen</button><button className="text-action" type="button" onClick={() => onDraftChange({open: true})}>Ändern</button><button className="text-action" type="button" disabled={busy} onClick={() => void save(false)}>Verwerfen</button></div> :
      <form onSubmit={event => {event.preventDefault(); void save(true);}}>
        <fieldset className="task-suggestion-fields" disabled={busy}><label>Aufgabe<input value={draft.title} onChange={event => onDraftChange({title: event.target.value})} required maxLength={4096} /></label>
          <div className="mail-task-form-fields"><label>Projekt<select value={draft.project} onChange={event => onDraftChange({project: event.target.value,newProject:""})}><option value="">Ohne Projekt</option>{projects.filter(value => value.open).map(value => <option key={value.id} value={value.id}>{value.name}</option>)}</select></label>
          <label>Neues Projekt (optional)<input value={draft.newProject} maxLength={200} onChange={event=>onDraftChange({newProject:event.target.value,project:""})}/></label><label>Fällig am<input type="date" value={draft.due} onChange={event => onDraftChange({due: event.target.value})} /><small>{item.temporal_status === "recent" && item.valid_until && draft.due === initialDraft(item).due ? `Vorgeschlagener Zeitpunkt bleibt erhalten: ${new Date(item.valid_until).toLocaleString('de-DE')}. Bitte an der Quelle prüfen.` : 'Ein neu gewählter Tag gilt bis 23:59 Uhr. Ohne Datum wird keine Frist gesetzt.'}</small></label>
          <label>Warte auf (optional)<input value={draft.waiting} onChange={event => onDraftChange({waiting: event.target.value})} maxLength={1024} /></label></div>
          <div className="task-suggestion-actions"><button className="primary-action" type="submit" disabled={!draft.title.trim()}>Aufgabe festhalten</button>
          <button className="secondary-action" type="button" onClick={() => onDraftChange({open: false})}>Abbrechen</button></div>
        </fieldset>
      </form>}
    {error && <p role="alert">{error}</p>}
  </article>;
}
