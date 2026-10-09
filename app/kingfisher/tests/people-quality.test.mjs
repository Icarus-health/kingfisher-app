import test from "node:test";
import assert from "node:assert/strict";
import { personNodes, quality } from "../src/peopleQuality.ts";

const node = (id, attributes = {}, kind = "person") => ({ id, kind, label: id, attributes });
const graph = (...nodes) => ({ nodes, edges: [] });
const ids = (g, filter) => personNodes(g, filter).map(n => n.id);

test("Bekannte Kategorien bleiben getrennt; alle erhält jede Personenakte", () => {
  const g = graph(node("human", {quality_category: "person"}), node("service", {quality_category: "review"}),
    node("robot", {quality_category: "automated"}), node("project", {}, "project"));
  assert.deepEqual(ids(g, "people"), ["human"]);
  assert.deepEqual(ids(g, "review"), ["service"]);
  assert.deepEqual(ids(g, "automated"), ["robot"]);
  assert.deepEqual(ids(g, "all"), ["human", "service", "robot"]);
});

test("Fehlende oder unbekannte Kennzeichnung braucht Prüfung statt Personenbehauptung", () => {
  const g = graph(node("missing"), node("unknown", {quality_category: "future-category"}),
    node("malformed", {quality_category: 7}), node("empty", {quality_category: ""}));
  assert.deepEqual(ids(g, "people"), []);
  assert.deepEqual(ids(g, "review"), ["missing", "unknown", "malformed", "empty"]);
  assert.equal(quality(g.nodes[0]), "review");
  assert.deepEqual(ids(g, "all"), ["missing", "unknown", "malformed", "empty"]);
});

test("Ausdrücklich bestätigte Identitäten bleiben auch ohne neue Kennzeichnung sichtbar", () => {
  const g = graph(node("registered", {identity_resolution: "explicit_registry"}),
    node("confirmed", {identity_resolution: "confirmed_group"}));
  assert.deepEqual(ids(g, "people"), ["registered", "confirmed"]);
  assert.deepEqual(ids(g, "review"), ["confirmed"]);
});

test("Vorhandene Prüfkennzeichnung und Duplikathinweise werden nicht überschrieben", () => {
  const g = graph(node("test", {identity_resolution: "explicit_registry", quality_category: "review"}),
    node("candidate", {quality_category: "person", duplicate_ids: [null, 9, "other"]}));
  const before = JSON.stringify(g);
  assert.deepEqual(ids(g, "people"), ["candidate"]);
  assert.deepEqual(ids(g, "review"), ["test", "candidate"]);
  assert.equal(JSON.stringify(g), before);
});
