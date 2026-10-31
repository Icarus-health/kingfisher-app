"""Begrenzte Lernvorschläge mit vorhandenen lokalen Gewichten.

Ollamas native Schnittstelle begrenzt den Kontext pro Aufruf. Das verändert
weder den Modellnamen noch den großen Kontext normaler Gespräche.
https://docs.ollama.com/api/chat
"""
from copy import copy, deepcopy
import json
import time
from urllib.parse import urlsplit, urlunsplit

import httpx

from .local_model_guard import verify_local_model
from .providers import OpenAICompatible, ProviderError, Reply, json_request_deadline, _json_transport_timeout


_TRIGGER_GUIDANCE = (
    '\nAuslöser beschreiben die Nutzertätigkeit oder den Auftrag, nicht die internen Prüfschritte. '
    'Für Zunftmail-Aufträge passen etwa zunftmail, zunftmails oder zunft; '
    'Anlass prüfen und Entwurf gegenlesen gehören in steps. '
    'Das Positivbeispiel ist eine gewöhnliche passende Nutzerbitte und enthält mindestens einen '
    'Auslöser sowie einen ausdrücklich genannten Anwendungskontext wörtlich, ohne Beugung oder Synonyme. '
    'Das Gegenbeispiel muss außerhalb dieses Anwendungsbereichs liegen. '
    'Nur die ursprüngliche Nutzeranweisung strukturieren; keine zusätzlichen Fakten oder Befugnisse ergänzen.'
)


def _allowed(provider):
    _json_transport_timeout(60.0)
    if (not getattr(provider, 'is_local', False)
            or not getattr(provider, '_verified_local_permitted', lambda: True)()):
        raise ProviderError('Die lokale Lernbitte ist nicht mehr freigegeben oder aktuell.')


def _instructions(messages, guidance):
    result = deepcopy(messages)
    if result and result[0].get('role') == 'system':
        result[0]['content'] += guidance
    else:
        result.insert(0, {'role':'system', 'content':guidance})
    return result


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


def draft(provider, messages, schema, *, permitted=None):
    from .procedures import ProcedureError, Spec, validate
    if schema != Spec.model_json_schema():
        return _draft_once(provider, messages, schema)
    # Eine lokale Kopie erhält die zusätzliche Quellbindung. Bestehende
    # Freigabeprüfungen bleiben erhalten; der genaue Anbietertyp bleibt gleich.
    local = copy(provider)
    previous = getattr(provider, '_verified_local_permitted', lambda: True)
    local._verified_local_permitted = lambda: (
        bool(getattr(provider, 'is_local', False)) and previous()
        and (permitted is None or permitted()))
    original = _instructions(messages, _TRIGGER_GUIDANCE)
    attempt = original
    # Beide Versuche teilen das bisherige 60s-Budget. Eine schon laufende
    # engere Anfragefrist wird durch json_request_deadline nicht verlängert.
    with json_request_deadline(time.monotonic() + 60.0):
        for number in range(2):
            _allowed(local)
            response = _draft_once(local, attempt, schema)
            _allowed(local)
            if getattr(response, 'tool_calls', None):
                raise ProviderError('Werkzeugaufrufe sind keine Ablaufbeschreibung.')
            try:
                validate(json.loads(response.text))
                return response
            except json.JSONDecodeError:
                reason = 'Die Antwort war kein gültiges JSON.'
            except ProcedureError:
                reason = ('Die Antwort erfüllt die Struktur- und Anwendungsprüfung nicht. '
                          'Prüfe besonders Auslöser, den wörtlichen Auslöser im Positivbeispiel, '
                          'den ausdrücklichen Kontext und das abgegrenzte Gegenbeispiel.')
            if number:
                raise ProcedureError('Der Ablauf konnte auch nach einer begrenzten Korrektur nicht geprüft werden.')
            # Nur ein fester lokaler Validierungsgrund, nie rohe Modellausgabe
            # als neue Anweisung. Nutzertext, Schema und Transport bleiben gleich.
            attempt = _instructions(original, '\nValidierungsprüfung: ' + reason
                                    + ' Korrigiere genau einmal den Ablauf zur ursprünglichen Nutzeranweisung.')


def _draft_once(provider, messages, schema):
    _allowed(provider)
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
    _allowed(provider)
    local = copy(provider)
    local._verified_local_transport = True
    base = urlsplit(local.base_url)
    origin = urlunsplit((base.scheme, base.netloc, '', '', ''))
    try:
        with local._ampel():
            if verify_local_model(local) != identity:
                raise ProviderError('Die lokalen Gewichte haben sich geändert.')
            _allowed(local)
            with local._client(_json_transport_timeout(60.0)) as client:
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
            _allowed(local)
    except (httpx.HTTPError, ValueError) as exc:
        raise ProviderError('Das lokale Modell konnte den Lernvorschlag gerade nicht erstellen.') from exc
    message = data.get('message') if isinstance(data, dict) else None
    if (not isinstance(message, dict) or not isinstance(message.get('content'), str)
            or message.get('tool_calls') or data.get('done') is not True
            or data.get('done_reason') not in (None, 'stop')):
        raise ProviderError('Das lokale Modell hat keinen vollständigen Ablaufvorschlag geliefert.')
    return Reply(text=message['content'], model=local.model)
