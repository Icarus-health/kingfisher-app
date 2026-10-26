import { useMemo, useState } from "react";
import type { GraphNode, MemoryGraph as MemoryGraphData } from "./api";
import "./MemoryDirectory.css";
import { displayLabel } from "./displayIdentity";
import { MemoryAvatar } from "./MemoryAvatar";
import { useWorkspaceMemoryView } from "./useWorkspaceMemoryView";
import { contactDateFromGraph } from "./WorkspaceMemoryModel";
import { GedaechtnisLeer } from "./GedaechtnisLeer";
import { Gruppe, Leer } from "./grundlage";
import { passtSuche } from "./suchform.ts";


export function MemoryDirectory({ nodes, title, onOpen, query: restoredQuery, page: restoredPage, onQueryChange, onPageChange, hasSources = false, graph }: {
  graph?: MemoryGraphData; nodes: GraphNode[]; title: string; onOpen: (node: GraphNode) => void;
  query?: string; page?: number; onQueryChange?: (query: string) => void; onPageChange?: (page: number) => void; hasSources?: boolean;
}) {
  const {overview, error: imageError, refresh: retryImages} = useWorkspaceMemoryView();
  const [localQuery, setLocalQuery] = useState("");
  const [localPage, setLocalPage] = useState(0);
  const query = restoredQuery ?? localQuery;
  const page = restoredPage === undefined ? localPage : restoredPage - 1;
  const setQuery = (value: string) => {setLocalQuery(value); onQueryChange?.(value);};
  const setPage = (value: number) => {setLocalPage(value); onPageChange?.(value + 1);};
  const sorted = useMemo(() => [...nodes].sort((a, b) =>
    displayLabel(a.label).name.localeCompare(displayLabel(b.label).name, "de") || a.id.localeCompare(b.id)), [nodes]);
  const matches = useMemo(() => {
    // „Müller“ findet „Mueller“ und umgekehrt (Befund A7, `suchform.ts`).
    return sorted.filter(node => passtSuche(node.label, query));
  }, [query, sorted]);
  const pages = Math.max(1, Math.ceil(matches.length / 25));
  const current = Math.min(page, pages - 1);
  const visible = matches.slice(current * 25, (current + 1) * 25);
  const zuordnung = (node: GraphNode) => node.attributes.identity_resolution === "explicit_registry" ? "Eigene Akte"
    : node.attributes.identity_resolution === "confirmed_group" ? "Gemeinsame Ansicht · Zuordnung prüfen" : "";
  return <section className="memory-directory gd-verzeichnis" aria-label={title}>
    <header className="gd-verzeichnis-kopf">
      <label className="directory-search"><span className="visually-hidden">{title === "Projekte" ? "Projekt suchen" : "Name oder E-Mail suchen"}</span>
        <input type="search" value={query} onChange={event => { setQuery(event.target.value); setPage(0); }} placeholder={title === "Projekte" ? "Projekt suchen …" : "Name oder E-Mail suchen …"} />
      </label></header>
    {imageError && <p role="alert" className="gd-hinweis">Eigene Bilder konnten nicht geladen werden. <button type="button" className="g-knopf-schlicht g-kompakt" onClick={() => void retryImages()}>Bilder erneut laden</button></p>}
    {visible.length ? <Gruppe titel={<span className="directory-count" aria-live="polite">{query ? `${matches.length} von ${nodes.length}` : `${nodes.length} ${nodes.length === 1 ? "Eintrag" : "Einträge"}`}</span>}><ul className="directory-list gd-liste">{visible.map(node => {
      const label = displayLabel(node.label);
      const neben = [label.detail, node.kind === "person" ? "" : node.attributes.area ? String(node.attributes.area) : "", zuordnung(node)].filter(Boolean).join(" · ");
      const kontakt = node.kind === "person" && graph ? contactDateFromGraph(graph, node.id) : "";
      return <li key={node.id} data-memory-row={node.id}><button type="button" className="g-zeile gd-zeile" onClick={() => onOpen(node)} aria-label={`Akte öffnen: ${node.label}`}>
        <MemoryAvatar id={node.id} label={label.name} available={overview?.avatars.some(record => record.id === node.id && record.data?.available) ?? false} revision={overview?.avatars.find(record => record.id === node.id)?.revision} />
        <span className="g-zeile-text"><span className="g-zeile-titel">{label.name}</span>{neben ? <span className="g-zeile-neben">{neben}</span> : null}</span>
        {kontakt && kontakt !== "unbekannt" ? <span className="g-zeile-wert" title="Letzter Kontakt">{kontakt}</span> : null}
        <span className="g-zeile-pfeil" aria-hidden="true" />
      </button></li>;
    })}</ul></Gruppe> : query ? <Leer zeichen="search" satz="Kein passender Eintrag." aktion={<button type="button" className="g-knopf-getoent" onClick={() => { setQuery(""); setPage(0); }}>Suche zurücksetzen</button>} />
      : title === "Projekte" && hasSources ? <Leer zeichen="project" satz="Noch keine Projekte zugeordnet." aktion={<a className="g-knopf-getoent" href="/memory?view=status">Einordnung ansehen</a>} />
      : <GedaechtnisLeer />}
    {pages > 1 && <nav className="directory-pagination" aria-label="Aktenseiten">
      <button type="button" className="g-knopf-getoent g-kompakt" disabled={current === 0} onClick={() => setPage(current - 1)}>Zurück</button>
      <span>Seite {current + 1} von {pages}</span>
      <button type="button" className="g-knopf-getoent g-kompakt" disabled={current + 1 >= pages} onClick={() => setPage(current + 1)}>Weiter</button>
    </nav>}
  </section>;
}
