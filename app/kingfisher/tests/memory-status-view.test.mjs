import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const src = new URL("../src/", import.meta.url);
const read = (name) => readFileSync(new URL(name, src), "utf8");

test("the status page can be opened directly without removing people review", () => {
  const graph = read("MemoryGraph.tsx");
  assert.match(graph, /get\("view"\) === "status" \? "status" : "browse"/);
  assert.match(graph, /query\.get\("people"\) === "review" \? "review" : "people"/);
  assert.match(graph, /if \(query\.get\("view"\) === "status"\) setSection\("status"\)/);
});

test("coverage refreshes every 15 seconds while visible and cleans up after leaving status", () => {
  const status = read("MemoryStatus.tsx");
  const coverageEffect = status.match(/useEffect\(\(\) => \{([\s\S]*?)\n  \}, \[refresh\]\);/)?.[1];
  assert.ok(coverageEffect, "coverage refresh effect exists");
  assert.match(coverageEffect, /document\.visibilityState !== "visible"/);
  assert.match(coverageEffect, /setInterval\([^\n]*15000\)/);
  assert.match(coverageEffect, /clearInterval\(interval\)/);
  assert.match(coverageEffect, /removeEventListener\("visibilitychange"/);
  assert.match(coverageEffect, /if \(active\)/);
  assert.doesNotMatch(coverageEffect, /setTimeline\(/, "polling must preserve the current timeline page");
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
