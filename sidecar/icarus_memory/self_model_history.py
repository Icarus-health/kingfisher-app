"""Versioned SelfModel context lineage; excludes arbitrary source_ref liveness.

Capture from the selected rendering object, never a later authoritative lookup.
Only IDs and hashes/state are persisted; no additional profile plaintext.
"""
from copy import deepcopy
import re
from . import model
from .currency import Currency, judge
from .model import Sensitivity, Status
from .self_model_basis import FrozenBuild, eligible

VERSION = 3
MAX_INPUTS = 128


def capture(assessment, at):
    """Capture only a completed assessment of the exact frozen rendering."""
    assertion = assessment.root
    currency = judge(assertion, at).value
    state = ('disputed' if assertion.status is Status.DISPUTED else
             'outdated' if currency == Currency.OUTDATED.value else 'current')
    return {'fingerprint': assessment.fingerprint, 'state': state, 'currency': currency,
            'basis': dict(assessment.basis), 'basis_signature': assessment.signature}


def valid_basis(value):
    return (isinstance(value, dict) and set(value) == {'version', 'state', 'reason'}
            and type(value['version']) is int and value['version'] == 1
            and value['state'] in ('none', 'supported', 'review')
            and (value['reason'] in ('changed', 'ambiguous', 'changed_and_ambiguous')
                 if value['state'] == 'review' else value['reason'] is None))


def valid_entry(value):
    return (isinstance(value, dict) and set(value) == {'fingerprint', 'state', 'currency', 'basis', 'basis_signature'}
            and valid_basis(value['basis'])
            and isinstance(value['basis_signature'], str)
            and re.fullmatch('[0-9a-f]{64}', value['basis_signature']) is not None
            and isinstance(value['fingerprint'], str)
            and re.fullmatch('[0-9a-f]{64}', value['fingerprint']) is not None
            and value['state'] in ('current', 'outdated', 'disputed')
            and value['currency'] in ('current', 'stale', 'outdated')
            and (value['state'] == 'disputed'
                 or (value['state'] == 'outdated') == (value['currency'] == 'outdated')))


def from_items(items):
    result = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('assertion_id'), str):
            return None
        identifier = item['assertion_id']
        if identifier.startswith('claim:'):
            continue
        value = item.get('self_model_input')
        if not identifier or identifier in result or not valid_entry(value) or value['state'] != item.get('state') or value['basis'] != item.get('basis'):
            return None
        result[identifier] = deepcopy(value)
    return result if len(result) <= MAX_INPUTS else None


def read_lineage(context):
    if (not isinstance(context, dict) or type(context.get('self_model_lineage_version')) is not int
            or context['self_model_lineage_version'] != VERSION):
        return None
    inputs = context.get('self_model_inputs')
    items = context.get('items')
    if (not isinstance(inputs, dict) or len(inputs) > MAX_INPUTS or not isinstance(items, list)
            or any(not isinstance(key, str) or not key or key.startswith('claim:')
                   or not valid_entry(value) for key, value in inputs.items())):
        return None
    selected = from_items(items)
    if selected is None or any(inputs.get(key) != value for key, value in selected.items()):
        return None
    return {key: deepcopy(value) for key, value in inputs.items()}


def metadata(inputs, reset=False):
    return {'self_model_lineage_version': VERSION,
            'self_model_inputs': {key: deepcopy(value) for key, value in sorted(inputs.items())},
            'self_model_history_reset': reset}


def available(inputs, store, max_sensitivity=Sensitivity.SPECIAL_CATEGORY, *, at=None, build=None, resolver=None, local=False):
    if len(inputs) > MAX_INPUTS:
        return False
    moment = at or model.now()
    build = build or FrozenBuild(store, at=moment, max_sensitivity=max_sensitivity,
        support_build=resolver.build(at=moment, local=local, max_sensitivity=max_sensitivity) if resolver else None)
    for identifier, expected in inputs.items():
        if not valid_entry(expected):
            return False
        assertion = build.capture(identifier)
        assessment = build.assess(assertion) if assertion is not None else None
        if assessment is None or capture(assessment, moment) != expected:
            return False
    return True
