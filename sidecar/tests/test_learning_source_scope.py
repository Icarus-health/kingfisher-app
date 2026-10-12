"""Gewohnheiten dürfen keine unbeteiligten Mailtexte oder Vorschläge laden."""
from datetime import timedelta

from fastapi.testclient import TestClient
import pytest

from icarus_memory.episodes import EpisodeKind
from icarus_memory.habits import create_habit, check_in, list_habits
from icarus_memory.learning_service import propose_patterns
from icarus_memory.model import Kind, Provenance, SourceType
from icarus_memory.proposals import Evidence, ProposalKind
from icarus_memory.store import ConflictError
from tests.test_learning_service import memory, NOW  # noqa: F401
from tests.test_learning_routes import _client, fixed_clock  # noqa: F401


def unrelated(episodes):
    for i in range(25):
        episodes.record(EpisodeKind.DOCUMENT, 'Unbeteiligte Mail', f'Archivtext {i}',
                        Provenance(SourceType.EMAIL), occurred_at=NOW)


def explicit(memory):
    store, episodes, _, _ = memory
    habit = create_habit(store, 'Lesen', 3)
    ids = [check_in(store, episodes, habit.id, f'2026-09-{day:02d}', at=NOW)['episode']['id']
           for day in (7, 6, 4)]
    return habit, set(ids)


def only_decode(episodes, allowed, monkeypatch):
    original = episodes._from_row
    seen = []
    def decode(row):
        item = original(row)
        assert item.id in allowed, 'Unbeteiligter Rohtext wurde in Python geladen.'
        seen.append(item.id)
        return item
    monkeypatch.setattr(episodes, '_from_row', decode)
    return seen


def test_habit_overview_does_not_decode_the_mail_archive(memory, monkeypatch):
    habit, ids = explicit(memory)
    store, episodes, _, _ = memory
    unrelated(episodes)
    seen = only_decode(episodes, ids, monkeypatch)
    item = list_habits(store, episodes, NOW)[0]
    assert item['id'] == habit.id and item['observed_days'] == ['2026-09-07']
    assert set(seen) <= ids and seen


def test_learning_scan_reads_only_sources_of_active_habits(memory, monkeypatch):
    habit, ids = explicit(memory)
    store, episodes, proposals, service = memory
    other = create_habit(store, 'Anderes Lesen', 3)
    check_in(store, episodes, other.id, '2026-09-07', at=NOW)
    store.retract(other.id, at=NOW)
    unrelated(episodes)
    only_decode(episodes, ids, monkeypatch)
    [candidate] = propose_patterns(store, episodes, proposals, service, at=NOW)
    assert candidate.subject_ref == f'habit:{habit.id}'
    assert {e.episode_id for e in candidate.evidence} == ids


def test_checkin_retry_finds_untagged_legacy_original_without_other_rawtexts(memory, monkeypatch):
    store, episodes, _, _ = memory
    habit = create_habit(store, 'Alte Eintragung', 2)
    original, _ = episodes.record(EpisodeKind.OBSERVATION, 'Alt', 'Original bleibt',
        Provenance(SourceType.USER_STATED, source_ref=f'habit:{habit.id}:2026-09-08'),
        occurred_at=NOW)
    unrelated(episodes)
    only_decode(episodes, {original.id}, monkeypatch)
    second = check_in(store, episodes, habit.id, '2026-09-08', 'Neue Notiz', at=NOW)
    assert second['created'] is False
    assert second['episode']['body'] == 'Original bleibt'
    episodes.ignore(original.id)
    with pytest.raises(ConflictError):
        check_in(store, episodes, habit.id, '2026-09-08', at=NOW)


def test_learning_scan_does_not_decode_unrelated_proposals(memory, monkeypatch):
    habit, ids = explicit(memory)
    store, episodes, proposals, service = memory
    [first] = propose_patterns(store, episodes, proposals, service, at=NOW)
    source = episodes.get(next(iter(ids)))
    proposals.propose(ProposalKind.ASSERTION, 'Andere Prüfung', 'Andere Herkunft',
        assertion_kind=Kind.EPISODE, evidence=[Evidence(source.id, source.body, source.digest)], proposed_by='mail-reader', at=NOW)
    original = proposals._from_row
    def decode(row):
        item = original(row)
        assert item.proposed_by.startswith('habit-pattern:'), 'Unbeteiligter Vorschlag wurde geladen.'
        return item
    monkeypatch.setattr(proposals, '_from_row', decode)
    assert propose_patterns(store, episodes, proposals, service, at=NOW)[0].id == first.id


def test_learning_route_filters_before_deserializing_unrelated_proposals(tmp_path, monkeypatch):
    client = _client(tmp_path); app = client.app
    habit = create_habit(app.state.store, 'Lesen', 3)
    for day in (7, 6, 4):
        check_in(app.state.store, app.state.episodes, habit.id, f'2026-09-{day:02d}', at=NOW)
    [first] = propose_patterns(app.state.store, app.state.episodes, app.state.proposals,
                               app.state.knowledge_service, at=NOW)
    episode = app.state.episodes.get(first.evidence[0].episode_id)
    app.state.proposals.propose(ProposalKind.ASSERTION, 'Andere Prüfung', 'Andere Herkunft',
        assertion_kind=Kind.EPISODE, evidence=[Evidence(episode.id, episode.body, episode.digest)], proposed_by='habit_pattern:fake', at=NOW)
    original = app.state.proposals._from_row
    def decode(row):
        item = original(row)
        assert item.proposed_by.startswith('habit-pattern:')
        return item
    monkeypatch.setattr(app.state.proposals, '_from_row', decode)
    response = client.get('/api/v1/learning')
    assert response.status_code == 200
    assert [item['id'] for item in response.json()['items']] == [first.id]


def test_exact_tag_scope_preserves_all_kinds_states_and_order(memory):
    _, episodes, _, _ = memory
    wanted = 'habit:id_%'
    rows = []
    for index, kind in enumerate((EpisodeKind.OBSERVATION, EpisodeKind.DOCUMENT, EpisodeKind.SUMMARY)):
        e, _ = episodes.record(kind, 'Markierter Beleg', f'Beleg {index}',
            Provenance(SourceType.USER_STATED), tags=[wanted, wanted], occurred_at=NOW-timedelta(days=index))
        rows.append(e)
    episodes.ignore(rows[1].id)
    episodes.record(EpisodeKind.OBSERVATION, 'Falsche Marke', 'Kein Treffer',
        Provenance(SourceType.USER_STATED), tags=['habit:id_x', wanted+'suffix'], occurred_at=NOW)
    before = [e.id for e in episodes.all_episodes(-1) if wanted in e.tags]
    assert [e.id for e in episodes.tagged_raw([wanted, wanted])] == before
    assert episodes.tagged_raw([]) == []


def test_source_reference_lookup_does_not_confuse_prefixes(memory):
    _, episodes, _, _ = memory
    first, _ = episodes.record(EpisodeKind.OBSERVATION, 'Exakt', 'Exakt',
        Provenance(SourceType.USER_STATED, source_ref='habit:id:2026-09-08'), occurred_at=NOW)
    episodes.ignore(first.id)
    episodes.record(EpisodeKind.OBSERVATION, 'Präfix', 'Falsch',
        Provenance(SourceType.USER_STATED, source_ref='habit:id:2026-09-080'), occurred_at=NOW)
    assert episodes.by_source_ref('habit:id:2026-09-08').id == first.id
    assert episodes.by_source_ref('unbekannt') is None
