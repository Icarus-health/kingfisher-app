import {restoreMemoryScroll} from "./MemoryViewState";
import { useEffect, useMemo, useRef, useState } from "react";

import { api, type GraphNode, type MemoryGraph } from "./api";
import { Sidebar } from "./chrome";
import { PeopleReview, personNodes, type PersonFilter } from "./PeopleReview";
import { icon, navigate } from "./ui";
import { InterfaceIcon } from "./InterfaceIcon";
import { MemoryStatus } from "./MemoryStatus";
import { MemoryDirectory } from "./MemoryDirectory";
import { SachenListe } from "./SachenListe";
import { SelfModelSupportReview } from "./SelfModelSupportReview";
import { GedaechtnisLeer } from "./GedaechtnisLeer";
import { MemoryAreas } from "./MemoryAreas";
import { memorySectionFromSearch } from "./MemoryAreaModel";
import { brauchtGraph, browseState, browseHref, type MemoryTab } from "./MemoryBrowseModel";
import { DocumentImport } from "./DocumentImport";
import { MemoryFolders } from "./MemoryFolders";
import { MemorySearch } from "./MemorySearch";
import { Leer, Seitenkopf, Segmente } from "./grundlage";
import "./MemoryWorkspace.css";
import "./Gedaechtnis.css";

type FilterId = MemoryTab;

const FILTERS: Array<{ id: FilterId; label: string; icon: "people" | "project" | "brain" | "check" | "document" | "building" | "pin" }> = [
  { id: "search", label: "Suchen", icon: "brain" },
  { id: "areas", label: "Bereiche", icon: "brain" },
  { id: "people", label: "Menschen", icon: "people" },
  { id: "projects", label: "Projekte", icon: "project" },
  { id: "documents", label: "Dokumente", icon: "document" },
];
const MORE_FILTERS: typeof FILTERS = [
  { id: "topic-files", label: "Themen", icon: "brain" },
  { id: "organizations", label: "Organisationen", icon: "building" },
  { id: "places", label: "Orte", icon: "pin" },
  { id: "decisions", label: "Entscheidungen", icon: "check" },
];

const PERSONEN_FILTER: Array<[PersonFilter, string]> = [["people", "Personen"], ["automated", "Automatische Absender"], ["review", "Prüfen"], ["all", "Alle"]];

const RING_POSITIONS = [
  [18, 20], [48, 13], [78, 22], [86, 53], [73, 78],
  [47, 76], [18, 76], [10, 49], [30, 44], [67, 43],
] as const;

function openProfile(node: GraphNode) {
  if (node.kind !== "person" && node.kind !== "project") return;
  const back = new URLSearchParams({return_to: window.location.pathname + window.location.search});
  if (node.attributes.identity_resolution === "confirmed_group") {
    navigate("/memory?people=review");
  } else if (node.attributes.identity_resolution === "explicit_registry") {
    navigate(`/memory/registry/${encodeURIComponent(node.id)}?${back}`);
  } else if (node.kind === "person") {
    back.set("source_node", node.id);
    navigate(`/memory/people/${encodeURIComponent(node.label)}?${back}`);
  } else {
    navigate(`/memory/projects/${encodeURIComponent(node.id.replace(/^project:/, ""))}?${back}`);
  }
}

/** Wer unten in der leisen Zeile eine Ansicht wählt, sieht sie von oben. */
function zumAnfang() {
  if (typeof document === "undefined") return;
  const seite = document.querySelector<HTMLElement>(".memory-page");
  if (seite) seite.scrollTop = 0;
  window.scrollTo(0, 0);
}

function isDocument(node: GraphNode) {
  return node.kind === "document" || node.attributes.episode_kind === "document";
}

function matchesFilter(node: GraphNode, filter: FilterId) {
  if (filter === "people") return node.kind === "person";
  if (filter === "projects") return node.kind === "project";
  if (filter === "topics") return node.kind === "topic";
  if (filter === "decisions") return node.kind === "decision";
  return isDocument(node);
}

function connectedNodes(primary: GraphNode[], graph: MemoryGraph) {
  const primaryIds = new Set(primary.map((node) => node.id));
  const relatedIds = new Set<string>();
  for (const edge of graph.edges) {
    if (primaryIds.has(edge.source)) relatedIds.add(edge.target);
    if (primaryIds.has(edge.target)) relatedIds.add(edge.source);
  }
  return graph.nodes.filter((node) => relatedIds.has(node.id) && !primaryIds.has(node.id));
}

