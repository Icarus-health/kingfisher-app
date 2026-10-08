"""Conditional evidence: select source clauses, never ask the model to copy them."""
import json
from datetime import datetime, timezone

import pytest

from icarus_memory import satzantwort as sa
from icarus_memory.providers import Reply

NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)
RULE = 'Lösungsmittel dürfen erst nach schriftlicher Freigabe verwendet werden.'
CLEAN = 'Reinigung: Vor dem Aushärten die Dichtung ausschließlich trocken abwischen.'


def evidence(text=RULE + ' ' + CLEAN, **kwargs):
    return sa.AntwortBeleg(1, {}, 'fact', 'source-1', 'Anweisung', '', text, None, **kwargs)


class Selector:
    is_local = True
    name = model = 'synthetic-selector'

    def __init__(self, output):
        self.output = output
        self.messages = []

    def complete_json(self, messages, **kwargs):
        self.messages.append((messages, kwargs))
        data = json.loads(messages[-1]['content'])
        output = self.output(data) if callable(self.output) else self.output
        return Reply(text=json.dumps(output))


def choose(data):
    source = data['belege'][0]
    selected = next(s for s in source['originalsaetze'] if s['text'] == CLEAN)
    return {'status': 'antwort', 'originalstellen': [{'beleg': source['nr'], 'satz': selected['nr']}]}


def test_selected_original_is_resolved_by_code_and_still_checked():
    provider = Selector(choose)
    result = sa.formulieren('Wie soll die Dichtung gereinigt werden?', [evidence()], provider, jetzt=NOW)
    assert result.status == 'saetze'
    assert [s.text for s in result.saetze] == [CLEAN]
    assert result.saetze[0].belege == (1,)
    assert len(provider.messages) == 1
    payload = json.loads(provider.messages[0][0][-1]['content'])
    assert 'text' not in payload['belege'][0], 'Do not duplicate source context'
    assert 'originalstellen' in provider.messages[0][1]['schema']['properties']


def test_original_condition_and_colon_header_are_never_reconstructed():
    source = 'Rückgabe: ' + RULE
    provider = Selector({'status': 'antwort', 'originalstellen': [{'beleg': 1, 'satz': 1}]})
    result = sa.formulieren('Wann dürfen Lösungsmittel verwendet werden?', [evidence(source)], provider, jetzt=NOW)
    assert result.status == 'saetze'
    assert [s.text for s in result.saetze] == [source]


@pytest.mark.parametrize('selection', [
    [{'beleg': 2, 'satz': 1}], [{'beleg': 1, 'satz': 999}],
    [{'beleg': True, 'satz': 1}], [{'beleg': 1, 'satz': True}],
    [{'beleg': 1, 'satz': 1, 'text': 'Die Freigabe liegt vor.'}],
    [{'beleg': 1, 'satz': 1}] * 2,
])
def test_invalid_selections_fail_closed(selection):
    result = sa.formulieren('Wann?', [evidence()],
                            Selector({'status': 'antwort', 'originalstellen': selection}), jetzt=NOW)
    assert result.status == 'zitate'


def test_hidden_full_source_is_not_offered_and_partial_excerpt_is_not_a_clause():
    full = RULE + ' ' + CLEAN
    excerpt = 'nach schriftlicher Freigabe verwendet werden. […] ' + CLEAN
    provider = Selector(lambda data: {'status': 'unklar', 'originalstellen': []})
    sa.formulieren('Wann?', [evidence(excerpt, pruef_text=full, gekuerzt=True)], provider, jetzt=NOW)
    payload = json.loads(provider.messages[0][0][-1]['content'])
    assert payload['belege'][0]['originalsaetze'] == [{'nr': 1, 'text': CLEAN}]
    assert RULE not in json.dumps(payload, ensure_ascii=False)


def test_selected_exact_text_does_not_bypass_negation_gate():
    source = 'Nach der Abnahme darf die Steuerung nicht zurückgesetzt werden. '
    source += 'Ein Zurücksetzen nach der Abnahme ist nur zulässig, wenn die Technikerin es schriftlich anordnet.'
    provider = Selector({'status': 'antwort', 'originalstellen': [{'beleg': 1, 'satz': 2}]})
    result = sa.formulieren('Ist ein Zurücksetzen erlaubt?', [evidence(source)], provider, jetzt=NOW)
    assert result.status == 'zitate'
    assert result.verworfen


def test_ordinary_evidence_keeps_existing_text_contract():
    provider = Selector({'status': 'antwort', 'saetze': [{'text': 'Der Bericht liegt im Tresor.', 'belege': [1]}]})
    result = sa.formulieren('Wo liegt der Bericht?', [evidence('Der Bericht liegt im Tresor.')], provider, jetzt=NOW)
    assert result.status == 'saetze'
    payload = json.loads(provider.messages[0][0][-1]['content'])
    assert payload['belege'][0]['text'] == 'Der Bericht liegt im Tresor.'
    assert 'originalsaetze' not in payload['belege'][0]


def test_legacy_text_output_does_not_bypass_literal_condition_gate():
    provider = Selector({'status': 'antwort', 'saetze': [{'text': 'Lösungsmittel dürfen verwendet werden.', 'belege': [1]}]})
    result = sa.formulieren('Wann?', [evidence()], provider, jetzt=NOW)
    assert result.status == 'zitate'
