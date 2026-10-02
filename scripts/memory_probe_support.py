"""Offline helpers for synthetic memory diagnostics; no network or file access.

A valid case is not a passing semantic evaluation. These helpers never qualify a
model, execute tools, open a source path, or modify application configuration.
"""
from __future__ import annotations

import copy
import time
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from icarus_memory.providers import Provider, Reply
from icarus_memory.relations import predicates_equivalent


def _text(value: Any, maximum: int = 20000) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError('Expected nonempty bounded text')


def _object(value: Any, required: set[str], optional: set[str] = frozenset()) -> None:
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - optional:
        raise ValueError('Missing or unknown fields')


def _rows(value: Any, required: set[str], optional: set[str] = frozenset()) -> set[str]:
    if not isinstance(value, list) or len(value) > 300:
        raise ValueError('Expected a bounded list')
    identifiers: set[str] = set()
    for row in value:
        _object(row, required, optional)
        for field in required:
            _text(row[field])
        if row['id'] in identifiers:
            raise ValueError('Duplicate identifier')
        identifiers.add(row['id'])
    return identifiers


def _strings(value: Any) -> set[str]:
    if not isinstance(value, list) or len(value) > 300:
        raise ValueError('Expected a bounded list')
    for item in value:
        _text(item)
    if len(set(value)) != len(value):
        raise ValueError('Duplicate list item')
    return set(value)


def _utc(value: Any) -> datetime:
    _text(value)
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None or result.utcoffset() != timedelta(0):
            raise ValueError
        return result
    except (ValueError, OverflowError) as exc:
        raise ValueError('Invalid UTC timestamp') from exc


def _aware(value: Any) -> datetime:
    _text(value)
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError
        return result
    except (ValueError, OverflowError) as exc:
        raise ValueError('Invalid aware timestamp') from exc


def validate_case(case: dict) -> None:
    """Validate the prepared-memory development format without changing it."""
    fields = {'id', 'scenario_id', 'split', 'fixture_mode', 'clock_utc', 'timezone', 'question',
              'sources', 'entities', 'assertions', 'expected_source_ids',
              'forbidden_source_ids', 'required', 'forbidden', 'severity'}
    _object(case, fields, {'calendar_callback'})
    for field in ('id', 'scenario_id', 'question', 'severity', 'clock_utc', 'timezone'):
        _text(case[field])
    if case['split'] != 'development' or case['fixture_mode'] != 'prepared_memory':
        raise ValueError('Only prepared development cases are supported')
    _utc(case['clock_utc'])
    if case['timezone'] not in {'Europe/Berlin'}:
        raise ValueError('Unsupported fixture timezone')
    sources = _rows(case['sources'], {'id', 'text', 'source_type'},
                    {'observed_at_utc', 'excluded_from_retrieval', 'exclusion_reason'})
    entities = _rows(case['entities'], {'id', 'kind', 'label'})
    assertion_ids = _rows(case['assertions'],
                          {'id', 'subject_ref', 'predicate', 'value', 'source_id'},
                          {'statement', 'quote', 'depends_on_assertion_ids',
                           'supersedes_assertion_ids', 'valid_from_utc', 'valid_to_utc'})
    for source in case['sources']:
        if source['source_type'] not in {'email', 'chat', 'document', 'calendar', 'user_stated'}:
            raise ValueError('Unsupported synthetic source type')
    for entity in case['entities']:
        if entity['kind'] not in {'person', 'project', 'organization', 'topic', 'place', 'document'}:
            raise ValueError('Unsupported entity kind')
    source_text = {source['id']: source['text'] for source in case['sources']}
    excluded_sources: set[str] = set()
    for source in case['sources']:
        excluded = source.get('excluded_from_retrieval', False)
        if not isinstance(excluded, bool):
            raise ValueError('Source exclusion must be boolean')
        if excluded != ('exclusion_reason' in source):
            raise ValueError('Excluded sources require exactly one exclusion reason')
        if 'exclusion_reason' in source:
            _text(source['exclusion_reason'])
        if excluded:
            excluded_sources.add(source['id'])
        if 'observed_at_utc' in source:
            _utc(source['observed_at_utc'])
    for assertion in case['assertions']:
        if assertion['subject_ref'] not in entities or assertion['source_id'] not in sources:
            raise ValueError('Unknown assertion reference')
        for field in ('statement', 'quote'):
            if field in assertion:
                _text(assertion[field])
        if 'quote' in assertion and assertion['quote'] not in source_text[assertion['source_id']]:
            raise ValueError('Quote is not present in source')
        for field in ('depends_on_assertion_ids', 'supersedes_assertion_ids'):
            references = _strings(assertion.get(field, []))
            if not references <= assertion_ids or assertion['id'] in references:
                raise ValueError('Invalid assertion dependency')
        start = _utc(assertion['valid_from_utc']) if 'valid_from_utc' in assertion else None
        end = _utc(assertion['valid_to_utc']) if 'valid_to_utc' in assertion else None
        if start and end and start >= end:
            raise ValueError('Invalid assertion validity interval')
    assertions_by_id = {assertion['id']: assertion for assertion in case['assertions']}
    for assertion in case['assertions']:
        for previous_id in assertion.get('supersedes_assertion_ids', []):
            previous = assertions_by_id[previous_id]
            if (previous['subject_ref'] != assertion['subject_ref'] or
                    not predicates_equivalent(previous['predicate'], assertion['predicate'])):
                raise ValueError('Incompatible superseded assertion')
    dependency_graph = {
        assertion['id']: set(assertion.get('depends_on_assertion_ids', [])) |
                         set(assertion.get('supersedes_assertion_ids', []))
        for assertion in case['assertions']
    }
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(identifier: str) -> None:
        if identifier in visiting:
            raise ValueError('Cyclic assertion dependency')
        if identifier in visited:
            return
        visiting.add(identifier)
        for dependency in dependency_graph[identifier]:
            visit(dependency)
        visiting.remove(identifier)
        visited.add(identifier)
    for identifier in assertion_ids:
        visit(identifier)
    expected = _strings(case['expected_source_ids'])
    forbidden = _strings(case['forbidden_source_ids'])
    if not (expected | forbidden) <= sources or expected & forbidden:
        raise ValueError('Invalid expected/forbidden sources')
    if excluded_sources & expected or not excluded_sources <= forbidden:
        raise ValueError('Excluded sources must be forbidden from retrieval')
    _strings(case['required'])
    _strings(case['forbidden'])
    if not case['required']:
        raise ValueError('A semantic rubric is required')
    if 'calendar_callback' in case:
        callback = case['calendar_callback']
        _object(callback, {'status', 'coverage', 'truncated', 'invalid_count', 'window_from',
                           'window_to', 'events', 'captured_at_utc', 'timezone', 'source_ids'})
        if callback['status'] not in {'available', 'stale', 'unavailable'}:
            raise ValueError('Invalid calendar callback status')
        if callback['coverage'] not in {'covered', 'unknown'} or callback['timezone'] != case['timezone']:
            raise ValueError('Invalid calendar callback coverage or timezone')
        if not isinstance(callback['truncated'], bool) or not isinstance(callback['invalid_count'], int) \
                or isinstance(callback['invalid_count'], bool) or callback['invalid_count'] < 0:
            raise ValueError('Invalid calendar callback counters')
        _utc(callback['captured_at_utc'])
        window_from = _utc(callback['window_from'])
        window_to = _utc(callback['window_to'])
        if window_from >= window_to:
            raise ValueError('Invalid calendar callback window')
        if not _strings(callback['source_ids']) <= sources:
            raise ValueError('Unknown calendar callback source')
        if not isinstance(callback['events'], list) or len(callback['events']) > 300:
            raise ValueError('Invalid calendar callback events')
        event_ids: set[str] = set()
        for event in callback['events']:
            _object(event, {'uid', 'source_id', 'summary', 'start', 'end', 'source_label', 'all_day'})
            for field in ('uid', 'source_id', 'summary', 'start', 'end', 'source_label'):
                _text(event[field])
            if event['uid'] in event_ids or not isinstance(event['all_day'], bool):
                raise ValueError('Invalid calendar event')
            if event['source_id'] not in sources or event['source_id'] not in callback['source_ids']:
                raise ValueError('Unknown calendar event source')
            if _aware(event['start']) >= _aware(event['end']):
                raise ValueError('Invalid calendar event interval')
            event_ids.add(event['uid'])
    if sum(len(source['text']) for source in case['sources']) > 1_000_000:
        raise ValueError('Source text budget exceeded')


