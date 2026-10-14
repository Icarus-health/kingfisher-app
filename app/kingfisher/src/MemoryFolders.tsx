import {readMemoryViewPosition,rememberMemoryPresentation} from './MemoryViewState';
import {useEffect,useMemo,useRef,useState} from 'react';
import {CATEGORY_FEEDBACK_EVENT} from './api';
import {workspaceViewApi,type FolderData,type ViewRecord} from './workspaceViewApi';
import {workspaceDocumentsApi,documentAreaLabel,type WorkspaceDocumentPage} from './workspaceDocumentsApi';
import {folderDescendants} from './WorkspaceMemoryModel';
import {ProfileSource} from './ProfileSource';
import './WorkspaceMemoryDetails.css';

// Bestehender reiner Graphadapter bleibt für andere Aufrufer typkompatibel.
export type FolderSource={id:string;title:string;kind?:'episode'|'note';project?:string|null;projectName?:string;areas?:string[]};
type Assignment=ViewRecord<{folder_id:string|null}>;
export function SourceFolderAssignment({sourceId,folders:givenFolders,initialRecord}: {sourceId:string;folders?:ViewRecord<FolderData>[];initialRecord?:Assignment}) {
  const [expanded,setExpanded]=useState(false);
  const [folders,setFolders]=useState(givenFolders??[]);
  const [record,setRecord]=useState<Assignment|null>(initialRecord??null);
  const [loading,setLoading]=useState(!givenFolders);
  const [error,setError]=useState(false);
  const [retry,setRetry]=useState(0);
  const targetRevision=useRef(0);
  const [target,setTarget]=useState<string|null>(null);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState<string|null>(null);
  useEffect(()=>{
    if(givenFolders){setFolders(givenFolders);if(initialRecord)setRecord(initialRecord);setLoading(false);return;}
    if(!expanded)return;
    let active=true;setLoading(true);setError(false);
    Promise.all([workspaceDocumentsApi.folders(),workspaceViewApi.get<{folder_id:string|null}>('source_folder',sourceId)])
      .then(([metadata,current])=>{if(active){setFolders(metadata.folders);setRecord(current);}})
      .catch(()=>{if(active)setError(true);})
      .finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[sourceId,givenFolders,initialRecord,retry,expanded]);
  async function choose(value:string) {
    if(busy)return;setBusy(true);setMessage(null);
    try {const current=await workspaceViewApi.get<{folder_id:string|null}>('source_folder',sourceId);setRecord(current);targetRevision.current=current.revision;setTarget(value);}
    catch{setMessage('Aktuelle Ordnerzuordnung nicht erreichbar. Es wurde nichts gespeichert.');}
    finally{setBusy(false);}
  }
  async function save(undo=false) {
    if(busy||error||loading)return;setBusy(true);setMessage(null);
    try {const result=undo?await workspaceViewApi.undo('source_folder',sourceId,record?.revision??0):await workspaceViewApi.save('source_folder',sourceId,{folder_id:target||null},targetRevision.current);setRecord(result as Assignment);setTarget(null);setMessage(undo?'Vorherige Ordnerzuordnung wiederhergestellt.':'Ordnerzuordnung gespeichert.');}
    catch{setMessage('Zuordnung nicht gespeichert. Bitte aktuellen Stand laden.');}
    finally{setBusy(false);}
  }
  return <details className="memory-view-panel memory-source-folder" onToggle={event=>setExpanded(event.currentTarget.open)}><summary>Virtueller Ordner{record?.data?.folder_id?` · ${folders.find(folder=>folder.id===record.data?.folder_id)?.data?.name??'Ordner'}`:''}</summary>
    {expanded&&loading&&<p role="status">Ordner werden geladen …</p>}
    {expanded&&!loading&&!error&&<><label>Ordner für diese Quelle<select disabled={busy} value={target??record?.data?.folder_id??''} onChange={event=>void choose(event.target.value)}><option value="">Ohne Ordner</option>{folders.filter(folder=>folder.data).map(folder=><option key={folder.id} value={folder.id}>{folder.data!.name}</option>)}</select></label>
      {target!==null&&<div className="memory-view-preview"><p>Vorschau: Diese Quelle wird {target?`„${folders.find(folder=>folder.id===target)?.data?.name}“ zugeordnet`:'ohne Ordner angezeigt'}.</p><button type="button" disabled={busy} onClick={()=>void save()}>Zuordnung bestätigen</button><button type="button" disabled={busy} onClick={()=>setTarget(null)}>Abbrechen</button></div>}
      {!!record?.revision&&<button type="button" disabled={busy} onClick={()=>void save(true)}>Zuordnung rückgängig</button>}</>}
    {expanded&&error&&<p role="alert">Ordnerstand nicht erreichbar. <button type="button" onClick={()=>setRetry(n=>n+1)}>Erneut laden</button></p>}{message&&<p role="status">{message}</p>}
  </details>;
}

export function MemoryFolders() {
  const restored=useRef(readMemoryViewPosition()?.folders);
  const [selected,setSelected]=useState<string|null>(()=>restored.current?.selected??null);
  const [project,setProject]=useState(()=>restored.current?.project??'');
  const [area,setArea]=useState(()=>restored.current?.area??'');
  const [sourceArea,setSourceArea]=useState(()=>restored.current?.sourceArea??'');
  const [q,setQ]=useState(()=>restored.current?.q??'');
  const [offset,setOffset]=useState(()=>restored.current?.offset??0);
  const [limit]=useState(()=>restored.current?.limit??25);
  const [sourceListOpen,setSourceListOpen]=useState(()=>restored.current?.sourceListOpen??true);
  const [data,setData]=useState<WorkspaceDocumentPage|null>(null);
  const [error,setError]=useState(false);
  const [retry,setRetry]=useState(0);
  const [finished,setFinished]=useState<string|null>(null);
  const queryKey=JSON.stringify([q,selected,project,area,sourceArea,offset,limit]);
  const key=JSON.stringify([queryKey,retry]);
  const [loadedQuery,setLoadedQuery]=useState<string|null>(null);
  const loading=finished!==key;
  const [name,setName]=useState('');
  const [parent,setParent]=useState('');
  const editingRevision=useRef(0);
  const [editing,setEditing]=useState<string|null>(null);
  const [message,setMessage]=useState<string|null>(null);
  const [busy,setBusy]=useState(false);
  const [preview,setPreview]=useState<FolderData|null>(null);
  const folders=data?.options.folders??[];
  const editingDescendants=useMemo(()=>editing?folderDescendants(folders,editing):new Set<string>(),[folders,editing]);
  const projects=data?.options.projects??[];
  const sourceAreas=data?.options.source_areas??[];
  const areas=data?.options.project_areas??[];
  useEffect(()=>{
    let active=true;setError(false);
    workspaceDocumentsApi.page({q,folder_id:selected??'',project_id:project,source_area:sourceArea,project_area:area,offset,limit})
      .then(value=>{if(active){setData(value);setLoadedQuery(queryKey);}})
      .catch(()=>{if(active){setError(true);setData(old=>old?{...old,items:[]}:null);}})
      .finally(()=>{if(active)setFinished(key);});
    return()=>{active=false;};
  },[key]);
  useEffect(()=>{
    const changed=()=>setRetry(n=>n+1);
    window.addEventListener('workspace-view-changed',changed);
    window.addEventListener(CATEGORY_FEEDBACK_EVENT,changed);
    window.addEventListener('focus',changed);
    // Eine offene Liste prüft Quellenentzug und Notizänderungen erneut lokal.
    const timer=window.setInterval?.(()=>{if(!document.hidden)changed();},15000);
    return()=>{window.removeEventListener('workspace-view-changed',changed);window.removeEventListener(CATEGORY_FEEDBACK_EVENT,changed);window.removeEventListener('focus',changed);if(timer!==undefined)window.clearInterval(timer);};
  },[]);
  useEffect(()=>{rememberMemoryPresentation('folders',{selected,project,area,sourceArea,sourceListOpen,q,offset,limit});},[selected,project,area,sourceArea,sourceListOpen,q,offset,limit]);
  function selectFolder(id:string|null){setSelected(id);setOffset(0);}
  async function save(undo=false,id=editing) {
    if(loading||error||busy||(!undo&&!preview))return;setBusy(true);setMessage(null);
    const target=id??crypto.randomUUID();
    try {const revision=undo?folders.find(folder=>folder.id===target)?.revision??0:editingRevision.current;
      if(undo)await workspaceViewApi.undo('folder',target,revision);else await workspaceViewApi.save('folder',target,preview!,revision);
      editingRevision.current=0;setPreview(null);setName('');setParent('');setEditing(null);setMessage(undo?'Vorheriger Ordnerstand wiederhergestellt.':'Virtueller Ordner gespeichert.');
    }catch{setMessage('Ordneränderung nicht gespeichert. Bitte Namen, übergeordneten Ordner und aktuellen Stand prüfen. Ein neuer Ordner lässt sich erst ohne Unterordner und Quellenzuordnungen rückgängig machen.');}
    finally{setBusy(false);}
  }
  return <section className="memory-view-panel memory-directory" data-memory-loading={loading} aria-label="Virtuelle Dokumentordner"><header><p className="eyebrow">GEDÄCHTNIS</p><h1>Dokumente</h1><p>Gespeicherte Dokumente und Notizen durchsuchen und in virtuellen Ordnern ablegen. Originaldateien und ihre Fassungen bleiben erhalten.</p></header>
    <label className="directory-search">Titel und Inhalt suchen<input type="search" maxLength={200} value={q} onChange={event=>{setQ(event.target.value.slice(0,200));setOffset(0);}} placeholder="Begriff, Titel oder Dateiname …"/></label>
    {error&&!loading&&<p role="alert">Dokumentablage nicht erreichbar. <button type="button" onClick={()=>setRetry(n=>n+1)}>Erneut laden</button></p>}
    {loading&&<p role="status">Dokumente werden geladen …</p>}
    {data&&<><div className="memory-folder-layout"><nav aria-label="Ordner auswählen"><h2>Dokumentordner</h2><button type="button" aria-pressed={selected===null} onClick={()=>selectFolder(null)}>Alle Dokumente und Notizen</button><ul><li><button type="button" aria-pressed={selected==='unassigned'} onClick={()=>selectFolder('unassigned')}>Ohne Ordner</button></li>
      {folders.filter(folder=>folder.data?.parent_id===(selected&&selected!=='unassigned'?selected:null)).map(folder=><li key={folder.id}><button type="button" aria-pressed={selected===folder.id} onClick={()=>selectFolder(folder.id)}>{folder.data!.name} →</button></li>)}</ul>
      {selected&&selected!=='unassigned'&&<><p>Geöffnet: <strong>{folders.find(folder=>folder.id===selected)?.data?.name??'Ordner nicht mehr verfügbar'}</strong> · inklusive Unterordner</p><button type="button" onClick={()=>selectFolder(folders.find(folder=>folder.id===selected)?.data?.parent_id??null)}>Übergeordneter Ordner</button><button type="button" disabled={loading||error} onClick={()=>{const folder=folders.find(f=>f.id===selected);if(folder?.data){editingRevision.current=folder.revision;setEditing(folder.id);setName(folder.data.name);setParent(folder.data.parent_id??'');setPreview(null);}}}>Ordner bearbeiten</button><button type="button" disabled={busy||loading||error} onClick={()=>void save(true,selected)}>Ordneränderung rückgängig</button></>}
    </nav><div><div className="memory-view-actions"><label>Projektfilter<select value={project} onChange={event=>{setProject(event.target.value);setOffset(0);}}><option value="">Alle vorhandenen Projekte</option>{project&&!projects.some(item=>item.id===project)&&<option value={project}>Gewähltes Projekt · ohne aktuelle Dokumente</option>}{projects.map(item=><option key={item.id} value={item.id}>{item.name}{['done','dropped'].includes(item.status)?' · geschlossen':''}</option>)}</select></label>
      <label>Bereich<select value={sourceArea} onChange={event=>{setSourceArea(event.target.value);setOffset(0);}}><option value="">Alle eingeordneten Bereiche</option>{sourceArea&&!sourceAreas.some(item=>item.id===sourceArea)&&<option value={sourceArea}>{documentAreaLabel(sourceArea)} · ohne aktuelle Zuordnung</option>}{sourceAreas.map(item=><option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
      <label>Projektbereich<select value={area} onChange={event=>{setArea(event.target.value);setOffset(0);}}><option value="">Alle vorhandenen Projektbereiche</option>{area&&!areas.includes(area)&&<option value={area}>{documentAreaLabel(area)} · ohne aktuelle Dokumente</option>}{areas.map(id=><option key={id} value={id}>{documentAreaLabel(id)}</option>)}</select></label></div>
      {loadedQuery===queryKey&&!error&&<><p>{data.total} passende Dokumente und Notizen im vollständigen aktuellen Bestand.</p><details open={sourceListOpen} onToggle={event=>setSourceListOpen(event.currentTarget.open)}><summary>Dokumente und Notizen ({data.total})</summary>
        {data.items.map(source=><article key={source.id} className="memory-view-row" data-memory-row={source.id}><div><strong>{source.title}</strong><p>{source.preview}</p>{source.project_name&&<p>Projekt: {source.project_name}</p>}<ProfileSource kind={source.kind} id={source.id.replace(/^(episode|note):/,'')} readOnly allowIgnore={false}/><SourceFolderAssignment sourceId={source.id} folders={folders} initialRecord={{kind:'source_folder',id:source.id,revision:source.source_folder_revision,data:{folder_id:source.folder_id}}}/></div></article>)}
        {!data.items.length&&<p>{data.total?'Auf dieser Seite liegen nach einer Bestandsänderung keine Treffer mehr. Gehe zur vorherigen Seite.':'Keine passenden Dokumente oder Notizen.'}</p>}
        <nav className="memory-view-actions" aria-label="Dokumentseiten"><button type="button" disabled={loading||offset===0} onClick={()=>setOffset(Math.max(0,offset-limit))}>Vorherige Seite</button><span>Seite {Math.floor(offset/limit)+1}{data.total>0?` von ${Math.ceil(data.total/limit)}`:''}</span><button type="button" disabled={loading||!data.has_more||offset+limit>1e8} onClick={()=>setOffset(offset+limit)}>Nächste Seite</button></nav>
      </details></>}
    </div></div><details open={editing!==null}><summary>{editing?'Ordner bearbeiten':'Ordner oder Unterordner anlegen'}</summary><form onSubmit={event=>{event.preventDefault();if(name.trim())setPreview({name:name.trim(),parent_id:parent||null});}}><div className="memory-view-actions"><label>Ordnername<input required maxLength={100} value={name} disabled={busy||loading||error} onChange={event=>{setName(event.target.value);setPreview(null);}}/></label><label>Übergeordneter Ordner<select value={parent} disabled={busy||loading||error} onChange={event=>{setParent(event.target.value);setPreview(null);}}><option value="">Oberste Ebene</option>{folders.filter(folder=>!editingDescendants.has(folder.id)).map(folder=><option key={folder.id} value={folder.id}>{folder.data!.name}</option>)}</select></label><button type="submit" disabled={busy||loading||error||!name.trim()}>Vorschau</button></div></form>
      {preview&&<div className="memory-view-preview"><p>{editing?'Änderung':'Neuer Ordner'}: <strong>{preview.name}</strong> · {preview.parent_id?`unter ${folders.find(folder=>folder.id===preview.parent_id)?.data?.name}`:'oberste Ebene'}</p><button type="button" disabled={busy||loading||error} onClick={()=>void save()}>Ordner bestätigen</button><button type="button" disabled={busy} onClick={()=>setPreview(null)}>Abbrechen</button></div>}
      {editing&&<button type="button" onClick={()=>{editingRevision.current=0;setEditing(null);setName('');setParent('');setPreview(null);}}>Bearbeitung beenden</button>}
    </details></>}{message&&<p role="status">{message}</p>}
  </section>;
}
