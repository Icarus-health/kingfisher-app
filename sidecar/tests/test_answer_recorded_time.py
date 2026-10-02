"""Ohne eigenen Zeitpunkt nennt die Antwort, wann die Quelle erfasst wurde — nicht mehr."""
from datetime import datetime, timezone

from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.working_memory_answers import prepare, render
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_memory_project_names import Selector, stores  # noqa: F401 - Fixture


def _source(episodes, body, occurred_at=None):
    episode, _ = episodes.record(EpisodeKind.DOCUMENT, 'orion.txt', body, Provenance(SourceType.DOCUMENT),
                                 occurred_at=occurred_at)
    assert WorkingMemoryStore(episodes).commit(
        episodes.support_snapshot(episode.id), [{'start': 0, 'end': len(body), 'kind': 'fact'}], model='t')
    return episode


def _time_line(episodes, claims):
    answer = prepare('Wann kommen die Prüfmuster?', episodes, claims, Selector())
    text, _, _ = render(answer, episodes, claims)
    return next(line for line in text.splitlines() if line.startswith('Quellenzeit:'))


def test_unknown_source_time_names_when_it_was_recorded(stores):  # noqa: F811
    episodes, claims = stores
    _source(episodes, 'Die Prüfmuster kommen am 3. Oktober.')
    line = _time_line(episodes, claims)
    assert line.startswith('Quellenzeit: unbekannt · Erfasst: ')
    assert line.endswith(' Uhr')


def test_known_source_time_needs_no_recorded_time(stores):  # noqa: F811
    episodes, claims = stores
    _source(episodes, 'Die Prüfmuster kommen am 3. Oktober.', datetime(2026, 9, 22, 9, tzinfo=timezone.utc))
    assert 'Erfasst' not in _time_line(episodes, claims)
