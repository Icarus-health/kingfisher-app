"""Vollständige begrenzte Quellenauswahl für explizit budgetfähige lokale Profile."""
from copy import deepcopy
import json
import time

from . import absatzauswahl
from .providers import ProviderError, json_request_deadline, _json_transport_timeout

MAX_PAGES = 4
SECONDS = 60.0
_UNCLEAR = frozenset(('person', 'scope', 'time', 'conflict'))


def _request(question, rows, instruction, schema):
    projected = absatzauswahl.modell_zeilen(rows)
    if absatzauswahl.hat_modellkopien(projected):
        instruction += '\n' + absatzauswahl.KOPIERHINWEIS
    page_schema = deepcopy(schema)
    page_schema['properties']['ids']['items']['enum'] = [row['id'] for row in rows]
    return [{'role': 'system', 'content': instruction}, {'role': 'user', 'content': json.dumps(
        {'question': question, 'sources': projected}, ensure_ascii=False, separators=(',', ':'))}], page_schema


def _decode(reply, rows, decisions, *, consistent=False):
    if reply.tool_calls or not isinstance(reply.text, str) or len(reply.text) > 8000:
        raise ValueError('Ungültige Auswahl')
    selection = json.loads(reply.text)
    if isinstance(selection, dict) and isinstance(selection.get('status'), str):
        selection['status'] = decisions.get(selection['status'], selection['status'])
    if (not isinstance(selection, dict) or set(selection) != {'status', 'ids'}
            or selection['status'] not in {'reports', 'unknown', *_UNCLEAR}
            or not isinstance(selection['ids'], list)
            or any(not isinstance(i, str) for i in selection['ids'])
            or len(set(selection['ids'])) != len(selection['ids'])):
        raise ValueError('Ungültige Auswahl')
    if any(identifier not in {row['id'] for row in rows} for identifier in selection['ids']):
        raise ValueError('Unbekannte Referenz')
    if consistent and ((selection['status'] == 'unknown') != (not selection['ids'])):
        raise ValueError('Inkonsistente Seitenauswahl')
    return selection


def select(provider, question, rows, instruction, schema, decisions, *, fresh):
    """Keine Teilantwort: alle Seiten und nötiger Gesamtvergleich müssen gelingen.

    Anbieter ohne ausdrücklich aktive Vorschau behalten genau einen Aufruf.
    Die vorhandenen globalen fachlichen Prüfungen laufen beim Aufrufer danach.
    """
    messages, original_schema = _request(question, rows, instruction, schema)
    bounded = getattr(provider, 'complete_json', None)

    def call(page, request, *, paged=False):
        if paged:
            _json_transport_timeout(SECONDS)
            if not fresh():
                raise ProviderError('Die Grundlage der Quellenauswahl hat sich verändert.')
            _json_transport_timeout(SECONDS)
        msgs, page_schema = request
        reply = bounded(msgs, max_tokens=256, schema=page_schema) if callable(bounded) else provider.complete(msgs, [])
        if paged:
            _json_transport_timeout(SECONDS)
        return _decode(reply, page, decisions, consistent=paged)

    preview = getattr(provider, 'can_complete_json', None) if getattr(provider, 'is_local', False) else None
    fits = preview(messages, max_tokens=256, schema=original_schema) if callable(preview) else None
    if fits is not False:
        return call(rows, (messages, original_schema))

    with json_request_deadline(time.monotonic() + SECONDS):
        # Erst den gesamten Kandidatenbestand einplanen, bevor Quellen versendet
        # werden. Auf jeder Seite Kopien neu aus den Originalzeilen berechnen.
        pages, page = [], []
        for row in rows:
            candidate = [*page, row]
            request = _request(question, candidate, instruction, schema)
            if preview(request[0], max_tokens=256, schema=request[1]) is True:
                page = candidate
                continue
            if not page:
                raise ProviderError('Eine vollständige Quelle überschreitet das lokale Auswahlbudget. Bitte enger fragen.')
            pages.append(page)
            page = [row]
            request = _request(question, page, instruction, schema)
            if preview(request[0], max_tokens=256, schema=request[1]) is not True:
                raise ProviderError('Eine vollständige Quelle überschreitet das lokale Auswahlbudget. Bitte enger fragen.')
        if page:
            pages.append(page)
        if len(pages) > MAX_PAGES:
            raise ProviderError('Die vollständige Auswahl braucht zu viele Seiten. Bitte enger fragen.')
        selections = [call(page, _request(question, page, instruction, schema), paged=True) for page in pages]
        positive = [selection for selection in selections if selection['ids']]
        if not positive:
            return {'status': 'unknown', 'ids': []}
        if len(positive) == 1:
            return positive[0]
        chosen = {identifier for selection in positive for identifier in selection['ids']}
        union = [row for row in rows if row['id'] in chosen]
        final_request = _request(question, union, instruction, schema)
        if preview(final_request[0], max_tokens=256, schema=final_request[1]) is not True:
            raise ProviderError('Der vollständige Quellenvergleich passt nicht ins lokale Auswahlbudget. Bitte enger fragen.')
        final = call(union, final_request, paged=True)
        unclear = {selection['status'] for selection in [*positive, final] if selection['status'] in _UNCLEAR}
        if len(unclear) > 1:
            raise ProviderError('Ungeklärte Seitenauswahl darf nicht durch den Gesamtvergleich verschwinden.')
        if unclear:
            # Kein Mehrheitsentscheid über eine offene Frage. Alle auf den
            # Seiten gewählten Belege bleiben Grundlage der einen Rückfrage.
            # Nur intern: Modellantworten dürfen diese Marke nicht liefern.
            return {'status': next(iter(unclear)), 'ids': [row['id'] for row in union],
                    '_page_uncertainty': True}
        return final
