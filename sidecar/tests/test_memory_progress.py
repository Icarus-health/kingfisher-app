"""Fortschritt der Einordnung: genaue Zahlen, Restzeit nur aus echten Messungen."""
from datetime import datetime, timezone

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.episodes import CHAT_LOOKUP_TAG
from icarus_memory.working_memory_store import WorkingMemoryStore
from icarus_memory.working_memory_worker import Pace
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_conversation_retraction import _close_app
from tests.test_source_answers_http import _api

AT = datetime(2026, 9, 23, tzinfo=timezone.utc)


def _record(episodes, body, *, key='', tags=None, kind=EpisodeKind.MESSAGE):
    episode, _ = episodes.record(kind, 'Mail', body, Provenance(SourceType.CHAT, source_ref='chat:local'),
                                 source_key=key, tags=tags, at=AT)
    if key:
        episodes.advance_source_head(key, episodes.source_head(key), episode.id)
    return episode


def test_progress_counts_only_current_sources(tmp_path):
    episodes = EpisodeStore(tmp_path / 'e.sqlite3')
    memory = WorkingMemoryStore(episodes)
    done = _record(episodes, 'Anna liefert am Freitag.')
    deferred = _record(episodes, 'Zu umfangreich.')
    _record(episodes, 'Noch offen.')
    ignored = _record(episodes, 'Ausgeschlossen.')
    _record(episodes, 'Nachschlagen im Gespräch.', tags=[CHAT_LOOKUP_TAG])
    _record(episodes, 'Alte Fassung.', key='document:a.txt')
    _record(episodes, 'Neue Fassung.', key='document:a.txt')
    _record(episodes, 'Zusammenfassung.', kind=EpisodeKind.SUMMARY)
    episodes.ignore(ignored.id)
    pending = {s.episode.id: s for s in memory.pending(limit=20)}
    assert memory.commit(pending[done.id], [{'start': 0, 'end': 5, 'kind': 'fact'}], model='t')
    assert memory.defer(pending[deferred.id])
    assert memory.progress() == {'total': 4, 'done': 1, 'skipped': 1, 'retry': 0, 'remaining': 2}
    episodes.close()


def test_pace_needs_two_batches_and_uses_wall_time():
    now = [0.0]
    pace = Pace(clock=lambda: now[0])
    pace.record(5)
    assert pace.estimate(100) is None
    now[0] = 60.0
    pace.record(0)  # leere Durchgänge zählen nicht
    pace.record(5)
    assert pace.seconds_per_source() == 12.0
    assert pace.estimate(100) == 1200 and pace.estimate(0) is None


def test_coverage_reports_progress_without_guessing(core, tmp_path, monkeypatch):  # noqa: F811
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        client.post('/api/v1/sources/documents', json={'filename': 'a.txt', 'body': 'Anna liefert am Freitag.'})
        progress = client.get('/api/v1/memory/coverage').json()['working_memory_progress']
        assert progress['total'] == 1 and progress['remaining'] == 1
        assert progress['estimate_seconds'] is None
        from icarus_memory.server import _working_memory_pace
        pace = _working_memory_pace(app)
        now = [0.0]
        pace._clock = lambda: now[0]
        pace.record(2)
        now[0] = 30.0
        pace.record(3)
        assert client.get('/api/v1/memory/coverage').json()['working_memory_progress']['estimate_seconds'] == 10
    finally:
        client.close()
        _close_app(app)


def test_worker_reports_processed_sources_to_pace(tmp_path):
    import json
    import threading
    from icarus_memory.providers import Reply
    from icarus_memory.working_memory_worker import run

    class Local:
        is_local, name, model = True, 'local', 'test-model'

        def complete_json(self, messages, **kwargs):
            blocks = json.loads(messages[-1]['content'])['blocks']
            return Reply(text=json.dumps({'items': [{'block_id': b['block_id'], 'kind': 'fact'} for b in blocks]}))

    episodes = EpisodeStore(tmp_path / 'e.sqlite3')
    for n in range(3):
        _record(episodes, f'Angabe Nummer {n} für Orion.')
    recorded = []
    pace = Pace()
    pace.record = recorded.append
    run(episodes, Local(), threading.Lock(), pace=pace, limit=2)
    run(episodes, Local(), threading.Lock(), pace=pace, limit=2)
    assert recorded == [2, 1]
    assert WorkingMemoryStore(episodes).progress()['remaining'] == 0
    episodes.close()
