import {readMemoryViewPosition,rememberMemoryPresentation} from "./MemoryViewState";
import {useEffect, useMemo, useRef, useState} from 'react';
import {request} from './api';
import {workspaceViewApi, type FolderData, type ViewRecord} from './workspaceViewApi';
import {useWorkspaceMemoryView} from './useWorkspaceMemoryView';
import {canonicalSourceId, folderDescendants} from './WorkspaceMemoryModel';
import {ProfileSource} from './ProfileSource';
import './WorkspaceMemoryDetails.css';
export type FolderSource = {id:string;title:string;kind?:'episode'|'note';project?:string|null;projectName?:string;areas?:string[]};
export function SourceFolderAssignment({sourceId}: {sourceId:string}) {
  const {overview,error,refresh} = useWorkspaceMemoryView();
  const remote = overview?.source_folders.find(item=>item.id===sourceId);
  const [local,setLocal] = useState<ViewRecord<{folder_id:string|null}>|null>(null);
  const record = local && local.id===sourceId && local.revision >= (remote?.revision??0) ? local : remote;
  const targetRevision = useRef(0);
  const [target,setTarget] = useState<string|null>(null);
  const [busy,setBusy] = useState(false);
  const [message,setMessage] = useState<string|null>(null);
  async function choose(value:string) {
    if(busy)return;setBusy(true);setMessage(null);
    try {const current=await workspaceViewApi.get<{folder_id:string|null}>('source_folder',sourceId);setLocal(current);targetRevision.current=current.revision;setTarget(value);}
    catch{setMessage('Aktuelle Ordnerzuordnung nicht erreichbar. Es wurde nichts gespeichert.');}
    finally{setBusy(false);}
  }
  async function save(undo=false) {
    if(!overview||busy)return;setBusy(true);setMessage(null);
    try {const result = undo ? await workspaceViewApi.undo('source_folder',sourceId,record?.revision??0) : await workspaceViewApi.save('source_folder',sourceId,{folder_id:target||null},targetRevision.current);setLocal(result as ViewRecord<{folder_id:string|null}>);setTarget(null);setMessage(undo?'Vorherige Ordnerzuordnung wiederhergestellt.':'Ordnerzuordnung gespeichert.');}
    catch{setMessage('Zuordnung nicht gespeichert. Bitte aktuellen Stand laden.');}
    finally{setBusy(false);}
  }
  return <details className="memory-view-panel memory-source-folder"><summary>Virtueller Ordner{record?.data?.folder_id?` · ${overview?.folders.find(folder=>folder.id===record.data?.folder_id)?.data?.name??'Ordner'}`:''}</summary>
    {overview&&<><label>Ordner für diese Quelle<select disabled={busy} value={target??record?.data?.folder_id??''} onChange={event=>void choose(event.target.value)}><option value="">Ohne Ordner</option>{overview.folders.filter(folder=>folder.data).map(folder=><option key={folder.id} value={folder.id}>{folder.data!.name}</option>)}</select></label>
      {target!==null&&<div className="memory-view-preview"><p>Vorschau: Diese Quelle wird {target?`„${overview.folders.find(folder=>folder.id===target)?.data?.name}“ zugeordnet`:'ohne Ordner angezeigt'}.</p><button type="button" disabled={busy} onClick={()=>void save()}>Zuordnung bestätigen</button><button type="button" disabled={busy} onClick={()=>setTarget(null)}>Abbrechen</button></div>}
      {!!record?.revision&&<button type="button" disabled={busy} onClick={()=>void save(true)}>Zuordnung rückgängig</button>}</>}
    {error&&<p role="alert">Ordnerstand nicht erreichbar. <button type="button" onClick={()=>void refresh()}>Erneut laden</button></p>}{message&&<p role="status">{message}</p>}
  </details>;
}
export function MemoryFolders({sources}: {sources:FolderSource[]}) {
  const restored=useRef(readMemoryViewPosition()?.folders);
  const {overview,error,loading:metadataLoading,refresh} = useWorkspaceMemoryView();
  const [selected,setSelected] = useState<string|null>(()=>restored.current?.selected??null);
  const [name,setName] = useState('');
  const [parent,setParent] = useState('');
  const editingRevision=useRef(0);
  const [editing,setEditing] = useState<string|null>(null);
  const [project,setProject] = useState(()=>restored.current?.project??'');
  const [area,setArea] = useState(()=>restored.current?.area??'');
  const [sourceArea,setSourceArea]=useState(()=>restored.current?.sourceArea??'');
  const [sourceListOpen,setSourceListOpen]=useState(()=>restored.current?.sourceListOpen??false);
  const [assignedAreas,setAssignedAreas]=useState<Record<string,string[]>>({});
  const [areaError,setAreaError]=useState(false);
  const [areaRevision,setAreaRevision]=useState(0);
  const sourceIds=JSON.stringify(sources.filter(source=>source.kind!=='note').map(source=>source.id.replace(/^episode:/,'')));
  const areaQueryKey=`${sourceIds}:${areaRevision}`;
  const [finishedAreaQuery,setFinishedAreaQuery]=useState<string|null>(null);
  useEffect(()=>{
    let active=true;setAssignedAreas({});setAreaError(false);
    const ids=JSON.parse(sourceIds) as string[];
    const batches=Array.from({length:Math.ceil(ids.length/100)},(_,i)=>ids.slice(i*100,(i+1)*100));
    Promise.all(batches.map(ids=>request<{areas:Record<string,string[]>}>('/api/v1/workspace-source-areas',{method:'POST',body:JSON.stringify({ids})})))
      .then(values=>{if(active)setAssignedAreas(Object.assign({},...values.map(v=>v.areas)));})
      .catch(()=>{if(active)setAreaError(true);})
      .finally(()=>{if(active)setFinishedAreaQuery(areaQueryKey);});
    return()=>{active=false;};
  },[sourceIds,areaRevision]);
  const [message,setMessage] = useState<string|null>(null);
  const [busy,setBusy] = useState(false);
  const [preview,setPreview] = useState<FolderData|null>(null);
  const folders = overview?.folders.filter(folder=>folder.data)??[];
  const descendants = useMemo(()=>selected?folderDescendants(folders,selected):new Set<string>(),[overview,selected]);
  const projects = [...new Set(sources.map(source=>source.project).filter((p):p is string=>!!p))];
  const areas = [...new Set(sources.flatMap(source=>source.areas??[]))];
  useEffect(()=>{rememberMemoryPresentation('folders',{selected,project,area,sourceArea,sourceListOpen});},[selected,project,area,sourceArea,sourceListOpen]);
  const visible = sources.filter(source=>{
    const member = overview?.source_folders.find(item=>item.id===canonicalSourceId(source.id,source.kind))?.data?.folder_id;
    return (!selected||(selected==='unassigned'?!member:!!member&&descendants.has(member)))&&(!project||source.project===project)&&(!area||source.areas?.includes(area))&&(!sourceArea||assignedAreas[source.id.replace(/^episode:/,'')]?.includes(sourceArea));
  });
  async function save(undo=false,id=editing) {
    if(!overview||busy||(!undo&&!preview))return;setBusy(true);setMessage(null);
    const target=id??crypto.randomUUID();
    try {const revision = undo ? folders.find(folder=>folder.id===target)?.revision??0 : editingRevision.current;
      if(undo)await workspaceViewApi.undo('folder',target,revision);else await workspaceViewApi.save('folder',target,preview!,revision);
      editingRevision.current=0;setPreview(null);setName('');setParent('');setEditing(null);setMessage(undo?'Vorheriger Ordnerstand wiederhergestellt.':'Virtueller Ordner gespeichert.');
    }catch{setMessage('Ordneränderung nicht gespeichert. Bitte Namen, übergeordneten Ordner und aktuellen Stand prüfen. Ein neuer Ordner lässt sich erst ohne Unterordner und Quellenzuordnungen rückgängig machen.');}
    finally{setBusy(false);}
  }
  return <section className="memory-view-panel" data-memory-loading={metadataLoading || (!overview && !error) || finishedAreaQuery !== areaQueryKey} aria-label="Virtuelle Dokumentordner"><h2>Dokumentordner</h2><p>Ordner und Unterordner ordnen Quellen in dieser Ansicht. Originaldateien und ihre Fassungen bleiben erhalten.</p>
    {error&&<p role="alert">Ordneransicht nicht erreichbar. <button type="button" onClick={()=>void refresh()}>Erneut laden</button></p>}
    {!overview&&!error&&<p role="status">Ordner werden geladen …</p>}
    {overview&&<><div className="memory-folder-layout"><nav aria-label="Ordner auswählen"><button type="button" aria-pressed={selected===null} onClick={()=>setSelected(null)}>Alle Quellen dieser Ansicht</button><ul><li><button type="button" aria-pressed={selected==='unassigned'} onClick={()=>setSelected('unassigned')}>Ohne Ordner</button></li>
      {folders.filter(folder=>folder.data?.parent_id===(selected&&selected!=='unassigned'?selected:null)).map(folder=><li key={folder.id}><button type="button" aria-pressed={selected===folder.id} onClick={()=>setSelected(folder.id)}>{folder.data!.name} →</button></li>)}</ul>
      {selected&&selected!=='unassigned'&&<><p>Geöffnet: <strong>{folders.find(folder=>folder.id===selected)?.data?.name??'Ordner nicht mehr verfügbar'}</strong> · inklusive Unterordner</p><button type="button" onClick={()=>setSelected(folders.find(folder=>folder.id===selected)?.data?.parent_id??null)}>Übergeordneter Ordner</button><button type="button" onClick={()=>{const folder=folders.find(f=>f.id===selected);if(folder?.data){editingRevision.current=folder.revision;setEditing(folder.id);setName(folder.data.name);setParent(folder.data.parent_id??'');setPreview(null);}}}>Ordner bearbeiten</button><button type="button" disabled={busy} onClick={()=>void save(true,selected)}>Ordneränderung rückgängig</button></>}
    </nav><div><div className="memory-view-actions"><label>Projektfilter<select value={project} onChange={event=>setProject(event.target.value)}><option value="">Alle vorhandenen Projekte</option>{project&&!projects.includes(project)&&<option value={project}>{project} · nicht im geladenen Ausschnitt</option>}{projects.map(id=><option key={id} value={id}>{sources.find(source=>source.project===id)?.projectName??id}</option>)}</select></label><label>Bereich<select value={sourceArea} onChange={event=>setSourceArea(event.target.value)}><option value="">Alle eingeordneten Bereiche</option>{sourceArea&&!Object.values(assignedAreas).flat().includes(sourceArea)&&<option value={sourceArea}>{sourceArea} · nicht im geladenen Ausschnitt</option>}{[...new Set(Object.values(assignedAreas).flat())].sort().map(label=><option key={label} value={label}>{label}</option>)}</select></label><label>Projektbereich<select value={area} onChange={event=>setArea(event.target.value)}><option value="">Alle vorhandenen Bereiche</option>{area&&!areas.includes(area)&&<option value={area}>{area} · nicht im geladenen Ausschnitt</option>}{areas.map(id=><option key={id} value={id}>{id}</option>)}</select></label></div>
      <p>{visible.length} von {sources.length} geladenen Quellen. Diese Vorschau deckt den geladenen Ausschnitt ab; weitere Quellen können im Archiv liegen.</p>
      {areaError&&<p role="status">Bereiche konnten nicht geladen werden. Ordner und Projektfilter bleiben nutzbar. <button type="button" onClick={()=>setAreaRevision(n=>n+1)}>Bereiche neu laden</button></p>}
      {overview?.truncated?.length ? <p role="status">Die Ablageübersicht zeigt höchstens 2.000 Einträge je Art. Weitere Zuordnungen bleiben gespeichert; die Übersicht ist begrenzt.</p> : null}
      <details open={sourceListOpen} onToggle={event=>setSourceListOpen(event.currentTarget.open)}><summary>Quellenvorschau ({visible.length})</summary>{visible.slice(0,25).map(source=><article key={canonicalSourceId(source.id,source.kind)} className="memory-view-row" data-memory-row={canonicalSourceId(source.id,source.kind)}><div><strong>{source.title}</strong><ProfileSource kind={source.kind??'episode'} id={source.id.replace(/^(episode|note):/,'')} readOnly allowIgnore={false}/><SourceFolderAssignment sourceId={canonicalSourceId(source.id,source.kind)}/></div></article>)}
      {visible.length>25&&<p>Die Vorschau zeigt die ersten 25 Treffer. Verfeinere Ordner- oder Projektfilter.</p>}
      {!visible.length&&<p>Keine passende Quelle in diesem geladenen Ausschnitt.</p>}</details>
    </div></div><details open={editing !== null}><summary>{editing?'Ordner bearbeiten':'Ordner oder Unterordner anlegen'}</summary><form onSubmit={event=>{event.preventDefault();if(name.trim())setPreview({name:name.trim(),parent_id:parent||null});}}><div className="memory-view-actions"><label>Ordnername<input required maxLength={100} value={name} disabled={busy} onChange={event=>{setName(event.target.value);setPreview(null);}}/></label><label>Übergeordneter Ordner<select value={parent} disabled={busy} onChange={event=>{setParent(event.target.value);setPreview(null);}}><option value="">Oberste Ebene</option>{folders.filter(folder=>!editing||!folderDescendants(folders,editing).has(folder.id)).map(folder=><option key={folder.id} value={folder.id}>{folder.data!.name}</option>)}</select></label><button type="submit" disabled={busy||!name.trim()}>Vorschau</button></div></form>
      {preview&&<div className="memory-view-preview"><p>{editing?'Änderung':'Neuer Ordner'}: <strong>{preview.name}</strong> · {preview.parent_id?`unter ${folders.find(folder=>folder.id===preview.parent_id)?.data?.name}`:'oberste Ebene'}</p><button type="button" disabled={busy} onClick={()=>void save()}>Ordner bestätigen</button><button type="button" disabled={busy} onClick={()=>setPreview(null)}>Abbrechen</button></div>}
      {editing&&<button type="button" onClick={()=>{editingRevision.current=0;setEditing(null);setName('');setParent('');setPreview(null);}}>Bearbeitung beenden</button>}
    </details></>}{message&&<p role="status">{message}</p>}
  </section>;
}
