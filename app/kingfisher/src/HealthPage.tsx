import "./HealthPage.css";
import {useEffect, useState} from 'react';
import {api, type HealthObservation, type HealthObservationPage} from './api';
import {Sidebar} from './chrome';
import {ProfileSource} from './ProfileSource';
import {HealthObservationEditor} from './HealthObservationEditor';

function measurementTime(value: string) {return value.replace('T',' · ').replace('Z',' UTC');}

function HealthHistory({id}: {id: string}) {
  const [open,setOpen]=useState(false);
  const [cursor,setCursor]=useState<string | null>(null);
  const [page,setPage]=useState<HealthObservationPage | null>(null);
  const [error,setError]=useState('');
  const [revision,setRevision]=useState(0);
  const [loadedAt,setLoadedAt]=useState<string | null>(null);
  useEffect(()=> {
    if(!open) return;
    let active=true;setPage(null);setError('');setLoadedAt(null);
    api.healthObservationHistory(id,cursor).then(result=>{if(active){setPage(result);setLoadedAt(new Date().toLocaleString('de-DE'));}})
      .catch(()=>{if(active)setError('Der Fassungsverlauf ist gerade nicht verfügbar. Bitte neu öffnen.');});
    return ()=>{active=false;};
  },[id,open,cursor,revision]);
  return <div className="health-history">
    <button type="button" aria-expanded={open} onClick={()=>{setOpen(!open);setCursor(null);}}>Fassungsverlauf {open ? 'schließen' : 'öffnen'}</button>
    {open && <section aria-label="Historische Originalfassungen">
      <p>Frühere Fassungen bleiben Originale. Die Kennzeichnung zeigt den Stand beim Laden, keinen dauerhaft geprüften Live-Stand.</p>
      <button type="button" onClick={()=>{setCursor(null);setRevision(n=>n+1);}}>Fassungen neu prüfen</button>
      {loadedAt && <p className="health-help">Geprüft beim Abruf: {loadedAt}</p>}
      {!page && !error && <p role="status">Verlauf wird geladen …</p>}
      {error && <p role="alert">{error}</p>}
      {page?.items.map(item=><div className="health-version" key={item.id}>
        <span>{item.status==='current' ? 'Aktuell beim Abruf' : item.status==='excluded' ? 'Ausgeschlossen' : 'Überholt'}</span>
        <p>{item.metric}: {item.value} {item.unit} · <time dateTime={item.observed_at}>{measurementTime(item.observed_at)}</time></p>
        <ProfileSource kind="episode" id={item.id} readOnly label="Originalfassung öffnen" />
      </div>)}
      {Boolean(page?.invalid_sources) && <p role="status">{page!.invalid_sources} Fassungen konnten nicht unverändert geprüft werden und werden nicht als Messwerte angezeigt.</p>}
      {page?.next_cursor && <button type="button" onClick={()=>setCursor(page.next_cursor)}>Weitere frühere Fassungen</button>}
    </section>}
  </div>;
}

function HealthEntry({item,onCorrect,onChange}: {item: HealthObservation;onCorrect:()=>void;onChange:()=>void}) {
  const [confirm,setConfirm]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  async function exclude() {
    if(busy) return;
    setBusy(true);setError('');
    try {await api.ignoreSource(item.id);onChange();}
    catch {setError('Die Quelle konnte nicht ausgeschlossen werden. Bitte erneut versuchen.');}
    finally {setBusy(false);}
  }
  return <article className="health-entry">
    <div className="health-entry-heading"><div><h3>{item.metric}</h3><p className="health-value">{item.value} <span>{item.unit}</span></p></div>
      <div><p>Eigene Angabe</p><time dateTime={item.observed_at}>{measurementTime(item.observed_at)}</time></div></div>
    {item.note && <p className="health-note">{item.note}</p>}
    <div className="health-actions"><ProfileSource kind="episode" id={item.id} readOnly label="Originalquelle öffnen" />
      <button type="button" onClick={onCorrect}>Korrigieren</button>
      <button type="button" disabled={busy} onClick={()=>setConfirm(!confirm)}>Nicht mehr verwenden</button></div>
    {confirm && <div className="health-confirm"><p>Diese Angabe wird als Quelle ausgeschlossen. Das Original bleibt erhalten; abgeleitete Aussagen verlieren diesen Beleg.</p>
      <button type="button" disabled={busy} onClick={exclude}>Quelle ausschließen</button><button type="button" disabled={busy} onClick={()=>setConfirm(false)}>Behalten</button></div>}
    {error && <p role="alert">{error}</p>}
    <HealthHistory id={item.id} />
  </article>;
}

