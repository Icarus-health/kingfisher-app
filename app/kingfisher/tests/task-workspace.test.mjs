import assert from 'node:assert/strict';
import {test} from 'node:test';
import {groupTasks, projectColumns} from '../src/taskWorkspaceModel.ts';

test('deadlines group by actual local day, without turning unknown dates into overdue tasks', () => {
  const now = new Date('2026-10-14T12:00:00');
  const tasks = [{id:'old', due:'2026-10-13T23:59:00'}, {id:'today',due:'2026-10-14T23:59:00'},
    {id:'next',due:'2026-10-15T08:00:00'}, {id:'none',due:null}, {id:'invalid',due:'bad'}];
  const groups = groupTasks(tasks, now);
  assert.deepEqual(groups.map(group => group.items.map(t => t.id)), [['old'],['today'],['next'],['none','invalid']]);
  assert.equal(new Set(groups.flatMap(group => group.items.map(t => t.id))).size, tasks.length);
});

test('list and board share task identities and explicit waiting status', () => {
  const tasks = [{id:'mine',status:'open'}, {id:'wait',status:'open',wartet_auf:'Alex'}, {id:'done',status:'done'}, {id:'drop',status:'dropped'}];
  const columns = projectColumns(tasks);
  assert.deepEqual(columns.map(col=>col.items.map(t=>t.id)), [['mine'],['wait'],['done']]);
  assert.equal(columns[1].items[0], tasks[1]);
});
