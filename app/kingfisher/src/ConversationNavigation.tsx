import {useEffect, useRef, useState} from 'react';
import {api, type ConversationSummary} from './api';
import {InterfaceIcon} from './InterfaceIcon';

// Preserve the navigation view when the thread is remounted for another chat.
let lastQuery = '';
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
  const abort = useRef<AbortController | null>(null);

  async function load(append = false) {
    const version = ++request.current;
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    setLoading(true); setError(false);
    try {
      const page = await api.conversationPage(query, append ? cursor ?? undefined : undefined, controller.signal);
      if (version !== request.current) return;
      setItems(previous => append ? [...previous, ...page.conversations.filter(item => !previous.some(old => old.id === item.id))] : page.conversations);
      setCursor(page.next_cursor); setTotal(page.total);
    } catch {
      if (version === request.current && !controller.signal.aborted) setError(true);
    } finally { if (version === request.current) setLoading(false); }
  }
  useEffect(() => {
    ++request.current; abort.current?.abort();
    setItems([]); setCursor(null); setLoading(true); setError(false);
    const timer = query ? setTimeout(() => void load(), 180) : null;
    if (!query) void load();
    return () => { if (timer !== null) clearTimeout(timer); ++request.current; abort.current?.abort(); };
  }, [query, revision, reload]);

  async function create() {
    if (creating) return;
    setCreating(true); setCreateError(false);
    try { await onCreate(); } catch { setCreateError(true); } finally { setCreating(false); }
  }
  return <nav className="conversation-navigation" aria-label="Gespräche">
    <header><strong>Gespräche</strong><button className="conversation-new" type="button" disabled={creating} onClick={create}><InterfaceIcon name="plus" />Neues Gespräch</button></header>
    <label className="conversation-nav-search"><InterfaceIcon name="search" /><input aria-label="Gespräche durchsuchen" placeholder="Titel oder Inhalt suchen …" maxLength={200} value={query} onChange={event => {
      ++request.current; abort.current?.abort(); lastQuery = event.target.value; setQuery(event.target.value);
    }} /></label>
    <div className="conversation-nav-list" aria-busy={loading}>
      {items.map(item => <button className="conversation-nav-item" type="button" aria-current={item.id === activeId ? 'page' : undefined} key={item.id} onClick={() => onSelect(item.id)}>
        <strong>{item.title}</strong>{item.preview && <span>{item.preview}</span>}<small>{new Date(item.updated_at).toLocaleDateString('de-DE', {day: '2-digit', month: 'short'})} · {item.message_count} Nachrichten</small>
      </button>)}
      {loading && <p role="status">Gespräche werden geladen …</p>}
      {error && <div role="alert"><p>Gespräche konnten nicht geladen werden.</p><button type="button" onClick={() => setReload(n => n + 1)}>Wiederholen</button></div>}
      {!loading && !error && !items.length && <p>{query ? 'Kein Gespräch passt zur Suche.' : 'Hier erscheinen deine Gespräche.'}</p>}
      {cursor && !error && <button className="conversation-more" type="button" disabled={loading} onClick={() => load(true)}>Weitere Gespräche</button>}
    </div>
    {!loading && items.length > 0 && <small className="conversation-nav-count">{items.length} von {total} Gesprächen</small>}
    {createError && <p role="alert">Das neue Gespräch konnte nicht angelegt werden. Bitte erneut versuchen.</p>}
  </nav>;
}
