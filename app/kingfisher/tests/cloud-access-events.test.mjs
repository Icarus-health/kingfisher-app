import assert from "node:assert/strict";
import {test} from "node:test";
import {announceCloudAccessChange, listenForCloudAccessChange} from "../src/cloudAccessEvents.ts";

test("cloud access change notifies mounted settings listeners and unsubscribe detaches them", () => {
  const target = new EventTarget();
  let count = 0;
  const unsubscribe = listenForCloudAccessChange(() => count++, target);
  announceCloudAccessChange(target);
  assert.equal(count, 1);
  unsubscribe();
  announceCloudAccessChange(target);
  assert.equal(count, 1);
});
