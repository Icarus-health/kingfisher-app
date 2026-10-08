import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const component = readFileSync(new URL("../src/CalendarPreparation.tsx", import.meta.url), "utf8");

test("calendar preparation renders historical evidence with an unresolved-time caption", () => {
  assert.match(component, /historical:\s*"Zeitbezug ungeklärt"/);
  assert.match(component, /source\.working_kinds\.map\(kind\s*=>\s*WORKING_KIND_LABELS\[kind\]\)/);
  assert.doesNotMatch(component, /historical:\s*"Frühere Aussage"/);
});
