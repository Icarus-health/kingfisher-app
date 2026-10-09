import test from "node:test";
import assert from "node:assert/strict";
import { loadContactProfile } from "../src/contactSources.ts";

const notFound = {status: 404};
const contact = (attributes = {quality_category: "automated"}) => ({id: "person:stable", kind: "person", label: "System <do_not_reply@example.org>", attributes});
const source = (id = "episode:one", state = "new") => ({id, kind: "episode", label: "Original", attributes: {state}});
const edge = (target = "episode:one", patch = {}) => ({source: "person:stable", target, relation: "participated_in", state: "observed", evidence_refs: [target], ...patch});
const graph = (node = contact()) => ({nodes: [node, source()], edges: [edge()]});
const read = (g, nodeId = "person:stable", cause = notFound) => loadContactProfile(contact().label, nodeId,
  async () => {throw cause;}, async () => g, error => error === notFound);

for (const category of ["automated", "review"]) test(`${category}: Originalquellen statt unerreichbarem Personenprofil`, async () => {
  const g = graph(contact({quality_category: category}));
  const before = JSON.stringify(g);
  const result = await read(g);
  assert.equal(result.kind, "sources");
  assert.equal(result.view.node.id, "person:stable");
  assert.deepEqual(result.view.sources.map(n => n.id), ["episode:one"]);
  assert.equal(JSON.stringify(g), before);
});

test("Erreichbares Personenprofil lädt keinen Ersatzgraphen", async () => {
  const profile = {id: "human"}; let calls = 0;
  const result = await loadContactProfile("Human", null, async () => profile, async () => {calls++;}, () => true);
  assert.deepEqual(result, {kind: "person", profile}); assert.equal(calls, 0);
});

test("Berechtigung, Mehrdeutigkeit und Serverfehler werden nicht kaschiert", async () => {
  for (const status of [401, 403, 409, 500, 503]) {
    const cause = {status}; let calls = 0;
    await assert.rejects(loadContactProfile(contact().label, "person:stable", async () => {throw cause;}, async () => {calls++; return graph();}, e => e === notFound), e => e === cause);
    assert.equal(calls, 0);
  }
});

test("Keine Ersatzzuordnung ohne gleiche Kennung und eindeutigen Namen", async () => {
  for (const id of [null, "person:other"]) await assert.rejects(read(graph(), id), e => e === notFound);
  const duplicate = graph(); duplicate.nodes.push({...contact(), id: "person:other"});
  await assert.rejects(read(duplicate), e => e === notFound);
  const changed = graph(); changed.nodes[0].label = "Other";
  await assert.rejects(read(changed), e => e === notFound);
});

test("Bestätigte Identitäten und unbekannte Qualitätswerte haben keinen Service-Ersatz", async () => {
  for (const attributes of [{quality_category: "person"}, {}, {quality_category: "future"},
    {quality_category: "review", identity_resolution: "explicit_registry"},
    {quality_category: "automated", identity_resolution: "confirmed_group"}])
    await assert.rejects(read(graph(contact(attributes))), e => e === notFound);
});

test("Nur aktuelle, genau belegte ausgehende Quellenbezüge; keine fremden oder widerrufenen Quellen", async () => {
  const g = graph();
  g.nodes.push(source("episode:ignored", "ignored"), source("episode:unlinked"), source("episode:wrong-ref"));
  g.edges.push(edge(), edge("episode:ignored"), edge("episode:missing"),
    edge("episode:unlinked", {source: "person:other"}), edge("episode:unlinked", {relation: "works_for"}),
    edge("episode:wrong-ref", {evidence_refs: ["episode:other"]}), edge("episode:unlinked", {state: "retracted"}));
  const result = await read(g);
  assert.deepEqual(result.view.sources.map(n => n.id), ["episode:one"]);
});

test("Ohne gültige Quellen bleibt die Seite unerreichbar", async () => {
  const g = graph(); g.edges = [];
  await assert.rejects(read(g), e => e === notFound);
});
