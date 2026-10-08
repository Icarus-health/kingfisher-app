import assert from "node:assert/strict";
import {test} from "node:test";
import {questionRelationLabel, questionTitle} from "../src/questionLabels.ts";

test("known relation names use ordinary language without resolving the subject", () => {
  assert.equal(questionRelationLabel("observed_email"), "E-Mail-Adresse");
  assert.equal(questionRelationLabel("works_on"), "Mitarbeit an einem Vorhaben");
  assert.equal(questionRelationLabel("deadline"), "Frist");
});

test("unknown relations use a neutral fallback and never expose an opaque identifier", () => {
  assert.equal(questionRelationLabel("person:anna:budget_27"), "Angabe");
  assert.equal(questionTitle("  " ), "Mögliche Angabe prüfen");
  assert.equal(questionTitle("Bisherige Aussage aus dem Original"), "Bisherige Aussage aus dem Original");
});

test('untrusted relation names cannot resolve inherited Object members', () => {
  for (const name of ['constructor', '__proto__', 'toString']) assert.equal(questionRelationLabel(name), 'Angabe');
});
