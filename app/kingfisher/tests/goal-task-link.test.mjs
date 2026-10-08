import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';

const goals = readFileSync(new URL('../src/GoalControls.tsx', import.meta.url), 'utf8');
const detail = readFileSync(new URL('../src/TaskDetail.tsx', import.meta.url), 'utf8');
const api = readFileSync(new URL('../src/api.ts', import.meta.url), 'utf8');

test('each open goal offers explicit next-step creation with a structured goal link', () => {
  assert.match(goals, /Nächsten Schritt festhalten/);
  assert.match(goals, /api\.addTask\(\{\s*title:[^}]*goal_id:\s*nextStepGoal\.id/s);
  assert.match(goals, /Aufgabe öffnen/);
});

test('task detail resolves and displays the linked goal after its lifecycle changes', () => {
  assert.match(api, /goal_id\?: string \| null/);
  assert.match(api, /addTask: \(data: \{[^}]*goal_id\?: string \| null/s);
  assert.match(detail, /api\.goalHistory\(task\.goal_id\)/);
  assert.match(detail, /Zielbezug/);
});
