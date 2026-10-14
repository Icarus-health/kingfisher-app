import {useRef,useState} from 'react';
import {workspaceViewApi,type PositionData,type ViewRecord} from './workspaceViewApi';
import {useWorkspaceMemoryView} from './useWorkspaceMemoryView';
import {coordinatePair,workspaceProfileHref} from './WorkspaceMemoryModel';
import {PlacesMap} from './PlacesMap';
import './WorkspaceMemoryDetails.css';
export function MemoryPlaces({entries}: {entries:Array<{id:string;name:string}>}) {
  const {overview,error,refresh}=useWorkspaceMemoryView();
  const selectedRevision=useRef(0);
  const [selected,setSelected]=useState<string|null>(null);
  const [lat,setLat]=useState('');const [lng,setLng]=useState('');
  const [pinning,setPinning]=useState(false);const [preview,setPreview]=useState(false);
  const [busy,setBusy]=useState(false);const [message,setMessage]=useState<string|null>(null);
  const [local,setLocal]=useState<ViewRecord<PositionData>|null>(null);
  const remote=overview?.places.find(place=>place.id===selected);
  const record=local&&local.id===selected&&local.revision>=(remote?.revision??0)?local:remote;
  const points=entries.flatMap(entry=>{const position=overview?.places.find(place=>place.id===entry.id)?.data;return position?[{...entry,...position}]:[];});
  async function choose(id:string) {
    if(busy)return;setBusy(true);setSelected(id);setPinning(false);setPreview(false);setMessage(null);
    try {const item=await workspaceViewApi.get<PositionData>('place',id);setLocal(item);selectedRevision.current=item.revision;setLat(item.data?String(item.data.lat):'');setLng(item.data?String(item.data.lng):'');}
    catch{setLat('');setLng('');setMessage('Aktueller Pin nicht erreichbar. Bitte Ort erneut prüfen.');}
    finally{setBusy(false);}
  }
  async function save(undo=false) {
    const position=coordinatePair(lat,lng);if(!overview||!selected||busy||(!undo&&(!preview||!position)))return;
    setBusy(true);setMessage(null);
    try{const result=undo?await workspaceViewApi.undo('place',selected,record?.revision??0):await workspaceViewApi.save('place',selected,position!,selectedRevision.current);const saved=result as ViewRecord<PositionData>;setLocal(saved);selectedRevision.current=saved.revision;if(undo){setLat(saved.data?String(saved.data.lat):'');setLng(saved.data?String(saved.data.lng):'');}setPreview(false);setPinning(false);setMessage(undo?'Vorheriger Pin wiederhergestellt.':'Koordinaten ausdrücklich gespeichert.');}
    catch{setMessage('Pin nicht gespeichert. Bitte aktuellen Stand erneut laden.');}finally{setBusy(false);}
  }
  return <section className="memory-view-panel" aria-label="Bestätigte Orte"><h2>Orte auf der Karte</h2><p>Koordinaten werden nur mit deiner Bestätigung gespeichert. Orte ohne Pin bleiben in der Liste. Die Karte zeigt die bestätigten Pins dieser geladenen Seite.</p>
    {error&&<p role="alert">Ortskoordinaten nicht erreichbar. <button type="button" onClick={()=>void refresh()}>Erneut laden</button></p>}
    <PlacesMap enabled={overview?.online.maps===true} points={points} selected={selected} pinning={pinning} onSelect={id=>void choose(id)} onPin={(latitude,longitude)=>{if(!pinning||!selected)return;const pair=coordinatePair(String(latitude),String(longitude));if(pair){setLat(String(pair.lat));setLng(String(pair.lng));setPreview(true);setPinning(false);}}}/>
    <label>Ort auswählen<select value={selected??''} disabled={busy||!overview} onChange={event=>event.target.value&&void choose(event.target.value)}><option value="">Bitte Ort wählen</option>{entries.map(entry=><option key={entry.id} value={entry.id}>{entry.name}{points.some(point=>point.id===entry.id)?' · bestätigter Pin':' · ohne Pin'}</option>)}</select></label>
    {selected&&<><p><a href={workspaceProfileHref(selected,'places',window.location?.search??'')}>Ortsakte öffnen: {entries.find(entry=>entry.id===selected)?.name}</a></p><button type="button" disabled={busy} onClick={()=>void choose(selected)}>Aktuellen Pin prüfen</button><form onSubmit={event=>{event.preventDefault();if(coordinatePair(lat,lng))setPreview(true);}}><div className="memory-view-actions"><label>Breitengrad<input inputMode="decimal" value={lat} disabled={busy} onChange={event=>{setLat(event.target.value);setPreview(false);}} placeholder="−90 bis 90"/></label><label>Längengrad<input inputMode="decimal" value={lng} disabled={busy} onChange={event=>{setLng(event.target.value);setPreview(false);}} placeholder="−180 bis 180"/></label><button type="submit" disabled={busy||!coordinatePair(lat,lng)}>Pin prüfen</button>{overview?.online.maps&&<button type="button" disabled={busy} aria-pressed={pinning} onClick={()=>setPinning(value=>!value)}>{pinning?'Pin-Auswahl beenden':'Pin setzen'}</button>}</div></form>
      {pinning&&<p role="status">Klicke die Position auf der Karte an. Danach bestätigst du den Pin.</p>}
      {preview&&<div className="memory-view-preview"><p>Pin für <strong>{entries.find(entry=>entry.id===selected)?.name}</strong>: {lat}, {lng}</p><button type="button" disabled={busy} onClick={()=>void save()}>Pin bestätigen</button><button type="button" disabled={busy} onClick={()=>setPreview(false)}>Abbrechen</button></div>}
      {!!record?.revision&&<button type="button" disabled={busy} onClick={()=>void save(true)}>Pinänderung rückgängig</button>}
    </>}{message&&<p role="status">{message}</p>}
  </section>;
}
