import {useEffect, useRef, useState} from 'react';
import {workspaceViewApi, type ViewRecord} from './workspaceViewApi';
import {initials, validateImageFile} from './WorkspaceMemoryModel';
import {useWorkspaceMemoryView} from './useWorkspaceMemoryView';
import './WorkspaceMemoryDetails.css';
import {OrganisationLogoEditor,CachedOrganisationLogo} from './OrganisationLogo';
type ImageData = {data_url: string};
const avatarCache=new Map<string,Promise<ViewRecord<ImageData>>>();
function cachedAvatar(id:string,revision?:number) {
  const key=`${id}:${revision??0}`;
  let pending=avatarCache.get(key);
  if(!pending){pending=workspaceViewApi.get<ImageData>('avatar',id).catch(error=>{avatarCache.delete(key);throw error;});avatarCache.set(key,pending);if(avatarCache.size>32)avatarCache.delete(avatarCache.keys().next().value!);}
  return pending;
}
// Local uploads are the only source. No remote lookup or generated face.
export function MemoryAvatar({id,label,available = false, revision}: {id:string;label:string;available?:boolean;revision?:number}) {
  const [imageError,setImageError]=useState(false);
  const [url,setUrl] = useState<string | null>(null);
  useEffect(() => {
    let current = true;setUrl(null);setImageError(false);
    if (available) cachedAvatar(id,revision).then(record => {if (current) setUrl(record.data?.data_url ?? null);}).catch(()=>{if(current)setImageError(true);});
    return () => {current = false;};
  },[id,available,revision]);
  return <span className="memory-avatar" aria-hidden="true" title={imageError?"Eigenes Bild gerade nicht erreichbar":undefined}>{url ? <img src={url} alt="" /> : initials(label)}</span>;
}
export function MemoryAvatarEditor({id,label,logo = false}: {id:string;label:string;logo?:boolean}) {
  const {overview,error,refresh} = useWorkspaceMemoryView();
  const [record,setRecord] = useState<ViewRecord<ImageData> | null>(null);
  const [preview,setPreview] = useState<string | null>(null);
  const [busy,setBusy] = useState(false);
  const [message,setMessage] = useState<string | null>(null);
  const [readRevision,setReadRevision]=useState(0);
  const selectionVersion=useRef(0);
  const previewRevision=useRef(0);
  const version = useRef(0);
  const input = useRef<HTMLInputElement>(null);
  const imageRevision = overview?.avatars.find(item => item.id === id)?.revision;
  useEffect(() => {const own = ++version.current;setRecord(null);setPreview(null);++selectionVersion.current;
    workspaceViewApi.get<ImageData>('avatar',id).then(result => {if (version.current === own) setRecord(result);}).catch(()=>{if(version.current===own)setMessage('Bildstand nicht erreichbar. Bitte erneut laden.');});
    return () => {++version.current;};
  },[id,imageRevision,readRevision]);
  async function choose(file?: File) {
    const selection=++selectionVersion.current;setPreview(null);
    if (!file) return;const invalid = validateImageFile(file);if(invalid){setMessage(invalid);return;}
    const own = version.current;previewRevision.current=record?.revision??0;setMessage(null);
    try {const value = await new Promise<string>((resolve,reject)=>{const reader = new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=reject;reader.readAsDataURL(file);});
      if(version.current===own&&selectionVersion.current===selection)setPreview(value);
    } catch {if(version.current===own)setMessage('Das lokale Bild konnte nicht gelesen werden.');}
  }
  async function save(undo = false) {
    if (!record || busy || (!undo && !preview)) return;
    setBusy(true);setMessage(null);
    try {const result=undo?await workspaceViewApi.undo('avatar',id,record.revision):await workspaceViewApi.save('avatar',id,{data_url:preview!},previewRevision.current);setRecord(result as ViewRecord<ImageData>);
      setPreview(null);setMessage(undo?'Vorheriges Bild wiederhergestellt.':'Eigenes Bild gespeichert.');
    }catch{setMessage('Bildänderung nicht gespeichert. Bitte den aktuellen Stand erneut laden.');}
    finally{setBusy(false);}
  }
  const image = preview ?? record?.data?.data_url;
  return <div className="memory-avatar-editor">
    <span className="memory-avatar memory-avatar-large" aria-hidden="true">{image ? <img src={image} alt=""/> : initials(label)}</span>
    <details><summary>{logo?'Eigenes Logo':'Eigenes Profilbild'}</summary><p>Lokale Datei · PNG, JPEG oder WebP · bis 1 MB</p>
      <label>Bild auswählen<input ref={input} type="file" accept="image/png,image/jpeg,image/webp" disabled={busy||!record} onChange={event=>void choose(event.target.files?.[0])}/></label>
      {preview&&<div className="memory-view-actions"><button type="button" disabled={busy} onClick={()=>void save()}>Vorschau speichern</button><button type="button" disabled={busy} onClick={()=>{setPreview(null);if(input.current)input.current.value='';}}>Verwerfen</button></div>}
      {(!!record?.revision)&&<button type="button" disabled={busy||!record} onClick={()=>void save(true)}>Bildänderung rückgängig</button>}
      {message&&<p role="status">{message}</p>}{(error||!record)&&<button type="button" disabled={busy} onClick={()=>{setReadRevision(n=>n+1);void refresh();}}>Bildstand neu laden</button>}
    </details>
    {logo&&<OrganisationLogoEditor id={id}/>}
  </div>;
}

export function WorkspaceAvatar({id,label}: {id:string;label:string}) {
  const {overview} = useWorkspaceMemoryView();
  const record = overview?.avatars.find(item=>item.id===id);
  const logo=overview?.logos?.find(item=>item.id===id);
  if(!record?.data?.available && logo && overview?.online.logos) return <span className="memory-avatar" aria-hidden="true"><CachedOrganisationLogo id={id} revision={logo.revision}/></span>;
  return <MemoryAvatar id={id} label={label} available={record?.data?.available??false} revision={record?.revision}/>;
}
