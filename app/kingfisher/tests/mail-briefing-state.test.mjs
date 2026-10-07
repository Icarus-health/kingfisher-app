import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mailBriefingFailure } from '../src/mailBriefingState.ts';

test('a busy local model gives a wait-and-retry explanation', () => {
  const text = mailBriefingFailure(429);
  assert.match(text, /läuft noch/);
  assert.match(text, /warten.*erneut/);
  assert.match(text, /Original/);
});

test('other failures do not pretend a model is busy or expose server details', () => {
  for (const status of [undefined, 401, 500, 503]) {
    assert.equal(mailBriefingFailure(status), 'Die Auszüge konnten gerade nicht ausgewählt werden.');
  }
});
