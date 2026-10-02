"""Die Eigentümeransicht zeigt Umfang und Zeit, keine erfundene Vollständigkeit."""
from threading import RLock

import pytest
from fastapi.testclient import TestClient
from icarus_memory.server import create_app
from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType


@pytest.mark.parametrize('truncated', [False, True])
def test_completed_mail_analysis_keeps_capture_gap_visible_without_retry(tmp_path, truncated):
    from icarus_memory.connectors.mail import Message
    from icarus_memory.episodes import EpisodeStore
    from icarus_memory.mail_ingestion import remember
    from icarus_memory.memory_routes import coverage
    from icarus_memory.proposals import ProposalStore
    from icarus_memory.providers import Reply
    from icarus_memory.task_detection import TaskDetector

    class Reader:
        name = model = 'synthetic-coverage'
        is_local = True

        def complete(self, messages, tools):
            return Reply(text='{"items": []}')

    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    proposals = ProposalStore(tmp_path / 'proposals.sqlite3')
    try:
        result = remember(episodes, Message(
            uid='work:7.1', subject='Fiktive Mail', sender='sender@example.invalid',
            date=None, preview='', unread=True, account_id='work',
            body='Technisch empfangener Text.', truncated=truncated))
        episode_id = result['episode']['id']
        detector = TaskDetector(episodes, proposals, Reader(), RLock())
        assert detector.run(with_model=True).analyzed == 1

        data = coverage(episodes, proposals)

        assert data['counts']['completed'] == (0 if truncated else 1)
        assert data['counts']['partial'] == (1 if truncated else 0)
        assert data['truncated_sources'] == (1 if truncated else 0)
        if truncated:
            assert 'gekürzt' in data['detail']
        assert data['semantic_completeness'] is False
        assert proposals.memory_analysis.snapshot(episode_id)['state'] == 'completed'
        assert detector.run(with_model=True).analyzed == 0
        assert proposals.memory_analysis.snapshot(episode_id)['attempts'] == 1
    finally:
        proposals.close()
        episodes.close()


def test_coverage_empty_and_unprocessed_source():
    app = create_app()
    with TestClient(app) as client:
        response = client.get('/api/v1/memory/coverage')
        assert response.status_code == 200
        assert response.json()['total_sources'] == 0
        app.state.episodes.record(EpisodeKind.MESSAGE, 'Fiktiver Test', 'Bitte prüfen.',
                                 Provenance(source_type=SourceType.EMAIL))
        data = client.get('/api/v1/memory/coverage').json()
        assert data['total_sources'] == 1
        assert data['counts']['pending'] == 1
        assert data['counts']['completed'] == 0
        assert data['semantic_completeness'] is False


def test_memory_endpoints_require_existing_auth(monkeypatch):
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'synthetic-only-token')
    with TestClient(create_app()) as client:
        for path in ('coverage', 'timeline', 'as-known?known_at=2026-09-12T00:00:00Z'):
            assert client.get('/api/v1/memory/' + path).status_code == 401


def test_timeline_distinguishes_source_date_from_recording():
    from datetime import datetime, timezone
    app = create_app()
    source_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    recorded = datetime(2026, 9, 10, tzinfo=timezone.utc)
    app.state.episodes.record(EpisodeKind.MESSAGE, 'Fiktive alte Mail', 'Originaltext',
        Provenance(source_type=SourceType.EMAIL), occurred_at=source_date, at=recorded)
    with TestClient(app) as client:
        data = client.get('/api/v1/memory/timeline?start=2026-09-01T00:00:00Z&end=2026-10-01T00:00:00Z').json()
        assert len(data['items']) == 1
        assert datetime.fromisoformat(data['items'][0]['recorded_at']) == recorded
        assert datetime.fromisoformat(data['items'][0]['occurred_at']) == source_date
        assert client.get('/api/v1/memory/timeline?limit=501').status_code == 422
        assert client.get('/api/v1/memory/as-known?known_at=2026-09-12T00:00:00').status_code == 400
