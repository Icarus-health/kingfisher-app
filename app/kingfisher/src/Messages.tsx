import {useCallback, useEffect, useRef, useState} from 'react';
import {api, type InboxMessage} from './api';
import {Sidebar} from './chrome';
import {MailReader} from './MailReader';
import {localMailApi, type LocalMailPage} from './localMailApi';
import {aktualisiertSatz} from './heute';
import {displayLabel} from './displayIdentity';

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
      setSyncNotice(result.partial_failure?.message || outcome || `Posteingang abgerufen: ${ids.length} Nachrichten in diesem Ausschnitt. Gespeicherte Quellen bleiben lokal angezeigt.`);
      setRevision(n => n+1);
    } catch {setSyncNotice('Das Postfach antwortet gerade nicht. Deine gespeicherten Nachrichten bleiben lesbar.');}
    finally {setSyncing(false);}
  }
  const freshVisible = freshMessages.filter(message=>(accountId===undefined||message.account_id===accountId)&&`${message.subject} ${message.sender} ${message.preview}`.toLocaleLowerCase('de').includes(query.toLocaleLowerCase('de')));
  return <div className="shell inbox-shell"><Sidebar active="Nachrichten" recentConversation={recentConversation} />
    <main className="inbox-page mail-workspace">
      <header className="inbox-heading"><h1>Nachrichten</h1><span className="inbox-heading-actions"><button className="text-action" type="button" disabled={syncing} onClick={() => void sync()}>{syncing?'Wird abgerufen …':'Neue Mails abrufen'}</button><a className="text-action" href="/settings#zugaenge">Konten</a></span></header>
      {syncNotice && <p className="inbox-abgerufen" role="status">{syncNotice}</p>}
      <div className={`inbox-content mailbox-columns ${selectedId?'has-reader':''}`}>
        <section className="mail-list-column" aria-label="Gespeicherte Nachrichten">
          <div className="mail-account-choice"><label>Postfach<select aria-label="Postfach auswählen" value={accountId??''} onChange={event=>{setAccountId(event.target.value||undefined);setOffset(0);close();}}><option value="">Alle gespeicherten Mails</option>{page?.accounts.map(item=><option key={item.id} value={item.id}>{item.label} ({item.count})</option>)}</select></label></div>
          <div className="mail-list-tools"><label>Nachrichten durchsuchen<input type="search" value={query} placeholder="Betreff, Absender oder Inhalt" onChange={event=>{setQuery(event.target.value);setOffset(0);opened.current=null;close();}} /></label></div>

          <div className="mail-list-scroll">
          {failure && <p className="inbox-error" role="alert">{failure} <button type="button" onClick={()=>setRevision(n=>n+1)}>Wiederholen</button></p>}
          {loading && !visiblePage && <p role="status">Nachrichten werden geladen …</p>}
          {freshVisible.length>0 && <section className="mail-fresh-results" aria-label="Ausdrücklich abgerufener Posteingang"><h2>Aktueller Abruf</h2><p>Die neuesten Mails aus dem Postfach; sie werden hier nur angezeigt, nicht gespeichert.</p>{freshVisible.map(message=><button type="button" className="inbox-row inbox-open mail-list-item" key={JSON.stringify([message.account_id,message.id])} aria-pressed={selectedMode==='live'&&selectedId===message.id} onClick={event=>{opened.current=event.currentTarget;setSelectedMode('live');setSelectedId(message.id);}}><span className="inbox-copy"><strong title={message.sender}>{displayLabel(message.sender).name}</strong><span className="mail-subject">{message.subject||'(Ohne Betreff)'}</span><small>{message.preview}{message.truncated ? " · Vorschau gekürzt" : ""}</small></span><span className="inbox-meta">{message.date?<time dateTime={message.date}>{new Date(message.date).toLocaleDateString('de-DE')}</time>:<small>Datum unbekannt</small>}<small>{message.source}</small></span></button>)}</section>}
          <div className="inbox-list" aria-busy={loading}>
            {visiblePage?.items.map(message=><button className="inbox-row inbox-open mail-list-item" type="button" key={message.episode_id} aria-pressed={selectedMode==='local'&&selectedId===message.episode_id} onClick={event=>{opened.current=event?.currentTarget??null;setSelectedMode('local');setSelectedId(message.episode_id);}}><span className="inbox-copy"><strong title={message.sender}>{displayLabel(message.sender).name}</strong><span className="mail-subject">{message.subject || '(Ohne Betreff)'}</span><small>{message.preview}</small></span><span className="inbox-meta">{message.date?<time dateTime={message.date}>{new Date(message.date).toLocaleDateString('de-DE')}</time>:<small>Datum unbekannt</small>}<small>{message.account_label}</small></span></button>)}
            {visiblePage && visiblePage.items.length===0 && !loading && <p className="inbox-empty">Keine gespeicherten Nachrichten in dieser Ansicht.</p>}
          </div>
          </div>
          <nav className="mail-pagination" aria-label="Nachrichtenseiten"><button type="button" disabled={loading||offset===0} onClick={()=>setOffset(n=>Math.max(0,n-40))}>Zurück</button><span>{visiblePage?.total ? `${offset+1}–${Math.min(offset+(visiblePage.items.length||0),visiblePage.total)} von ${visiblePage.total}`:'0 Nachrichten'}</span><button type="button" disabled={loading||!visiblePage?.has_more} onClick={()=>setOffset(n=>n+40)}>Weiter</button></nav>
        </section>
        <section className="mail-reading-column" aria-label="Lesebereich" ref={readerRegion}>{selectedId?<MailReader key={`${selectedMode}:${selectedId}`} uid={selectedId} localEpisodeId={selectedMode==='local'?selectedId:undefined} localRevision={revision} onClose={close} onTaskSaved={sourceChanged} />:<p className="mail-reader-placeholder">Wähle eine Nachricht zum Lesen.</p>}</section>
      </div>
    </main></div>;
}
