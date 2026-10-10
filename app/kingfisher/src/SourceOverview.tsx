import {useEffect,useRef,useState} from 'react';
import {api} from './api';
import {buildSourceOverview,type SourceOverviewState} from './sourceOverviewRows';
import {adoptSourceResult,watchSourceOverview} from './sourceOverviewWatch';

// These endpoints inspect stored metadata. None is the live calendar-content route.
export const sourceMetadataReaders=()=>({
  intake:(signal:AbortSignal)=>api.mailIntake(signal),
  integrations:(signal:AbortSignal)=>api.integrations(signal),
  schedule:(signal:AbortSignal)=>api.schedule(signal),
  mac:(signal:AbortSignal)=>api.macCalendar(signal),
  documents:(signal:AbortSignal)=>api.sourceFolderStatus('/api/v1/folder-sync',signal),
  meetings:(signal:AbortSignal)=>api.sourceFolderStatus('/api/v1/transcript-sync',signal),
});
const date=(value:string)=>new Date(value).toLocaleString('de-DE',{dateStyle:'medium',timeStyle:'short'});

export function SourceOverviewView({state,busy,onRefresh,at=Date.now()}: {
  state:SourceOverviewState;busy:boolean;onRefresh:()=>void;at?:number;
}) {
  const rows=buildSourceOverview(state,at);
  return <section className="memory-status-card memory-source-overview" aria-label="Deine Informationsquellen">
    <header><div><h2>Deine Informationsquellen</h2><p>Was verbunden ist, was bereits angekommen ist und wo noch etwas fehlt.</p></div>
      <button type="button" disabled={busy} onClick={onRefresh}>{busy ? 'Wird abgefragt …' : 'Quellenstand aktualisieren'}</button></header>
    <div className="memory-source-grid">{rows.map(row=><article className="memory-source-row" key={row.id}>
      <small>{row.kind}</small><h3>{row.title}</h3><p className={row.stale ? 'memory-source-stale' : undefined}>{row.status}</p>
      {row.warning ? <p className="memory-source-stale">{row.warning}</p> : null}
      {row.details.slice(0,2).map((line,i)=><p key={i}>{line}</p>)}
      <p className="memory-status-note">{row.lastSuccess ? <>{row.lastSuccessLabel}: <time dateTime={row.lastSuccess}>{date(row.lastSuccess)}</time>.</> : `${row.lastSuccessLabel}: noch nicht belegt.`}</p>
      {row.details.length>2 ? <details><summary>Umfang und Grenzen</summary>{row.details.slice(2).map((line,i)=><p key={i}>{line}</p>)}</details> : null}
      <a href={row.href}>{row.linkLabel} →</a>
    </article>)}</div>
    <p className="memory-status-note">Verbunden bedeutet noch nicht vollständig gelesen oder eingeordnet. Zeitpunkte beziehen sich auf den jeweils genannten Abgleich. Die Übersicht startet keinen Import. Einzelne Dateiimporte und manuelle Notizen zählen zum Gesamtstand des Gedächtnisses oben.</p>
  </section>;
}

export function SourceOverview({refreshKey=0}:{refreshKey?:number}) {
  const [state,setState]=useState<SourceOverviewState>({});
  const [busy,setBusy]=useState(false);
  const watcher=useRef<ReturnType<typeof watchSourceOverview>|null>(null);
  useEffect(()=>{
    const current=watchSourceOverview({readers:sourceMetadataReaders(),
      onPart:result=>setState(previous=>adoptSourceResult(previous,result)),onBusy:setBusy,visible:document.visibilityState==='visible'});
    watcher.current=current;
    const visibility=()=>current.setVisible(document.visibilityState==='visible');
    document.addEventListener('visibilitychange',visibility);
    return ()=>{document.removeEventListener('visibilitychange',visibility);current.stop();if(watcher.current===current)watcher.current=null;};
  },[]);
  useEffect(()=>{void watcher.current?.refresh();},[refreshKey]);
  return <SourceOverviewView state={state} busy={busy} onRefresh={()=>void watcher.current?.refresh()}/>;
}
