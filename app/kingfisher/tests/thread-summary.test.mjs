import assert from 'node:assert/strict';
import {test} from 'node:test';
import {summaryBelongsToContext} from '../src/threadSummary.ts';

const context = {uid: 'work:1', context_fingerprint: 'exact', status: 'ready', items: [
  {episode_id: 'old', current: false, text: 'Nur wenn die Freigabe kommt, bitte senden.', occurred_at: null},
  {episode_id: null, current: true, text: 'Bitte nicht mehr senden; der Auftrag entfällt.', occurred_at: '2026-10-07'},
]};
const summary = {uid: 'work:1', context_fingerprint: 'exact', selection_review: 'proposed', semantic_validation: false,
  items: [{episode_id: null, current: true, quote: context.items[1].text, occurred_at: '2026-10-07', interpretation: 'unconfirmed'}]};

test('exact source excerpts remain visibly proposed and belong to the displayed chronology', () => {
  assert.equal(summaryBelongsToContext(summary, context), true);
  for (const changes of [{uid: 'private:1'}, {context_fingerprint: 'old'}, {semantic_validation: true}, {selection_review: 'confirmed'}]) {
    assert.equal(summaryBelongsToContext({...summary, ...changes}, context), false);
  }
});

test('invented quotes, wrong source identities and inferred source dates are rejected', () => {
  for (const changes of [{quote: 'Send it now.'}, {episode_id: 'old'}, {current: false}, {occurred_at: null}, {interpretation: 'confirmed'}]) {
    assert.equal(summaryBelongsToContext({...summary, items: [{...summary.items[0], ...changes}]}, context), false);
  }
  assert.equal(summaryBelongsToContext(summary, {...context, status: 'excluded'}), false);
});
