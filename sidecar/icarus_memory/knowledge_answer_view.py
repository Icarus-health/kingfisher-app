"""Current validity of saved claim-based answers; preserve the stored audit record.

This projects status, never promotes pending text or reinterprets an old answer.
Original-source answers have their own reference-only projection.
"""
import copy

from . import knowledge_history, self_model_history
from .knowledge_conflicts import MESSAGES

NEUTRAL_PREVIEW = 'Gedächtnisantwort — beim Öffnen erneut geprüft.'
INVALIDATED = 'Die Beleggrundlage dieser früheren Antwort ist nicht mehr aktuell. Bitte frage erneut.'
LIMITED = 'Diese ältere Gedächtnisantwort wurde noch nicht erneut geprüft. Bitte frage erneut.'


def applies(message):
    metadata = message.get('metadata')
    context = metadata.get('context') if isinstance(metadata, dict) else None
    contract = context.get('answer_contract') if isinstance(context, dict) else None
    return (message.get('role') == 'assistant' and isinstance(context, dict)
            and 'source_answer' not in context
            and (bool(context.get('knowledge_claim_ids'))
                 or (context.get('answer_mode') == 'memory_evidence'
                     and isinstance(contract, dict) and contract.get('status')
                     in {'evidence', 'clarify', 'fallback'})))


def project_message(message, claims, episodes, conflict_check, *, resolve=True):
    if not applies(message):
        return message
    context = message['metadata']['context']
    inputs = knowledge_history.read_lineage(context)
    status = 'unchecked'
    reply = LIMITED
    if resolve:
        if inputs is None or not knowledge_history.available(inputs, claims, episodes):
            status, reply = 'invalidated', INVALIDATED
        else:
            selected = list(inputs)
            contract = context.get('answer_contract')
            if (context.get('answer_mode') == 'memory_evidence'
                    and isinstance(contract, dict) and contract.get('status') == 'evidence'):
                ids = contract.get('selected_assertion_ids')
                if (not isinstance(ids, list) or not ids or len(ids) > 5
                        or any(not isinstance(item, str) or not item.startswith('claim:')
                               or item[6:] not in inputs for item in ids)):
                    ids = []
                if not ids:
                    return _withheld(message, claims, 'invalidated', INVALIDATED)
                selected = [item[6:] for item in ids]
            try:
                status = conflict_check(selected)
            except Exception:
                status = 'unchecked'
            if status == 'clear':
                return message
            reply = MESSAGES.get(status, MESSAGES['unchecked'])
    return _withheld(message, claims, status, reply)


def _withheld(message, claims, status, reply):
    result = copy.deepcopy(message)
    result['content'] = reply
    result['metadata'] = {'context': {
        'items': [], 'memory_revision': claims.revision,
        'answer_mode': 'memory_evidence', 'history_egress': 'local_only',
        'memory_answer_withheld': True,
        **knowledge_history.metadata({}), **self_model_history.metadata({}),
        'answer_contract': {'version': 1, 'presentation_version': 2,
            'status': status if status in {'conflict', 'invalidated'} else 'conflict_unchecked',
            'model_called': False, 'selected_assertion_ids': [], 'semantic_validation': False},
    }}
    return result
