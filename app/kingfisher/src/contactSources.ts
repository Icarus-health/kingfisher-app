import type { GraphNode, MemoryGraph, PersonProfile } from "./api";

export type ContactSourceView = { node: GraphNode; sources: GraphNode[] };
export type ContactProfile = { kind: "person"; profile: PersonProfile } | { kind: "sources"; view: ContactSourceView };

export async function loadContactProfile(
  name: string, nodeId: string | null,
  profile: (name: string) => Promise<PersonProfile>, graph: () => Promise<MemoryGraph>,
  isNotFound: (cause: unknown) => boolean,
): Promise<ContactProfile> {
  try { return { kind: "person", profile: await profile(name) }; }
  catch (cause) {
    if (!nodeId || !isNotFound(cause)) throw cause;
    const current = await graph();
    const matches = current.nodes.filter(node => node.kind === "person" && node.label === name);
    if (matches.length !== 1 || matches[0].id !== nodeId) throw cause;
    const node = matches[0];
    if (node.attributes.identity_resolution === "explicit_registry" || node.attributes.identity_resolution === "confirmed_group"
      || !["automated", "review"].includes(String(node.attributes.quality_category))) throw cause;
    // Nur genau belegte Beteiligung; kein Name, Claim oder Firmenbezug wird ergänzt.
    const sourceIds = new Set(current.edges.filter(edge => edge.source === node.id
      && edge.relation === "participated_in" && edge.state === "observed"
      && edge.target.startsWith("episode:") && edge.target.length > 8
      && edge.evidence_refs.length === 1 && edge.evidence_refs[0] === edge.target).map(edge => edge.target));
    const sources = current.nodes.filter(source => source.kind === "episode" && sourceIds.has(source.id)
      && ["new", "consolidated", "archived"].includes(String(source.attributes.state)));
    if (!sources.length) throw cause;
    return { kind: "sources", view: { node, sources } };
  }
}
