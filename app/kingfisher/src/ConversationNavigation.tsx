import {useEffect, useRef, useState} from 'react';
import {api, type ConversationSummary} from './api';
import {InterfaceIcon} from './InterfaceIcon';

// Preserve the navigation view when the thread is remounted for another chat.
let lastQuery = '';
const savedViews = new Map<string,{pages:number;scroll:number}>();
export function ConversationNavigation({activeId, revision, onSelect, onCreate}: {
  activeId?: string; revision?: string | number; onSelect: (id: string) => void; onCreate: () => Promise<void>;
}) {
  const [query, setQuery] = useState(lastQuery);
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState(false);
  const [reload, setReload] = useState(0);
  const request = useRef(0);
  const list = useRef<HTMLDivElement>(null);
  const restoreScroll = useRef<number|null>(null);
  const previousRevision = useRef(revision);
  const abort = useRef<AbortController | null>(null);

  async function load(append = false, restore = false) {
    const version = ++request.current;
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    setLoading(true); setError(false);
    try {
      const saved=savedViews.get(query);
      let nextCursor=append ? cursor ?? undefined : undefined;
      const result:ConversationSummary[]=[];
      const pages=restore ? saved?.pages ?? 1 : 1;
      let totalCount=0,loaded=0;
      for(let n=0;n<Math.min(pages,20);n++) {
        const page=await api.conversationPage(query,nextCursor,controller.signal);
        if(version!==request.current) return;
        result.push(...page.conversations);nextCursor=page.next_cursor ?? undefined;
        totalCount=page.total;loaded++;
        if(!nextCursor) break;
      }
      setItems(previous => append ? [...previous, ...result.filter(item => !previous.some(old => old.id === item.id))] : result);
      setCursor(nextCursor ?? null);setTotal(totalCount);
      savedViews.set(query,{pages:append ? (saved?.pages ?? 1)+loaded : loaded,scroll:saved?.scroll ?? 0});
      if(restore) restoreScroll.current=saved?.scroll ?? 0;
    } catch {
      if (version === request.current && !controller.signal.aborted) setError(true);
    } finally { if (version === request.current) setLoading(false); }
  }
  useEffect(() => {
    ++request.current; abort.current?.abort();
    setItems([]); setCursor(null); setLoading(true); setError(false);
    const timer = query ? setTimeout(() => void load(false,true), 180) : null;
    if (!query) void load(false,true);
    return () => { if (timer !== null) clearTimeout(timer); ++request.current; abort.current?.abort(); };
  }, [query, reload]);
  useEffect(()=>{
    if(previousRevision.current!==undefined && revision!==undefined && previousRevision.current!==revision) void load(false,true);
    previousRevision.current=revision;
  },[revision]);
  useEffect(()=>{if(list.current && restoreScroll.current!==null && items.length){list.current.scrollTop=restoreScroll.current;restoreScroll.current=null;}},[items]);

  async function create() {
    if (creating) return;
    setCreating(true); setCreateError(false);
    try { await onCreate(); } catch { setCreateError(true); } finally { setCreating(false); }
  }
  return <nav className="conversation-navigation" aria-label="Gespräche">
    <header><strong>Gespräche</strong><button className="conversation-new" type="button" aria-label="Neues Gespräch" title="Neues Gespräch" disabled={creating} onClick={create}><InterfaceIcon name="plus" /></button></header>
    <label className="conversation-nav-search"><InterfaceIcon name="search" /><input aria-label="Gespräche durchsuchen" placeholder="Titel oder Inhalt suchen …" maxLength={200} value={query} onChange={event => {
      ++request.current; abort.current?.abort(); lastQuery = event.target.value; setQuery(event.target.value);
    }} /></label>
    <div ref={list} className="conversation-nav-list" aria-busy={loading} onScroll={event=>{const saved=savedViews.get(query);if(saved) savedViews.set(query,{...saved,scroll:event.currentTarget.scrollTop});}}>
      {items.map(item => <button className="conversation-nav-item" type="button" aria-current={item.id === activeId ? 'page' : undefined} key={item.id} onClick={() => onSelect(item.id)}>
        <span className="conversation-nav-kopf"><strong>{item.title}</strong><small title={`${item.message_count} Nachrichten`}>{new Date(item.updated_at).toLocaleDateString('de-DE', {day: 'numeric', month: 'short'})}</small></span>{item.preview && <span>{item.preview}</span>}
      </button>)}
      {loading && !items.length && <p role="status">Gespräche werden geladen …</p>}
      {error && <div className="conversation-nav-fehler" role="alert"><p>Gespräche konnten nicht geladen werden.</p><button className="g-knopf-schlicht" type="button" onClick={() => setReload(n => n + 1)}>Wiederholen</button></div>}
      {!loading && !error && !items.length && <p>{query ? 'Kein Gespräch passt zur Suche.' : 'Hier erscheinen deine Gespräche.'}</p>}
      {cursor && !error && <button className="conversation-more" type="button" disabled={loading} onClick={() => load(true)}>Weitere Gespräche</button>}
    </div>
    {!loading && items.length > 0 && total > items.length && <small className="conversation-nav-count">{items.length} von {total} Gesprächen</small>}
    {createError && <p role="alert">Das neue Gespräch konnte nicht angelegt werden. Bitte erneut versuchen.</p>}
  </nav>;
}
