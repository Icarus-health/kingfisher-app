import assert from 'node:assert/strict';
import {test} from 'node:test';
import {calendarWindow, eventsInRange, findCalendarEvent} from '../src/calendarRange.ts';

test('preparation selects an exact series occurrence and rejects an ambiguous UID-only link', () => {
  const first = {uid: 'series', start: '2030-01-01T10:00:00Z'};
  const second = {uid: 'series', start: '2030-01-02T10:00:00Z'};
  assert.equal(findCalendarEvent([first, second], 'series', '2030-01-02T11:00:00+01:00'), second);
  assert.equal(findCalendarEvent([first, second], 'series'), null);
  assert.equal(findCalendarEvent([first, second], 'series', '2030-01-03T10:00:00Z'), null);
});

test('calendar windows use exact visible local day boundaries', () => {
  const focus = new Date(2026, 9, 7, 14, 30);
  const today = new Date(2026, 9, 7, 18, 0);
  const month = calendarWindow(focus, 'Monat', today);
  assert.deepEqual([month.from.getFullYear(), month.from.getMonth(), month.from.getDate()], [2026, 9, 1]);
  assert.deepEqual([month.until.getFullYear(), month.until.getMonth(), month.until.getDate()], [2026, 10, 1]);
  const week = calendarWindow(focus, 'Woche', today);
  assert.deepEqual([week.from.getFullYear(), week.from.getMonth(), week.from.getDate()], [2026, 9, 5]);
  assert.deepEqual([week.until.getFullYear(), week.until.getMonth(), week.until.getDate()], [2026, 9, 12]);
  const agenda = calendarWindow(focus, 'Liste', today);
  assert.deepEqual([agenda.from.getFullYear(), agenda.from.getMonth(), agenda.from.getDate()], [2026, 9, 7]);
  assert.deepEqual([agenda.until.getFullYear(), agenda.until.getMonth(), agenda.until.getDate()], [2026, 9, 14]);
});

test('calendar windows navigate across years, including a week crossing New Year', () => {
  const focus = new Date(2027, 0, 1, 9);
  const week = calendarWindow(focus, 'Woche', focus);
  assert.deepEqual([week.from.getFullYear(), week.from.getMonth(), week.from.getDate()], [2026, 11, 28]);
  assert.deepEqual([week.until.getFullYear(), week.until.getMonth(), week.until.getDate()], [2027, 0, 4]);
  const year = calendarWindow(focus, 'Jahr', focus);
  assert.deepEqual([year.from.getFullYear(), year.from.getMonth(), year.from.getDate()], [2027, 0, 1]);
  assert.deepEqual([year.until.getFullYear(), year.until.getMonth(), year.until.getDate()], [2028, 0, 1]);
});

test('local calendar windows retain 23-hour days across spring clock change', () => {
  const focus = new Date(2027, 2, 28, 11);
  const dayWeek = calendarWindow(focus, 'Woche', focus);
  const march = calendarWindow(focus, 'Monat', focus);
  assert.deepEqual([march.from.getDate(), march.until.getDate()], [1, 1]);
  assert.equal((dayWeek.until.getTime() - dayWeek.from.getTime()) / 3600000,
    168 + (dayWeek.until.getTimezoneOffset() - dayWeek.from.getTimezoneOffset()) / 60);
});

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

// A dated link must bring its actual period into view even when the user last
// selected the seven-day list. Otherwise a real event appears to be missing.
test('dated preparation links leave the current seven-day list when necessary', async () => {
  const {preparationView} = await import('../src/calendarRange.ts');
  const now = new Date(2026, 9, 7, 12);
  assert.equal(preparationView('Liste', new Date(2030, 0, 1), now), 'Monat');
  assert.equal(preparationView('Liste', new Date(2026, 9, 14), now), 'Monat');
  assert.equal(preparationView('Liste', new Date(2026, 9, 8), now), 'Liste');
  assert.equal(preparationView('Liste', new Date(2026, 9, 6), now), 'Monat');
  assert.equal(preparationView('Woche', new Date(2030, 0, 1), now), 'Woche');
  assert.equal(preparationView('Liste', null, now), 'Liste');
});

test('a mirrored calendar event retains source-specific links', () => {
  const item = {uid:'feed:remote',start:'2026-10-10T18:00:00Z',end:'2026-10-10T19:00:00Z',source_id:'feed',source_label:'Feed',source_copies:[{uid:'feed:remote',source_id:'feed',source_label:'Feed'},{uid:'mac:local',source_id:'mac',source_label:'Mac'}]};
  const result=findCalendarEvent([item],'mac:local',item.start);
  assert.equal(result?.uid,'mac:local');assert.equal(result?.source_id,'mac');
  assert.equal(findCalendarEvent([item],'revoked:gone',item.start),null);
  assert.equal(findCalendarEvent([item,{...item,uid:'other'}],'mac:local',item.start),null);
});

test('mirror actions retain the writable source UID and withdrawal removes it', async () => {
  const {calendarSourceVersions} = await import('../src/calendarRange.ts');
  const {editableEventId} = await import('../src/calendarActionState.ts');
  const item = {uid:'ical:remote', source_id:'ical', source_label:'Abo', source_copies:[
    {uid:'ical:remote',source_id:'ical',source_label:'Abo'},
    {uid:'google:event123',source_id:'google',source_label:'Google'},
    {uid:'mac-calendar:opaque',source_id:'mac-calendar',source_label:'Mac'}]};
  const actions=calendarSourceVersions(item).filter(copy => copy.source_id==='google' && editableEventId(copy));
  assert.equal(actions.length,1);
  assert.equal(actions[0].uid,'google:event123');
  assert.equal(editableEventId(actions[0]),'event123');
  assert.equal(calendarSourceVersions({...item,source_copies:undefined}).filter(copy => copy.source_id==='google').length,0);
});
