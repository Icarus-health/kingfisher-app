import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const akte = readFileSync(new URL("../src/AkteAbschnitte.tsx", import.meta.url), "utf8");

test("gemeinsame Quellen werden nicht als Beteiligte bezeichnet", () => {
  assert.match(akte, /<Teil titel="In gemeinsamen Quellen" kind="beteiligte">/);
  assert.match(akte, /\{b\.anzahl\} gemeinsame \{b\.anzahl === 1 \? "Quelle" : "Quellen"\}/);
});
