import { useMemo, useState } from "react";
import type { GraphNode } from "./api";
import "./MemoryDirectory.css";
import { displayLabel } from "./displayIdentity";
import { GedaechtnisLeer } from "./GedaechtnisLeer";


export function MemoryDirectory({ nodes, title, onOpen, query: restoredQuery, page: restoredPage, onQueryChange, onPageChange, hasSources = false }: {
  nodes: GraphNode[]; title: string; onOpen: (node: GraphNode) => void;
  query?: string; page?: number; onQueryChange?: (query: string) => void; onPageChange?: (page: number) => void; hasSources?: boolean;
}) {
  const [localQuery, setLocalQuery] = useState("");
  const [localPage, setLocalPage] = useState(0);
  const query = restoredQuery ?? localQuery;
  const page = restoredPage === undefined ? localPage : restoredPage - 1;
  const setQuery = (value: string) => {setLocalQuery(value); onQueryChange?.(value);};
  const setPage = (value: number) => {setLocalPage(value); onPageChange?.(value + 1);};
  const sorted = useMemo(() => [...nodes].sort((a, b) =>
    displayLabel(a.label).name.localeCompare(displayLabel(b.label).name, "de") || a.id.localeCompare(b.id)), [nodes]);
  const matches = useMemo(() => {
    const terms = query.toLocaleLowerCase("de").trim().split(/\s+/).filter(Boolean);
    return sorted.filter(node => terms.every(term => node.label.toLocaleLowerCase("de").includes(term)));
  }, [query, sorted]);
  const pages = Math.max(1, Math.ceil(matches.length / 25));
  const current = Math.min(page, pages - 1);
  const visible = matches.slice(current * 25, (current + 1) * 25);
  return <section className="memory-directory" aria-label={title}>
    <header><p className="eyebrow">GEDÄCHTNIS</p><h1>{title}</h1>
      <p>Eine Akte pro Eintrag. Beziehungen und Originalquellen findest du in der jeweiligen Akte.</p></header>
    <label className="directory-search">{title === "Projekte" ? "Projekt suchen" : "Name oder E-Mail suchen"}
      <input type="search" value={query} onChange={event => { setQuery(event.target.value); setPage(0); }} placeholder="Suchen …" />
    </label>
    <p className="directory-count" aria-live="polite">{matches.length} von {nodes.length} Einträgen</p>
    {visible.length ? <ul className="directory-list">{visible.map(node => {
      const label = displayLabel(node.label);
      return <li key={node.id}><button type="button" onClick={() => onOpen(node)} aria-label={`Akte öffnen: ${node.label}`}>
        <span className="directory-monogram" aria-hidden="true">{label.name.slice(0, 1).toLocaleUpperCase("de")}</span>
        <span className="directory-label"><strong>{label.name}</strong>{label.detail && <small>{label.detail}</small>}
          <small>{node.attributes.identity_resolution === "explicit_registry" ? "Eigene Akte" : node.attributes.identity_resolution === "confirmed_group" ? "Gemeinsame Ansicht · Zuordnung prüfen" : "Aus vorhandenen Quellen"}</small></span>
        <span className="directory-open">Akte öffnen <span aria-hidden="true">→</span></span>
      </button></li>;
    })}</ul> : <div className="directory-empty"><h2>{query ? "Kein passender Eintrag" : title === "Projekte" && hasSources ? "Noch keine Projekte zugeordnet" : "Hier ist noch Platz"}</h2>
      {query ? <p>Versuche einen anderen Namen oder einen Teil der E-Mail-Adresse.</p> : title === "Projekte" && hasSources ? <p>Quellen sind vorhanden. Sobald sie einem Projekt zugeordnet sind, erscheint es hier. <a href="/memory?view=status">Einordnung und Quellenstand ansehen</a></p> : <GedaechtnisLeer />}
      {query && <button type="button" onClick={() => { setQuery(""); setPage(0); }}>Suche zurücksetzen</button>}</div>}
    {pages > 1 && <nav className="directory-pagination" aria-label="Aktenseiten">
      <button type="button" disabled={current === 0} onClick={() => setPage(current - 1)}>Zurück</button>
      <span>Seite {current + 1} von {pages}</span>
      <button type="button" disabled={current + 1 >= pages} onClick={() => setPage(current + 1)}>Weiter</button>
    </nav>}
  </section>;
}
