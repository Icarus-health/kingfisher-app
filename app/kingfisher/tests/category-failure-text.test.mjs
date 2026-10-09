import {test} from "node:test";
import assert from "node:assert/strict";
import {categoryFailureText} from "../src/categoryFailureText.ts";

test("failure codes map to static safe labels and unknown values use generic wording", () => {
  assert.equal(categoryFailureText("provider_error"), "Die Themenauswertung beim Modellanbieter konnte nicht abgeschlossen werden.");
  assert.equal(categoryFailureText("validation_category_evidence"), "Themenvorschläge ließen sich nicht mit der Quelle belegen.");
  assert.equal(categoryFailureText(null), "Automatische Zuordnung fehlgeschlagen; Ursache unbekannt.");
  assert.equal(categoryFailureText("untrusted-private-error"), "Automatische Zuordnung fehlgeschlagen; Ursache unbekannt.");
  assert.equal(categoryFailureText("__proto__"), "Automatische Zuordnung fehlgeschlagen; Ursache unbekannt.");
});
