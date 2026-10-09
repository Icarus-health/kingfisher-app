"""Distinct reported statuses must be checked in their own answer sentences."""
from datetime import datetime, timezone

import pytest

from icarus_memory import satzantwort as sa
from icarus_memory.satzpruefung import Satz

NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)
RULE = ('Bei Z-204 darf die Lieferung erst nach schriftlicher Zustimmung versandt werden. '
        'Die Zustimmung liegt noch nicht vor.')


def check(source, text):
    evidence = sa.AntwortBeleg(1, {}, 'status', 'source-1', 'Sachstand', '', source, None)
    return sa.pruefe_satz(Satz(text, ('1',)), {'1': evidence}, NOW)


def test_an_atomic_original_rule_and_negative_status_do_not_contradict_themselves():
    result = check(RULE, RULE)
    assert result.bestanden, result.gruende


@pytest.mark.parametrize('text', [
    'Die Lieferung Z-204 wurde versandt. Die Rechnung R-719 ist noch offen.',
    'Die Rechnung R-719 ist noch offen. Die Lieferung Z-204 wurde versandt.',
])
def test_each_exact_current_status_is_kept_with_its_own_subject(text):
    result = check(text, text)
    assert result.bestanden, result.gruende


@pytest.mark.parametrize('text', [
    'Die Lieferung Z-204 ist noch offen. Die Rechnung R-719 wurde bezahlt.',
    'Die Lieferung Z-204 wurde versandt. Die Rechnung R-719 wurde bezahlt.',
])
def test_status_of_another_subject_cannot_support_a_false_status(text):
    source = 'Die Lieferung Z-204 wurde versandt. Die Rechnung R-719 ist noch offen.'
    result = check(source, text)
    assert not result.bestanden
    assert any('Beleg sagt' in reason or 'Aussage' in reason or 'Verneinung' in reason for reason in result.gruende)


def test_selected_rule_still_cannot_omit_its_condition():
    result = check(RULE, 'Bei Z-204 darf die Lieferung versandt werden.')
    assert not result.bestanden
