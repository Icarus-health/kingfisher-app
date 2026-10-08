"""Constrain time hints before generation without accepting invented time scopes."""
import json
from copy import deepcopy

import httpx
import pytest

from icarus_memory.frage import SCHEMA, verstehen
from icarus_memory.providers import OpenAICompatible


def local_model(monkeypatch, calls, *, ignore_schema=False):
    def respond(request):
        payload = json.loads(request.content)
        schema = payload['response_format']['json_schema']['schema']
        allowed = schema['properties']['zeitraum']['enum']
        # Reproduce the real model's tendency to add 'heute', if the grammar
        # permits it. The product validator must still reject noncompliance.
        period = 'heute' if ignore_schema else next((v for v in allowed if v != 'keiner'), 'keiner')
        calls.append(deepcopy(schema))
        result = {'sachen': ['Mainz'], 'zeitraum': period, 'absicht': 'ueberblick',
                  'suchworte': ['Mainz'], 'umschreibungen': ['Projekt']}
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop',
            'message': {'content': json.dumps(result)}}]})
    provider = OpenAICompatible('synthetic', base_url='http://127.0.0.1:11439/v1')
    monkeypatch.setattr(provider, '_client', lambda timeout: httpx.Client(
        transport=httpx.MockTransport(respond), timeout=timeout, trust_env=False))
    return provider


@pytest.mark.parametrize('question,expected', [
    ('Was ist mit Mainz los?', None),
    ('Was war gestern mit Mainz?', 'gestern'),
    ('Was war vorige Woche mit Mainz?', 'letzte_woche'),
])
def test_time_grammar_keeps_valid_search_expansion(monkeypatch, question, expected):
    calls = []
    result = verstehen(question, local_model(monkeypatch, calls))
    assert result.herkunft == 'modell'
    assert result.zeitraum == expected
    assert result.umschreibungen == ('Projekt',)
    assert calls[0]['properties']['zeitraum']['enum'] == ['keiner'] + ([expected] if expected else [])


def test_question_specific_time_schema_does_not_leak_between_requests(monkeypatch):
    before = deepcopy(SCHEMA)
    calls = []
    provider = local_model(monkeypatch, calls)
    for question in ('Was war gestern mit Mainz?', 'Was ist mit Mainz los?', 'Was ist heute mit Mainz?'):
        verstehen(question, provider)
    assert [s['properties']['zeitraum']['enum'] for s in calls] == [
        ['keiner', 'gestern'], ['keiner'], ['keiner', 'heute']]
    assert SCHEMA == before


def test_noncompliant_time_output_still_falls_back(monkeypatch):
    calls = []
    result = verstehen('Was ist mit Mainz los?', local_model(monkeypatch, calls, ignore_schema=True))
    assert result.herkunft == 'rueckfall'
    assert result.zeitraum is None
    assert result.grund == 'ungültige Ausgabe'
