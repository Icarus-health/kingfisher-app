"""One-shot Small4 EU source transport with durable conservative accounting."""
from __future__ import annotations

import json
import re

import httpx

from .cloud_import_budget import ENDPOINT, MODEL, MistralBudgetError
from .providers import Reply

_MAX_RESPONSE_BYTES = 1_048_576
_MAX_OUTPUT_BYTES = 131_072
_MAX_REQUEST_BYTES = 4_194_304
_MAX_SCHEMA_BYTES = 131_072


def _reject_constant(_value):
    raise ValueError('Non-finite JSON')


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _bounded_tree(value):
    pending = [(value, 0)]
    nodes = 0
    while pending:
        child, depth = pending.pop()
        nodes += 1
        if depth > 64 or nodes > 100000:
            raise ValueError('JSON bounds')
        if isinstance(child, dict):
            if any(type(key) is not str for key in child):
                raise ValueError('Non-JSON object key')
            pending.extend((item, depth + 1) for item in child.values())
        elif isinstance(child, list):
            pending.extend((item, depth + 1) for item in child)
    return value


def _parse_json(raw):
    return _bounded_tree(json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant))


class MistralImportProvider:
    """No network activity until complete_json_guarded explicitly permits it.

    The app supplies one shared ledger. Only this job adapter caches the exact
    numeric regional model context; construction, status and preview do not probe.
    """
    name = 'mistral'
    is_local = False
    is_remote = True
    entity_anchor_mode = 'block_quote'

    def __init__(self, model, api_key, credential_revision, current_revision, *, budget,
                 job_id, budget_id, budget_revision, price_id):
        self.model = model
        self._key = api_key
        self.credential_revision = credential_revision
        self._current_revision = current_revision
        self._budget = budget
        self._job_id = job_id
        self._budget_id = budget_id
        self._budget_revision = budget_revision
        self._price_id = price_id
        self._context_limit = None

    def _credential_current(self):
        return (self.model == MODEL and type(self._key) is str and bool(self._key)
                and type(self.credential_revision) is str and bool(self.credential_revision)
                and self._job_identity_valid()
                and self._current_revision() == self.credential_revision)

    def _job_identity_valid(self):
        return (type(self._job_id) is str
                and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', self._job_id) is not None)

    def available(self):
        try:
            return (self._credential_current() and self._budget.status()['cap_microusd'] > 0
                    and self._budget.matches(self._budget_id, self._budget_revision, self._price_id))
        except Exception:
            return False

    def _client(self):
        return httpx.Client(timeout=90, trust_env=False, follow_redirects=False)

    def _check(self, still_permitted):
        try:
            allowed = still_permitted()
        except Exception:
            raise MistralBudgetError('permission_changed') from None
        if not allowed:
            raise MistralBudgetError('permission_changed')
        try:
            current = self._credential_current()
        except Exception:
            raise MistralBudgetError('credential_changed') from None
        if not current:
            raise MistralBudgetError('credential_changed')
        if not self._budget.matches(self._budget_id, self._budget_revision, self._price_id):
            reason = self._budget.status()['blocked_reason']
            raise MistralBudgetError(reason if reason in {'budget_uncertain', 'pricing_changed'} else 'budget_changed')

    def _admissible(self):
        state = self._budget.status()
        if not state['ready']:
            raise MistralBudgetError(state['blocked_reason'])

    def _payload(self, messages, max_tokens, schema):
        try:
            if (self.model != MODEL or not self._job_identity_valid()
                    or type(max_tokens) is not int or not 64 <= max_tokens <= 1200
                    or not isinstance(schema, dict) or schema.get('type') != 'object'
                    or not isinstance(messages, list)):
                raise ValueError
            for message in messages:
                if (not isinstance(message, dict) or set(message) != {'role', 'content'}
                        or message['role'] not in {'system', 'user', 'assistant'}
                        or not isinstance(message['content'], str)):
                    raise ValueError
            # Freeze caller data without stripping or weakening schema keywords.
            schema_json = json.dumps(_bounded_tree(schema), allow_nan=False, ensure_ascii=False)
            if len(schema_json.encode('utf-8')) > _MAX_SCHEMA_BYTES:
                raise ValueError
            payload = {'model': MODEL, 'messages': messages, 'max_tokens': max_tokens,
                       'n': 1, 'stream': False, 'temperature': 0,
                       'reasoning_effort': 'none', 'service_tier': 'standard_only',
                       'response_format': {'type': 'json_schema', 'json_schema': {
                           'name': 'memory_result', 'strict': True, 'schema': schema}}}
            raw = json.dumps(payload, allow_nan=False, ensure_ascii=False)
            if len(raw.encode('utf-8')) > _MAX_REQUEST_BYTES:
                raise ValueError
            return _parse_json(raw)
        except (ValueError, TypeError, RecursionError, UnicodeError):
            raise MistralBudgetError('invalid_request') from None

    def _exchange(self, client, method, path, payload=None):
        failure = 'metadata_unavailable' if method == 'GET' else 'budget_uncertain'
        headers = {'authorization': 'Bearer ' + self._key, 'content-type': 'application/json'}
        options = {} if payload is None else {'json': payload}
        try:
            # Stream transport bytes solely to enforce a finite response bound;
            # model generation remains explicitly nonstreaming in the payload.
            with client.stream(method, ENDPOINT + path, headers=headers, **options) as response:
                if not 200 <= response.status_code < 300:
                    raise MistralBudgetError('metadata_unavailable' if method == 'GET' else 'provider_rejected')
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > _MAX_RESPONSE_BYTES:
                        raise MistralBudgetError(failure)
                    chunks.append(chunk)
                return _parse_json(b''.join(chunks))
        except (httpx.HTTPError, ValueError, TypeError, RecursionError, UnicodeError):
            raise MistralBudgetError(failure) from None

    @staticmethod
    def _metadata(data):
        try:
            if not isinstance(data, dict) or not isinstance(data.get('data'), list):
                raise ValueError
            selected = [model for model in data['data'] if isinstance(model, dict) and model.get('id') == MODEL]
            if len(selected) != 1:
                raise ValueError
            model = selected[0]
            context = model.get('max_context_length')
            if (type(context) is not int or not 1 <= context <= 2**31 - 1
                    or not isinstance(model.get('capabilities'), dict)
                    or model['capabilities'].get('completion_chat') is not True):
                raise ValueError
            return context
        except (ValueError, TypeError):
            raise MistralBudgetError('metadata_unavailable') from None

    def _settle_billing(self, data, reservation):
        # Unknown fields may imply an unpriced charge. Do not invent SDK zeros or
        # canonical aliases, and never price visible characters as completion.
        # standard_only pins request pricing. The documented response has no
        # tier property; if an endpoint adds one it must explicitly be standard.
        allowed = {'id', 'object', 'created', 'model', 'choices', 'usage', 'service_tier', 'system_fingerprint'}
        if (not isinstance(data, dict) or set(data) - allowed or data.get('model') != MODEL
                or ('service_tier' in data and data['service_tier'] != 'standard')
                or not isinstance(data.get('usage'), dict)
                or set(data['usage']) != {'prompt_tokens', 'completion_tokens', 'total_tokens'}):
            raise MistralBudgetError('budget_uncertain')
        usage = data['usage']
        self._budget.settle(reservation, usage['prompt_tokens'], usage['completion_tokens'], usage['total_tokens'])

    @staticmethod
    def _output(data):
        try:
            choices = data.get('choices')
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError
            choice = choices[0]
            if (not isinstance(choice, dict) or type(choice.get('index')) is not int
                    or choice['index'] != 0 or choice.get('finish_reason') != 'stop'):
                raise ValueError
            message = choice.get('message')
            if (not isinstance(message, dict) or message.get('role') != 'assistant'
                    or set(message) - {'role', 'content', 'tool_calls'}
                    or message.get('tool_calls')):
                raise ValueError
            text = message.get('content')
            if (not isinstance(text, str) or not text.strip()
                    or len(text.encode('utf-8')) > _MAX_OUTPUT_BYTES
                    or not isinstance(_parse_json(text), dict)):
                raise ValueError
            return text
        except (ValueError, TypeError, RecursionError, UnicodeError):
            raise MistralBudgetError('response_invalid') from None

    def complete_json_guarded(self, messages, *, max_tokens, schema, before_send, still_permitted):
        payload = self._payload(messages, max_tokens, schema)
        reservation = None
        dispatched = settled = False
        try:
            self._check(still_permitted)
            self._admissible()
            with self._client() as client:
                self._check(still_permitted)
                self._admissible()
                if self._context_limit is None:
                    data = self._exchange(client, 'GET', '/models')
                    self._check(still_permitted)
                    self._admissible()
                    self._context_limit = self._metadata(data)
                self._check(still_permitted)
                reservation = self._budget.reserve(self._job_id, MODEL, self._context_limit, max_tokens,
                    budget_id=self._budget_id, revision=self._budget_revision, price_id=self._price_id)
                self._check(still_permitted)
                try:
                    before_send()
                except Exception:
                    raise MistralBudgetError('permission_changed') from None
                self._check(still_permitted)
                # A marker write can commit and then fail on acknowledgement.
                # Treat even that boundary as ambiguous rather than refunding.
                dispatched = True
                self._budget.dispatch(reservation)
                self._check(still_permitted)
                data = self._exchange(client, 'POST', '/chat/completions', payload)
                self._settle_billing(data, reservation)
                settled = True
                self._check(still_permitted)
                return Reply(text=self._output(data), model=MODEL)
        except Exception as error:
            if reservation is not None and not settled:
                try:
                    if dispatched:
                        self._budget.hold(reservation)
                    else:
                        self._budget.cancel_unsent(reservation)
                except Exception:
                    # A persisted dispatch marker remains outstanding even if a
                    # later disk write fails. It cannot be retried or refunded.
                    raise MistralBudgetError('budget_uncertain') from None
            if isinstance(error, MistralBudgetError):
                raise MistralBudgetError(error.code) from None
            raise MistralBudgetError('budget_uncertain' if dispatched else 'metadata_unavailable') from None