function nodeTone(node: GraphNode) {
  if (node.kind === "person") return "person";
  if (node.kind === "project") return "project";
  if (node.kind === "decision") return "decision";
  return "reference";
}

function GraphCanvas({ graph, filter, personFilter }: { graph: MemoryGraph; filter: FilterId; personFilter: PersonFilter }) {
  const [page, setPage] = useState(0);
  const canvasLabel = filter === "people"
    ? ({ people: "Personen", automated: "automatische Absender", review: "Prüffälle", all: "Einträge" }[personFilter])
    : [...FILTERS, ...MORE_FILTERS].find(item => item.id === filter)?.label ?? "Einträge";
  const { nodes, edges, total, currentPage, pageCount } = useMemo(() => {
    const primary = filter === "people"
      ? personNodes(graph, personFilter)
      : graph.nodes.filter((node) => matchesFilter(node, filter));
    // Frühere Aussagen bleiben in der Profilhistorie. Im aktuellen Graphen
    // dürfen widerrufene oder abgelaufene Claims nicht wie gültiges Wissen wirken.
    const pageCount = Math.max(1, Math.ceil(primary.length / RING_POSITIONS.length));
    const currentPage = Math.min(page, pageCount - 1);
    const visible = primary.slice(currentPage * RING_POSITIONS.length, (currentPage + 1) * RING_POSITIONS.length);
    const allowedPeople = filter === "people" ? new Set(personNodes(graph, personFilter).map(node => node.id)) : null;
    const related = connectedNodes(visible, graph).filter((node) =>
      (node.kind !== "claim" || node.attributes.usable === true)
      && (node.kind !== "person" || allowedPeople?.has(node.id) !== false),
    );
    const ordered = [...visible, ...related]
      .filter((node, index, items) => items.findIndex((item) => item.id === node.id) === index)
      .slice(0, RING_POSITIONS.length);
    const ids = new Set(ordered.map((node) => node.id));
    return {
      nodes: ordered,
      edges: graph.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target)),
      total: primary.length,
      currentPage,
      pageCount,
    };
  }, [filter, graph, page, personFilter]);

  const positions = useMemo(
    () => new Map(nodes.map((node, index) => [node.id, RING_POSITIONS[index]])),
    [nodes],
  );

  if (total === 0) {
    return (
      <section className="memory-canvas memory-empty" aria-live="polite">
        <GedaechtnisLeer satz={`Noch keine belegten ${canvasLabel}.`} />
      </section>
    );
  }

  return (
    <section className="memory-canvas" aria-label={`Gedächtnisgraph: ${canvasLabel}`}>
      <svg aria-hidden="true" className="memory-edges" preserveAspectRatio="none" viewBox="0 0 100 100">
        {edges.map((edge) => {
          const source = positions.get(edge.source);
          const target = positions.get(edge.target);
          if (!source || !target) return null;
          return <line key={edge.id} x1={source[0]} x2={target[0]} y1={source[1]} y2={target[1]} />;
        })}
      </svg>
      <div className="memory-brand-node" aria-hidden="true">
        <img src="/03_Media/Approved/kingfisher-flight-transparent-approved-v1.png" alt="" />
        <span>Kingfisher</span>
      </div>
      {nodes.map((node) => {
        const position = positions.get(node.id);
        if (!position) return null;
        return (
          <div
            className={`memory-node ${nodeTone(node)}`}
            key={node.id}
            onClick={() => {
              openProfile(node);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                openProfile(node);
              }
            }}
            style={{ left: `${position[0]}%`, top: `${position[1]}%` }}
            role={node.kind === "person" || node.kind === "project" ? "button" : undefined}
            tabIndex={node.kind === "person" || node.kind === "project" ? 0 : undefined}
            title={node.label}
          >
            <InterfaceIcon name={node.kind === "person" ? "people" : node.kind === "project" ? "project" : node.kind === "decision" ? "check" : isDocument(node) ? "document" : "brain"} />
            <span>{node.label}</span>
          </div>
        );
      })}
      {pageCount > 1 ? <nav className="memory-pagination" aria-label="Weitere Gedächtniseinträge">
        <button type="button" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>Zurück</button>
        <span aria-live="polite">{currentPage * RING_POSITIONS.length + 1}–{Math.min((currentPage + 1) * RING_POSITIONS.length, total)} von {total} {canvasLabel}</span>
        <button type="button" disabled={currentPage + 1 === pageCount} onClick={() => setPage(currentPage + 1)}>Weiter</button>
      </nav> : null}
    </section>
  );
}

