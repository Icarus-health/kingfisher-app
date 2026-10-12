import {test} from 'node:test';
import assert from 'node:assert/strict';
import {connectLocalAnswer} from '../src/localAnswerConnection.ts';

const model = 'qwen3.5:9b';
const endpoint = 'http://host.docker.internal:11434/v1';
function ports(overrides = {}) {
  const calls = [];
  const setup = {settings: {provider: 'ollama', model, endpoint}, status: {provider: 'ollama', model, endpoint}};
  return {calls, setup, api: {
    saveModelRole: async (role, body) => {calls.push(['role', role, body]); return {rollen: [{rolle: 'antwort', wirksam: {modell: model, lokal: true}}]};},
    saveLocalModel: async (...args) => {calls.push(['standard', ...args]); return setup;},
    testModel: async () => {calls.push(['test']); return {ok: true};},
    ...overrides,
  }};
}

test('the visible local choice pins the answer role before changing the standard and tests the active agent', async () => {
  const p = ports();
  const result = await connectLocalAnswer(p.api, model, endpoint);
  assert.equal(result.state, 'ready');
  assert.deepEqual(p.calls, [['role', 'antwort', {modell: model, cloud: false, local_only: true}], ['standard', model, endpoint], ['test']]);
});
test('a rejected answer role does not change the standard or run a readiness call', async () => {
  const p = ports({saveModelRole: async () => {throw Error('RAM reserve');}});
  await assert.rejects(connectLocalAnswer(p.api, model, endpoint), /RAM reserve/);
  assert.deepEqual(p.calls, []);
});
test('an unverified or different answer selection stops before changing the standard', async () => {
  for (const wirksam of [{modell: model, lokal: null}, {modell: 'missing:12b', lokal: true}, {modell: model, lokal: false}]) {
    const p = ports({saveModelRole: async () => ({rollen: [{rolle: 'antwort', wirksam}]})});
    assert.equal((await connectLocalAnswer(p.api, model, endpoint)).state, 'unverified');
    assert.deepEqual(p.calls, []);
  }
});
test('an environment override never reports a successful connection or tests the wrong model', async () => {
  const p = ports();
  p.setup.status.model = 'missing:12b';
  assert.equal((await connectLocalAnswer(p.api, model, endpoint)).state, 'different');
  assert.equal(p.calls.some(call => call[0] === 'test'), false);
});
test('HTTP success with failed model readiness stays disconnected', async () => {
  const p = ports({testModel: async () => ({ok: false})});
  assert.equal((await connectLocalAnswer(p.api, model, endpoint)).state, 'unavailable');
});
test('a failed standard save does not attempt model readiness', async () => {
  const p = ports({saveLocalModel: async () => {throw Error('disk unavailable');}});
  await assert.rejects(connectLocalAnswer(p.api, model, endpoint), /disk unavailable/);
  assert.equal(p.calls.some(call => call[0] === 'test'), false);
});
