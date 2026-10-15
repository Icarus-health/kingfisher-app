import {useEffect,useRef,useState} from 'react';
import {savedMailWorkflowApi,type SavedMailWorkflowView} from './savedMailWorkflowApi';
import {initialSavedTask,savedTaskPayload,type SavedTaskDraft} from './savedMailWorkflowState';
import {navigate} from './ui';

export function SavedMailWorkflow({episodeId,sourceDigest,sourceVerified=true,onTaskSaved}: {
 episodeId:string;sourceDigest:string;sourceVerified?:boolean;onTaskSaved?:()=>void;
}) {
 const [view,setView]=useState<SavedMailWorkflowView|null>(null);
 const [drafts,setDrafts]=useState<Record<string,SavedTaskDraft>>({});
 const [saved,setSaved]=useState<Record<string,string>>({});
 const [error,setError]=useState('');
 const [busy,setBusy]=useState('');
 const [loading,setLoading]=useState(true);
 const [readVerified,setReadVerified]=useState(false);
 const [revision,setRevision]=useState(0);
 const epoch=useRef(0);
 const active=useRef(true);
 const draftSource=useRef('');
 useEffect(()=>{
  active.current=true;
  let controller:AbortController|null=null;
  const sourceKey=episodeId+'|'+sourceDigest;
  if(draftSource.current!==sourceKey){setDrafts({});setSaved({});draftSource.current=sourceKey;}
  setBusy('');
  function load() {
   controller?.abort();controller=new AbortController();const version=++epoch.current;
   setLoading(true);setReadVerified(false);setError('');setView(previous=>previous?.episode_id===episodeId ? previous : null);
   void savedMailWorkflowApi.read(episodeId,controller.signal).then(value=>{
    if(active.current && version===epoch.current){setView(value);setReadVerified(true);}
   }).catch(failure=>{if(active.current && version===epoch.current){
    if(failure instanceof Error && /^HTTP (401|403|404|409)$/.test(failure.message))setView(null);
    setError('Der gespeicherte Überblick konnte gerade nicht geprüft werden. Bestätigung erst nach erneuter Prüfung.');
   }})
    .finally(()=>{if(active.current && version===epoch.current) setLoading(false);});
  }
  load();window.addEventListener('focus',load);
  return ()=>{active.current=false;epoch.current++;controller?.abort();window.removeEventListener('focus',load);};
 },[episodeId,sourceDigest,sourceVerified,revision]);
 const valid=sourceVerified && readVerified && !loading && view?.source_digest===sourceDigest;
 async function prepare() {
  const version=epoch.current;setBusy('prepare');setError('');
  try {const value=await savedMailWorkflowApi.prepare(episodeId);if(active.current && version===epoch.current){setView(value);setReadVerified(true);}}
  catch(failure){if(active.current && version===epoch.current){
   if(failure instanceof Error && /^HTTP (401|403|404|409)$/.test(failure.message)){setReadVerified(false);setView(null);}
   setError(failure instanceof Error && failure.message==='HTTP 409'
    ? 'Die Quelle oder Zuordnung wurde geändert. Bitte die gespeicherte Mail neu öffnen.' : 'Die lokale Vorbereitung ist gerade nicht verfügbar. Bitte erneut versuchen.');
  }}
  finally {if(active.current && version===epoch.current) setBusy('');}
 }
 async function save(id:string,draft:SavedTaskDraft) {
  if(!view || !valid)return;
  const version=epoch.current;setBusy(id);setError('');
  try {
   const task=await savedMailWorkflowApi.accept(episodeId,id,savedTaskPayload(view,draft));
   if(active.current && version===epoch.current) {setSaved(values=>({...values,[id]:task.title}));onTaskSaved?.();}
  } catch(failure) {if(active.current && version===epoch.current) setError(failure instanceof Error && failure.message==='HTTP 409'
   ? 'Die Quelle, Zuordnung oder das Projekt wurde geändert. Bitte erneut prüfen. Deine Eingaben bleiben erhalten.'
   : 'Die Aufgabe konnte gerade nicht bestätigt werden. Deine Eingaben bleiben erhalten; Wiederholen legt dieselbe Aufgabe nur einmal an.');}
  finally {if(active.current && version===epoch.current)setBusy('');}
 }
 return <section className="saved-mail-workflow" aria-label="Überblick und Aufgaben aus gespeicherter Mail">
  <h2>Nächste Schritte</h2>
  {loading && <p role="status">Vorbereiteter Überblick wird geprüft …</p>}
  {error && <p role="alert">{error}</p>}
  {view && <>
   {view.episode_id===episodeId && view.source_digest===sourceDigest && Object.entries(saved).map(([id,title])=><p key={id} role="status">Aufgabe gespeichert: {title} <a href="/vorhaben?view=mine" onClick={event=>{event.preventDefault();navigate('/vorhaben?view=mine');}}>Aufgaben öffnen</a></p>)}
   {(!sourceVerified || !readVerified) && <p role="status">Zuletzt geladener Überblick · Quellenstand ungeprüft. Deine Eingaben bleiben erhalten; Bestätigung erst nach erneuter Prüfung.</p>}
   {!readVerified && !loading && sourceVerified && <button type="button" onClick={()=>setRevision(value=>value+1)}>Quellenstand erneut prüfen</button>}
   {view.temporal_status==='recent' ? <details className="quiet-details"><summary>Zeitliche Einordnung</summary><p className="saved-mail-workflow-context">{view.temporal_reason}</p></details> : <p className="saved-mail-workflow-context" role="status">{view.temporal_reason || 'Zeitliche Einordnung unbekannt · Aktualität prüfen.'}</p>}
   {view.status==='unavailable' && <p role="status">{view.detail}</p>}
   {view.quotes.length>0 && <details className="saved-mail-overview"><summary>Überblick aus Originalstellen ({view.quotes.length})</summary><p>{view.detail}</p>{view.quotes.map((quote,index)=><blockquote key={index}>{quote}</blockquote>)}</details>}
   {(view.status==='unprepared' || view.status==='unavailable') && <button type="button" disabled={!valid || Boolean(busy)} onClick={()=>void prepare()}>{busy==='prepare'?'Wird lokal vorbereitet …':'Diese Mail lokal vorbereiten'}</button>}
   {(view.project_preparation_status==='unprepared' || view.project_preparation_status==='unavailable') && view.status==='ready' && <>
    <p role="status">{view.project_preparation_detail}</p><button type="button" disabled={!valid || Boolean(busy)} onClick={()=>void prepare()}>{busy==='prepare'?'Projektvorschläge werden lokal geprüft …':'Projektvorschläge erneut vorbereiten'}</button>
   </>}
   {view.status==='incomplete' && <p>Überblick über einen Ausschnitt. Aufgaben aus unvollständigem Text werden hier nicht neu vorgeschlagen.</p>}
   {view.status==='ready' && !view.items.length && <p>Keine offenen belegten Aufgabenvorschläge aus dieser Quelle.</p>}
   {view.items.filter(item=>!saved[item.id]).map(item=>{
    const draft=drafts[item.id] || initialSavedTask(item,view.projects);
    const update=(change:Partial<SavedTaskDraft>)=>setDrafts(values=>({...values,[item.id]:{...draft,...change}}));
    return <form key={item.id} className="saved-mail-workflow-task" onSubmit={event=>{event.preventDefault();void save(item.id,draft);}}>
     <>
      <h3>{item.review_required?'Bitte auf heutige Aktualität prüfen':'Aufgabenvorschlag'}</h3>
      <details className="saved-task-evidence"><summary>Beleg und Zuordnung prüfen</summary><blockquote>{item.evidence[0]?.quote}</blockquote>{item.project_suggestion && <p>Projektvorschlag: {item.project_suggestion.name} · {item.project_suggestion.reason}</p>}</details>
      <div className="saved-task-fields">
      <label>Aufgabe<textarea rows={2} value={draft.title} onChange={event=>update({title:event.target.value})} maxLength={4096} disabled={Boolean(busy)}/></label>
      <label>Projekt<select value={draft.project} onChange={event=>update({project:event.target.value})} disabled={Boolean(busy)}>
       <option value="">Ohne Projekt</option>{view.projects.map(project=><option key={project.id} value={project.id}>{project.name}</option>)}<option value="new">Neues Projekt anlegen</option>
      </select></label>
      {draft.project==='new' && <label>Neues Projekt<input value={draft.newProject} onChange={event=>update({newProject:event.target.value})} maxLength={200} disabled={Boolean(busy)}/></label>}
      </div>
      <div className="saved-task-confirmation"><small>Ohne Frist und wartende Person{draft.project==='new'?' · Neues Projekt wird mit angelegt':''}.</small><button className="primary-action" type="submit" disabled={!valid || Boolean(busy) || !draft.title.trim() || (draft.project==='new' && !draft.newProject.trim())}>{busy===item.id?'Wird gespeichert …':draft.project==='new'?'Aufgabe und Projekt bestätigen':'Aufgabe bestätigen'}</button></div>
     </>
    </form>;
   })}
  </>}
  {!loading && !view && <button type="button" onClick={()=>setRevision(value=>value+1)} disabled={!sourceVerified || Boolean(busy)}>Überblick erneut laden</button>}
 </section>;
}
