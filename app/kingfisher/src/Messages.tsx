import {useCallback, useEffect, useRef, useState} from 'react';
import {api, type InboxMessage} from './api';
import {Sidebar} from './chrome';
import {MailReader} from './MailReader';
import {localMailApi, type LocalMailPage} from './localMailApi';
import {aktualisiertSatz} from './heute';
import {displayLabel} from './displayIdentity';
import {navigate} from './ui';
import {Leer, Seitenkopf} from './grundlage';
import {postfachDatum} from './postfachAnzeige';

export function Messages({recentConversation}: {recentConversation:string|null}) {
  const [selectedId,setSelectedId] = useState<string|null>(null);
  const [selectedMode,setSelectedMode] = useState<'local'|'live'>('local');
  const [freshMessages,setFreshMessages] = useState<InboxMessage[]>([]);
  const [page,setPage] = useState<LocalMailPage|null>(null);
  const [pageKey,setPageKey] = useState('');
  const [accountId,setAccountId] = useState<string|undefined>(undefined);
  const [query,setQuery] = useState('');
  const [offset,setOffset] = useState(0);
  const [revision,setRevision] = useState(0);
  const [loading,setLoading] = useState(false);
  const [failure,setFailure] = useState('');
  const [syncing,setSyncing] = useState(false);
  const [syncNotice,setSyncNotice] = useState('');
  const opened = useRef<HTMLButtonElement|null>(null);
  const autoOpened = useRef('');
  const quietOpen = useRef(false);
  const readerRegion = useRef<HTMLElement|null>(null);
  const syncBaselines = useRef(new Map<string,string[]>());
  const selectionKey = JSON.stringify([accountId??null,query,offset]);
  const visiblePage = pageKey===selectionKey?page:null;
  const sourceChanged = useCallback(()=>setRevision(n=>n+1),[]);
  const close = useCallback(() => {setSelectedId(null);},[]);
  useEffect(() => {
    if(selectedId) {
      if(readerRegion.current) readerRegion.current.scrollTop=0;
      // Die von selbst geöffnete erste Mail nimmt der Suche nicht den Fokus.
      if(quietOpen.current) quietOpen.current=false;
      else readerRegion.current?.querySelector<HTMLButtonElement>('button')?.focus({preventScroll:true});
    }
    else opened.current?.focus({preventScroll:true});
    const escape=(event:KeyboardEvent)=>{if(event.key==='Escape'&&selectedId)close();};
    window.addEventListener('keydown',escape);
    return()=>window.removeEventListener('keydown',escape);
  },[selectedId,selectedMode,close]);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setLoading(true);setFailure('');
    localMailApi.page({q:query,account_id:accountId,offset},controller.signal).then(value => {
      if(active) {setPage(value);setPageKey(selectionKey);if(offset && value.total <= offset) setOffset(0);}
    }).catch(() => {if(active) setFailure('Gespeicherte Nachrichten konnten gerade nicht geladen werden.');})
      .finally(() => {if(active) setLoading(false);});
    return () => {active=false;controller.abort();};
  },[accountId,query,offset,revision]);
  // Die Liste lädt selbst neu, wenn das Fenster wieder in den Blick kommt; kein Knopf dafür.
  useEffect(() => {
    const neu = () => {if(typeof document==='undefined'||document.visibilityState!=='hidden') setRevision(n=>n+1);};
    window.addEventListener('focus',neu);
    if(typeof document!=='undefined') document.addEventListener?.('visibilitychange',neu);
    return () => {window.removeEventListener('focus',neu);if(typeof document!=='undefined') document.removeEventListener?.('visibilitychange',neu);};
  },[]);
  // Auf breitem Fenster steht die neueste Mail gleich offen da, auf schmalem bleibt die Liste.
  useEffect(() => {
    const first = visiblePage?.items[0];
    if(!first || selectedId || autoOpened.current===selectionKey) return;
    autoOpened.current=selectionKey;
    const breit = typeof window.matchMedia==='function' && window.matchMedia('(min-width: 1101px)').matches;
    if(!breit) return;
    quietOpen.current=true;setSelectedMode('local');setSelectedId(first.episode_id);
  },[visiblePage,selectedId,selectionKey]);
  async function sync() {
    if(syncing) return;
    setSyncing(true);setSyncNotice('');
    try {
      const result = await api.messages(accountId || undefined);
      if (!result.partial_failure || result.messages.length) setFreshMessages(old => accountId === undefined ? result.messages : [...old.filter(message=>message.account_id!==accountId),...result.messages]);
      const syncKey=accountId??'*', ids=result.messages.map(message=>JSON.stringify([message.account_id,message.id]));
      const outcome=aktualisiertSatz(syncBaselines.current.get(syncKey)??null,ids,result.abgerufen_um||new Date().toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'}));
      if(!result.partial_failure)syncBaselines.current.set(syncKey,ids);
      setSyncNotice(result.partial_failure?.message || outcome || `Abgerufen: ${ids.length === 1 ? 'eine Nachricht' : `${ids.length} Nachrichten`}.`);
      setRevision(n => n+1);
    } catch {setSyncNotice('Das Postfach antwortet gerade nicht. Deine gespeicherten Nachrichten bleiben lesbar.');}
    finally {setSyncing(false);}
  }
  const freshVisible = freshMessages.filter(message=>(accountId===undefined||message.account_id===accountId)&&`${message.subject} ${message.sender} ${message.preview}`.toLocaleLowerCase('de').includes(query.toLocaleLowerCase('de')));
  // Die Postfachwahl steht nur da, wenn es etwas zu wählen gibt; das Postfach in der Zeile nur, wenn es mehrere gibt.
  const mehrerePostfaecher = (page?.accounts.length ?? 0) > 1 || accountId !== undefined;
  const postfachInZeile = (page?.accounts.length ?? 0) > 1 && accountId === undefined;
  const zeile = (key:string, gewaehlt:boolean, absender:string, betreff:string, vorschau:string, datum:string|null, neben:string|null, oeffnen:(ziel:HTMLButtonElement|null)=>void) =>
    <button type="button" className="inbox-row inbox-open mail-list-item" key={key} aria-pressed={gewaehlt} onClick={event=>oeffnen(event?.currentTarget??null)}>
      <span className="mail-zeile-kopf"><strong title={absender}>{displayLabel(absender).name}</strong>{datum?<time dateTime={datum}>{postfachDatum(datum)}</time>:<time>{postfachDatum(null)}</time>}</span>
      <span className="mail-subject" title={betreff || undefined}>{betreff||'(Ohne Betreff)'}</span>
      <small>{vorschau}</small>
      {neben ? <small className="mail-zeile-postfach">{neben}</small> : null}
    </button>;
  const seitenweise = Boolean(visiblePage && (visiblePage.has_more || offset > 0));
  return <div className="shell inbox-shell"><Sidebar active="Nachrichten" recentConversation={recentConversation} />
    <main className="inbox-page mail-workspace">
      <Seitenkopf titel="Nachrichten" className="inbox-heading" aktionen={<>
        <button className="g-knopf-schlicht" type="button" disabled={syncing} onClick={() => void sync()}>{syncing?'Wird abgerufen …':'Neue Mails abrufen'}</button>
        <a className="g-knopf-schlicht mail-konten" href="/settings#zugaenge" onClick={event=>{event.preventDefault();navigate('/settings#zugaenge');}}>Konten</a>
      </>} />
      {syncNotice && <p className="inbox-abgerufen" role="status">{syncNotice}</p>}
      <div className={`inbox-content mailbox-columns ${selectedId?'has-reader':''}`}>
        <section className="mail-list-column" aria-label="Gespeicherte Nachrichten">
          <div className="mail-list-tools">
            <input type="search" aria-label="Nachrichten durchsuchen" value={query} placeholder="Suchen" onChange={event=>{setQuery(event.target.value);setOffset(0);opened.current=null;close();}} />
            {mehrerePostfaecher && <select aria-label="Postfach auswählen" value={accountId??''} onChange={event=>{setAccountId(event.target.value||undefined);setOffset(0);close();}}><option value="">Alle Postfächer</option>{page?.accounts.map(item=><option key={item.id} value={item.id}>{item.label} ({item.count})</option>)}</select>}
          </div>
          <div className="mail-list-scroll">
          {failure && <p className="inbox-error" role="alert">{failure} <button type="button" className="g-knopf-schlicht" onClick={()=>setRevision(n=>n+1)}>Wiederholen</button></p>}
          {loading && !visiblePage && !failure && <p className="mail-list-laden" role="status">Wird geladen …</p>}
          {freshVisible.length>0 && <section className="mail-fresh-results" aria-label="Ausdrücklich abgerufener Posteingang"><h2>Gerade abgerufen</h2><p>Nur angezeigt, nicht gespeichert.</p>{freshVisible.map(message=>zeile(JSON.stringify([message.account_id,message.id]),selectedMode==='live'&&selectedId===message.id,message.sender,message.subject,`${message.preview}${message.truncated ? " …" : ""}`,message.date,message.source,ziel=>{opened.current=ziel;setSelectedMode('live');setSelectedId(message.id);}))}</section>}
          <div className="inbox-list" aria-busy={loading}>
            {visiblePage?.items.map(message=>zeile(message.episode_id,selectedMode==='local'&&selectedId===message.episode_id,message.sender,message.subject,message.preview,message.date,postfachInZeile?message.account_label:null,ziel=>{opened.current=ziel;setSelectedMode('local');setSelectedId(message.episode_id);}))}
            {visiblePage && visiblePage.items.length===0 && !loading && <Leer className="inbox-empty" zeichen="mail" satz={query?'Keine Nachricht passt zu dieser Suche.':'Noch keine Nachrichten gespeichert.'} />}
          </div>
          </div>
          {seitenweise && <nav className="mail-pagination" aria-label="Nachrichtenseiten"><button type="button" className="g-knopf-schlicht" disabled={loading||offset===0} onClick={()=>setOffset(n=>Math.max(0,n-40))}>Zurück</button><span>{visiblePage?.total ? `${offset+1}–${Math.min(offset+(visiblePage.items.length||0),visiblePage.total)} von ${visiblePage.total}`:''}</span><button type="button" className="g-knopf-schlicht" disabled={loading||!visiblePage?.has_more} onClick={()=>setOffset(n=>n+40)}>Weiter</button></nav>}
        </section>
        <section className="mail-reading-column" aria-label="Lesebereich" ref={readerRegion}>{selectedId?<MailReader key={`${selectedMode}:${selectedId}`} uid={selectedId} localEpisodeId={selectedMode==='local'?selectedId:undefined} localRevision={revision} onClose={close} onTaskSaved={sourceChanged} />:<Leer className="mail-reader-placeholder" zeichen="mail" satz="Wähle eine Nachricht zum Lesen." />}</section>
      </div>
    </main></div>;
}
