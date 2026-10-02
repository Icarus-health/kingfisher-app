import {test} from "node:test";
import assert from "node:assert/strict";
import {nichtMehrZuordenbar} from "../src/personMergeLost.ts";

const graph = (attributes) => ({nodes: [{id: "merge-1", kind: "person", label: "Anna", attributes}], edges: []});

test("Nicht mehr zuordenbare Mitglieder einer Zusammenführung werden genannt", () => {
  const lost = nichtMehrZuordenbar(graph({unassigned_members: [{id: "p1", label: "A. Beispiel", reason: "Nicht mehr zuordenbar"}, {id: "p2"}]}), "merge-1");
  assert.deepEqual(lost, [{id: "p1", label: "A. Beispiel"}, {id: "p2", label: "Unbekannte Person"}]);
});

test("Ohne solche Mitglieder oder bei unbekannter Zusammenführung bleibt die Liste leer", () => {
  assert.deepEqual(nichtMehrZuordenbar(graph({unassigned_members: []}), "merge-1"), []);
  assert.deepEqual(nichtMehrZuordenbar(graph({}), "merge-1"), []);
  assert.deepEqual(nichtMehrZuordenbar(graph({unassigned_members: "kaputt"}), "merge-1"), []);
  assert.deepEqual(nichtMehrZuordenbar(graph({unassigned_members: [null, 3, {label: "x"}]}), "merge-1"), []);
  assert.deepEqual(nichtMehrZuordenbar(graph({unassigned_members: [{id: "p1"}]}), "andere"), []);
});
