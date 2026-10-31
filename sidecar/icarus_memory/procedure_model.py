"""Begrenzte Lernvorschläge mit vorhandenen lokalen Gewichten.

Ollamas native Schnittstelle begrenzt den Kontext pro Aufruf. Das verändert
weder den Modellnamen noch den großen Kontext normaler Gespräche.
https://docs.ollama.com/api/chat
"""
from copy import copy
import json
from urllib.parse import urlsplit, urlunsplit

import httpx

from .local_model_guard import verify_local_model
from .providers import OpenAICompatible, ProviderError, Reply


def local_context_allowed(provider):
    if not getattr(provider, 'is_local', False):
        return False
    if type(provider) is OpenAICompatible:
        try:
            verify_local_model(provider)
        except ProviderError:
            return False
    # Eingebettete Anbieter erfüllen wie bisher den expliziten Providervertrag.
    # Konfigurierbare OpenAI-/Ollama-URLs werden oben unabhängig geprüft.
    return True


def draft(provider, messages, schema):
    if type(provider) is not OpenAICompatible:
        if hasattr(provider, 'complete_json'):
            return provider.complete_json(messages, max_tokens=1200, schema=schema)
        return provider.complete(messages, [])
    from .local_context_profile import selected
    if selected(provider):
        # Dasselbe endgültige Nachrichten-/Schemabudget und dieselben
        # Nicht-Kürzen-Flags wie alle Aufrufe des ausdrücklich gewählten Profils.
        return provider.complete_json(messages,max_tokens=1200,schema=schema)
    if len(json.dumps(messages, ensure_ascii=False).encode()) > 16000:
        raise ProviderError('Die Lernbitte ist für diesen kleinen Kontext zu lang.')
    identity = verify_local_model(provider)
    local = copy(provider)
    local._verified_local_transport = True
    base = urlsplit(local.base_url)
    origin = urlunsplit((base.scheme, base.netloc, '', '', ''))
    try:
        with local._ampel():
            if verify_local_model(local) != identity:
                raise ProviderError('Die lokalen Gewichte haben sich geändert.')
            with local._client(60.0) as client:
                response = client.post(origin + '/api/chat', json={
                    'model':local.model, 'messages':messages, 'format':schema,
                    'stream':False, 'think':False,
                    'options':{'num_ctx':8192, 'num_predict':1200, 'temperature':0},
                    'keep_alive':0 if local.model.startswith('kingfisher-') else '15s',
                })
                response.raise_for_status()
                data = response.json()
            if verify_local_model(local) != identity:
                raise ProviderError('Die lokalen Gewichte haben sich geändert.')
    except (httpx.HTTPError, ValueError) as exc:
        raise ProviderError('Das lokale Modell konnte den Lernvorschlag gerade nicht erstellen.') from exc
    message = data.get('message') if isinstance(data, dict) else None
    if (not isinstance(message, dict) or not isinstance(message.get('content'), str)
            or message.get('tool_calls') or data.get('done') is not True
            or data.get('done_reason') not in (None, 'stop')):
        raise ProviderError('Das lokale Modell hat keinen vollständigen Ablaufvorschlag geliefert.')
    return Reply(text=message['content'], model=local.model)
