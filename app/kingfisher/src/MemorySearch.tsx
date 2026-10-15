import {useEffect, useMemo, useState} from 'react';
import {api, type GraphNode, type MemoryGraph, type MemorySearchResult} from './api';
import {browseMatches, documentNodes, sourceReference} from './MemoryBrowseModel';
import {displayLabel} from './displayIdentity';
import {ProfileSource} from './ProfileSource';

function sourceDate(value: unknown): string {
  if (typeof value !== 'string' || !value) return 'Quelldatum unbekannt';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Quelldatum unbekannt' : date.toLocaleDateString('de-DE', {day:'numeric', month:'numeric', year:'numeric'});
}

export function MemorySearch({graph, query, page, onQueryChange, onPageChange, onOpen, documents = false, graphError = false, onGraphRetry}: {
  graph: MemoryGraph | null; query: string; page: number; onQueryChange: (q: string) => void;
  onPageChange: (page: number) => void; onOpen: (node: GraphNode) => void; documents?: boolean;
  graphError?: boolean; onGraphRetry?: () => void;
}) {
  const [submitted, setSubmitted] = useState(query.trim());
  const [result, setResult] = useState<MemorySearchResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  const needle = query.trim();
  useEffect(() => {
    setResult(null); setError(false);
    if (documents || submitted.length < 2 || submitted !== needle) {setBusy(false); return;}
    const controller = new AbortController();
    setBusy(true);
    api.memorySearch(submitted, controller.signal).then(data => {
      if (!controller.signal.aborted) setResult(data);
    }).catch(() => {if (!controller.signal.aborted) setError(true);})
      .finally(() => {if (!controller.signal.aborted) setBusy(false);});
    return () => controller.abort();
  }, [submitted, needle, documents, retry]);
  const entries = useMemo(() => {
    const nodes = documents ? documentNodes(graph?.nodes ?? []) : (graph?.nodes ?? []).filter(node =>
      ['person','project'].includes(node.kind));
    return documents && !needle ? nodes : browseMatches(nodes, needle);
  }, [graph, needle, documents]);
  const pages = Math.max(1, Math.ceil(entries.length / 25));
  const current = Math.min(page, pages);
  const visible = entries.slice((current - 1) * 25, current * 25);
  return <section data-memory-loading={busy || (!documents && submitted.length >= 2 && submitted === needle && !result && !error)} className="memory-directory memory-search" aria-label={documents ? 'Dokumente' : 'Gedächtnissuche'}>
    <header><p className="eyebrow">GEDÄCHTNIS</p><h1>{documents ? 'Dokumente' : 'Was möchtest du wiederfinden?'}</h1>
      </header>
    <form className="memory-search-form" onSubmit={event => {event.preventDefault(); setSubmitted(needle); setRetry(n => n + 1);}}>
      <label className="directory-search">{documents ? 'Dokumenttitel suchen' : 'Gedächtnis durchsuchen'}
        <input type="search" maxLength={200} value={query} onChange={event => onQueryChange(event.target.value)} placeholder={documents ? 'Titel oder Teil des Dateinamens …' : 'Name, Projekt oder Begriff, z. B. Redaktionsschluss …'} /></label>
      {!documents && <button type="submit" disabled={needle.length < 2 || busy}>{busy ? 'Suche läuft …' : 'Suchen'}</button>}
    </form>
    <details className="quiet-details memory-search-help"><summary>So funktioniert die Suche</summary><p>Einträge werden nach Namen und Titeln gefiltert. „Suchen“ durchsucht zusätzlich wörtlich gespeicherte Originaltexte, ohne KI-Aufruf.</p><p>Quellen berichten; ihre Aussagen sind damit noch nicht bestätigt.</p></details>
    {!graph && <p role={graphError ? 'alert' : 'status'}>{graphError ? 'Die Eintragsübersicht konnte nicht geladen werden.' : 'Eintragsübersicht wird geladen …'}{!documents && ' Die Quellensuche kann separat verwendet werden.'}{graphError && <button type="button" onClick={onGraphRetry}>Erneut laden</button>}</p>}
    {graph && (documents || (needle && entries.length > 0)) && <><h2>{documents ? 'Gespeicherte Dokumente' : 'Menschen und Projekte'}</h2>
      <p className="directory-count" aria-live="polite">{entries.length} {entries.length === 1 ? 'Eintrag' : 'Einträge'}</p>
      <ul className="memory-search-results">{visible.map(node => {
        const ref = sourceReference(node); const label = displayLabel(node.label);
        return <li key={node.id} data-memory-row={node.id}>
          <h3>{ref ? label.name : <button className="memory-entry-link" type="button" onClick={() => onOpen(node)}>{label.name}</button>}</h3>
          <p>{documents ? sourceDate(node.attributes.occurred_at) : node.kind === 'project' ? 'Projekt' : 'Kontakt aus vorhandenen Quellen'}{label.detail ? ` · ${label.detail}` : ''}</p>
          {ref && <><ProfileSource kind={ref.kind} id={ref.id} label="Originalquelle öffnen" originalOnly />{ref.kind === 'episode' && <ProfileSource kind={ref.kind} id={ref.id} label="Zuordnung & Korrektur" allowDismiss />}</>}
          {!ref && documents && <p>Kein direkter Originalbezug verfügbar.</p>}
        </li>;
      })}</ul>
      {!entries.length && <p>{documents && !needle ? 'Noch keine Dokumente gespeichert. Bereits aufgenommene Mails findest du in der Gedächtnissuche.' : 'Keine passenden Namen oder Titel in dieser Übersicht.'}</p>}
      {pages > 1 && <nav className="directory-pagination" aria-label="Ergebnisseiten"><button type="button" disabled={current === 1} onClick={() => onPageChange(current - 1)}>Zurück</button><span>Seite {current} von {pages}</span><button type="button" disabled={current === pages} onClick={() => onPageChange(current + 1)}>Weiter</button></nav>}
    </>}
    {!documents && needle.length >= 2 && <section aria-label="Treffer in Originalquellen" className="memory-search-originals"><h2>Originalquellen</h2>
      {submitted !== needle && <p>Mit „Suchen“ findest du den Begriff auch im gespeicherten Text.</p>}
      {busy && <p role="status">Originalquellen werden durchsucht …</p>}
      {error && <p role="alert">Die Quellensuche ist gerade nicht erreichbar. Daraus folgt nicht, dass die Information fehlt. <button type="button" onClick={() => setRetry(n => n + 1)}>Erneut versuchen</button></p>}
      {result && result.query === needle && submitted === needle && <>
        <p className="directory-count">{result.items.length + (result.note_items?.length ?? 0)} Quellentreffer</p>
        <details><summary>Suchumfang ansehen</summary><p>{result.scope}</p></details>
        {result.truncated && <p role="status">Die Suche ist begrenzt oder enthält unvollständige Quellen. Weitere passende Informationen können fehlen. Bitte grenze den Begriff ein.</p>}
        {!result.items.length && !result.note_items?.length && <p>Keine passende Stelle im durchsuchten Bestand gefunden. Versuche einen anderen Begriff.</p>}
        <ul className="memory-search-results">{result.items.map(item => <li key={item.episode_id} data-memory-row={`episode:${item.episode_id}`}><h3>{item.title}</h3><p>{sourceDate(item.occurred_at)} · {item.source_type === 'chat' ? 'Gesprächseingabe · noch keine bestätigte Aussage' : 'Quelle berichtet'}</p>
          <blockquote>{item.quote}</blockquote><ProfileSource kind="episode" id={item.episode_id} label="Originalquelle öffnen" originalOnly /><ProfileSource kind="episode" id={item.episode_id} label="Zuordnung & Korrektur" allowDismiss />
        </li>)}{result.note_items?.map(item => <li key={'note:'+item.note_id} data-memory-row={`note:${item.note_id}`}><h3>{item.title}</h3><p>Notiz · zuletzt geändert {sourceDate(item.recorded_at)} · noch keine bestätigte Aussage</p><blockquote>{item.quote}</blockquote><ProfileSource kind="note" id={item.note_id} label="Originalquelle öffnen" originalOnly /></li>)}</ul>
      </>}
    </section>}
    {!documents && !needle && <p className="memory-search-start">Gib einen Begriff ein oder wähle oben Menschen, Projekte, Dokumente oder einen Lebensbereich.</p>}
  </section>;
}
