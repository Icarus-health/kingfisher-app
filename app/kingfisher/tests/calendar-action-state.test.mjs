import assert from 'node:assert/strict';
import {test} from 'node:test';
import {execFileSync} from 'node:child_process';
import {localDateTime, calendarActionState, editableEventId} from '../src/calendarActionState.ts';

test('only a prepared draft can be executed; an unknown result requires checking', () => {
  assert.equal(calendarActionState('draft').canExecute, true);
  for (const status of ['running', 'uncertain', 'done', 'failed', 'unexpected']) {
    assert.equal(calendarActionState(status).canExecute, false);
  }
  assert.match(calendarActionState('uncertain').message, /Google.*prüfen/);
  assert.match(calendarActionState('done').message, /bestätigt/);
});

test('datetime inputs preserve the device-local instant and reject all-day/invalid values', () => {
  const value = localDateTime('2026-10-25T10:45:00Z');
  assert.equal(new Date(value).getTime(), new Date('2026-10-25T10:45:00Z').getTime());
  assert.equal(localDateTime('2026-10-25'), '');
  assert.equal(localDateTime('bad'), '');
});

test('provider IDs are extracted only from the exact named source namespace', () => {
  assert.equal(editableEventId({uid:'source:event:tail', source_id:'source'}), 'event:tail');
  assert.equal(editableEventId({uid:'other:event', source_id:'source'}), null);
  assert.equal(editableEventId({uid:'source:', source_id:'source'}), null);
  assert.equal(editableEventId({uid:'unscoped'}), null);
});

test('editing a title preserves an unchanged original instant including seconds and DST offset', async () => {
  const {calendarInputInstant} = await import('../src/calendarActionState.ts');
  const original = '2026-10-25T02:30:17+01:00';
  assert.equal(calendarInputInstant(localDateTime(original), original), original);
  assert.throws(() => calendarInputInstant('not a date'), /Zeit/);
});


test('new ambiguous or nonexistent local times are rejected instead of silently shifted', () => {
  const moduleUrl = new URL('../src/calendarActionState.ts', import.meta.url).href;
  const script = `import assert from 'node:assert/strict'; import {calendarInputInstant} from ${JSON.stringify(moduleUrl)};
    assert.throws(() => calendarInputInstant('2026-10-25T02:30'), /zweimal/);
    assert.throws(() => calendarInputInstant('2026-03-29T02:30'), /Zeitumstellung/);
    assert.equal(calendarInputInstant('2026-10-25T03:30'), '2026-10-25T02:30:00.000Z');`;
  execFileSync(process.execPath, ['--experimental-strip-types', '--input-type=module', '-e', script], {env:{...process.env, TZ:'Europe/Berlin'}});
});