def score_retrieval(expected: set[str], forbidden: set[str], actual: set[str]) -> dict:
    """Report source selection only; never infer semantic model correctness."""
    if expected & forbidden:
        raise ValueError('Expected and forbidden sources overlap')
    found = expected & actual
    return dict(missing=sorted(expected - actual), forbidden_seen=sorted(forbidden & actual),
                unexpected=sorted(actual - expected - forbidden), expected_count=len(expected),
                found_count=len(found), actual_count=len(actual),
                recall=len(found) / len(expected) if expected else None)


class RecordingProvider:
    """Capture exactly the inputs at the Provider boundary, then delegate.

    Calls must contain synthetic data. The trace intentionally contains full
    inputs; it is not a redactor for arbitrary personal application traffic.
    """
    def __init__(self, delegate: Provider):
        self.delegate = delegate
        self.calls: list[dict[str, Any]] = []

    @property
    def name(self):
        return self.delegate.name

    @property
    def model(self):
        return self.delegate.model

    @property
    def is_local(self):
        return self.delegate.is_local

    @property
    def supports_json(self):
        return (callable(getattr(self.delegate, 'complete_json', None))
                and getattr(self.delegate, 'supports_json', True))

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Reply:
        return self._record({'messages': messages, 'tools': tools},
                            lambda: self.delegate.complete(messages, tools))

    def __getattr__(self, name):
        # Advertise the optional capability only when the real delegate has it;
        # otherwise wrapping a provider would change Agent's chosen path.
        method = getattr(self.delegate, name, None) if name == 'complete_json' else None
        if not callable(method):
            raise AttributeError(name)
        def complete_json(messages, **kwargs):
            return self._record({'method': name, 'messages': messages, **kwargs},
                                lambda: method(messages, **kwargs))
        return complete_json

    def _record(self, request, invoke):
        call: dict[str, Any] = {
            'request': copy.deepcopy(request),
            'started_monotonic': time.monotonic(), 'status': 'started',
            'semantic_verdict': None, 'technical_status': 'pending',
            'token_count': None, 'finish_reason': None,
            'metadata_limit': 'Provider Reply does not expose token count or finish reason',
        }
        self.calls.append(call)
        try:
            reply = invoke()
            call.update(status='returned', reply=copy.deepcopy(asdict(reply)),
                        technical_status=('unexpected_tools' if reply.tool_calls else
                                          'empty_response' if not reply.text.strip() else
                                          'review_required'))
            return reply
        except Exception as exc:
            call.update(status='error', technical_status='provider_error', error_type=type(exc).__name__)
            raise
        finally:
            call['elapsed_seconds'] = time.monotonic() - call['started_monotonic']
