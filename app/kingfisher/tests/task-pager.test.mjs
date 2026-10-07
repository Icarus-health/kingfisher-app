import assert from 'node:assert/strict';
import {test} from 'node:test';
import {TaskPager} from '../src/taskPager.ts';

const selection = {view: 'mine', projectId: '', q: ''};
const page = (id, next_cursor = null) => ({tasks: [{id}], total: 2, next_cursor});

test('next/back preserve selection and search; refresh starts a fresh complete list', async () => {
  const calls = [], states = [];
  const pager = new TaskPager(async (s, cursor) => {calls.push([s, cursor]); return cursor ? page('second') : page('first', 'next');}, state => states.push(state));
  await pager.select({...selection, projectId: 'p', q: 'Änderung'});
  await pager.next();
  assert.equal(states.at(-1).tasks[0].id, 'second');
  assert.equal(states.at(-1).canPrevious, true);
  await pager.previous();
  assert.equal(states.at(-1).tasks[0].id, 'first');
  await pager.refresh();
  assert.deepEqual(calls.map(call => call[1]), [null, 'next', null, null]);
  assert.ok(calls.every(([s]) => s.q === 'Änderung' && s.projectId === 'p'));
});

test('late responses cannot overwrite a newer view or a disposed screen', async () => {
  const pending = [], states = [];
  const pager = new TaskPager((s, cursor) => new Promise(resolve => pending.push(resolve)), state => states.push(state));
  const old = pager.select(selection);
  const latest = pager.select({...selection, view: 'waiting'});
  pending[1](page('new')); await latest;
  pending[0](page('old')); await old;
  assert.equal(states.at(-1).tasks[0].id, 'new');
  const stopped = pager.refresh();
  const count = states.length;
  pager.cancel(); pending[2](page('unmounted')); await stopped;
  assert.equal(states.length, count);
});

test('a changed snapshot recovers at the first page with a visible notice', async () => {
  let calls = 0;
  const states = [];
  const pager = new TaskPager(async (_, cursor) => {
    calls++;
    if (cursor) throw Object.assign(new Error(), {status: 409});
    return page(calls === 1 ? 'before' : 'after', 'next');
  }, state => states.push(state));
  await pager.select(selection); await pager.next();
  assert.equal(states.at(-1).tasks[0].id, 'after');
  assert.match(states.at(-1).notice, /geändert/);
  assert.equal(states.at(-1).canPrevious, false);
});

test('failed loads clear the old list and block navigation until a fresh result', async () => {
  let fail = false; const states = [];
  const pager = new TaskPager(async () => {if (fail) throw new Error('offline'); return page('first', 'next');}, state => states.push(state));
  await pager.select(selection); fail = true; await pager.next();
  assert.equal(states.at(-1).tasks, null);
  assert.match(states.at(-1).error, /erreichbar/);
  const count = states.length; await pager.next();
  assert.equal(states.length, count);
});