export function MemoryGraph({ recentConversation }: { recentConversation: string | null }) {
  const [documentImportOpen,setDocumentImportOpen] = useState(false);
  const [graph, setGraph] = useState<MemoryGraph | null>(null);
  const [error, setError] = useState(false);
  const [filter, setFilter] = useState<FilterId>(() => browseState(window.location.search).tab);
  const [query, setQuery] = useState(() => browseState(window.location.search).q);
  const [directoryPage, setDirectoryPage] = useState(() => browseState(window.location.search).page);
  const [section, setSection] = useState<"browse" | "status" | "support">(() =>
    memorySectionFromSearch(window.location.search));
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const reviewSubmittingRef = useRef(false);
  const [personFilter, setPersonFilter] = useState<PersonFilter>(() => browseState(window.location.search).people);
  function updateBrowse(change: Partial<ReturnType<typeof browseState>>, replace = false) {
    const next = {...browseState(window.location.search), ...change};
    const href = browseHref(next);
    if (replace) {
      window.history.replaceState({}, "", href);
      setFilter(next.tab); setQuery(next.q); setDirectoryPage(next.page); setPersonFilter(next.people);
    } else navigate(href);
  }

  useEffect(() => {
    if (typeof document !== "undefined") return restoreMemoryScroll(document.querySelector<HTMLElement>(".memory-page"));
  },[filter,query,directoryPage,section]);

  async function load() {
    setError(false);
    try { setGraph(await api.memoryGraph()); } catch { setError(true); }
  }

  // Der Graph kommt erst, wenn eine Ansicht ihn braucht (Suchen, Menschen, Projekte, Entscheidungen), und nur einmal.
  const graphNoetig = brauchtGraph(filter, section);
  const graphAngefragt = useRef(false);
  const aktiv = useRef(true);
  useEffect(() => { aktiv.current = true; return () => { aktiv.current = false; }; }, []);
  useEffect(() => {
    if (!graphNoetig || graphAngefragt.current) return;
    graphAngefragt.current = true;
    api.memoryGraph().then((result) => aktiv.current && setGraph(result)).catch(() => aktiv.current && setError(true));
  }, [graphNoetig]);

  useEffect(() => {
    const applyPeopleQuery = () => {
      if (window.location.pathname !== "/memory") return;
      // Ein History-Wechsel innerhalb von /memory darf die wirksame
      // Bestätigung nicht aushängen und ihre Auditwarnung verschlucken.
      if (reviewSubmittingRef.current) return;
      setSection(memorySectionFromSearch(window.location.search));
      const restored = browseState(window.location.search);
      setFilter(restored.tab); setQuery(restored.q); setDirectoryPage(restored.page);
      setPersonFilter(restored.people);
    };
    window.addEventListener("popstate", applyPeopleQuery);
    return () => window.removeEventListener("popstate", applyPeopleQuery);
  }, []);

  // Ansichten außerhalb der Segmente tragen ihren Namen als Titel unter der Leiste.
  const unteransicht = section === "browse" && filter === "decisions" ? "Entscheidungen" : null;

  return (
    <div className="shell memory-shell">
      <Sidebar active="Gedächtnis" recentConversation={recentConversation} navigationDisabled={reviewSubmitting} />
      <main data-memory-loading={graphNoetig && !graph && !error} className={`memory-page memory-page-workspace${section !== "browse" ? " memory-page-status" : ""}`}>
        <Seitenkopf titel="Gedächtnis" aktionen={section === "browse" && filter === "documents" ? <button className="g-knopf document-add" type="button" onClick={()=>setDocumentImportOpen(true)}><img src={icon("plus","Outline")} alt=""/>Dokument hinzufügen</button> : undefined} />
        <aside className="memory-filter" aria-label="Gedächtnisbereich auswählen">
          <Segmente label="Gedächtnisbereich" wert={section === "browse" ? filter : ("" as FilterId)}
            optionen={FILTERS.map(item => ({wert: item.id, titel: item.label, deaktiviert: reviewSubmitting}))}
            onWahl={id => updateBrowse({tab: id, q: "", page: 1, people: "people"})} />
          {section === "browse" && filter === "people" ? <Segmente kompakt className="memory-person-filter" label="Personenqualität auswählen" wert={personFilter}
            optionen={PERSONEN_FILTER.map(([id, label]) => ({wert: id, titel: label, zahl: graph ? personNodes(graph, id).length : undefined, deaktiviert: reviewSubmitting}))}
            onWahl={id => updateBrowse({tab: "people", people: id, q: "", page: 1})} /> : null}
        </aside>
        {unteransicht ? <h2 className="g-titel memory-unteransicht">{unteransicht}</h2> : null}
        {documentImportOpen && <DocumentImport initiallyExpanded showLibrary={false} title="Dokument hinzufügen" onClose={()=>{setDocumentImportOpen(false);window.dispatchEvent(new Event("workspace-view-changed"));}} />}
        {section === "support" ? <SelfModelSupportReview onSubmittingChange={submitting => { reviewSubmittingRef.current = submitting; setReviewSubmitting(submitting); }} /> : section === "status" ? <MemoryStatus /> : filter === "areas" ? <MemoryAreas /> : filter === "search" || filter === "documents" ? <div className="memory-documents-workspace">{filter === "documents" ? <MemoryFolders /> : <MemorySearch key={filter} graph={graph} graphError={error} onGraphRetry={load} query={query} page={directoryPage} onQueryChange={q => updateBrowse({q,page:1},true)} onPageChange={page => updateBrowse({page},true)} onOpen={openProfile} />}</div> : error && graphNoetig ? (
          <section className="memory-canvas memory-error" aria-live="polite">
            <Leer zeichen="brain" satz="Das Gedächtnis ist gerade nicht erreichbar." aktion={<button className="g-knopf-getoent" onClick={load} type="button">Wiederholen</button>} />
          </section>
        ) : filter === "organizations" || filter === "places" || filter === "topic-files" || filter === "topics" ? (
          <SachenListe art={filter === "organizations" ? "organisation" : filter === "places" ? "ort" : "thema"} query={query} page={directoryPage} onQueryChange={q => updateBrowse({q,page:1},true)} onPageChange={page => updateBrowse({page},true)} />
        ) : graph ? (filter === "people" && personFilter === "review"
          ? <PeopleReview graph={graph} onGraphRefresh={load} />
          : filter === "people" || filter === "projects"
          ? <MemoryDirectory key={`${filter}:${personFilter}`} title={filter === "projects" ? "Projekte" : personFilter === "automated" ? "Automatische Absender" : personFilter === "all" ? "Alle Kontakte" : "Menschen"}
              graph={graph} nodes={filter === "people" ? personNodes(graph, personFilter) : graph.nodes.filter(node => node.kind === "project")} onOpen={openProfile} query={query} page={directoryPage} onQueryChange={q => updateBrowse({q,page:1},true)} onPageChange={page => updateBrowse({page},true)} hasSources={graph.nodes.some(node => node.kind === "episode")} />
          : <GraphCanvas key={`${filter}:${personFilter}`} filter={filter} personFilter={personFilter} graph={graph} />
        ) : <section className="memory-canvas memory-loading" aria-label="Gedächtnis wird geladen" />}
        {/* Seltene Ansichten und Pflege: eine leise Zeile am Ende statt eines Aufklappers im Kopf. */}
        <nav className="memory-tools" aria-label="Weitere Ansichten und Pflege">
          {MORE_FILTERS.map(item => <button type="button" disabled={reviewSubmitting} key={item.id} aria-pressed={section === "browse" && filter === item.id} onClick={() => {updateBrowse({tab:item.id,q:"",page:1,people:"people"});zumAnfang();}}>{item.label}</button>)}
          <button type="button" disabled={reviewSubmitting} aria-pressed={section === "support"} onClick={() => {navigate("/memory?view=support");zumAnfang();}}>Aussagen prüfen</button>
          <button type="button" disabled={reviewSubmitting} aria-pressed={section === "status"} onClick={() => {navigate("/memory?view=status");zumAnfang();}}>Verarbeitung & Verlauf</button>
          <a href="/settings#ki">KI-Zugänge & Modelle</a>
        </nav>
      </main>
    </div>
  );
}
