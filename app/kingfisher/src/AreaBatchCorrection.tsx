import {useRef,useState} from 'react';
import {api,type SourceCategoriesResult} from './api';
import {batchCategorySave,type BatchResult} from './WorkspaceMemoryModel';
import {MEMORY_AREAS} from './MemoryAreaModel';
export function AreaBatchCorrection({selected,onClear}: {selected:Array<{id:string;title:string}>;onClear:()=>void}) {
  const [area,setArea]=useState<string>('work');
  const [previews,setPreviews]=useState<SourceCategoriesResult[]|null>(null);
  const [results,setResults]=useState<BatchResult[]>([]);
  const [message,setMessage]=useState<string|null>(null);
  const [busy,setBusy]=useState(false);
  const snapshot=useRef<Array<{id:string;title:string}>>([]);
  const signature=selected.map(item=>item.id).sort().join('\n');
  const previewSignature=useRef('');
  const [saving,setSaving]=useState(false);
  const current=previews&&previewSignature.current===signature;
  async function preview() {
    if(!selected.length||busy)return;setBusy(true);setMessage(null);setResults([]);setPreviews(null);
    snapshot.current=[...selected];previewSignature.current=signature;
    try {
      const taxonomy=await api.categoryTaxonomy();if(!taxonomy.items.some(item=>item.id===area))throw Error('Bereich nicht verfügbar');
      const loaded=await Promise.allSettled(snapshot.current.map(item=>api.sourceCategories(item.id)));
      const next:SourceCategoriesResult[]=[];const failures:BatchResult[]=[];
      loaded.forEach((result,index)=>{const id=snapshot.current[index].id;if(result.status==='fulfilled'&&result.value.episode_id===id&&result.value.revision&&result.value.status!=='excluded')next.push(result.value);else failures.push({id,ok:false,message:'Aktuelle Quelle nicht sicher verfügbar; wird ausgelassen.'});});
      setPreviews(next);setResults(failures);
    }catch{setMessage('Vorschau oder Bereichsverzeichnis nicht erreichbar. Es wurde nichts gespeichert.');}
    finally{setBusy(false);}
  }
  async function save() {
    if(!current||!previews.length||busy)return;setBusy(true);setSaving(true);setMessage(null);
    const result=await batchCategorySave(previews,area,(id,categories,revision)=>api.correctSourceCategories(id,categories,revision));
    setResults(previous=>[...previous,...result]);setPreviews(null);setBusy(false);setSaving(false);
    setMessage(`${result.filter(item=>item.ok).length} gespeichert, ${result.filter(item=>!item.ok).length} nicht gespeichert. Bestehende Bereiche wurden beibehalten.`);
  }
  return <section className="memory-view-panel memory-area-batch" aria-label="Mehrere Quellen zuordnen"><h3>Ausgewählte Quellen zuordnen</h3><p>{selected.length} Quellen ausdrücklich ausgewählt. Ergänzt einen Bereich; andere Zuordnungen bleiben erhalten.</p>
    <div className="memory-view-actions"><label>Bereich ergänzen<select value={area} disabled={busy} onChange={event=>{setArea(event.target.value);setPreviews(null);}}>{MEMORY_AREAS.map(item=><option key={item.id} value={item.id}>{item.label}</option>)}</select></label><button type="button" disabled={busy||!selected.length} onClick={()=>void preview()}>{busy&&!saving?'Vorschau wird geladen …':'Auswahl prüfen'}</button><button type="button" disabled={busy||!selected.length} onClick={()=>{onClear();setPreviews(null);}}>Auswahl aufheben</button></div>
    {current&&<div className="memory-view-preview"><h4>Vorschau · {MEMORY_AREAS.find(item=>item.id===area)?.label}</h4><ul>{previews.map(source=><li key={source.episode_id}><strong>{snapshot.current.find(item=>item.id===source.episode_id)?.title||'Quelle ohne Titel'}</strong> · {source.categories.map(item=>item.label).join(', ')||'bisher ohne Bereich'} → Bereich ergänzen{source.correction?.stale&&<small> · Frühere Korrektur gehört zu einer älteren Fassung; prüfe die Originalquelle.</small>}</li>)}</ul><button type="button" disabled={busy||!previews.length} onClick={()=>void save()}>{saving?'Wird gespeichert …':`${previews.length} Zuordnungen bestätigen`}</button><button type="button" disabled={busy} onClick={()=>setPreviews(null)}>Abbrechen</button></div>}
    {message&&<p role="status">{message}</p>}{results.length>0&&<ul aria-label="Einzelergebnisse">{results.map((result,index)=><li key={`${result.id}:${index}`}>{snapshot.current.find(item=>item.id===result.id)?.title||result.id}: {result.message}</li>)}</ul>}
  </section>;
}
