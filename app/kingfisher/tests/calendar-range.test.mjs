import assert from 'node:assert/strict';
import {test} from 'node:test';
import {eventsInRange} from '../src/calendarRange.ts';

test('seven-day agenda includes a running multiday event and excludes events outside the period', () => {
  const items = [
    {uid: 'running', start: '2026-10-06T08:00:00+02:00', end: '2026-10-09T18:00:00+02:00'},
    {uid: 'finished', start: '2026-10-06T08:00:00+02:00', end: '2026-10-07T00:00:00+02:00'},
    {uid: 'last-day', start: '2026-10-13T23:30:00+02:00', end: '2026-10-14T01:00:00+02:00'},
    {uid: 'next-period', start: '2026-10-14T00:00:00+02:00'},
  ];
  assert.deepEqual(eventsInRange(items, new Date('2026-10-07T00:00:00+02:00'), new Date('2026-10-14T00:00:00+02:00')).map(e => e.uid), ['running', 'last-day']);
});

test('all-day event has an exclusive end, including across the year boundary', () => {
  const items = [{uid: 'holiday', start: '2026-12-30T00:00:00+01:00', end: '2027-01-02T00:00:00+01:00'}];
  assert.equal(eventsInRange(items, new Date('2027-01-01T00:00:00+01:00'), new Date('2027-01-02T00:00:00+01:00')).length, 1);
  assert.equal(eventsInRange(items, new Date('2027-01-02T00:00:00+01:00'), new Date('2027-01-03T00:00:00+01:00')).length, 0);
});

test('missing or unusable end timestamps are point events on their actual start day', () => {
  const items = [
    {uid: 'missing-end', start: '2026-10-07T10:00:00+02:00'},
    {uid: 'zero-duration', start: '2026-10-07T10:00:00+02:00', end: '2026-10-07T10:00:00+02:00'},
    {uid: 'invalid-end', start: '2026-10-07T10:00:00+02:00', end: 'unknown'},
    {uid: 'reversed-end', start: '2026-10-07T10:00:00+02:00', end: '2026-10-06T10:00:00+02:00'},
    {uid: 'missing-start', end: '2026-10-07T11:00:00+02:00'},
    {uid: 'invalid-start', start: 'unknown'},
  ];
  const from = new Date('2026-10-07T00:00:00+02:00'), until = new Date('2026-10-08T00:00:00+02:00');
  assert.deepEqual(eventsInRange(items, from, until).map(e => e.uid), ['missing-end', 'zero-duration', 'invalid-end', 'reversed-end']);
  assert.deepEqual(eventsInRange(items, new Date('2026-10-08T00:00:00+02:00'), new Date('2026-10-09T00:00:00+02:00')), []);
});

test('a local day spanning the autumn clock change includes both repeated clock hours', () => {
  const items = [
    {uid: 'first', start: '2026-10-25T02:30:00+02:00'},
    {uid: 'second', start: '2026-10-25T02:30:00+01:00'},
    {uid: 'late', start: '2026-10-25T23:30:00+01:00'},
    {uid: 'tomorrow', start: '2026-10-26T00:00:00+01:00'},
  ];
  assert.deepEqual(eventsInRange(items, new Date('2026-10-25T00:00:00+02:00'), new Date('2026-10-26T00:00:00+01:00')).map(e => e.uid), ['first', 'second', 'late']);
});
