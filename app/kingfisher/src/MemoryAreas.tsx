import {readMemoryViewPosition, rememberMemoryArea} from "./MemoryViewState";
import { useEffect, useRef, useState } from "react";

import { api, CATEGORY_FEEDBACK_EVENT, type MemoryAreaSource } from "./api";
import { ProfileSource } from "./ProfileSource";
import { CategoryCorrection } from "./CategoryCorrection";
import { areaEmptyText, areaLink, areaViewFromSearch, firstAreaNavigation, initialAreaPager, MEMORY_AREAS,
  nextAreaNavigation, previousAreaNavigation, receiveAreaPage, type MemoryAreaView } from "./MemoryAreaModel";
import "./MemoryAreas.css";
import { AreaBatchCorrection } from "./AreaBatchCorrection";
import "./WorkspaceMemoryDetails.css";

const PAGE_SIZE = 50;

function datum(value: string | null) {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toLocaleDateString("de-DE");
}

function statusText(status: string) {
  if (status === "pending") return "Themenhinweise stehen noch aus.";
  if (status === "failed") return "Themenhinweise konnten nicht vollständig ausgewertet werden.";
  if (status === "deferred") return "Diese Quelle wurde zurückgestellt.";
  if (status === "empty") return "Noch keine Themenhinweise gefunden.";
  if (status === "excluded") return "Diese Quelle ist ausgeschlossen.";
  return null;
}

function SourceHints({ source, onSaved, selected, onSelect }: { source: MemoryAreaSource; onSaved: () => void; selected: boolean; onSelect: (selected: boolean) => void }) {
  const date = datum(source.occurred_at);
  return <article className="memory-area-source" data-memory-row={`episode:${source.episode_id}`}>
    <header><label className="memory-area-select"><input type="checkbox" checked={selected} disabled={source.status === "excluded"} onChange={event => onSelect(event.target.checked)} aria-label={`Quelle auswählen: ${source.title || "Quelle ohne Titel"}`} />Auswählen</label><div><h3>{source.title || "Quelle ohne Titel"}</h3>{date ? <time dateTime={source.occurred_at ?? undefined}>{date}</time> : <span>Quelldatum unbekannt</span>}</div></header>
    {statusText(source.status) && <p className="memory-area-status">{statusText(source.status)}</p>}
    {source.categories.length ? <ul className="memory-area-categories">{source.categories.map(category => <li key={category.id}>
      <strong>{category.label}</strong><span>{category.origin === "user" ? "Von dir zugeordnet" : "Ungeprüfter Themenhinweis"}</span>
      {category.evidence.length > 0 && <details><summary>Belege ({category.evidence.length})</summary>{category.evidence.map((evidence, index) => <blockquote key={`${category.id}:${evidence.start}:${index}`}>
        {evidence.quote}{evidence.quote_truncated ? <small>Belegauszug gekürzt</small> : null}
      </blockquote>)}</details>}
    </li>)}</ul> : !statusText(source.status) ? <p className="memory-area-status">Für diese Quelle ist noch kein Themenhinweis verfügbar.</p> : null}
    <div className="memory-area-source-actions"><CategoryCorrection key={source.episode_id} id={source.episode_id} title={source.title} onSaved={onSaved} />
    <ProfileSource kind="episode" id={source.episode_id} label="Originalquelle öffnen" readOnly allowIgnore={false} /></div>
  </article>;
}

