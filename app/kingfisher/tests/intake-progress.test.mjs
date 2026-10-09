import {test} from "node:test";
import assert from "node:assert/strict";
import {deriveIntakeProgress, watchMailIntake} from "../src/mailIntakeProgress.ts";

const folder = (overrides = {}) => ({folder: "INBOX", inventory_complete: true, total: 10,
  captured: 4, duplicates: 1, failed: 0, pending: 5, live_pending: 0, analyzed: 2,
  deferred: 0, excluded: 0, categorized: 2, categories_pending: 3, categories_failed: 0, ...overrides});
const account = (overrides = {}) => ({account_id: "mail-1", label: "Privat", connected: true,
  started: true, paused: false, folders: [folder()], step: "capture", error: null,
  scope: "inbox", ...overrides});
const settle = async () => {for (let i = 0; i < 8; i++) await Promise.resolve();};

test("incomplete inventory keeps all percentages unknown even when enumerated counts exist", () => {
  const progress = deriveIntakeProgress(account({folders: [folder({inventory_complete: false})]}));
  assert.equal(progress.total, null);
  assert.equal(progress.counted, 10);
  assert.equal(progress.capturePercent, null);
  assert.equal(progress.analysisPercent, null);
  assert.equal(progress.overallPercent, null);
  assert.equal(progress.stage, "inventory");
});

test("unique folder work counts known sources separately from newly captured sources", () => {
  const progress = deriveIntakeProgress(account());
  assert.equal(progress.total, 10);
  assert.equal(progress.captured, 4);
  assert.equal(progress.duplicates, 1);
  assert.equal(progress.processed, 5);
  assert.equal(progress.capturePercent, 50);
  assert.equal(progress.analysisPercent, 40);
  assert.equal(progress.complete, false);
});

test("category deferred and failure reasons remain distinct across folders", () => {
  const progress = deriveIntakeProgress(account({folders: [
    folder({categories_deferred: 2, categories_failed: 3, categories_failed_by: {provider_error: 2, internal_error: 1}}),
    folder({folder: "Archive", categories_deferred: 1, categories_failed: 1, categories_failed_by: {provider_error: 1}}),
  ]}));
  assert.equal(progress.categoriesDeferred, 3);
  assert.equal(progress.categoriesFailed, 4);
  assert.deepEqual(progress.categoriesFailedBy, {provider_error: 3, internal_error: 1});
});

test("captured and duplicate source counts are summed across folders", () => {
  const progress = deriveIntakeProgress(account({folders: [folder(), folder({folder: "Archive", total: 20, captured: 7, duplicates: 2, pending: 11, analyzed: 3})]}));
  assert.equal(progress.total, 30);
  assert.equal(progress.captured, 11);
  assert.equal(progress.duplicates, 3);
  assert.equal(progress.analyzed, 5);
  assert.equal(progress.processed, 14);
});

for (const unfinished of [{pending: 1}, {live_pending: 1}, {failed: 1}, {deferred: 1}, {analyzed: 9}, {categories_pending: 1}, {categories_failed: 1}, {categorized: 9}]) {
  test(`unfinished ${Object.keys(unfinished)[0]} never reports overall completion`, () => {
    const progress = deriveIntakeProgress(account({folders: [folder({captured: 10, duplicates: 0, pending: 0, analyzed: 10, categorized: 10, categories_pending: 0, ...unfinished})]}));
    assert.equal(progress.complete, false);
    assert.ok(progress.overallPercent < 100);
  });
}

test("deferred categories cannot be hidden by contradictory completed counters", () => {
  const progress = deriveIntakeProgress(account({folders: [folder({total: 1, captured: 1, duplicates: 0,
    pending: 0, analyzed: 1, categorized: 1, categories_pending: 0, categories_deferred: 1})]}));
  assert.equal(progress.complete, false);
  assert.equal(progress.stage, "analysis");
  assert.ok(progress.overallPercent < 100);
});

test("unverified category status keeps explicit retry available while mailbox is paused", () => {
  const progress = deriveIntakeProgress(account({folders: [folder({total: 1, captured: 1, duplicates: 0,
    pending: 0, analyzed: 1, categorized: 1, categories_pending: 0, categories_unverified: 2})], paused: true}));
  assert.equal(progress.categoriesUnverified, 2);
  assert.equal(progress.retryAvailable, true);
  assert.equal(progress.complete, false);
  assert.equal(progress.stage, "paused");
  assert.ok(progress.overallPercent < 100);
});

test("paused and error states preserve real counters without implying completion", () => {
  const paused = deriveIntakeProgress(account({paused: true}));
  assert.equal(paused.stage, "paused");
  assert.equal(paused.captured, 4);
  const error = deriveIntakeProgress(account({error: "unavailable", folders: [folder({captured: 10, duplicates: 0, pending: 0, analyzed: 10, categorized: 10, categories_pending: 0})]}));
  assert.equal(error.stage, "error");
  assert.equal(error.complete, false);
  assert.ok(error.overallPercent < 100);
});

