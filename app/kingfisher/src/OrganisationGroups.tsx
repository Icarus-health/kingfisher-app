import {useRef,useState} from 'react';
import {workspaceViewApi} from './workspaceViewApi';
import {useWorkspaceMemoryView} from './useWorkspaceMemoryView';
import {workspaceProfileHref} from "./WorkspaceMemoryModel";
import {MemoryAvatarEditor} from './MemoryAvatar';
import './WorkspaceMemoryDetails.css';
export type OrganisationEntry={id:string;name:string};
export function OrganisationGroups({entries}: {entries:OrganisationEntry[]}) {
  const {overview,error,refresh}=useWorkspaceMemoryView();
  const [members,setMembers]=useState<string[]>([]);
  const [name,setName]=useState('');
  const editingRevision=useRef(0);
  const [editing,setEditing]=useState<string|null>(null);
  const [preview,setPreview]=useState(false);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState<string|null>(null);
  const groups=overview?.organisation_groups.filter(group=>group.data)??[];
  const label=(id:string)=>entries.find(entry=>entry.id===id)?.name??id;
  async function save(undo=false,id=editing) {
    if(!overview||busy||(!undo&&(!preview||!name.trim()||members.length<2)))return;
    setBusy(true);setMessage(null);const target=id??crypto.randomUUID();
    try{const revision=undo?groups.find(group=>group.id===target)?.revision??0:editingRevision.current;
      if(undo)await workspaceViewApi.undo('organisation_group',target,revision);else await workspaceViewApi.save('organisation_group',target,{name:name.trim(),members},revision);
      editingRevision.current=0;setPreview(false);setEditing(null);setName('');setMembers([]);setMessage(undo?'Vorherige Gruppenansicht wiederhergestellt.':'Anzeigegruppe gespeichert.');
    }catch{setMessage('Gruppe nicht gespeichert. Bitte aktuellen Stand prüfen.');}finally{setBusy(false);}
  }
  return <section className="memory-view-panel" aria-label="Organisationsgruppen"><h2>Gemeinsame Ansichten</h2><p>Wähle Organisationen ausdrücklich für eine Anzeigegruppe. Einzelakten, Rechnungsaussteller und rechtliche Absender bleiben einzeln erreichbar.</p>
    {error&&<p role="alert">Gruppen nicht erreichbar. <button type="button" onClick={()=>void refresh()}>Erneut laden</button></p>}
    {groups.map(group=><details key={group.id}><summary>{group.data!.name} · {group.data!.members.length} Einzelakten</summary><MemoryAvatarEditor id={`organisation-group:${group.id}`} label={group.data!.name} logo/><ul>{group.data!.members.map(id=><li key={id}><a href={workspaceProfileHref(id,'organizations',window.location?.search??'')}>{label(id)}</a></li>)}</ul><div className="memory-view-actions"><button type="button" disabled={busy} onClick={()=>{editingRevision.current=group.revision;setEditing(group.id);setName(group.data!.name);setMembers(group.data!.members);setPreview(false);}}>Gruppe bearbeiten</button><button type="button" disabled={busy} onClick={()=>void save(true,group.id)}>Gruppierung rückgängig</button></div></details>)}
    {overview&&<details><summary>Eigene Logos der Einzelorganisationen</summary>{entries.map(entry=><section key={entry.id}><h3>{entry.name}</h3><MemoryAvatarEditor id={entry.id} label={entry.name} logo/></section>)}</details>}
    {overview&&<details open={!!editing}><summary>{editing?'Anzeigegruppe bearbeiten':'Anzeigegruppe anlegen'}</summary><form onSubmit={event=>{event.preventDefault();if(members.length>=2&&name.trim())setPreview(true);}}><label>Name der Gruppe<input required value={name} maxLength={100} disabled={busy} onChange={event=>{setName(event.target.value);setPreview(false);}}/></label><fieldset disabled={busy}><legend>Organisationen aus dieser Seite auswählen</legend>{entries.map(entry=><label key={entry.id}><input type="checkbox" checked={members.includes(entry.id)} onChange={event=>{setMembers(current=>event.target.checked?[...current,entry.id]:current.filter(id=>id!==entry.id));setPreview(false);}}/>{entry.name}</label>)}</fieldset>
      {members.filter(id=>!entries.some(entry=>entry.id===id)).map(id=><label key={id}><input type="checkbox" checked onChange={()=>{setMembers(current=>current.filter(member=>member!==id));setPreview(false);}}/>{label(id)} · außerhalb der geladenen Seite</label>)}
      <p>{members.length} Organisationen ausgewählt. Mindestens zwei erforderlich.</p><button type="submit" disabled={busy||members.length<2||!name.trim()}>Gruppierung ansehen</button></form>
      {preview&&<div className="memory-view-preview"><p>Anzeigegruppe <strong>{name}</strong></p><ul>{members.map(id=><li key={id}>{label(id)}</li>)}</ul><button type="button" disabled={busy} onClick={()=>void save()}>Gruppierung bestätigen</button><button type="button" disabled={busy} onClick={()=>setPreview(false)}>Abbrechen</button></div>}
      {editing&&<button type="button" onClick={()=>{editingRevision.current=0;setEditing(null);setMembers([]);setName('');setPreview(false);}}>Bearbeitung beenden</button>}
    </details>}{message&&<p role="status">{message}</p>}
  </section>;
}
