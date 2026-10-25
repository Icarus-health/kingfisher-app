import type { GraphNode } from './api';

export const MEMORY_TABS = ['search', 'areas', 'people', 'projects', 'organizations', 'places', 'topics', 'topic-files', 'decisions', 'documents'] as const;
export type MemoryTab = typeof MEMORY_TABS[number];
export type BrowseState = {tab: MemoryTab; q: string; page: number; people: 'people' | 'automated' | 'review' | 'all'; area?: string};

export function browseState(search: string): BrowseState {
  const params = new URLSearchParams(search);
  const tab = params.get('tab');
  const people = params.get('people');
  const area = params.get('area');
  const validArea = area !== null && ['work','personal','health','finance','other'].includes(area);
  const page = Number(params.get('page'));
  return {
    tab: people === 'review' ? 'people' : tab === 'topics' ? 'topic-files' : MEMORY_TABS.includes(tab as MemoryTab) ? tab as MemoryTab : validArea ? 'areas' : 'search',
    q: (params.get('q') || '').slice(0, 200),
    page: Number.isSafeInteger(page) && page > 0 ? page : 1,
    people: people === 'all' || people === 'automated' || people === 'review' ? people : 'people',
    ...(validArea ? {area} : {}),
  };
}

// Diese Ansichten kommen ohne den Gedächtnisgraphen aus (eigene, seitenweise Abfragen). Der Graph umfasst jede Quelle
// und war bei 10.000 Quellen 20 MB und Sekunden entfernt; Organisationen, Bereiche, Dokumente, Orte und Themen warteten
// trotzdem auf ihn (V6, viel Bestand).
const OHNE_GRAPH: readonly MemoryTab[] = ['areas', 'documents', 'organizations', 'places', 'topics', 'topic-files'];

/** Braucht die gewählte Ansicht des Gedächtnisses den ganzen Graphen? Nur dann wird er geladen. */
export function brauchtGraph(tab: MemoryTab, section: 'browse' | 'status' | 'support' = 'browse'): boolean {
  return section === 'browse' && !OHNE_GRAPH.includes(tab);
}

export function browseHref(state: BrowseState): string {
  const params = new URLSearchParams({tab: state.tab});
  if (state.q) params.set('q', state.q.slice(0, 200));
  if (state.page > 1) params.set('page', String(state.page));
  if (state.people !== 'people') params.set('people', state.people);
  if (state.tab === 'areas' && state.area) params.set('area', state.area);
  return '/memory?' + params;
}

export function browseMatches(nodes: GraphNode[], query: string): GraphNode[] {
  const terms = query.trim().toLocaleLowerCase('de').split(/\s+/).filter(Boolean);
  if (!terms.length) return [];
  return nodes.filter(node => (node.kind !== 'claim' || node.attributes.usable === true)
    && terms.every(term => node.label.toLocaleLowerCase('de').includes(term)));
}

export function documentNodes(nodes: GraphNode[]): GraphNode[] {
  return nodes.filter(node => (node.kind === 'document' || node.attributes.episode_kind === 'document')
    && node.attributes.source_current !== false && node.attributes.state !== 'archived' && node.attributes.state !== 'ignored');
}

export function sourceReference(node: GraphNode): {kind: 'episode' | 'note'; id: string} | null {
  const match = /^(episode|note):(.+)$/.exec(node.id);
  return match ? {kind: match[1] as 'episode' | 'note', id: match[2]} : null;
}