test("an empty inventory can complete without invented analysis percentage", () => {
  const progress = deriveIntakeProgress(account({folders: [folder({total: 0, captured: 0, duplicates: 0, pending: 0, analyzed: 0, categorized: 0, categories_pending: 0})]}));
  assert.equal(progress.total, 0);
  assert.equal(progress.complete, true);
  assert.equal(progress.analysisPercent, null);
});

test("unknown categories cannot imply fully interpreted sources", () => {
  const progress = deriveIntakeProgress(account({folders: [folder({captured: 10, duplicates: 0, pending: 0, analyzed: 10, categorized: undefined})]}));
  assert.equal(progress.complete, false);
  assert.equal(progress.analysisPercent, null);
  assert.ok(progress.overallPercent < 100);
});

test("excluded sources overlap capture counts and do not double-count finished work", () => {
  const progress = deriveIntakeProgress(account({folders: [folder({captured: 10, duplicates: 0, pending: 0, analyzed: 8, categorized: 8, categories_pending: 0, excluded: 2})]}));
  assert.equal(progress.processed, 10);
  assert.equal(progress.analysisSources, 8);
  assert.equal(progress.complete, true);
});

test("preview requests share the queue without replacing status", async t => {
  const {watcher, values} = watcherSetup(t, async () => ({accounts: []}));
  await settle();
  const preview = await watcher.inspect(async () => ({folders: ["INBOX"], description: "Nur INBOX"}));
  assert.equal(preview.description, "Nur INBOX");
  assert.deepEqual(values, [{accounts: []}]);
});

test("connection and explicit start remain distinct", () => {
  assert.equal(deriveIntakeProgress(account({started: false, folders: []})).stage, "ready");
  assert.equal(deriveIntakeProgress(account({connected: false})).stage, "disconnected");
});

function watcherSetup(t, read) {
  t.mock.timers.enable({apis: ["setTimeout"]});
  const values = [], errors = [];
  const watcher = watchMailIntake({read, onStatus: value => values.push(value), onError: kind => errors.push(kind)});
  t.after(() => watcher.stop());
  return {watcher, values, errors};
}

test("polling waits three seconds after completion and never overlaps", async t => {
  let resolve, calls = 0;
  const {watcher, values} = watcherSetup(t, () => {calls++; return new Promise(r => {resolve = r;});});
  await watcher.refresh();
  t.mock.timers.tick(12000); await settle();
  assert.equal(calls, 1);
  resolve({accounts: []}); await settle();
  assert.equal(values.length, 1);
  t.mock.timers.tick(2999); await settle(); assert.equal(calls, 1);
  t.mock.timers.tick(1); await settle(); assert.equal(calls, 2);
});

test("hiding aborts pending status and ignores stale results; showing resumes", async t => {
  let resolve, signal, calls = 0;
  const {watcher, values} = watcherSetup(t, nextSignal => {signal = nextSignal; calls++; return new Promise(r => {resolve = r;});});
  watcher.setVisible(false);
  assert.equal(signal.aborted, true);
  resolve({stale: true}); await settle();
  assert.deepEqual(values, []);
  t.mock.timers.tick(12000); await settle(); assert.equal(calls, 1);
  watcher.setVisible(true); assert.equal(calls, 2);
});

test("status errors preserve prior results and retry automatically", async t => {
  let calls = 0;
  const {values, errors} = watcherSetup(t, async () => {
    if (++calls === 2) throw new Error("offline");
    return {accounts: []};
  });
  await settle();
  t.mock.timers.tick(3000); await settle();
  assert.equal(values.length, 1); assert.deepEqual(errors, ["status"]);
  t.mock.timers.tick(3000); await settle(); assert.equal(values.length, 2);
});

test("mutations wait for an aborted read and cannot publish its old result", async t => {
  let resolveRead, readSignal, mutateCalls = 0;
  const {watcher, values} = watcherSetup(t, signal => {readSignal = signal; return new Promise(r => {resolveRead = r;});});
  const action = watcher.run(async () => {mutateCalls++; return {updated: true};});
  assert.equal(readSignal.aborted, true);
  assert.equal(mutateCalls, 0);
  resolveRead({stale: true}); await settle(); await action;
  assert.equal(mutateCalls, 1);
  assert.deepEqual(values, [{updated: true}]);
});

test("cleanup aborts a pending action and rejects late updates", async t => {
  const {watcher, values} = watcherSetup(t, async () => ({accounts: []}));
  await settle();
  let resolveAction, actionSignal;
  const pending = watcher.run(signal => {actionSignal = signal; return new Promise(r => {resolveAction = r;});});
  await settle(); watcher.stop();
  assert.equal(actionSignal.aborted, true);
  resolveAction({late: true}); await pending;
  assert.deepEqual(values, [{accounts: []}]);
});
