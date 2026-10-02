import {test} from "node:test";
import assert from "node:assert/strict";
import {watchGoogleSignIn, GOOGLE_SIGN_IN_LIMIT_MS} from "../src/googleSignInProgress.ts";

const settle = async () => { await Promise.resolve(); await Promise.resolve(); };
function setup(t, read) {
  t.mock.timers.enable({apis:["setTimeout"]});
  const sessions = [], errors = [], timeouts = [];
  const watcher = watchGoogleSignIn({read, onSession:s => sessions.push(s.status),
    onError:() => errors.push(true), onTimeout:() => timeouts.push(true)});
  t.after(() => watcher.stop());
  return {watcher, sessions, errors, timeouts};
}

test("waiting and processing automatically advance to ready, then stop", async t => {
  const states = ["waiting", "processing", "ready"];
  let calls = 0;
  const {watcher, sessions} = setup(t, async () => ({status:states[calls++]}));
  await settle();
  t.mock.timers.tick(2500); await settle();
  t.mock.timers.tick(2500); await settle();
  assert.deepEqual(sessions, states);
  await watcher.refresh(); t.mock.timers.tick(GOOGLE_SIGN_IN_LIMIT_MS); await settle();
  assert.equal(calls, 3);
});

for (const status of ["expired", "failed", "connected"]) {
  test(`${status} stops polling and the deadline`, async t => {
    let calls = 0;
    const {watcher, sessions, timeouts} = setup(t, async () => {calls++; return {status};});
    await settle(); await watcher.refresh();
    t.mock.timers.tick(GOOGLE_SIGN_IN_LIMIT_MS); await settle();
    assert.deepEqual(sessions, [status]); assert.equal(calls, 1); assert.equal(timeouts.length, 0);
  });
}

test("manual and focus refresh cannot overlap a pending request", async t => {
  let resolve, calls = 0;
  const {watcher, sessions} = setup(t, () => {calls++; return new Promise(r => {resolve = r;});});
  await watcher.refresh(); await watcher.refresh();
  t.mock.timers.tick(10000); await settle();
  assert.equal(calls, 1);
  resolve({status:"waiting"}); await settle();
  assert.deepEqual(sessions, ["waiting"]);
  void watcher.refresh(); assert.equal(calls, 2);
  resolve({status:"ready"}); await settle();
});

test("temporary errors retry and do not erase a successful account", async t => {
  let calls = 0;
  const {sessions, errors} = setup(t, async () => {
    if (++calls === 1) throw new Error("offline");
    return {status:"ready", email:"synthetic@example.com"};
  });
  await settle(); assert.equal(errors.length, 1); assert.deepEqual(sessions, []);
  t.mock.timers.tick(2500); await settle();
  assert.deepEqual(sessions, ["ready"]);
  t.mock.timers.tick(10000); await settle(); assert.equal(calls, 2);
});

test("ten-minute limit stops a hung request and ignores its late response", async t => {
  let resolve;
  const {sessions, timeouts} = setup(t, () => new Promise(r => {resolve = r;}));
  t.mock.timers.tick(GOOGLE_SIGN_IN_LIMIT_MS); await settle();
  assert.equal(timeouts.length, 1);
  resolve({status:"ready"}); await settle(); assert.deepEqual(sessions, []);
});

test("cleanup ignores a previous flow response and cancels timers", async t => {
  let resolve;
  const {watcher, sessions, timeouts, errors} = setup(t, () => new Promise(r => {resolve = r;}));
  watcher.stop(); resolve({status:"ready"}); await settle();
  t.mock.timers.tick(GOOGLE_SIGN_IN_LIMIT_MS); await settle();
  assert.deepEqual(sessions, []); assert.deepEqual(errors, []); assert.deepEqual(timeouts, []);
});
