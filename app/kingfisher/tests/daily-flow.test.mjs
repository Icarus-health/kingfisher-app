import assert from 'node:assert/strict';
import { test } from 'node:test';
import { sourceStatus, activityAction, createDailyRefresh, dailyIntroduction } from '../src/dailyFlow.ts';

const briefing = {generated_at: '2026-10-07T10:00:00+02:00', timezone: 'Europe/Berlin', partial_failures: [], post_ausstehend: false};

test('an empty day with missing sources never claims nothing needs preparing', () => {
  assert.equal(dailyIntroduction('Heute liegt nichts an.', false, true), 'Dein Tag ist noch nicht vollständig erfasst.');
  assert.equal(dailyIntroduction('Ein Termin steht an.', true, true), 'Ein Termin steht an.');
});

test('unconnected calendar is visible and never presented as an empty successful agenda', () => {
  const status = sourceStatus({...briefing, partial_failures: [{section: 'calendar', message: 'Kalender ist nicht verbunden.'}]});
  assert.equal(status.attention, true);
  assert.match(status.text, /Kalender ist nicht verbunden/);
  assert.equal(status.href, '/settings#zugaenge');
});

test('pending mail remains an explicit incomplete overview', () => {
  const status = sourceStatus({...briefing, post_ausstehend: true});
  assert.match(status.text, /Posteingang wird/);
  assert.equal(status.attention, true);
});

test('incomplete mail-thread review directs the user to tasks, not connection setup', () => {
  const status = sourceStatus({...briefing, partial_failures: [{section: 'source_review', message: 'Einige Mailverläufe konnten nicht vollständig geprüft werden.'}]});
  assert.equal(status.attention, true);
  assert.match(status.text, /nicht vollständig geprüft/);
  assert.equal(status.href, '/vorhaben?view=mine');
  assert.equal(status.actionLabel, 'Aufgaben prüfen');
});

test('a concurrent connection failure keeps its setup action and extra review hints stay neutral', () => {
  const status = sourceStatus({...briefing, partial_failures: [
    {section: 'calendar', message: 'Kalender fehlt.'},
    {section: 'mail', message: 'Post fehlt.'},
    {section: 'source_review', message: 'Verlauf ungeprüft.'},
  ]});
  assert.equal(status.href, '/settings#zugaenge');
  assert.equal(status.actionLabel, 'Quellen prüfen');
  assert.match(status.text, /1 weitere Hinweise/);
  assert.doesNotMatch(status.text, /Bereiche nicht verfügbar/);
});

test('source success wording describes an overview, not verified source synchronization', () => {
  assert.equal(sourceStatus(briefing).text, 'Überblick erstellt · Quellen können sich danach geändert haben.');
});

test('mail activity goes straight to its exact mail while raw source remains separately addressable', () => {
  assert.deepEqual(activityAction({source: 'mail', source_ref: 'work:1/42'}), {uid: 'work:1/42', label: 'Nachricht öffnen'});
  assert.equal(activityAction({source: 'mail', source_ref: null}), null);
  assert.equal(activityAction({source: 'working_memory', source_ref: 'episode-42'}), null);
});

test('refresh coalesces concurrent requests, throttles automatic refresh, and allows explicit retry', async () => {
  let clock = 100000; let calls = 0; let resolve; const results = [];
  const refresh = createDailyRefresh(() => { calls++; return new Promise(r => {resolve = r;}); }, value => results.push(value), () => clock);
  const first = refresh.run();
  await refresh.run();
  assert.equal(calls, 1);
  resolve('first'); await first;
  await refresh.run(); assert.equal(calls, 1);
  const manual = refresh.run(true); assert.equal(calls, 2);
  resolve('manual'); await manual;
  clock += 60000;
  const later = refresh.run(); assert.equal(calls, 3);
  refresh.dispose(); resolve('late'); await later;
  assert.deepEqual(results, ['first', 'manual']);
});

test('failed refresh reports failure and can be explicitly retried without losing previous value', async () => {
  const results = []; let fail = false;
  const refresh = createDailyRefresh(async () => {if (fail) throw Error('offline'); return 'existing';}, value => results.push(value));
  assert.equal(await refresh.run(true), 'updated');
  fail = true;
  assert.equal(await refresh.run(true), 'failed');
  assert.deepEqual(results, ['existing']);
  fail = false;
  assert.equal(await refresh.run(true), 'updated');
});

test('an explicit change during an old request queues one fresh snapshot afterwards', async () => {
  const resolvers = []; const values = [];
  const refresh = createDailyRefresh(() => new Promise(resolve => resolvers.push(resolve)), value => values.push(value));
  const beforeChange = refresh.run();
  void refresh.run(true);
  void refresh.run(true);
  resolvers[0]('before change');
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(resolvers.length, 2);
  resolvers[1]('after change');
  await beforeChange;
  assert.equal(values.at(-1), 'after change');
});
