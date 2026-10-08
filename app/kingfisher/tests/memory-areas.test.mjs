import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { currentAreaNavigation, firstAreaNavigation, initialAreaPager, MEMORY_AREAS, nextAreaNavigation,
  otherHintSources, previousAreaNavigation, receiveAreaPage, sourcesForArea } from "../src/MemoryAreaModel.ts";

const sources = [
  { episode_id: "work", status: "complete", categories: [{ id: "work", label: "Arbeit", origin: "automatic" }] },
  { episode_id: "health", status: "complete", categories: [{ id: "health", label: "Gesundheit", origin: "user" }] },
  { episode_id: "cross", status: "complete", categories: [
    { id: "work", label: "Arbeit", origin: "automatic" },
    { id: "finance", label: "Finanzen", origin: "automatic" },
  ] },
  { episode_id: "appointments", status: "complete", categories: [{ id: "appointments", label: "Termine", origin: "automatic" }] },
  { episode_id: "unassigned", status: "empty", categories: [] },
  { episode_id: "pending", status: "pending", categories: [] },
];

test("the four agreed views are present even without health hints", () => {
  assert.deepEqual(MEMORY_AREAS.map(area => area.label), [
    "Arbeit & Projekte", "Privat & Familie", "Gesundheit", "Finanzen & Verträge",
  ]);
});

test("a source can appear in each explicitly suggested area without changing its labels", () => {
  assert.deepEqual(sourcesForArea(sources, "work").map(source => source.episode_id), ["work", "cross"]);
  assert.deepEqual(sourcesForArea(sources, "finance").map(source => source.episode_id), ["cross"]);
  assert.equal(sources[2].categories.length, 2, "the original multi-label projection remains intact");
});

test("other topics and sources without hints remain accessible", () => {
  assert.deepEqual(otherHintSources(sources).map(source => source.episode_id), ["appointments", "unassigned", "pending"]);
});

test("area pagination retains only cursor positions and can move backward or branch", () => {
  const source = id => ({episode_id: id, title: id, occurred_at: null, status: "complete", categories: []});
  const page = (id, next_cursor) => ({areas: [], sources: [source(id)], taxonomy_version: 2,
    scanned_count: 1, counts_scope: "page", next_cursor, truncated: next_cursor !== null});
  let pager = initialAreaPager();
  pager = receiveAreaPage(firstAreaNavigation(), page("neueste", 900));
  const page2 = nextAreaNavigation(pager);
  assert.equal(page2.cursor, 900);
  pager = receiveAreaPage(page2, page("ältere", 840));
  assert.deepEqual(pager.page.sources.map(row => row.episode_id), ["ältere"], "only the current source page is retained");
  assert.deepEqual(currentAreaNavigation(pager).cursor, 900);
  const back = previousAreaNavigation(pager);
  assert.equal(back.cursor, undefined, "the first-page cursor is retained for return navigation");
  pager = receiveAreaPage(back, page("neueste", 900));
  const branch = nextAreaNavigation(pager);
  assert.equal(branch.cursor, 900);
  assert.equal(previousAreaNavigation(initialAreaPager()), null);
  pager = receiveAreaPage(branch, page("letzte", null));
  assert.equal(nextAreaNavigation(pager), null, "the API cursor closes pagination at the last page");
});

test("the overview reads bounded pages only and retains the established memory views", () => {
  const component = readFileSync(new URL("../src/MemoryAreas.tsx", import.meta.url), "utf8");
  const graph = readFileSync(new URL("../src/MemoryGraph.tsx", import.meta.url), "utf8");
  assert.match(component, /api\.memoryAreas\(PAGE_SIZE, navigation\.cursor, selected\)/);
  assert.match(component, /Vorherige Seite/);
  assert.match(component, /Nächste Seite/);
  assert.match(component, /setPager\(receiveAreaPage\(navigation, result\)\)/);
  assert.doesNotMatch(component, /setPages|flatMap\(page => page\.sources\)/, "only one source page is held in UI state");
  assert.match(component, /ProfileSource kind="episode"[\s\S]*readOnly allowIgnore=\{false\}/);
  assert.doesNotMatch(component, /api\.addCategory|correctSourceCategories|setInterval/);
  for (const view of ['"people"', '"projects"', '"organizations"', '"places"', '"topics"', '"decisions"', '"documents"']) {
    assert.ok(graph.includes(view), `existing view ${view} remains available`);
  }
});

test('direct health entry and bounded empty states cannot claim an empty whole memory', async () => {
  const { areaViewFromSearch, areaEmptyText } = await import('../src/MemoryAreaModel.ts');
  assert.equal(areaViewFromSearch('?area=health'), 'health');
  assert.equal(areaViewFromSearch('?area=unknown'), 'work');
  assert.match(areaEmptyText({scan_limited: true, next_cursor: 42}), /Weiterprüfen/);
  assert.match(areaEmptyText({scan_limited: false, next_cursor: null}), /zugeordnet/);
  assert.doesNotMatch(areaEmptyText({scan_limited: false, next_cursor: null}), /keine.*Gesundheitsdaten/i);
});

test('choosing an area removes people and status flags from reloadable links', async () => {
  const { areaLink } = await import('../src/MemoryAreaModel.ts');
  for (const previous of ['?people=review', '?view=status', '?people=review&view=status&area=work']) {
    assert.equal(areaLink('health', previous), '/memory?area=health');
  }
});
