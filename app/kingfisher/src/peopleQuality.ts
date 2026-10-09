import type { GraphNode, MemoryGraph } from "./api";

export type PersonFilter = "people" | "automated" | "review" | "all";

export const isPerson = (node: GraphNode) => node.kind === "person";
export function quality(node: GraphNode): "person" | "automated" | "review" {
  const category = node.attributes.quality_category;
  if (category === "person" || category === "automated" || category === "review") return category;
  // Nur eine bestätigte Identität trägt die Personenansicht ohne Qualitätskennzeichnung.
  return node.attributes.identity_resolution === "explicit_registry" || node.attributes.identity_resolution === "confirmed_group"
    ? "person" : "review";
}
export const duplicateIds = (node: GraphNode) => Array.isArray(node.attributes.duplicate_ids)
  ? node.attributes.duplicate_ids.filter((id): id is string => typeof id === "string") : [];

export function personNodes(graph: MemoryGraph, filter: PersonFilter) {
  return graph.nodes.filter(node => {
    if (!isPerson(node)) return false;
    if (filter === "automated") return quality(node) === "automated";
    if (filter === "review") return quality(node) === "review" || duplicateIds(node).length > 0 || node.attributes.identity_resolution === "confirmed_group";
    if (filter === "people") return quality(node) === "person";
    return true;
  });
}