export function HealthPage({recentConversation}: {recentConversation: string | null}) {
  const [page,setPage]=useState<HealthObservationPage | null>(null);
  const [error,setError]=useState('');
  const [cursor,setCursor]=useState<string | null>(null);
  const [previous,setPrevious]=useState<Array<string | null>>([]);
  const [revision,setRevision]=useState(0);
  const [loadedAt,setLoadedAt]=useState<string | null>(null);
  const [editor,setEditor]=useState(false);
  const [editing,setEditing]=useState<HealthObservation | null>(null);
  const [notice,setNotice]=useState('');
  function reload() {setCursor(null);setPrevious([]);setRevision(n=>n+1);}
  useEffect(()=> {
    let active=true;setPage(null);setError('');setLoadedAt(null);
    api.healthObservations(cursor).then(result=>{if(active){setPage(result);setLoadedAt(new Date().toLocaleTimeString('de-DE'));}})
      .catch(()=>{if(active)setError('Die Angaben sind gerade nicht verfügbar. Bitte neu laden; frühere Ergebnisse werden hier nicht als aktueller Stand angezeigt.');});
    return ()=>{active=false;};
  },[cursor,revision]);
  useEffect(()=> {
    const refresh=()=>{if(!document.hidden){setCursor(null);setPrevious([]);setRevision(n=>n+1);}};
    window.addEventListener('focus',refresh);document.addEventListener('visibilitychange',refresh);
    return ()=>{window.removeEventListener('focus',refresh);document.removeEventListener('visibilitychange',refresh);};
  },[]);
  return <div className="shell tasks-shell">
    <Sidebar active="Gedächtnis" recentConversation={recentConversation} />
    <main className="tasks-page development-page health-page">
      <header className="tasks-heading"><div><p className="eyebrow">DEIN ALLTAG</p><h1>Gesundheit</h1></div></header>
      <p>Eigene Messwerte mit Datum, Einheit und Originalquelle. Kingfisher bewahrt deine Angaben, ohne sie medizinisch zu bewerten.</p>
      <nav className="development-links" aria-label="Gesundheitsbereich">
        <a className="today-text-link" href="/today">Zurück zu Heute →</a>
        <a className="today-text-link" href="/memory?area=health">Alle Gesundheitsquellen →</a>
        <a className="today-text-link" href="/development">Persönliche Entwicklung →</a>
      </nav>
      {!editor && <button className="primary" type="button" onClick={()=>{setEditing(null);setEditor(true);setNotice('');}}>Eigene Angabe festhalten</button>}
      {editor && <HealthObservationEditor key={editing?.id || 'new'} observation={editing}
        onCancel={()=>{setEditor(false);setEditing(null);}}
        onSaved={()=>{setEditor(false);setEditing(null);setNotice('Die Angabe ist als Quelle gespeichert.');reload();}} />}
      {notice && <p role="status">{notice}</p>}
      <section className="health-timeline" aria-label="Datierte eigene Angaben">
        <div className="health-list-heading"><div><h2>Deine Angaben im Verlauf</h2><p>Nach Messzeit sortiert, neueste zuerst. Je Seite bis zu 25 Angaben.</p></div><button type="button" onClick={reload}>Neu laden</button></div>
        {loadedAt && <p className="health-help">Zuletzt geladen: {loadedAt}. Quellen werden beim Zurückkehren erneut geprüft.</p>}
        {!page && !error && <p role="status">Angaben werden geladen …</p>}
        {error && <p role="alert">{error}</p>}
        {page?.items.map(item=><HealthEntry key={item.id} item={item} onChange={reload} onCorrect={()=>{setEditing(item);setEditor(true);setNotice('');}} />)}
        {page?.items.length===0 && <p role="status">{page.next_cursor ? 'In diesem Ausschnitt ist keine geprüfte Angabe verfügbar. Ältere Angaben können folgen.' : 'In diesem Ausschnitt sind keine aktuellen eigenen Messangaben vorhanden.'}</p>}
        {Boolean(page?.invalid_sources) && <p role="status">{page!.invalid_sources} Quellen konnten nicht als unveränderte Messangaben geprüft werden und bleiben aus dieser Ansicht ausgeblendet.</p>}
        {page && <div className="health-actions">
          {previous.length>0 && <button type="button" onClick={()=>{setCursor(previous[previous.length-1]);setPrevious(values=>values.slice(0,-1));}}>Neuere Angaben</button>}
          {page.next_cursor && <button type="button" onClick={()=>{setPrevious(values=>[...values,cursor]);setCursor(page.next_cursor);}}>Ältere Angaben</button>}
        </div>}
      </section>
    </main>
  </div>;
}
