"""Read-only inbox labels from current rules and existing review hints."""
from .mail_filter import classify, policy


def classify_row(message, settings):
    selected = policy(settings)
    selected['ai_enabled'] = False  # Viewing the inbox never triggers a model call.
    decision = classify(message, selected)
    if not decision.include:
        return {'category': decision.category, 'filter_reason': decision.reason}
    # Advisory labels only; never grant permission or write evidence here.
    for item in settings.mail_filter.get('pending', {}).values():
        if (message.account_id and item.get('account_id') == message.account_id
                and message.uid == f"{message.account_id}:{item.get('uid')}"
                and item.get('sender') == message.sender[:500]
                and item.get('subject') == message.subject[:500]
                and item.get('preview') == message.preview[:300]
                and str(item.get('reason', '')).startswith(('ai_', 'content_'))):
            category = item.get('category')
            if category in ('spam', 'newsletter', 'unclear'):
                return {'category': category, 'filter_reason': item['reason']}
    return {'category': 'inbox', 'filter_reason': 'not_flagged'}
