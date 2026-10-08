import { useEffect, useMemo, useRef, useState } from "react";

import { api, type MemoryAreaSource } from "./api";
import { ProfileSource } from "./ProfileSource";
import { firstAreaNavigation, initialAreaPager, MEMORY_AREAS,
  nextAreaNavigation, otherHintSources, previousAreaNavigation, receiveAreaPage, sourcesForArea } from "./MemoryAreaModel";
import "./MemoryAreas.css";

const PAGE_SIZE = 50;
type ViewId = typeof MEMORY_AREAS[number]["id"] | "other";

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

function SourceHints({ source }: { source: MemoryAreaSource }) {
  const date = datum(source.occurred_at);
  return <article className="memory-area-source">
    <header><div><h3>{source.title || "Quelle ohne Titel"}</h3>{date ? <time dateTime={source.occurred_at ?? undefined}>{date}</time> : <span>Quelldatum unbekannt</span>}</div></header>
    {statusText(source.status) && <p className="memory-area-status">{statusText(source.status)}</p>}
    {source.categories.length ? <ul className="memory-area-categories">{source.categories.map(category => <li key={category.id}>
      <strong>{category.label}</strong><span>{category.origin === "user" ? "Von dir zugeordnet" : "Ungeprüfter Themenhinweis"}</span>
      {category.evidence.map((evidence, index) => <blockquote key={`${category.id}:${evidence.start}:${index}`}>
        {evidence.quote}{evidence.quote_truncated ? <small>Belegauszug gekürzt</small> : null}
      </blockquote>)}
    </li>)}</ul> : !statusText(source.status) ? <p className="memory-area-status">Für diese Quelle ist noch kein Themenhinweis verfügbar.</p> : null}
    <ProfileSource kind="episode" id={source.episode_id} label="Originalquelle öffnen" readOnly allowIgnore={false} />
  </article>;
}

export function MemoryAreas() {
  const [view, setView] = useState<ViewId>("work");
  const [pager, setPager] = useState(initialAreaPager);
  const {page, index: pageIndex} = pager;
  const [retryNavigation, setRetryNavigation] = useState(firstAreaNavigation);
  const [loading, setLoading] = useState(false);
  const loadingRef = useRef(false);
  const [error, setError] = useState(false);
  const sources = useMemo(() => page?.sources ?? [], [page]);
  const visible = useMemo(() => view === "other" ? otherHintSources(sources) : sourcesForArea(sources, view), [sources, view]);
  const nextCursor = page?.next_cursor ?? null;
  const taxonomyVersion = page?.taxonomy_version;
  const unavailable = page?.areas.find(area => area.id === view)?.available === false;

  async function load(navigation: ReturnType<typeof firstAreaNavigation>) {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setRetryNavigation(navigation);
    setLoading(true); setError(false);
    try {
      const result = await api.memoryAreas(PAGE_SIZE, navigation.cursor);
      setPager(receiveAreaPage(navigation, result));
    } catch { setError(true); }
    finally { loadingRef.current = false; setLoading(false); }
  }

  useEffect(() => { void load(firstAreaNavigation()); }, []);

  function olderSources() {
    const navigation = nextAreaNavigation(pager);
    if (navigation) void load(navigation);
  }

  function newerSources() {
    const navigation = previousAreaNavigation(pager);
    if (navigation) void load(navigation);
  }

  function refresh() {
    void load(firstAreaNavigation());
  }

  const heading = view === "other" ? "Weitere Hinweise" : MEMORY_AREAS.find(area => area.id === view)?.label ?? "Gedächtnisbereich";
  return <section className="memory-areas" aria-label="Gedächtnisbereiche">
    <header className="memory-areas-heading"><p className="eyebrow">GEDÄCHTNIS</p><h1>Bereiche</h1>
      <p>Themenhinweise aus vorhandenen Quellen. Automatische Hinweise sind ungeprüft und keine bestätigten Aussagen. Bereiche ändern weder Originale noch Suche. Menschen, Orte, Organisationen und Zeitverlauf bleiben in ihren eigenen Ansichten.</p>
    </header>
    <nav className="memory-area-tabs" aria-label="Bereichsansichten">
      {MEMORY_AREAS.map(area => <button key={area.id} type="button" aria-pressed={view === area.id} className={view === area.id ? "active" : ""} onClick={() => setView(area.id)}>{area.label}</button>)}
      <button type="button" aria-pressed={view === "other"} className={view === "other" ? "active" : ""} onClick={() => setView("other")}>Weitere Hinweise</button>
    </nav>
    <div className="memory-areas-title"><h2>{heading}</h2><p>{page ? `${visible.length} passende Quellen auf dieser Seite` : "Quellenhinweise"}</p></div>
    {page && <p className="memory-area-meta">Seite {pageIndex + 1} · {page.scanned_count} Quellen in diesem Ausschnitt geprüft · Zahlen gelten nur für diese Seite{taxonomyVersion !== undefined ? ` · Themenstand ${taxonomyVersion}` : ""}</p>}
    {error && <p role="alert">Die Themenhinweise konnten nicht geladen werden. <button type="button" disabled={loading} onClick={() => void load(retryNavigation)}>Erneut versuchen</button></p>}
    {!page && !error && <p role="status">Bereiche werden geladen …</p>}
    {unavailable && <p role="status">Dieser Bereich ist im bestehenden Themenverzeichnis nicht verfügbar. Vorhandene Zuordnungen bleiben erhalten.</p>}
    {page && !unavailable && (visible.length ? <div className="memory-area-list">{visible.map((source, index) => <SourceHints key={`${source.episode_id}:${index}`} source={source} />)}</div>
      : <p className="memory-area-empty">{view === "other" ? `In diesem Ausschnitt mit ${page.scanned_count} Quellen gibt es keine weiteren Hinweise oder offenen Einordnungen.` : `In diesem Ausschnitt mit ${page.scanned_count} Quellen gibt es keine Hinweise für diesen Bereich.`}{nextCursor !== null ? " Ältere Quellen kannst du seitenweise ansehen." : " Das ist nur die aktuelle Seite der Quellenansicht."}</p>)}
    {page?.truncated && <p role="status">Diese Seite zeigt einen Ausschnitt. Ältere Quellen bleiben über die Seitennavigation erreichbar.</p>}
    {page && <nav className="memory-area-pagination" aria-label="Quellenseiten">
      <button className="memory-area-more" type="button" disabled={loading || pageIndex === 0} onClick={newerSources}>{loading ? "Wird geladen …" : "Neuere Quellen"}</button>
      <span aria-live="polite">Seite {pageIndex + 1}</span>
      <button className="memory-area-more" type="button" disabled={loading || nextCursor === null} onClick={olderSources}>{loading ? "Wird geladen …" : "Ältere Quellen"}</button>
      <button className="memory-area-refresh" type="button" disabled={loading} onClick={refresh}>{loading ? "Wird aktualisiert …" : "Ansicht aktualisieren"}</button>
    </nav>}
  </section>;
}
