import assert from "node:assert/strict";
import { test } from "node:test";
import { newestSourceMonth, timelineDateValues } from "../src/memoryStatusDates.ts";

process.env.TZ = "Europe/Berlin";

test("the newest source month follows the local month of the latest source date", () => {
  assert.equal(newestSourceMonth("2026-09-30T23:30:00Z"), "2026-10");
});

test("a missing latest source date has no jump target", () => {
  assert.equal(newestSourceMonth(null), null);
  assert.equal(newestSourceMonth("not-a-date"), null);
});

test("source history leads with source time and keeps capture time separate", () => {
  const item = {occurred_at: "2026-09-22T10:00:00Z", recorded_at: "2026-10-01T08:00:00Z"};
  assert.deepEqual(timelineDateValues(item, "source"), {main: item.occurred_at, secondary: item.recorded_at});
  assert.deepEqual(timelineDateValues(item, "recorded"), {main: item.recorded_at, secondary: item.occurred_at});
});

test("unknown source dates remain unknown in source history", () => {
  assert.deepEqual(timelineDateValues({occurred_at: null, recorded_at: "2026-10-01T08:00:00Z"}, "source"),
    {main: null, secondary: "2026-10-01T08:00:00Z"});
});
