"""A stated cutoff must not acquire an unsupported calendar start boundary."""
from datetime import datetime, timezone

import pytest

from icarus_memory.satzpruefung import Beleg, Satz, satz_pruefen


SOURCE = ('Die Frist für die Druckdaten wurde geändert: Statt dem 2. November '
          'gilt jetzt der 4. November 2026 um 18 Uhr.')
TITLE = 'Projekt Atlas: Druckdatenfrist geändert'


def check(source, answer, *, title=TITLE):
    return satz_pruefen(Satz(answer, ('1',)), {
        '1': Beleg('1', source, datetime(2026, 10, 30, 10, tzinfo=timezone.utc), title),
    })


def test_observed_deadline_does_not_become_start_of_validity():
    # Exact source and model sentence from fresh synthetic run c, q03/m02.
    answer = 'Die Frist für die Druckdaten von Projekt Atlas gilt ab dem 4. November 2026 um 18 Uhr.'
    result = check(SOURCE, answer)
    assert not result.bestanden, result
    assert any('Datumsgrenze' in reason for reason in result.gruende)


@pytest.mark.parametrize('boundary', ['ab', 'erst ab', 'seit', 'nach'])
def test_neutral_deadline_does_not_support_new_start_bound(boundary):
    result = check('Die Einreichfrist ist der 4. November 2026.',
                   f'Die Einreichfrist gilt {boundary} dem 04.11.2026.')
    assert not result.bestanden, result
    assert any('Datumsgrenze' in reason for reason in result.gruende)


def test_header_cannot_supply_deadline_start_bound():
    result = check('Die Frist ist der 4. November 2026.',
                   'Die Frist gilt ab dem 04.11.2026.', title='Die Frist gilt ab dem 04.11.2026.')
    assert not result.bestanden, result
    assert any('Datumsgrenze' in reason for reason in result.gruende)


@pytest.mark.parametrize('source,answer', [
    (SOURCE, 'Die Frist für die Druckdaten von Projekt Atlas ist der 4. November 2026 um 18 Uhr.'),
    (SOURCE, 'Die Frist für die Druckdaten von Projekt Atlas gilt am 04.11.2026 um 18 Uhr.'),
    ('Die Einreichfrist ist der 4. November 2026.', 'Die Einreichfrist ist der 04.11.2026.'),
    ('Die Frist gilt ab dem 4. November 2026.', 'Die Frist gilt ab 04.11.2026.'),
    ('Die Frist gilt erst ab dem 4. November 2026.', 'Die Frist gilt ab 04.11.2026.'),
    ('Die Frist gilt seit dem 4. November 2026.', 'Die Frist gilt seit 04.11.2026.'),
    ('Die Frist gilt nach dem 4. November 2026.', 'Die Frist gilt nach 04.11.2026.'),
    ('Die Lizenz gilt ab dem 4. November 2026.', 'Die Lizenz gilt ab 04.11.2026.'),
])
def test_neutral_deadline_and_explicit_start_conditions_remain_usable(source, answer):
    result = check(source, answer)
    assert result.bestanden, result.gruende
