import {readMemoryViewPosition,rememberMemoryPresentation} from './MemoryViewState';
import {MemoryEntityLink} from './MemoryEntityLink';
import {useEffect,useRef,useState} from 'react';
import {workspaceViewApi} from './workspaceViewApi';
import {useWorkspaceMemoryView} from './useWorkspaceMemoryView';
import {organisationSuggestionsApi,type OrganisationSnapshot,type OrganisationSuggestion,type OrganisationConfirmation} from './organisationSuggestionsApi';
import {workspaceProfileHref} from './WorkspaceMemoryModel';
import {MemoryAvatarEditor} from './MemoryAvatar';
import './WorkspaceMemoryDetails.css';
export type OrganisationEntry={id:string;name:string};
export function OrganisationGroups({entries}: {entries:OrganisationEntry[]}) {
  const restored=useRef(readMemoryViewPosition()?.organisations);
  const {overview,error,refresh}=useWorkspaceMemoryView();
  const [snapshot,setSnapshot]=useState<OrganisationSnapshot|null>(null);
  const [basisError,setBasisError]=useState(false);
  const [members,setMembers]=useState<string[]>(()=>restored.current?.members??[]);
  const [name,setName]=useState(()=>restored.current?.name??'');
  const [editing,setEditing]=useState<string|null>(()=>restored.current?.editing??null);
  const [candidate,setCandidate]=useState<OrganisationSuggestion|null>(null);
  const editingRevision=useRef<number|null>(null);
  const previewBasis=useRef<OrganisationSnapshot|null>(null);
  const previewRequest=useRef<OrganisationConfirmation|null>(null);
  const reviewRequestPending=useRef(false);
  const [reviewLoading,setReviewLoading]=useState(false);
  const [manualDraft,setManualDraft]=useState(false);
  const [preview,setPreview]=useState(false);
  const [busy,setBusy]=useState(false);
  const actionPending=useRef(false);
  const requestVersion=useRef(0);
  const [message,setMessage]=useState<string|null>(null);
  const [memberSearch,setMemberSearch]=useState('');
  const [logoId,setLogoId]=useState('');
  const [openGroups,setOpenGroups]=useState<string[]>([]);
  const allEntries=snapshot?.entries??entries;
  const groups=snapshot?.groups??overview?.organisation_groups.filter(group=>group.data)??[];
  const label=(id:string)=>allEntries.find(entry=>entry.id===id)?.name??entries.find(entry=>entry.id===id)?.name??id;
  async function loadBasis(recheckDraft=false) {
    if(reviewRequestPending.current)return;
    if(recheckDraft){reviewRequestPending.current=true;setReviewLoading(true);invalidatePreview();}
    const version=++requestVersion.current;
    try{
      const current=await organisationSuggestionsApi.overview();
      if(version===requestVersion.current){
        setSnapshot(current);setBasisError(false);
        if(recheckDraft){
          if(editing){
            const group=current.groups.find(group=>group.id===editing);
            if(group){editingRevision.current=group.revision;setMessage('Aktueller Gruppenstand geladen. Dein Entwurf bleibt erhalten. Prüfe die gespeicherte Gruppe und deinen Entwurf in einer neuen Vorschau.');}
            else{editingRevision.current=null;setEditing(null);setCandidate(null);setManualDraft(true);setMessage('Die bisherige Gruppe ist nicht mehr vorhanden. Dein Entwurf bleibt als eigene Anzeigegruppe erhalten. Bitte erneut ansehen und bestätigen.');}
          }else if(candidate){
            const matching=current.suggestions.find(value=>value.id===candidate.id);
            setCandidate(matching??null);setManualDraft(!matching);
            setMessage(matching?'Aktueller Vorschlag geladen. Dein bearbeiteter Entwurf bleibt erhalten. Bitte eine neue Vorschau prüfen.':'Der Vorschlag hat sich verändert oder wurde bereits entschieden. Dein bearbeiteter Entwurf wird als eigene Anzeigegruppe geprüft. Bitte eine neue Vorschau ansehen.');
          }else{setMessage('Aktueller Stand geladen. Dein Entwurf bleibt erhalten. Bitte eine neue Vorschau prüfen.');}
        }
      }
    }catch{if(version===requestVersion.current)setBasisError(true);}
    finally{if(recheckDraft){reviewRequestPending.current=false;setReviewLoading(false);}}
  }
  useEffect(()=>{void loadBasis();const changed=()=>void loadBasis();window.addEventListener('workspace-view-changed',changed);return()=>{++requestVersion.current;window.removeEventListener('workspace-view-changed',changed);};},[]);
  useEffect(()=>{rememberMemoryPresentation('organisations',{members,name,editing});},[members,name,editing]);
  useEffect(()=>{if(!snapshot||!editing||editingRevision.current!==null)return;const group=snapshot.groups.find(group=>group.id===editing);if(group)editingRevision.current=group.revision;else setEditing(null);},[snapshot,editing]);
  function invalidatePreview(){previewBasis.current=null;previewRequest.current=null;setPreview(false);}
  function finish(){editingRevision.current=null;invalidatePreview();setEditing(null);setCandidate(null);setManualDraft(false);setName('');setMembers([]);setMemberSearch('');}
  function chooseSuggestion(value:OrganisationSuggestion){editingRevision.current=null;setEditing(null);setCandidate(value);setManualDraft(false);setName(value.name);setMembers([...value.members]);setMemberSearch('');invalidatePreview();setMessage(null);}
  async function action(run:()=>Promise<unknown>,success:string,clear=false){
    if(actionPending.current)return;
    actionPending.current=true;setBusy(true);setMessage(null);
    try{await run();if(clear)finish();setMessage(success);await loadBasis();await refresh();}
    catch{setMessage('Nicht gespeichert: Quelle, Organisation oder Gruppenstand möglicherweise geändert. Dein Entwurf bleibt erhalten. Bitte aktuellen Stand laden und die Vorschau erneut prüfen.');}
    finally{actionPending.current=false;setBusy(false);}
  }
  async function save(){
    const request=previewRequest.current;
    if(!preview||!request||basisError||reviewLoading)return;
    await action(()=>organisationSuggestionsApi.confirm(request),'Anzeigegruppe gespeichert.',true);
  }
  const canReview=!!snapshot?.complete&&!basisError&&!busy&&!reviewLoading;
  function createPreview(){
    if(!snapshot||!canReview||members.length<2||!name.trim())return;
    if((editing&&snapshot.groups.find(group=>group.id===editing)?.revision!==editingRevision.current)
        ||(candidate&&!snapshot.suggestions.some(value=>value.id===candidate.id))){
      invalidatePreview();setMessage('Nicht gespeichert: Vorschlag oder Gruppe wurde verändert. Dein Entwurf bleibt erhalten. Bitte aktuellen Stand laden und erneut prüfen.');return;
    }
    previewBasis.current=snapshot;
    previewRequest.current={source_revision:snapshot.source_revision,groups_revision:snapshot.groups_revision,
      candidate_id:candidate?.id??null,group_id:editing,group_revision:editingRevision.current??0,name:name.trim(),members:[...members]};
    setPreview(true);
  }
  const currentGroup=previewBasis.current?.groups.find(group=>group.id===previewRequest.current?.group_id);
  const visibleEntries=allEntries.filter(entry=>entry.name.toLocaleLowerCase().includes(memberSearch.toLocaleLowerCase()));
  // Als Gruppe der Grundlage: Überschrift klein, Inhalt in der Fläche, der eine nötige Satz als Fußnote.
  return <section className="memory-view-panel gd-karte g-gruppe" aria-label="Organisationsgruppen"><div className="g-gruppe-kopf"><h2 className="g-gruppe-titel">Gemeinsame Ansichten</h2></div><div className="g-flaeche g-flaeche-frei">
    {(error||basisError)&&<p role="alert">Organisationsstand nicht erreichbar. <button type="button" disabled={busy||reviewLoading} onClick={()=>{void loadBasis(true);void refresh();}}>Aktuellen Stand laden</button></p>}
    {!snapshot&&!basisError&&<p role="status">Organisationsvorschläge werden aus dem gespeicherten Bestand vorbereitet …</p>}
    {snapshot&&<p>{snapshot.total} Organisationen · Vorschläge nur aus lokalen Namensregeln.</p>}
    {snapshot?.suggestions.map(value=><section key={value.id} className="memory-view-preview" aria-label={`Vorschlag ${value.name}`}><h3>Anzeigegruppe {value.name}</h3><p>{value.reason}</p><ul>{value.members.map(id=><li key={id}>{label(id)}</li>)}</ul><div className="memory-view-actions"><button type="button" disabled={!canReview} onClick={()=>chooseSuggestion(value)}>Vorschlag bearbeiten</button><button type="button" disabled={!canReview} onClick={()=>void action(()=>organisationSuggestionsApi.dismiss(value.id,{source_revision:snapshot.source_revision,groups_revision:snapshot.groups_revision}),'Vorschlag abgelehnt.')}>Vorschlag ablehnen</button></div></section>)}
    {snapshot&&!snapshot.suggestions.length&&<p>Keine offenen Gruppenvorschläge nach diesen konservativen Namensregeln.</p>}
    {groups.map(group=><details key={group.id} onToggle={event=>{const open=event.currentTarget.open;setOpenGroups(current=>open?[...new Set([...current,group.id])]:current.filter(id=>id!==group.id));}}><summary>{group.data!.name} · {group.data!.members.length} Einzelakten</summary>{openGroups.includes(group.id)&&<MemoryAvatarEditor id={`organisation-group:${group.id}`} label={group.data!.name} logo/>}<ul>{group.data!.members.map(id=><li key={id}><MemoryEntityLink href={workspaceProfileHref(id,'organizations',window.location?.search??'')}>{label(id)}</MemoryEntityLink></li>)}</ul><div className="memory-view-actions"><button type="button" disabled={!canReview} onClick={()=>{editingRevision.current=group.revision;setEditing(group.id);setCandidate(null);setManualDraft(false);setName(group.data!.name);setMembers([...group.data!.members]);setMemberSearch('');invalidatePreview();}}>Gruppe bearbeiten</button><button type="button" disabled={busy} onClick={()=>void action(()=>workspaceViewApi.undo('organisation_group',group.id,group.revision),'Vorherige Gruppenansicht wiederhergestellt.',editing===group.id)}>Gruppierung rückgängig</button></div></details>)}
    {!!snapshot?.dismissals.length&&<details><summary>Abgelehnte Vorschläge ({snapshot.dismissals.length})</summary>{snapshot.dismissals.map(record=><p key={record.id}>Abgelehnter Namensvorschlag: {record.name??'nicht mehr im aktuellen Bestand'} <button type="button" disabled={busy} onClick={()=>void action(()=>organisationSuggestionsApi.undoDismissal(record.id,record.revision),'Ablehnung zurückgenommen.')}>Ablehnung rückgängig</button></p>)}</details>}
    {overview&&snapshot&&<details><summary>Eigene Logos der Einzelorganisationen</summary><label>Organisation auswählen<select value={logoId} onChange={event=>setLogoId(event.target.value)}><option value="">Bitte wählen</option>{allEntries.map(entry=><option key={entry.id} value={entry.id}>{entry.name}</option>)}</select></label>{logoId&&allEntries.some(entry=>entry.id===logoId)&&<MemoryAvatarEditor id={logoId} label={label(logoId)} logo/>}</details>}
    {(snapshot||members.length>0||name||editing)&&<details open={!!editing||!!candidate||manualDraft}><summary>{editing?'Anzeigegruppe bearbeiten':candidate?'Vorschlag prüfen':'Anzeigegruppe anlegen'}</summary>
      {candidate&&<p>{candidate.reason}</p>}
      <form onSubmit={event=>{event.preventDefault();createPreview();}}>
        <label>Name der Gruppe<input required value={name} maxLength={200} disabled={busy} onChange={event=>{setName(event.target.value);invalidatePreview();}}/></label>
        <label>Organisationen finden<input type="search" value={memberSearch} disabled={busy} onChange={event=>setMemberSearch(event.target.value)}/></label>
        <fieldset disabled={!canReview} style={{maxHeight:'20rem',overflowY:'auto'}}><legend>{snapshot?'Organisationen aus dem vollständigen Bestand auswählen':'Vorherige Auswahl · aktueller Bestand wird geladen'}</legend>{visibleEntries.map(entry=><label key={entry.id}><input type="checkbox" checked={members.includes(entry.id)} onChange={event=>{setMembers(current=>event.target.checked?[...current,entry.id]:current.filter(id=>id!==entry.id));invalidatePreview();}}/>{entry.name}</label>)}</fieldset>
        {members.filter(id=>!allEntries.some(entry=>entry.id===id)).map(id=><label key={id}><input type="checkbox" checked disabled={busy} onChange={()=>{setMembers(current=>current.filter(member=>member!==id));invalidatePreview();}}/>{label(id)} · keine aktuelle zulässige Quelle</label>)}
        <p>{members.length} Organisationen ausgewählt. Mindestens zwei erforderlich.</p><button type="submit" disabled={!canReview||members.length<2||!name.trim()}>Gruppierung ansehen</button>
      </form>
      {preview&&<div className="memory-view-preview">{currentGroup&&<section aria-label="Aktuelle gespeicherte Gruppe"><p>Aktuell gespeichert: <strong>{currentGroup.data!.name}</strong></p><ul>{currentGroup.data!.members.map(id=><li key={id}>{label(id)}</li>)}</ul><p>Mit deiner Bestätigung wird diese Gruppenansicht durch deinen folgenden Entwurf ersetzt.</p></section>}<p>Anzeigegruppe <strong>{name}</strong></p><ul>{members.map(id=><li key={id}>{label(id)}</li>)}</ul><p>Die Bestätigung speichert eine reversible Anzeigegruppe; sie bestätigt keine rechtliche Verbindung.</p><button type="button" disabled={busy||basisError||reviewLoading} onClick={()=>void save()}>Gruppierung bestätigen</button><button type="button" disabled={busy} onClick={invalidatePreview}>Abbrechen</button></div>}
      {(editing||candidate||manualDraft)&&<button type="button" disabled={busy} onClick={finish}>Bearbeitung beenden</button>}
    </details>}
    {message&&<p role="status">{message} {message.startsWith('Nicht gespeichert')&&<button type="button" disabled={busy||reviewLoading} onClick={()=>void loadBasis(true)}>Aktuellen Stand laden</button>}</p>}
  </div><p className="g-gruppe-fussnote">Gruppen fassen Akten nur für die Ansicht zusammen; jede Akte bleibt einzeln erreichbar. Ein Vorschlag ist kein Nachweis gleicher Rechtsperson.</p></section>;
}
