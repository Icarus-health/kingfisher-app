import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {localReminderInput, reminderInputToIso, tomorrowAtNine, reminderLabel, reminderEditChanges} from '../src/reminderDates.ts';

const row = readFileSync(new URL('../src/TaskRow.tsx', import.meta.url), 'utf8');
const history = readFileSync(new URL('../src/TaskHistory.tsx', import.meta.url), 'utf8');
const panel = readFileSync(new URL('../src/TaskReminders.tsx', import.meta.url), 'utf8');

test('datetime-local roundtrip keeps the local wall time and rejects invalid calendar or DST gap values', () => {
  const previous = process.env.TZ;
  process.env.TZ = 'Europe/Berlin';
  try {
    const value = reminderInputToIso('2026-10-25T02:30');
    assert.equal(localReminderInput(value), '2026-10-25T02:30');
    assert.throws(() => reminderInputToIso('2026-03-29T02:30'), /Uhrzeit/);
    assert.throws(() => reminderInputToIso('2026-02-30T09:00'), /Datum/);
    assert.equal(reminderInputToIso(''), null);
  } finally {if (previous === undefined) delete process.env.TZ; else process.env.TZ = previous;}
});

test('tomorrow at nine uses local calendar arithmetic across both DST changes', () => {
  const previous = process.env.TZ;
  process.env.TZ = 'Europe/Berlin';
  try {
    const spring = tomorrowAtNine(new Date('2026-03-28T12:00:00+01:00'));
    const autumn = tomorrowAtNine(new Date('2026-10-24T12:00:00+02:00'));
    assert.equal(new Date(spring).toISOString(), '2026-03-29T07:00:00.000Z');
    assert.equal(new Date(autumn).toISOString(), '2026-10-25T08:00:00.000Z');
  } finally {if (previous === undefined) delete process.env.TZ; else process.env.TZ = previous;}
});

test('displaying a saved reminder uses the machine local time', () => {
  const previous = process.env.TZ;
  process.env.TZ = 'Europe/Berlin';
  try { assert.match(reminderLabel('2026-10-07T07:00:00Z'), /09:00/); }
  finally {if (previous === undefined) delete process.env.TZ; else process.env.TZ = previous;}
});

test('task edit keeps reminder independent from due date and saves only a changed reminder', () => {
  assert.match(row, /reminderEditChanges\(editOriginalReminder.current, editRemindAt\)/);
  assert.match(row, /Wieder vorlegen am/);
  assert.match(row, /Wiedervorlage löschen/);
  assert.match(row, /Morgen 09:00/);
  assert.match(row, /editOriginalReminder.current = remindAt/);
  assert.match(row, /Änderungen speichern/);
});

test('an unchanged form retains the exact original instant; an edit or clear guards that original', () => {
  const original = '2026-10-12T09:30:17.123Z';
  assert.deepEqual(reminderEditChanges(original, localReminderInput(original)), {});
  assert.deepEqual(reminderEditChanges(original, ''), {remind_at: null, expected_remind_at: original});
  assert.equal(reminderEditChanges(original, '2026-10-13T10:00').expected_remind_at, original);
});

test('task history includes the reminder in its reload revision and reports reminder changes', () => {
  assert.match(row, /remind_at\?: string \| null/);
  assert.match(history, /remind_at/);
  assert.match(history, /Wiedervorlage/);
});

test('Today reminders fetch bounded data, open exact tasks, do not confuse reminder with completion, and guard updates', () => {
  assert.match(panel, /taskReminders\(100\)/);
  assert.match(panel, /slice\(0, expanded \? 100 : 5\)/);
  assert.match(panel, /truncated/);
  assert.match(panel, /taskHref\(task\)/);
  assert.match(panel, /Wiedervorlage abschließen/);
  assert.match(panel, /editTask\(task\.id, \{remind_at: remindAt, expected_remind_at: task\.remind_at \?\? null\}\)/);
  assert.match(panel, /update\(task, null, "close"\)/);
  assert.match(panel, /Morgen 09:00/);
  assert.match(panel, /pending\.current/);
  assert.match(panel, /version\.current/);
  assert.match(panel, /setItems\(null\)/);
  assert.doesNotMatch(panel, /completeTask|reopenTask/);
});

test('Today reminders distinguish an empty result from a failed refresh and expose the cap', () => {
  assert.match(panel, /role="alert"/);
  assert.match(panel, /role="status"/);
  assert.match(panel, /Nicht alle/);
  assert.match(panel, /Erneut laden/);
});
