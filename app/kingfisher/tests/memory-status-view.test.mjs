import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { memorySectionFromSearch } from "../src/MemoryAreaModel.ts";
import { browseState } from "../src/MemoryBrowseModel.ts";

const src = new URL("../src/", import.meta.url);
const read = (name) => readFileSync(new URL(name, src), "utf8");

test("the status page can be opened directly without removing people review", () => {
  const graph = read("MemoryGraph.tsx");
  assert.equal(memorySectionFromSearch('?view=status'), 'status');
  assert.match(graph, /memorySectionFromSearch\(window.location.search\)/);
  assert.equal(browseState('?people=review&view=status').tab, 'people');
  assert.equal(browseState('?people=review&view=status').people, 'review');
  assert.match(graph, /setFilter\(restored\.tab\)/);
  assert.match(graph, /setPersonFilter\(restored\.people\)/);
  assert.match(graph, /setSection\(memorySectionFromSearch\(window.location.search\)\)/);
});

test("both timeline page requests carry the selected source or recorded basis", () => {
  const status = read("MemoryStatus.tsx");
  assert.match(status, /api\.memoryTimeline\(start, end, undefined, basis\)/);
  assert.match(status, /api\.memoryTimeline\(timeline\.start, timeline\.end, timeline\.next_cursor, basis\)/);
  assert.match(status, /timeline\.basis !== basis/);
});

test("local model progress opens the direct memory status view", () => {
  assert.match(read("LocalModelSettings.tsx"), /navigate\("\/memory\?view=status"\).*Fortschritt ansehen/);
});