export function MemoryAreas() {
  const restored = useRef(readMemoryViewPosition()?.area);
  const [view, setView] = useState<MemoryAreaView>(() => areaViewFromSearch(window.location.search));
  const [pager, setPager] = useState(() => restored.current ? {page:null, history:restored.current.navigation.history, index:restored.current.navigation.index} : initialAreaPager());
  const {page, index: pageIndex} = pager;
  const [retryNavigation, setRetryNavigation] = useState(() => restored.current?.navigation ?? firstAreaNavigation());
  const [loading, setLoading] = useState(false);
  const requestVersion = useRef(0);
  const [error, setError] = useState(false);
  const [selectedSources, setSelectedSources] = useState<Array<{id:string;title:string}>>(() => (restored.current?.selected ?? []).map(id => ({id,title:""})));
  const [notice, setNotice] = useState<string | null>(null);
  const visible = page?.sources ?? [];
  const nextCursor = page?.next_cursor ?? null;
  const taxonomyVersion = page?.taxonomy_version;
  const unavailable = page?.areas.find(area => area.id === view)?.available === false;

  async function load(navigation: ReturnType<typeof firstAreaNavigation>, selected: MemoryAreaView = view) {
    const version = ++requestVersion.current;
    setView(selected);
    setPager({page:null,history:navigation.history,index:navigation.index});
    setRetryNavigation(navigation);
    setLoading(true); setError(false);
    try {
      const result = await api.memoryAreas(PAGE_SIZE, navigation.cursor, selected);
      if (result.area !== selected) throw new Error('Bereichsauswahl fehlt');
      if (version === requestVersion.current) {
        setPager(receiveAreaPage(navigation, result));
        setSelectedSources(current => current.flatMap(item => {const source=result.sources.find(source=>source.episode_id===item.id&&source.status!=="excluded");return source?[{id:item.id,title:source.title}]:[];}));
      }
    } catch { if (version === requestVersion.current) setError(true); }
    finally { if (version === requestVersion.current) setLoading(false); }
  }

  useEffect(() => {
    const sync = () => {
      if (window.location.pathname && window.location.pathname !== "/memory") return;
      const saved=readMemoryViewPosition()?.area;
      setSelectedSources((saved?.selected ?? []).map(id=>({id,title:""})));
      void load(saved?.navigation ?? firstAreaNavigation(), areaViewFromSearch(window.location.search));
    };
    sync();
    window.addEventListener('popstate', sync);
    return () => { ++requestVersion.current; window.removeEventListener('popstate', sync); };
  }, []);

  useEffect(() => {
    const saved = () => { void load(retryNavigation, view); };
    window.addEventListener(CATEGORY_FEEDBACK_EVENT, saved);
    return () => window.removeEventListener(CATEGORY_FEEDBACK_EVENT, saved);
  }, [retryNavigation, view]);

  useEffect(() => {
    if (!window.location.pathname || window.location.pathname === "/memory") rememberMemoryArea(view,retryNavigation,selectedSources.map(item=>item.id));
  },[view,retryNavigation,selectedSources]);

  function select(selected: MemoryAreaView) {
    setNotice(null);setSelectedSources([]);
    window.history.replaceState({}, '', areaLink(selected, window.location.search));
    void load(firstAreaNavigation(), selected);
  }

  function olderSources() {
    setSelectedSources([]);
    const navigation = nextAreaNavigation(pager);
    if (navigation) void load(navigation);
  }

  function newerSources() {
    setSelectedSources([]);
    const navigation = previousAreaNavigation(pager);
    if (navigation) void load(navigation);
  }

  function refresh() {
    setSelectedSources([]);
    void load(firstAreaNavigation());
  }

  const heading = view === "other" ? "Weitere Hinweise" : MEMORY_AREAS.find(area => area.id === view)?.label ?? "Gedächtnisbereich";
  return <section className="memory-areas" data-memory-loading={loading || (!page && !error)} aria-label="Gedächtnisbereiche">
    <header className="memory-areas-heading"><p className="eyebrow">GEDÄCHTNIS</p><h1>Bereiche</h1>
      <details className="quiet-details"><summary>Über die Zuordnung</summary><p>Deine Quellen nach Lebensbereichen. Eine Quelle kann zu mehreren Bereichen gehören. Automatische Zuordnungen sind ungeprüfte Vorschläge.</p></details>
    </header>
    <nav className="memory-area-tabs" aria-label="Bereichsansichten">
      {MEMORY_AREAS.map(area => <button key={area.id} type="button" disabled={loading} aria-pressed={view === area.id} className={view === area.id ? "active" : ""} onClick={() => select(area.id)}>{area.label}</button>)}
      <button type="button" disabled={loading} aria-pressed={view === "other"} className={view === "other" ? "active" : ""} onClick={() => select("other")}>Weitere Hinweise</button>
    </nav>
    <div className="memory-areas-title"><h2>{heading}</h2><p>{page ? `${visible.length} Quellen angezeigt` : "Quellenhinweise"}</p></div>
    {page && <details className="quiet-details"><summary>Quellenstand</summary><p className="memory-area-meta">Bereichsauswahl im gesamten Bestand · Seite {pageIndex + 1}{taxonomyVersion !== undefined ? ` · Themenstand ${taxonomyVersion}` : ""}. Angezeigt werden vorhandene Zuordnungen, keine neue Auswertung.</p></details>}
    {error && <p role="alert">Die Themenhinweise konnten nicht geladen werden. <button type="button" disabled={loading} onClick={() => void load(retryNavigation)}>Erneut versuchen</button></p>}
    {notice && <p role="status">{notice}</p>}
    {!page && !error && <p role="status">Bereiche werden geladen …</p>}
    {unavailable && <p role="status">Dieser Bereich ist im bestehenden Themenverzeichnis nicht verfügbar. Vorhandene Zuordnungen bleiben erhalten.</p>}
    {!loading && page && selectedSources.length > 0 && <AreaBatchCorrection selected={selectedSources} onClear={() => setSelectedSources([])} />}
    {page && !unavailable && (visible.length ? <div className="memory-area-list">{visible.map((source, index) => <SourceHints key={`${source.episode_id}:${index}`} source={source} selected={selectedSources.some(item => item.id === source.episode_id)} onSelect={checked => setSelectedSources(current => checked ? [...current.filter(item => item.id !== source.episode_id), {id: source.episode_id, title: source.title}] : current.filter(item => item.id !== source.episode_id))} onSaved={() => {
      setNotice("Deine Zuordnung wurde gespeichert. Die Quelle kann dadurch in einen anderen Bereich wechseln; ihr Original bleibt erhalten.");
    }} />)}</div>
      : <p className="memory-area-empty">{areaEmptyText(page)}</p>)}
    {page?.scan_limited && <p role="status">Die Prüfung dieses Suchabschnitts ist begrenzt. Weitere aktuelle Hinweise können dahinter liegen.</p>}
    {page?.truncated && <p role="status">Die Seiten folgen der Aufnahme in den Bestand, nicht dem Quelldatum. Weitere Quellen findest du auf der nächsten Seite.</p>}
    {page && <nav className="memory-area-pagination" aria-label="Quellenseiten">
      <button className="memory-area-more" type="button" disabled={loading || pageIndex === 0} onClick={newerSources}>{loading ? "Wird geladen …" : "Vorherige Seite"}</button>
      <span aria-live="polite">Seite {pageIndex + 1}</span>
      <button className="memory-area-more" type="button" disabled={loading || nextCursor === null} onClick={olderSources}>{loading ? "Wird geladen …" : page.scan_limited ? "Weiterprüfen" : "Nächste Seite"}</button>
      <button className="memory-area-refresh" type="button" disabled={loading} onClick={refresh}>{loading ? "Wird aktualisiert …" : "Ansicht aktualisieren"}</button>
    </nav>}
  </section>;
}
