import type {MailThreadContext, MailThreadSummary} from './api';

/** Only project a response belonging to the exact currently displayed sources. */
export function summaryBelongsToContext(summary: MailThreadSummary, context: MailThreadContext) {
  return context.status === 'ready' && summary.uid === context.uid
    && Boolean(context.context_fingerprint) && summary.context_fingerprint === context.context_fingerprint
    && summary.selection_review === 'proposed' && summary.semantic_validation === false
    && summary.items.every(row => row.interpretation === 'unconfirmed' && Boolean(row.quote)
      && context.items.some(source => source.episode_id === row.episode_id && source.current === row.current
        && source.text.includes(row.quote) && source.occurred_at === row.occurred_at));
}
