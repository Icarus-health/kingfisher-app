import {useEffect,useRef,useState} from 'react';
import {request} from './api';
import {workspaceViewApi,type ViewRecord} from './workspaceViewApi';
import {useWorkspaceMemoryView} from './useWorkspaceMemoryView';
type Logo={domain:string;data_url:string};
const cache=new Map<string,Promise<ViewRecord<Logo>>>();
function cached(id:string,revision:number){const key=`${id}:${revision}`;let value=cache.get(key);if(!value){value=workspaceViewApi.get<Logo>('organisation_logo',id);cache.set(key,value);value.catch(()=>cache.delete(key));if(cache.size>32)cache.delete(cache.keys().next().value!);}return value;}

export function CachedOrganisationLogo({id,revision}: {id:string;revision:number}) {
  const [url,setUrl]=useState<string|null>(null);
  useEffect(()=>{let active=true;setUrl(null);cached(id,revision).then(record=>{if(active)setUrl(record.data?.data_url??null);}).catch(()=>{});return()=>{active=false;};},[id,revision]);
  return url ? <img src={url} alt=""/> : null;
}

export function OrganisationLogoEditor({id}: {id:string}) {
  const {overview,refresh}=useWorkspaceMemoryView();
  const [record,setRecord]=useState<ViewRecord<Logo>|null>(null);
  const [domain,setDomain]=useState('');
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState('');
  const [readRevision,setReadRevision]=useState(0);
  const version=useRef(0),pending=useRef(false);
  const revision=overview?.logos?.find(r=>r.id===id)?.revision;
  useEffect(()=>{const own=++version.current;setRecord(null);setDomain('');setMessage('');workspaceViewApi.get<Logo>('organisation_logo',id).then(value=>{if(own===version.current){setRecord(value);setDomain(value.data?.domain??'');}}).catch(()=>{if(own===version.current)setMessage('Bildstand nicht erreichbar.');});return()=>{version.current++;};},[id,revision,readRevision]);
  async function load(){if(!record||pending.current)return;const own=version.current;pending.current=true;setBusy(true);setMessage('');
    try{const value=await request<ViewRecord<Logo>>(`/api/v1/workspace-logos/${encodeURIComponent(id)}`,{method:'POST',body:JSON.stringify({domain:domain.trim(),revision:record.revision})});if(own===version.current){setRecord(value);setMessage('Firmenbild lokal gespeichert.');}window.dispatchEvent(new Event('workspace-view-changed'));}
    catch{if(own===version.current)setMessage('Firmenbild nicht übernommen. Prüfe die Domain und die Online-Freigabe oder lade ein eigenes Logo hoch.');}
    finally{pending.current=false;if(own===version.current)setBusy(false);}}
  return <details className="memory-online-logo"><summary>Firmenbild aus öffentlicher Domain</summary>
    {!overview?.online.logos ? <p>Online-Firmenbilder sind ausgeschaltet. <a href="/settings#workspace-online">Auswahl öffnen</a></p> : <>
      <p>Bestätige die Domain dieser Organisation. Die Seite erhält nur den Bildabruf und deine Internetadresse. Das gespeicherte Bild ist eine Anzeigehilfe, kein Identitätsnachweis.</p>
      <label>Öffentliche Firmendomain<input disabled={busy} value={domain} onChange={e=>setDomain(e.target.value)} placeholder="beispiel.de" maxLength={253}/></label>
      <button type="button" disabled={busy||!record||!domain.trim()} onClick={()=>void load()}>{busy?'Bild wird geladen …':'Domain bestätigen und Firmenbild laden'}</button>
    </>}
    {record?.data&&<p><img style={{width:40,height:40,objectFit:'contain'}} src={record.data.data_url} alt="Gespeichertes Firmenbild"/> {record.data.domain}</p>}
    {record?.revision ? <button disabled={busy} type="button" onClick={()=>{setBusy(true);workspaceViewApi.undo('organisation_logo',id,record.revision).catch(()=>setMessage('Rückgängig nicht bestätigt.')).finally(()=>setBusy(false));}}>Firmenbildänderung rückgängig</button>:null}
    {message&&<p role="status">{message}<button type="button" onClick={()=>{setReadRevision(n=>n+1);void refresh();}}>Stand laden</button></p>}
  </details>;
}
