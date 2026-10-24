import {readMemoryViewPosition, rememberMemoryArea} from "./MemoryViewState";
import { useEffect, useRef, useState } from "react";

import { api, CATEGORY_FEEDBACK_EVENT, type MemoryAreaSource } from "./api";
import { ProfileSource } from "./ProfileSource";
import { CategoryCorrection } from "./CategoryCorrection";
import { areaEmptyText, areaLink, areaViewFromSearch, firstAreaNavigation, initialAreaPager, MEMORY_AREAS,
  nextAreaNavigation, previousAreaNavigation, receiveAreaPage, type MemoryAreaView } from "./MemoryAreaModel";
import { Gruppe, Leer, Segmente } from "./grundlage";
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

  const optionen = [...MEMORY_AREAS.map(area => ({wert: area.id as MemoryAreaView, titel: area.label})), {wert: "other" as MemoryAreaView, titel: "Weitere Hinweise"}]
    .map(option => ({...option, deaktiviert: loading}));
  const blaettern = page && (pageIndex > 0 || nextCursor !== null);
  // Ein Klick auf den gewählten Bereich lädt ihn neu; einen eigenen „Aktualisieren“-Knopf braucht es nicht.
  return <section className="memory-areas gd-bereiche" data-memory-loading={loading || (!page && !error)} aria-label="Gedächtnisbereiche">
    <Segmente kompakt className="memory-area-tabs" label="Bereichsansichten" wert={view} optionen={optionen} onWahl={select} />
    {error && <p role="alert" className="gd-hinweis">Die Themenhinweise konnten nicht geladen werden. <button type="button" className="g-knopf-schlicht g-kompakt" disabled={loading} onClick={() => void load(retryNavigation)}>Erneut versuchen</button></p>}
    {notice && <p role="status" className="gd-hinweis">{notice}</p>}
    {!page && !error && <p role="status" className="gd-hinweis">Bereiche werden geladen …</p>}
    {unavailable && <Leer zeichen="brain" satz="Dieser Bereich ist im Themenverzeichnis nicht verfügbar; vorhandene Zuordnungen bleiben erhalten." />}
    {!loading && page && selectedSources.length > 0 && <AreaBatchCorrection selected={selectedSources} onClear={() => setSelectedSources([])} />}
    {page && !unavailable && (visible.length ? <Gruppe titel={`${visible.length} ${visible.length === 1 ? "Quelle" : "Quellen"}${blaettern ? ` · Seite ${pageIndex + 1}` : ""}`} fussnote="Automatische Zuordnungen sind ungeprüfte Vorschläge; eine Quelle kann zu mehreren Bereichen gehören."><div className="memory-area-list">{visible.map((source, index) => <SourceHints key={`${source.episode_id}:${index}`} source={source} selected={selectedSources.some(item => item.id === source.episode_id)} onSelect={checked => setSelectedSources(current => checked ? [...current.filter(item => item.id !== source.episode_id), {id: source.episode_id, title: source.title}] : current.filter(item => item.id !== source.episode_id))} onSaved={() => {
      setNotice("Deine Zuordnung wurde gespeichert. Die Quelle kann dadurch in einen anderen Bereich wechseln; ihr Original bleibt erhalten.");
    }} />)}</div></Gruppe>
      : <Leer zeichen="brain" className="memory-area-empty" satz={areaEmptyText(page)} />)}
    {page?.scan_limited && <p role="status" className="gd-hinweis">Die Prüfung dieses Suchabschnitts ist begrenzt. Weitere aktuelle Hinweise können dahinter liegen.</p>}
    {page?.truncated && <p role="status" className="gd-hinweis">Die Seiten folgen der Aufnahme in den Bestand, nicht dem Quelldatum.</p>}
    {blaettern && <nav className="memory-area-pagination directory-pagination" aria-label="Quellenseiten">
      <button className="memory-area-more g-knopf-getoent g-kompakt" type="button" disabled={loading || pageIndex === 0} onClick={newerSources}>{loading ? "Wird geladen …" : "Vorherige Seite"}</button>
      <span aria-live="polite">Seite {pageIndex + 1}</span>
      <button className="memory-area-more g-knopf-getoent g-kompakt" type="button" disabled={loading || nextCursor === null} onClick={olderSources}>{loading ? "Wird geladen …" : page.scan_limited ? "Weiterprüfen" : "Nächste Seite"}</button>
    </nav>}
  </section>;
}
