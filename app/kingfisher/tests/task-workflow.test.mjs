import assert from 'node:assert/strict';
import {test} from 'node:test';
import {taskHref, endOfTaskDay, explicitDeadline, candidateDeadline, localTaskDay} from '../src/taskWorkflow.ts';

test('task links retain exact identity even for waiting or completed tasks', () => {
  assert.equal(taskHref({id: 'mail/1', status: 'open', wartet_auf: 'Anna', project_id: 'a&b'}), '/vorhaben?view=waiting&task=mail%2F1&project=a%26b');
  assert.equal(taskHref({id: 'done', status: 'done', wartet_auf: 'Anna'}), '/vorhaben?view=done&task=done');
});

test('a selected task day is due at its local end, including DST changes', () => {
  for (const day of ['2026-03-29', '2026-10-25', '2026-10-07']) {
    const value = new Date(endOfTaskDay(day));
    assert.equal(value.getHours(), 23);
    assert.equal(value.getMinutes(), 59);
    assert.equal(value.getDate(), Number(day.slice(-2)));
  }
  assert.equal(endOfTaskDay(''), null);
  assert.throws(() => endOfTaskDay('2026-02-30'));
});

test('only a single unconditional absolute deadline is offered, never an import-relative guess', () => {
  assert.equal(explicitDeadline('Bitte den Bericht bis zum 12.10.2026 senden.'), '2026-10-12');
  assert.equal(explicitDeadline('Bitte bis spätestens 2026-10-14 antworten.'), '2026-10-14');
  for (const quote of ['Bitte bis Freitag antworten.', 'Treffen am 12.10.2026.',
    'Falls die Freigabe kommt, bitte bis 12.10.2026 senden.',
    'Bitte bis 31.02.2026 senden.', 'Bitte bis 12.10.2026 um 14:00 senden.',
    'Bitte bis 12.10.2026 oder bis 14.10.2026 senden.',
    'Nicht bis 12.10.2026 senden.', 'Die alte Frist bis 12.10.2026 entfällt.',
    'Termin am 10.10.2026, bitte bis 12.10.2026 bestätigen.']) {
    assert.equal(explicitDeadline(quote), null, quote);
  }
});

test('an unchanged source deadline retains its exact time; a newly chosen day is explicit', () => {
  const source = {temporal_status: 'recent', valid_until: '2026-10-12T09:30:00+02:00'};
  assert.equal(candidateDeadline(source, '2026-10-12'), source.valid_until);
  assert.equal(candidateDeadline(source, ''), null);
  assert.equal(new Date(candidateDeadline(source, '2026-10-13')).getHours(), 23);
  assert.equal(new Date(candidateDeadline({...source, temporal_status: 'old'}, '2026-10-12')).getHours(), 23);
});

test('deadline field and unchanged-time comparison use the same local calendar day', () => {
  const previous = process.env.TZ;
  process.env.TZ = 'Europe/Berlin';
  try {
    const source = {temporal_status: 'recent', valid_until: '2026-10-12T23:30:00Z'};
    assert.equal(localTaskDay(source.valid_until), '2026-10-13');
    assert.equal(candidateDeadline(source, '2026-10-13'), source.valid_until);
    assert.equal(localTaskDay(null), '');
  } finally {if (previous === undefined) delete process.env.TZ; else process.env.TZ = previous;}
});
