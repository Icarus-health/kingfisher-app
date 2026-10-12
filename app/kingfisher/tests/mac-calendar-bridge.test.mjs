import test from 'node:test';
import assert from 'node:assert/strict';
import { requestMacCalendarPermission } from '../src/macCalendarBridge.ts';

test('Nur ein aktuelles Connect-Ergebnis wird an das native Fenster übergeben', () => {
  const messages = [];
  const window = { webkit: { messageHandlers: { kingfisher: { postMessage: message => messages.push(message) } } } };
  assert.equal(requestMacCalendarPermission({ enabled: true, authorize: true, generation: 7 }, window), true);
  assert.deepEqual(messages, [{ aktion: 'kalenderFreigeben', generation: 7 }]);
  for (const state of [{ enabled: false, authorize: true, generation: 7 },
    { enabled: true, authorize: false, generation: 7 },
    { enabled: true, authorize: true, generation: true },
    { enabled: true, authorize: true, generation: -1 },
    { enabled: true, authorize: true, generation: 1.5 }]) {
    assert.equal(requestMacCalendarPermission(state, window), false);
  }
  assert.equal(messages.length, 1);
});

test('Browser oder defekte Brücke lösen keine versteckte Ersatzfreigabe aus', () => {
  const state = { enabled: true, authorize: true, generation: 4 };
  assert.equal(requestMacCalendarPermission(state, {}), false);
  assert.equal(requestMacCalendarPermission(state, { webkit: { messageHandlers: { kingfisher: { postMessage: () => { throw Error('unavailable'); } } } } }), false);
});
