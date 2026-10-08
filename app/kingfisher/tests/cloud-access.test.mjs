import test from "node:test";
import assert from "node:assert/strict";
import { cloudAccessSaveBody } from "../src/cloudAccessForm.ts";

test("cloud access save omits an empty key so changing a model keeps the saved secret", () => {
  assert.deepEqual(cloudAccessSaveBody("   ", "  mistral-small  "), {model: "mistral-small"});
});

test("cloud access save only sends the key that was typed and permits an empty model", () => {
  assert.deepEqual(cloudAccessSaveBody(" key-from-form ", ""), {api_key: "key-from-form", model: ""});
});
