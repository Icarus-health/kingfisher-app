"""Exakte Wissenseingaben und getrennte Kontinuität aller transitiven Originale."""
import copy
import re
from .knowledge_render import KnowledgeInputBuild, FORMAT, signature, valid_projection

VERSION = 2
MAX_INPUT_CLAIMS = 128


def claim_ids(items):
    return {item['assertion_id'][6:] for item in items
            if isinstance(item, dict) and isinstance(item.get('assertion_id'), str)
            and item['assertion_id'].startswith('claim:')}


def valid_entry(identifier, entry):
    if not isinstance(entry, dict) or set(entry) != {'version', 'claim_id', 'primary_episode_id', 'projection_sha256', 'source_generations'}:
        return False
    generations = entry['source_generations']
    return (type(entry['version']) is int and entry['version'] == 1
            and entry['claim_id'] == identifier and isinstance(identifier, str) and bool(identifier)
            and isinstance(entry['primary_episode_id'], str) and bool(entry['primary_episode_id'])
            and isinstance(entry['projection_sha256'], str)
            and re.fullmatch('[0-9a-f]{64}', entry['projection_sha256']) is not None
            and isinstance(generations, dict) and 0 < len(generations) <= 128
            and entry['primary_episode_id'] in generations
            and all(isinstance(key, str) and key and type(value) is int and value >= 0
                    for key, value in generations.items()))


def from_items(items):
    if not isinstance(items, list):
        return None
    entries = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('assertion_id'), str) or not item['assertion_id']:
            return None
        if not item['assertion_id'].startswith('claim:'):
            continue
        identifier = item['assertion_id'][6:]
        entry, projection = item.get('knowledge_input'), item.get('knowledge_projection')
        if identifier in entries or not valid_entry(identifier, entry) or not valid_projection(projection):
            return None
        try:
            source = projection['primary_evidence']
            basis = 'occurred_at' if source['occurred_at'] is not None else 'recorded_at'
            if (item.get('evidence_at_basis') != basis or item.get('evidence_at') != source[basis]
                    or projection.get('format') != FORMAT or projection.get('assertion_id') != item['assertion_id']
                    or any(projection[key] != item.get(key) for key in
                           ('statement', 'subject_ref', 'target_ref', 'scope_ref', 'reason'))
                    or any(projection['primary_evidence'][key] != item.get(key) for key in ('source_type', 'source_ref'))
                    or signature(projection, entry['source_generations']) != entry):
                return None
        except (KeyError, TypeError, ValueError):
            return None
        entries[identifier] = copy.deepcopy(entry)
    return entries if len(entries) <= MAX_INPUT_CLAIMS else None


def read_lineage(context):
    if not isinstance(context, dict) or type(context.get('knowledge_claim_lineage_version')) is not int:
        return None
    version = context['knowledge_claim_lineage_version']
    ids, items = context.get('knowledge_claim_ids'), context.get('items')
    if (not isinstance(ids, list) or len(ids) > MAX_INPUT_CLAIMS
            or any(not isinstance(value, str) or not value for value in ids)
            or len(set(ids)) != len(ids)):
        return None
    selected = from_items(items)
    if selected is None:
        return None
    # Strikt leere v1-Historie benötigt keine neue Wissensaufnahme.
    if version == 1:
        return {} if not ids and not selected and 'knowledge_inputs' not in context else None
    entries = context.get('knowledge_inputs')
    if (version != VERSION or not isinstance(entries, dict) or set(ids) != set(entries)
            or any(not valid_entry(key, value) for key, value in entries.items())
            or any(entries.get(key) != value for key, value in selected.items())):
        return None
    return copy.deepcopy(entries)


def metadata(entries, reset=False):
    return {'knowledge_claim_lineage_version': VERSION, 'knowledge_claim_ids': sorted(entries),
            'knowledge_inputs': copy.deepcopy(entries), 'knowledge_history_reset': reset}


def available(entries, claims, episodes=None, *, snapshot_provider=None, build=None):
    if not isinstance(entries, dict) or len(entries) > MAX_INPUT_CLAIMS:
        return False
    if not entries:
        return True
    if claims is None:
        return False
    build = build or KnowledgeInputBuild(claims, snapshot_provider or getattr(episodes, 'support_snapshot', None))
    for identifier, entry in entries.items():
        if not valid_entry(identifier, entry):
            return False
        captured = build.capture(identifier)
        if captured is None or captured[2] != entry:
            return False
    return True


def after_last_reset(messages):
    start = 0
    for index, message in enumerate(messages):
        context = message.get('context')
        if (message.get('role') == 'assistant' and isinstance(context, dict)
                and (context.get('calendar_history_reset') is True
                     or context.get('knowledge_history_reset') is True
                     or context.get('self_model_history_reset') is True
                     or context.get('history_omitted') is True)):
            start = index - 1 if index and messages[index-1].get('role') == 'user' else index
    return messages[start:]
