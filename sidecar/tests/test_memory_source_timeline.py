"""Original chronology must never inherit an import timestamp."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.server import create_app


def record(app, title, date=None):
    return app.state.episodes.record(
        EpisodeKind.MESSAGE, title, 'Private original body: ' + title,
        Provenance(source_type=SourceType.EMAIL),
        occurred_at=datetime.fromisoformat(date) if date else None,
        at=datetime(2026, 10, 7, tzinfo=timezone.utc))[0]


def test_source_chronology_filters_original_date_and_counts_unknown_dates():
    app = create_app()
    old = record(app, 'Old', '2015-02-03T12:00:00+00:00')
    record(app, 'Unknown')
    hidden = record(app, 'Withdrawn', '2010-01-01T00:00:00+00:00')
    app.state.episodes.ignore(hidden.id)
    with TestClient(app) as client:
        params = {'basis': 'source', 'start': '2015-02-01T00:00:00Z', 'end': '2015-03-01T00:00:00Z'}
        response = client.get('/api/v1/memory/timeline', params=params)
        assert response.status_code == 200
        data = response.json()
        assert [x['episode_id'] for x in data['items']] == [old.id]
        assert data['basis'] == 'source' and data['time_axis'] == 'occurred_at'
        assert 'Private original body' not in response.text
        assert client.get('/api/v1/memory/timeline', params={**params, 'start': '2026-10-01T00:00:00Z', 'end': '2026-11-01T00:00:00Z'}).json()['items'] == []
        coverage = client.get('/api/v1/memory/coverage').json()['source_dates']
        assert datetime.fromisoformat(coverage['earliest']).year == 2015
        assert coverage['earliest'] == coverage['latest']
        assert coverage['undated'] == 1
        assert client.get('/api/v1/memory/timeline', params={**params, 'basis': 'invalid'}).status_code == 422


def test_source_pages_order_instants_not_offset_strings_and_bind_cursor_to_axis():
    app = create_app()
    earlier = record(app, 'Earlier', '2015-02-03T13:30:00+02:00')
    later = record(app, 'Later', '2015-02-03T12:00:00+00:00')
    with TestClient(app) as client:
        params = {'basis': 'source', 'start': '2015-02-01T00:00:00Z', 'end': '2015-03-01T00:00:00Z', 'limit': 1}
        first = client.get('/api/v1/memory/timeline', params=params).json()
        assert [x['episode_id'] for x in first['items']] == [later.id]
        second = client.get('/api/v1/memory/timeline', params={**params, 'cursor': first['next_cursor']}).json()
        assert [x['episode_id'] for x in second['items']] == [earlier.id]
        assert not second['truncated']
        assert client.get('/api/v1/memory/timeline', params={**params, 'basis': 'recorded', 'cursor': first['next_cursor']}).status_code == 400
        dates = client.get('/api/v1/memory/coverage').json()['source_dates']
        assert datetime.fromisoformat(dates['earliest']) < datetime.fromisoformat(dates['latest'])
