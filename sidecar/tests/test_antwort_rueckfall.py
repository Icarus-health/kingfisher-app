"""Befund A1: Fällt eine Antwort auf die Quellen zurück, liest sie sich als Sätze, nicht als Rohliste mit Fachwörtern.

Vorher stand da „Quelle berichtet · automatisch eingeordnet“, „Angabe · Einladung … · neueste Quelle“ und
„Quellenzeit: 23.10.2026, 20:48 Uhr“. Jetzt sagt ein Satz, dass hier die Quellen sprechen, und jede Quelle heißt so,
wie ein Mensch sie nennt. Der Wortlaut der Quelle bleibt unverändert und vollständig.
"""
from datetime import datetime, timezone

from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.working_memory_answers import ZITAT_EINLEITUNG, prepare, render
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_memory_project_names import Selector, stores  # noqa: F401 - Fixture

EINLADUNG = ('Liebe Helga,\n\nhiermit lade ich dich herzlich zur nächsten Vorstandssitzung ein: am Donnerstag, '
             '29. Oktober, um 18 Uhr im Vereinsheim.\n\nHerzliche Grüße\nErika')
FACHWOERTER = ('Quelle berichtet', 'Quellenzeit', 'automatisch eingeordnet', 'Angabe ·', '· neueste Quelle',
               'Erfasst:')


def _mail(episodes, titel, text, wann, kind='fact'):
    episode, _ = episodes.record(EpisodeKind.MESSAGE, titel, text, Provenance(SourceType.EMAIL),
                                 participants=['Erika Schulte <erika@gartenfreunde.example>'], occurred_at=wann)
    assert WorkingMemoryStore(episodes).commit(
        episodes.support_snapshot(episode.id), [{'start': 0, 'end': len(text), 'kind': kind}], model='t')
    return episode


def test_rueckfall_ist_ein_lesbarer_satz_mit_dem_wortlaut(stores):  # noqa: F811
    episodes, claims = stores
    _mail(episodes, 'Einladung zur Vorstandssitzung', EINLADUNG, datetime(2026, 10, 23, 18, 48, tzinfo=timezone.utc))
    _mail(episodes, 'Vorstandssitzung: Raum', 'Die Vorstandssitzung ist im kleinen Raum.',
          datetime(2026, 10, 24, 9, 0, tzinfo=timezone.utc), kind='request')
    answer = prepare('Wann ist die Vorstandssitzung?', episodes, claims, Selector())
    text, links, status = render(answer, episodes, claims)
    assert status == 'working_reports'
    zeilen = text.splitlines()
    assert zeilen[0] == ZITAT_EINLEITUNG == 'So steht es in deinen Quellen:'
    for wort in FACHWOERTER:
        assert wort not in text, f'{wort!r} ist ein Fachwort im Rückfall'
    assert 'E-Mail „Vorstandssitzung: Raum“ von Erika Schulte vom 24. Oktober 2026, 11:00 Uhr, die neueste (darin: Bitte):' in zeilen
    assert 'E-Mail „Einladung zur Vorstandssitzung“ von Erika Schulte vom 23. Oktober 2026, 20:48 Uhr:' in zeilen
    assert EINLADUNG in text, 'Der Wortlaut der Quelle bleibt vollständig'
    assert [link['label'] for link in links] == ['Quelle 1 öffnen', 'Quelle 2 öffnen']
