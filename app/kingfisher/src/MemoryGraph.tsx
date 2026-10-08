import { useEffect, useMemo, useRef, useState } from "react";

import { api, type GraphNode, type MemoryGraph } from "./api";
import { Sidebar } from "./chrome";
import { PeopleReview, personNodes, type PersonFilter } from "./PeopleReview";
import { navigate } from "./ui";
import { InterfaceIcon } from "./InterfaceIcon";
import { MemoryStatus } from "./MemoryStatus";
import { MemoryDirectory } from "./MemoryDirectory";
import { SachenListe } from "./SachenListe";
import { SelfModelSupportReview } from "./SelfModelSupportReview";
import { GedaechtnisLeer } from "./GedaechtnisLeer";

type FilterId = "people" | "projects" | "topics" | "decisions" | "documents" | "organizations" | "places" | "topic-files";

const FILTERS: Array<{ id: FilterId; label: string; icon: "people" | "project" | "brain" | "check" | "document" | "building" | "pin" }> = [
  { id: "people", label: "Menschen", icon: "people" },
  { id: "projects", label: "Projekte", icon: "project" },
  { id: "organizations", label: "Organisationen", icon: "building" },
  { id: "places", label: "Orte", icon: "pin" },
  { id: "topics", label: "Themen", icon: "brain" },
  { id: "topic-files", label: "Themenakten", icon: "brain" },
  { id: "decisions", label: "Entscheidungen", icon: "check" },
  { id: "documents", label: "Dokumente", icon: "document" },
];

const RING_POSITIONS = [
  [18, 20], [48, 13], [78, 22], [86, 53], [73, 78],
  [47, 76], [18, 76], [10, 49], [30, 44], [67, 43],
] as const;

function openProfile(node: GraphNode) {
  if (node.kind !== "person" && node.kind !== "project") return;
  if (node.attributes.identity_resolution === "confirmed_group") {
    navigate("/memory?people=review");
  } else if (node.attributes.identity_resolution === "explicit_registry") {
    navigate(`/memory/registry/${encodeURIComponent(node.id)}`);
  } else if (node.kind === "person") {
    navigate(`/memory/people/${encodeURIComponent(node.label)}`);
  } else {
    navigate(`/memory/projects/${encodeURIComponent(node.id.replace(/^project:/, ""))}`);
  }
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
    : FILTERS.find(item => item.id === filter)?.label;
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
        <img src="/03_Media/Approved/kingfisher-flight-transparent-approved-v1.png" alt="" />
        <p>Noch keine belegten {canvasLabel}.</p>
        <GedaechtnisLeer />
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
  const [graph, setGraph] = useState<MemoryGraph | null>(null);
  const [error, setError] = useState(false);
  const [filter, setFilter] = useState<FilterId>("people");
  const [section, setSection] = useState<"browse" | "status" | "support">(() =>
    new URLSearchParams(window.location.search).get("view") === "status" ? "status" : "browse");
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const reviewSubmittingRef = useRef(false);
  const [personFilter, setPersonFilter] = useState<PersonFilter>(() => new URLSearchParams(window.location.search).get("people") === "review" ? "review" : "people");

  async function load() {
    setError(false);
    try { setGraph(await api.memoryGraph()); } catch { setError(true); }
  }

  useEffect(() => {
    let active = true;
    api.memoryGraph().then((result) => active && setGraph(result)).catch(() => active && setError(true));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const applyPeopleQuery = () => {
      if (window.location.pathname !== "/memory") return;
      // Ein History-Wechsel innerhalb von /memory darf die wirksame
      // Bestätigung nicht aushängen und ihre Auditwarnung verschlucken.
      if (reviewSubmittingRef.current) return;
      setSection("browse");
      setFilter("people");
      const query = new URLSearchParams(window.location.search);
      setPersonFilter(query.get("people") === "review" ? "review" : "people");
      if (query.get("view") === "status") setSection("status");
    };
    window.addEventListener("popstate", applyPeopleQuery);
    return () => window.removeEventListener("popstate", applyPeopleQuery);
  }, []);

  return (
    <div className="shell memory-shell">
      <Sidebar active="Gedächtnis" recentConversation={recentConversation} navigationDisabled={reviewSubmitting} />
      <main className={`memory-page${section !== "browse" ? " memory-page-status" : ""}`}>
        <aside className="memory-filter" aria-label="Gedächtnisbereich auswählen">
          <p>GEDÄCHTNIS</p>
          <div>
            {FILTERS.map((item) => (
              <button
                aria-pressed={section === "browse" && filter === item.id}
                className={section === "browse" && filter === item.id ? "active" : ""}
                disabled={reviewSubmitting}
                key={item.id}
                onClick={() => { setFilter(item.id); setSection("browse"); }}
                type="button"
              >
                <InterfaceIcon name={item.icon} />
                <span>{item.label}</span>
              </button>
            ))}
          </div>
          {section === "browse" && filter === "people" ? <div className="memory-person-filter" aria-label="Personenqualität auswählen">
            {([["people", "Personen"], ["automated", "Automatische Absender"], ["review", "Prüfen"], ["all", "Alle"]] as Array<[PersonFilter, string]>).map(([id, label]) => (
              <button aria-pressed={personFilter === id} className={personFilter === id ? "active" : ""} disabled={reviewSubmitting} key={id} onClick={() => setPersonFilter(id)} type="button">{label}{graph ? ` (${personNodes(graph, id).length})` : ""}</button>
            ))}
          </div> : null}
          <small>Nur belegte Verbindungen</small>
          <a href="/settings#ki">Mit ChatGPT einordnen & nachprüfen</a>
          <button type="button" disabled={reviewSubmitting} className={section === "support" ? "active" : ""} aria-pressed={section === "support"} onClick={() => setSection("support")}>Aussagen prüfen</button>
          <button type="button" disabled={reviewSubmitting} className={section === "status" ? "active" : ""} aria-pressed={section === "status"} onClick={() => setSection("status")}>Verarbeitung & Verlauf</button>
        </aside>
        {section === "support" ? <SelfModelSupportReview onSubmittingChange={submitting => { reviewSubmittingRef.current = submitting; setReviewSubmitting(submitting); }} /> : section === "status" ? <MemoryStatus /> : error ? (
          <section className="memory-canvas memory-error" aria-live="polite">
            <p>Das Gedächtnis ist gerade nicht erreichbar.</p>
            <button onClick={load} type="button">Wiederholen</button>
          </section>
        ) : filter === "organizations" || filter === "places" || filter === "topic-files" ? (
          <SachenListe art={filter === "organizations" ? "organisation" : filter === "places" ? "ort" : "thema"} />
        ) : graph ? (filter === "people" && personFilter === "review"
          ? <PeopleReview graph={graph} onGraphRefresh={load} />
          : filter === "people" || filter === "projects"
          ? <MemoryDirectory key={`${filter}:${personFilter}`} title={filter === "projects" ? "Projekte" : personFilter === "automated" ? "Automatische Absender" : personFilter === "all" ? "Alle Kontakte" : "Menschen"}
              nodes={filter === "people" ? personNodes(graph, personFilter) : graph.nodes.filter(node => node.kind === "project")} onOpen={openProfile} />
          : <GraphCanvas key={`${filter}:${personFilter}`} filter={filter} personFilter={personFilter} graph={graph} />
        ) : <section className="memory-canvas memory-loading" aria-label="Gedächtnis wird geladen" />}
      </main>
    </div>
  );
}
