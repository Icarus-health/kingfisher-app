import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";

const component = readFileSync(new URL("../src/TaskSuggestions.tsx", import.meta.url), "utf8");
const api = readFileSync(new URL("../src/api.ts", import.meta.url), "utf8");

test("task review uses bounded pages and offers all, recent, and review filters", () => {
  assert.match(component, /api\.taskCandidatePage\(/);
  assert.match(component, /value="all"/);
  assert.match(component, /value="recent"/);
  assert.match(component, /value="review"/);
  assert.match(component, /Vorherige/);
  assert.match(component, /Weitere/);
  assert.match(component, /visiblePage\.total/);
  assert.match(api, /taskCandidatePage: \(limit: number, offset: number, temporal: "all" \| "recent" \| "review", generation\?: string\)/);
});

test("task review keeps per-candidate edits when navigating and clamps after removals", () => {
  assert.match(component, /drafts/);
  assert.match(component, /setDrafts/);
  assert.match(component, /result\.items\.length === 0/);
  assert.match(component, /Math\.floor\(\(result\.total - 1\) \/ PAGE_SIZE\)/);
});

test("task review hides a page while loading or when its offset/filter is stale", async () => {
  const { isVisibleTaskPage } = await import("../src/taskSuggestionsView.ts");
  const page = {offset: 25, temporal: "recent"};
  assert.equal(isVisibleTaskPage(page, 25, "recent", false, false), true);
  assert.equal(isVisibleTaskPage(page, 25, "recent", true, false), false);
  assert.equal(isVisibleTaskPage(page, 0, "recent", false, false), false);
  assert.equal(isVisibleTaskPage(page, 25, "review", false, false), false);
  assert.equal(isVisibleTaskPage(page, 25, "recent", false, true), false);
});

test("only later task pages send their filter generation", async () => {
  const { generationForTaskPage } = await import("../src/taskSuggestionsView.ts");
  assert.equal(generationForTaskPage(0, "current-generation"), undefined);
  assert.equal(generationForTaskPage(25, "current-generation"), "current-generation");
  assert.equal(generationForTaskPage(25, undefined), undefined);
});

test("pagination carries a generation token and handles stale queues without retry loops", () => {
  assert.match(component, /generationForTaskPage/);
  assert.match(component, /Die Prüfliste hat sich geändert/);
  assert.match(component, /setOffset\(0\)/);
  assert.match(api, /generation\?: string/);
  assert.match(api, /generation/);
});
