"""Begrenzter direkter Claude-API-Zugang ausschließlich für freigegebene Quellen."""
from __future__ import annotations

import hashlib
import hmac
import json
import os

import httpx

from .providers import ProviderError, Reply
from .secrets import KeychainError
from .cloud_credentials import PREPARED_CLOUD_KEYS

REVISION_KEY = 'CLOUD_IMPORT_ANTHROPIC_REVISION'
ENDPOINT = 'https://api.anthropic.com/v1'


def _strict_schema(schema):
    """Copy to Anthropic's supported grammar subset, retaining caller validators.

    Array sizes, string lengths and numerical ranges are checked by the existing
    source validators. Sending these unsupported keywords with strict=true
    causes rejection before inference. Property names are data, not keywords.
    """
    unsupported = {'minLength', 'maxLength', 'minimum', 'maximum', 'exclusiveMinimum',
                   'exclusiveMaximum', 'multipleOf', 'maxItems', 'uniqueItems',
                   'minProperties', 'maxProperties'}
    result = {}
    for key, value in schema.items():
        if key in unsupported or (key == 'minItems' and value not in (0, 1)):
            continue
        if key in {'properties', '$defs', 'definitions'}:
            result[key] = {name: _strict_schema(child) for name, child in value.items()}
        elif isinstance(value, dict):
            result[key] = _strict_schema(value)
        elif key in {'anyOf', 'allOf', 'oneOf', 'prefixItems'} and isinstance(value, list):
            result[key] = [_strict_schema(child) for child in value]
        else:
            result[key] = value
    return result


def credential_status(keychain, settings, environment=None):
    """Undurchsichtige Freigabefassung; weder Schlüssel noch Schlüsselhash ausgeben."""
    unavailable = {'available': False, 'credential_revision': None, 'model': ''}
    if keychain is None or not keychain.available:
        return unavailable
    environment = os.environ if environment is None else environment
    try:
        stored = keychain.get(PREPARED_CLOUD_KEYS['anthropic'])
        salt = keychain.get(REVISION_KEY)
    except KeychainError:
        return unavailable
    active = environment.get(PREPARED_CLOUD_KEYS['anthropic'])
    model = settings.cloud_models.get('anthropic', '')
    if not stored or not salt or not model or not active or not hmac.compare_digest(stored, active):
        return unavailable
    revision = hmac.new(salt.encode(), json.dumps([active, model]).encode(), hashlib.sha256).hexdigest()
    return {'available': True, 'credential_revision': revision, 'model': model}


class AnthropicImportProvider:
    """Ein einzelner gezählter Aufruf, ohne Umleitung, Wiederholung oder Ausweichanbieter."""
    name = 'anthropic'
    is_local = False
    is_remote = True
    entity_anchor_mode = 'block_quote'

    def __init__(self, model, api_key, credential_revision, current_revision):
        self.model = model
        self._key = api_key
        self.credential_revision = credential_revision
        self._current_revision = current_revision

    def available(self):
        return bool(self.credential_revision and self._current_revision() == self.credential_revision)

    def _client(self):
        return httpx.Client(timeout=90, trust_env=False, follow_redirects=False)

    def complete_json_guarded(self, messages, *, max_tokens, schema, before_send, still_permitted):
        if type(max_tokens) is not int or not 64 <= max_tokens <= 1200 or not isinstance(schema, dict):
            raise ProviderError('Ungültiges Auswertungsbudget oder Ausgabeschema.')
        system = '\n'.join(m['content'] for m in messages if m.get('role') == 'system')
        payload = {
            'model': self.model, 'max_tokens': max_tokens,
            'messages': [m for m in messages if m.get('role') != 'system'],
            'tools': [{'name': 'memory_result', 'description': 'Quellengebundene Einordnung als JSON.',
                       'strict': True, 'input_schema': _strict_schema(schema)}],
            'tool_choice': {'type': 'tool', 'name': 'memory_result'},
        }
        if system:
            payload['system'] = system
        try:
            with self._client() as client:
                if not still_permitted() or not self.available():
                    raise ProviderError('Die Freigabe oder der API-Zugang hat sich geändert.')
                before_send()
                if not still_permitted() or not self.available():
                    raise ProviderError('Die Freigabe oder der API-Zugang hat sich geändert.')
                response = client.post(ENDPOINT + '/messages', json=payload,
                                       headers={'x-api-key': self._key, 'anthropic-version': '2023-06-01',
                                                'content-type': 'application/json'})
                if response.status_code == 429:
                    raise ProviderError('Anfragelimit erreicht (429).')
                if response.status_code in {401, 403}:
                    raise ProviderError('API-Anmeldung ungültig.')
                if not 200 <= response.status_code < 300:
                    raise ProviderError('Der API-Anbieter hat die Anfrage abgelehnt.')
                data = response.json()
        except httpx.HTTPError:
            raise ProviderError('API-Verbindung unterbrochen.') from None
        except (ValueError, TypeError):
            raise ProviderError('Ungültiges API-Antwortformat.') from None
        if not isinstance(data, dict) or not isinstance(data.get('content'), list):
            raise ProviderError('Ungültiges API-Antwortformat.')
        blocks = data['content']
        results = [block for block in blocks if isinstance(block, dict) and block.get('type') == 'tool_use']
        if (data.get('stop_reason') != 'tool_use' or len(results) != 1
                or results[0].get('name') != 'memory_result' or not isinstance(results[0].get('input'), dict)):
            raise ProviderError('Die API hat keine vollständige strukturierte Einordnung geliefert.')
        return Reply(text=json.dumps(results[0]['input'], ensure_ascii=False), model=self.model)
