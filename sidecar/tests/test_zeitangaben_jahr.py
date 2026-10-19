"""Mehr Zeitangaben: letztes und dieses Jahr, vor N Tagen/Wochen/Monaten, die letzten N Monate.

Zusicherungen:
1. Die Angaben werden als Zeitraum erkannt, mit einer Beschriftung für Menschen.
2. Die Wörter des Zeitraums sind keine Suchwörter („letztes“, „Jahr“).
3. Ein Zeitraum sucht zusätzlich unter seinen Quellen: Eine alte Quelle kommt auch dann nach vorn, wenn viele
   neuere dasselbe Wort tragen. Ausgeschlossen wird nichts.
"""
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeStore
from icarus_memory.time_scope import mentioned_period, ohne_zeitraum
from icarus_memory.working_memory_answers import prepare, render
from tests.test_answer_time_scope import NOW, Selector, _mail


@pytest.mark.parametrize('question,expected', [
    ('Was war letztes Jahr mit der Akademie?', ('2025-01-01', '2026-01-01', 'des Jahres 2025')),
    ('Was war im Vorjahr mit der Akademie?', ('2025-01-01', '2026-01-01', 'des Jahres 2025')),
    ('Was hat Silke dieses Jahr geschrieben?', ('2026-01-01', '2026-09-27', 'des Jahres 2026')),
    ('Was schrieb Ben vor zwei Wochen?', ('2026-09-07', '2026-09-14', 'der Woche ab 7. September')),
    ('Was kam vor 3 Tagen von der Stiftung?', ('2026-09-23', '2026-09-24', 'vom 23. September')),
    ('Was war vor einem Monat?', ('2026-08-01', '2026-09-01', 'aus dem August 2026')),
    ('Welche Rechnungen kamen in den letzten drei Monaten?', ('2026-06-29', '2026-09-27', 'der letzten 3 Monate')),
    ('Was kam nicht letztes Jahr, sondern dieses Jahr?', ('2026-01-01', '2026-09-27', 'des Jahres 2026')),
    ('Wann treffen wir uns in zwei Wochen?', None),
    ('Was steht im Jahresbericht?', None),
    ('Wann ist der Termin vor dem Workshop?', None),
])
def test_neue_zeitangaben(question, expected):
    found = mentioned_period(question, NOW)
    assert (None if found is None else (str(found[0].date()), str(found[1].date()), found[2])) == expected


def test_zeitwoerter_sind_keine_suchwoerter():
    assert ohne_zeitraum('Was war letztes Jahr mit der Akademie?').split() == ['Was', 'war', 'mit', 'der', 'Akademie?']
    # Bleibt nichts übrig, gilt die Frage unverändert.
    assert ohne_zeitraum('Was war letzte Woche?') == 'Was war letzte Woche?'


@pytest.fixture
def akademie(tmp_path, monkeypatch):
    episodes = EpisodeStore(tmp_path / 'e.sqlite3')
    claims = ClaimStore(tmp_path / 'k.sqlite3')
    neu = [_mail(episodes, f'Akademie Rundbrief {n}: Termine im Jahr, letztes Treffen, neues Jahr.',
                 NOW - timedelta(days=1 + n)) for n in range(70)]
    alt = _mail(episodes, 'Die Akademie hat die Rechnung für den Kurs bezahlt.', datetime(2025, 5, 12, tzinfo=timezone.utc))
    monkeypatch.setattr('icarus_memory.time_scope.datetime',
                        type('Fixed', (datetime,), {'now': classmethod(lambda cls, tz=None: NOW)}))
    yield episodes, claims, alt, neu
    claims.close()
    episodes.close()


def test_letztes_jahr_findet_die_alte_quelle_trotz_vieler_neuer(akademie):
    episodes, claims, alt, neu = akademie
    ohne = prepare('Was war mit der Akademie?', episodes, claims, Selector())
    assert alt not in {ref['episode_id'] for ref in ohne['basis']}
    antwort = prepare('Was war letztes Jahr mit der Akademie?', episodes, claims, Selector())
    basis = [ref['episode_id'] for ref in antwort['basis']]
    assert basis[0] == alt and antwort['time_label'] == 'des Jahres 2025'
    # Nichts ausgeschlossen: Die neueren Quellen bleiben Kandidaten.
    assert set(neu) & set(basis)
    text, _, _ = render(antwort, episodes, claims)
    assert 'Zuerst berücksichtigt: Quellen des Jahres 2025.' in text
