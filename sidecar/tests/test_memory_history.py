"""Historische Kenntnis ist nicht das Alter einer Quelle."""
from datetime import datetime, timezone

import pytest

from icarus_memory.claims import ClaimStore, KnowledgeService
from icarus_memory.episodes import EpisodeStore, EpisodeKind
from icarus_memory.proposals import ProposalStore, Evidence
from icarus_memory.model import Provenance, SourceType


def day(n):
    return datetime(2026, 9, n, tzinfo=timezone.utc)


@pytest.fixture
def core(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    proposals = ProposalStore(tmp_path / "proposals.sqlite3")
    claims = ClaimStore(tmp_path / "knowledge.sqlite3")
    service = KnowledgeService(episodes=episodes, proposals=proposals, claims=claims)
    yield episodes, proposals, claims, service
    claims.close()
    proposals.close()
    episodes.close()


def accepted(core, *, text="Anna arbeitet an Mainz.", created=10, valid_from=1, valid_until=None, supersedes=None):
    episodes, _, claims, service = core
    episode = episodes.record(EpisodeKind.MESSAGE, "Fiktiver Test", text,
        Provenance(source_type=SourceType.EMAIL), occurred_at=day(1), at=day(2))[0]
    proposal, _ = service.propose(subject_ref="person:anna", predicate="works_on", value=text,
        statement=text, rationale="Test", evidence=[Evidence(episode.id, text, episode.digest)],
        valid_from=day(valid_from), valid_until=day(valid_until) if valid_until else None)
    claim = service.accept(proposal.id, supersedes=supersedes or [], at=day(created))
    return claim, episode


def test_old_source_does_not_backdate_recognition(core):
    _, _, claims, _ = core
    claim, _ = accepted(core)
    before = claims.as_known_at(day(5), episodes=core[0], valid_at=day(3))
    assert before["items"] == []
    after = claims.as_known_at(day(11), episodes=core[0], valid_at=day(3))
    assert [item["id"] for item in after["items"]] == [claim.id]
    assert datetime.fromisoformat(after["items"][0]["recorded_at"]) == day(10)


def test_correction_preserves_earlier_knowledge(core):
    _, _, claims, _ = core
    old, _ = accepted(core, created=3)
    new, _ = accepted(core, text="Anna arbeitet an Freiburg.", created=10, supersedes=[old.id])
    earlier = claims.as_known_at(day(5), episodes=core[0], valid_at=day(4))
    later = claims.as_known_at(day(11), episodes=core[0], valid_at=day(4))
    assert [item["id"] for item in earlier["items"]] == [old.id]
    assert [item["id"] for item in later["items"]] == [new.id]


def test_valid_interval_has_exclusive_end(core):
    _, _, claims, _ = core
    accepted(core, created=2, valid_until=5)
    assert len(claims.as_known_at(day(10), episodes=core[0], valid_at=day(4))["items"]) == 1
    assert claims.as_known_at(day(10), episodes=core[0], valid_at=day(5))["items"] == []


def test_historical_read_cannot_restore_withdrawn_source(core):
    episodes, _, claims, _ = core
    claim, episode = accepted(core, created=3)
    claims.invalidate_source(episode.id, at=day(10))
    episodes.ignore(episode.id)
    assert claims.as_known_at(day(5), episodes=episodes)["items"] == []


def test_legacy_missing_journal_is_a_gap(core):
    _, _, claims, _ = core
    accepted(core, created=3)
    with claims._conn:
        claims._conn.execute("DELETE FROM knowledge_changes")
    snapshot = claims.as_known_at(day(5), episodes=core[0])
    assert snapshot["items"] == []
    assert snapshot["gaps"]["missing_history"] == 1


def test_redacted_claim_never_reappears_in_historical_read(core):
    from icarus_memory.model import Status
    episodes, _, claims, _ = core
    claim, _ = accepted(core, created=3)
    with claims._lock, claims._conn:
        claims._set_status(claim.id, Status.REDACTED)
    result = claims.as_known_at(day(5), episodes=episodes)
    assert result['items'] == []
    assert result['gaps']['unavailable_evidence'] == 1


def test_historical_knowledge_survives_store_restart(core, tmp_path):
    episodes, _, _, _ = core
    claim, _ = accepted(core, created=3)
    reopened = ClaimStore(tmp_path / 'knowledge.sqlite3')
    try:
        assert [item['id'] for item in reopened.as_known_at(day(5), episodes=episodes)['items']] == [claim.id]
    finally:
        reopened.close()


def test_snapshot_pages_identical_timestamps_filter_and_restart(core, tmp_path, monkeypatch):
    import icarus_memory.memory_history as history
    monkeypatch.setattr(history, 'SCAN_BUDGET', 2)
    episodes, _, claims, _ = core
    pairs = [accepted(core, text=f'Synthetic project {n}', created=3) for n in range(7)]
    ordered = sorted(pairs, key=lambda pair: pair[0].id)
    # An entire first scan is filtered: a cursor still must make progress.
    for _, source in ordered[:3]:
        episodes.ignore(source.id)
    page = claims.as_known_at(day(5), episodes=episodes, limit=2, reference='person:anna')
    assert page['items'] == []
    assert page['budget_truncated'] is True
    assert page['scanned'] == 2
    assert page['gaps']['unavailable_evidence'] == 2
    cursor = page['next_cursor']
    assert cursor
    # A backdated insert after page one must not enter this traversal.
    accepted(core, text='Inserted later with earlier date', created=3)
    reopened = ClaimStore(tmp_path / 'knowledge.sqlite3')
    found = []
    try:
        for _ in range(10):
            page = reopened.as_known_at(day(5), episodes=episodes, limit=2,
                                       reference='person:anna', cursor=cursor)
            found.extend(item['id'] for item in page['items'])
            cursor = page['next_cursor']
            if cursor is None:
                break
        else:
            pytest.fail('Pagination did not terminate')
    finally:
        reopened.close()
    assert found == [claim.id for claim, _ in ordered[3:]]
    assert not page['truncated']


def test_snapshot_cursor_rejects_invalid_and_changed_queries(core):
    episodes, _, claims, _ = core
    for n in range(3):
        accepted(core, text=f'Synthetic {n}', created=3)
    cursor = claims.as_known_at(day(5), episodes=episodes, limit=1)['next_cursor']
    assert cursor
    for invalid in ('!', 'e30', 'W10', 'A' * 2050):
        with pytest.raises(ValueError, match='Cursor'):
            claims.as_known_at(day(5), episodes=episodes, limit=1, cursor=invalid)
    for params in ({'reference': 'person:other'}, {'valid_at': day(4)}, {'limit': 2}):
        with pytest.raises(ValueError, match='Cursor'):
            claims.as_known_at(day(5), episodes=episodes, cursor=cursor, **({'limit': 1} | params))
    with pytest.raises(ValueError, match='Cursor'):
        claims.as_known_at(day(6), episodes=episodes, limit=1, cursor=cursor)


def test_snapshot_rechecks_revocation_between_pages(core):
    episodes, _, claims, _ = core
    pairs = sorted([accepted(core, text=f'Synthetic {n}', created=3) for n in range(3)],
                   key=lambda pair: pair[0].id)
    page = claims.as_known_at(day(5), episodes=episodes, limit=1)
    episodes.ignore(pairs[1][1].id)
    page = claims.as_known_at(day(5), episodes=episodes, limit=1, cursor=page['next_cursor'])
    assert [item['id'] for item in page['items']] == [pairs[2][0].id]
    assert page['gaps']['unavailable_evidence'] == 1


def test_timeline_cursor_pages_filtered_rows_equal_times_and_restart(core, tmp_path, monkeypatch):
    import icarus_memory.memory_routes as routes
    monkeypatch.setattr(routes, 'SCAN_BUDGET', 2)
    episodes, _, claims, _ = core
    pairs = [accepted(core, text=f'Synthetic timeline {n}', created=3) for n in range(6)]
    # Changes sort newest first; make the first two unavailable.
    for _, source in pairs[-2:]:
        episodes.ignore(source.id)
    page = routes.timeline(episodes, claims, day(1), day(5), 2)
    assert page['items'] == []
    assert page['budget_truncated']
    assert page['gaps']['unavailable_evidence'] == 2
    cursor = page['next_cursor']
    reopened = ClaimStore(tmp_path / 'knowledge.sqlite3')
    found = []
    try:
        for _ in range(20):
            page = routes.timeline(episodes, reopened, day(1), day(5), 2, cursor=cursor)
            found.extend(item['id'] for item in page['items'])
            cursor = page['next_cursor']
            if cursor is None:
                break
        else:
            pytest.fail('Pagination did not terminate')
    finally:
        reopened.close()
    # Restore the budget to obtain an independent complete comparison.
    monkeypatch.setattr(routes, 'SCAN_BUDGET', 2000)
    expected = routes.timeline(episodes, claims, day(1), day(5), 100)['items']
    assert found == [item['id'] for item in expected]
    assert len(found) == len(set(found)) == 8


def test_timeline_range_cursor_binding_and_half_open_end(core):
    from icarus_memory.memory_routes import timeline
    episodes, _, claims, _ = core
    for n in range(3):
        accepted(core, text=f'Synthetic range {n}', created=3)
    # Source received on day 2; decisions on day 3 are outside [2,3).
    page = timeline(episodes, claims, day(2), day(3), 1)
    assert page['items'][0]['kind'] == 'source_received'
    with pytest.raises(ValueError, match='Cursor'):
        timeline(episodes, claims, day(2), day(4), 1, cursor=page['next_cursor'])
    with pytest.raises(ValueError, match='Cursor'):
        timeline(episodes, claims, day(2), day(3), 1, cursor='!')


def test_history_http_cursor_roundtrip_and_errors(core):
    import threading
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from icarus_memory.memory_routes import install_routes
    episodes, _, claims, _ = core
    for n in range(3):
        accepted(core, text=f'Synthetic HTTP {n}', created=3)
    app = FastAPI()
    app.state.episodes = episodes
    app.state.claims = claims
    app.state.conversation_lock = threading.RLock()
    install_routes(app, [])
    with TestClient(app) as client:
        for endpoint, query in (
            ('as-known', {'known_at': day(5).isoformat(), 'limit': 1}),
            ('timeline', {'start': day(1).isoformat(), 'end': day(5).isoformat(), 'limit': 1}),
        ):
            first = client.get('/api/v1/memory/' + endpoint, params=query)
            assert first.status_code == 200
            cursor = first.json()['next_cursor']
            second = client.get('/api/v1/memory/' + endpoint, params=query | {'cursor': cursor})
            assert second.status_code == 200
            assert second.json()['items'][0]['id'] != first.json()['items'][0]['id']
            invalid = client.get('/api/v1/memory/' + endpoint, params=query | {'cursor': '!'})
            assert invalid.status_code == 400
            oversized = client.get('/api/v1/memory/' + endpoint, params=query | {'cursor': 'A' * 2049})
            assert oversized.status_code == 422


def history_client(core):
    import threading
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from icarus_memory.memory_routes import install_routes
    app = FastAPI()
    app.state.episodes = core[0]
    app.state.claims = core[2]
    app.state.conversation_lock = threading.RLock()
    install_routes(app, [])
    return TestClient(app)


@pytest.mark.parametrize('coordinate', [10**30, -(10**30), float('inf'), float('nan'), 0, 5373484.5])
def test_historical_http_rejects_out_of_range_cursor_coordinates(core, coordinate):
    import base64
    import json
    for n in range(3):
        accepted(core, text=f'Synthetic cursor numeric {n}', created=3)
    with history_client(core) as client:
        for endpoint, query in (
            ('as-known', {'known_at': day(5).isoformat(), 'limit': 1}),
            ('timeline', {'start': day(1).isoformat(), 'end': day(5).isoformat(), 'limit': 1}),
        ):
            first = client.get('/api/v1/memory/' + endpoint, params=query).json()
            cursor = first['next_cursor']
            data = json.loads(base64.urlsafe_b64decode(cursor + '=' * (-len(cursor) % 4)))
            data['p'][0] = coordinate
            changed = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip('=')
            response = client.get('/api/v1/memory/' + endpoint, params=query | {'cursor': changed})
            assert response.status_code == 400
            assert 'Cursor' in response.json()['detail']


def test_timeline_default_bounds_require_explicit_echo_for_continuation(core, monkeypatch):
    import icarus_memory.memory_routes as routes

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return day(5).astimezone(tz)

    for n in range(3):
        accepted(core, text=f'Synthetic default bounds {n}', created=3)
    with history_client(core) as client:
        # Keep the September fixture inside the default 30-day window forever.
        # Patch after route creation so request annotations retain datetime.
        monkeypatch.setattr(routes, 'datetime', FixedDateTime)
        first = client.get('/api/v1/memory/timeline', params={'limit': 1}).json()
        assert first['next_cursor']
        query = {'limit': 1, 'cursor': first['next_cursor']}
        for incomplete in (query, query | {'start': first['start']}, query | {'end': first['end']}):
            response = client.get('/api/v1/memory/timeline', params=incomplete)
            assert response.status_code == 400
            assert 'start und end' in response.json()['detail']
        response = client.get('/api/v1/memory/timeline', params=query | {
            'start': first['start'], 'end': first['end']})
        assert response.status_code == 200
        assert response.json()['items'][0]['id'] != first['items'][0]['id']


@pytest.mark.parametrize('replace_deleted', [False, True])
def test_timeline_rejects_deleted_or_reused_summary_ceiling(core, replace_deleted):
    episodes = core[0]
    pairs = [accepted(core, text=f'Synthetic anchor {n}', created=3) for n in range(3)]
    summary = episodes.record_summary('Synthetic summary', 'Derived text', 'test',
                                      [pairs[0][1].id], at=day(4))
    with episodes._lock:
        old_rowid = episodes._conn.execute('SELECT rowid FROM episodes WHERE id=?', (summary.id,)).fetchone()[0]
    query = {'start': day(1).isoformat(), 'end': day(5).isoformat(), 'limit': 1}
    with history_client(core) as client:
        first = client.get('/api/v1/memory/timeline', params=query).json()
        assert first['next_cursor']
        episodes.delete_summary(summary.id)
        if replace_deleted:
            new_source = episodes.record(EpisodeKind.MESSAGE, 'Synthetic replacement', 'New raw source',
                Provenance(source_type=SourceType.EMAIL), at=day(2))[0]
            with episodes._lock:
                reused = episodes._conn.execute('SELECT rowid FROM episodes WHERE id=?', (new_source.id,)).fetchone()[0]
            assert reused == old_rowid  # Exercise actual SQLite rowid reuse.
        response = client.get('/api/v1/memory/timeline', params=query | {'cursor': first['next_cursor']})
        assert response.status_code == 400
        assert 'Grenzzeile' in response.json()['detail']
        assert client.get('/api/v1/memory/timeline', params=query).status_code == 200


def test_timeline_excludes_normal_backdated_insert_above_ceiling(core):
    from icarus_memory.memory_routes import timeline
    episodes, _, claims, _ = core
    for n in range(3):
        accepted(core, text=f'Synthetic non-reuse {n}', created=3)
    baseline = timeline(episodes, claims, day(1), day(5), 100)['items']
    first = timeline(episodes, claims, day(1), day(5), 1)
    episodes.record(EpisodeKind.MESSAGE, 'Synthetic later insert', 'New backdated source',
        Provenance(source_type=SourceType.EMAIL), at=day(2))
    found = first['items'][:]
    cursor = first['next_cursor']
    while cursor:
        page = timeline(episodes, claims, day(1), day(5), 1, cursor=cursor)
        found.extend(page['items'])
        cursor = page['next_cursor']
    assert [item['id'] for item in found] == [item['id'] for item in baseline]


def test_snapshot_rejects_deleted_claim_ceiling(core):
    episodes, _, claims, _ = core
    for n in range(3):
        accepted(core, text=f'Synthetic claim anchor {n}', created=3)
    page = claims.as_known_at(day(5), episodes=episodes, limit=1)
    with claims._lock, claims._conn:
        claims._conn.execute('DELETE FROM knowledge_claims WHERE rowid=(SELECT MAX(rowid) FROM knowledge_claims)')
    with pytest.raises(ValueError, match='Grenzzeile'):
        claims.as_known_at(day(5), episodes=episodes, limit=1, cursor=page['next_cursor'])


def test_historical_read_retains_archived_original_evidence(core):
    episodes, _, claims, _ = core
    claim, episode = accepted(core, created=3)
    episodes.mark_consolidated(episode.id)
    episodes.archive_before(day(20))
    result = claims.as_known_at(day(5), episodes=episodes)
    assert [item['id'] for item in result['items']] == [claim.id]
    # Archiving is storage organization; explicit exclusion still removes it.
    episodes.ignore(episode.id)
    assert claims.as_known_at(day(5), episodes=episodes)['items'] == []
