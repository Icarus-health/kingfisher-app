import type { MemoryAreaSource, MemoryAreasPage } from "./api";

export const MEMORY_AREAS = [
  { id: "work", label: "Arbeit & Projekte" },
  { id: "personal", label: "Privat & Familie" },
  { id: "health", label: "Gesundheit" },
  { id: "finance", label: "Finanzen & Verträge" },
] as const;

const AREA_IDS = new Set<string>(MEMORY_AREAS.map(area => area.id));

export type MemoryAreaView = typeof MEMORY_AREAS[number]['id'] | 'other';

export function areaLink(area: MemoryAreaView, _previousSearch?: string): string {
  // A chosen area is a complete view; people/status flags would override it on reload.
  return `/memory?area=${area}`;
}

export function areaViewFromSearch(search: string): MemoryAreaView {
  const area = new URLSearchParams(search).get('area');
  return area === 'other' || (area !== null && AREA_IDS.has(area)) ? area as MemoryAreaView : 'work';
}

export function areaEmptyText(page: {scan_limited?: boolean; next_cursor: number | null}): string {
  if (page.scan_limited || page.next_cursor !== null) return 'In diesem Suchabschnitt gibt es keine passenden aktuellen Hinweise. Weiterprüfen zeigt die nächsten Quellen.';
  return 'Diesem Bereich sind noch keine aktuellen Themenhinweise zugeordnet. Noch nicht ausgewertete Quellen können weitere Informationen enthalten.';
}

export function sourcesForArea(sources: MemoryAreaSource[], areaId: string): MemoryAreaSource[] {
  return sources.filter(source => source.categories.some(category => category.id === areaId));
}

export function otherHintSources(sources: MemoryAreaSource[]): MemoryAreaSource[] {
  return sources.filter(source => source.status !== "complete"
    || source.categories.length === 0
    || source.categories.some(category => !AREA_IDS.has(category.id)));
}

export type MemoryAreaNavigation = {cursor: number | undefined; history: Array<number | undefined>; index: number};
export type MemoryAreaPager = {page: MemoryAreasPage | null; history: Array<number | undefined>; index: number};

export function initialAreaPager(): MemoryAreaPager {
  return {page: null, history: [undefined], index: 0};
}

export function firstAreaNavigation(): MemoryAreaNavigation {
  return {cursor: undefined, history: [undefined], index: 0};
}

export function nextAreaNavigation(pager: MemoryAreaPager): MemoryAreaNavigation | null {
  const next = pager.page?.next_cursor;
  if (next === undefined || next === null) return null;
  const history = [...pager.history.slice(0, pager.index + 1), next];
  return {cursor: next, history, index: history.length - 1};
}

export function previousAreaNavigation(pager: MemoryAreaPager): MemoryAreaNavigation | null {
  if (pager.index <= 0 || pager.index >= pager.history.length) return null;
  return {cursor: pager.history[pager.index - 1], history: pager.history, index: pager.index - 1};
}

export function currentAreaNavigation(pager: MemoryAreaPager): MemoryAreaNavigation {
  return {cursor: pager.history[pager.index], history: pager.history, index: pager.index};
}

export function memorySectionFromSearch(search: string): "browse" | "status" | "support" {
  const view = new URLSearchParams(search).get("view");
  return view === "support" || view === "status" ? view : "browse";
}

export function receiveAreaPage(navigation: MemoryAreaNavigation, page: MemoryAreasPage): MemoryAreaPager {
  return {page, history: navigation.history, index: navigation.index};
}
