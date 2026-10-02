import type { MemoryGraph } from "./api";

// Mitglieder einer Zusammenführung, die es im Gedächtnis nicht mehr gibt (etwa weil die Quelle entzogen wurde).
export function nichtMehrZuordenbar(graph: MemoryGraph, mergeId: string): Array<{ id: string; label: string }> {
  const node = graph.nodes.find(item => item.id === mergeId);
  const rohe = node?.attributes.unassigned_members;
  if (!Array.isArray(rohe)) return [];
  return rohe.flatMap(eintrag => eintrag && typeof eintrag === "object" && typeof (eintrag as { id?: unknown }).id === "string"
    ? [{ id: (eintrag as { id: string }).id, label: String((eintrag as { label?: unknown }).label || "Unbekannte Person") }] : []);
}
