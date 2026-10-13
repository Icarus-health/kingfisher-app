"""Literal source lookup is independent of classification and cannot revive sources."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from icarus_memory.episodes import CHAT_LOOKUP_TAG, EpisodeKind, EpisodeState
from icarus_memory.model import Provenance, SourceType
from icarus_memory.server import create_app


@pytest.fixture
def source_app():
    # No lifespan: background workers must not run while checking a read-only request.
    app = create_app()
    client = TestClient(app)
    yield app, client
    client.close()


def record(app, body, *, title='Original', participants=None, tags=None,
           source_type=SourceType.EMAIL, source_key='', at=None):
    episode = app.state.episodes.record(
        EpisodeKind.MESSAGE, title, body, Provenance(source_type=source_type),
        participants=participants, tags=tags, source_key=source_key,
        at=at or datetime(2026, 10, 1, tzinfo=timezone.utc))[0]
    if source_key:
        app.state.episodes.advance_source_head(
            source_key, app.state.episodes.source_head(source_key), episode.id)
    return episode


def search(client, query, **params):
    response = client.get('/api/v1/memory/search', params={'q': query, **params})
    assert response.status_code == 200
    return response.json()


def test_search_uses_existing_auth(monkeypatch):
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'synthetic-search-token')
    client = TestClient(create_app())
    assert client.get('/api/v1/memory/search', params={'q': 'Original'}).status_code == 401
    assert client.get('/api/v1/memory/search', params={'q': 'Original'},
                      headers={'x-icarus-token': 'synthetic-search-token'}).status_code == 200
    client.close()


@pytest.mark.parametrize('params', [
    {}, {'q': ''}, {'q': 'x'}, {'q': ' ' * 3}, {'q': 'x' * 201},
    {'q': 'valid', 'limit': 0}, {'q': 'valid', 'limit': 51},
])
def test_query_and_result_limits_are_bounded(source_app, params):
    _, client = source_app
    assert client.get('/api/v1/memory/search', params=params).status_code == 422


def test_unevaluated_body_match_returns_exact_late_quote(source_app):
    app, client = source_app
    body = ('Earlier context. ' * 100) + 'Remember the literal needle here.' + (' Afterwards.' * 100)
    episode = record(app, body)
    data = search(client, 'literal needle')
    assert set(data) == {'query', 'items', 'note_items', 'truncated', 'scope', 'scanned', 'scan_limit',
                         'note_scanned', 'note_scan_limit'}
    assert data['query'] == 'literal needle' and data['truncated'] is False
    item = data['items'][0]
    assert set(item) == {'episode_id', 'title', 'quote', 'start', 'end',
                         'occurred_at', 'recorded_at', 'source_type'}
    assert item['episode_id'] == episode.id
    assert item['start'] > 400
    assert item['quote'] == body[item['start']:item['end']]
    assert 'literal needle' in item['quote'] and len(item['quote']) <= 400
    assert item['occurred_at'] is None and item['source_type'] == 'email'
    assert app.state.episodes.get(episode.id).state is EpisodeState.NEW
    assert 'wörtlich' in data['scope'].casefold() and 'Bestätigung' in data['scope']


@pytest.mark.parametrize(('body', 'query', 'fragment'), [
    ('Vorher ÖkOlOgIe danach.', 'ökologie', 'ÖkOlOgIe'),
    ('Straße und mehr.', 'STRASSE', 'Straße'),
    ('A mainwordinside B.', 'wordinside', 'mainwordinside'),
    ('Die Quote heißt 50%_fest und bleibt.', '50%_fest', '50%_fest'),
    ("Die Phrase O'Reilly enthält ein Zitat.", "O'Reilly", "O'Reilly"),
    ('Die Pfadangabe C:\\data ist wörtlich.', 'C:\\data', 'C:\\data'),
])
def test_unicode_substrings_and_sql_characters_are_literal(source_app, body, query, fragment):
    app, client = source_app
    episode = record(app, body)
    record(app, 'No matching text at all.')
    data = search(client, query)
    assert [item['episode_id'] for item in data['items']] == [episode.id]
    item = data['items'][0]
    assert fragment in item['quote']
    assert item['quote'] == body[item['start']:item['end']]


def test_title_and_participant_hits_only_show_initial_original_excerpt(source_app):
    app, client = source_app
    titled = record(app, 'Unrelated original title body.', title='Needle title')
    named = record(app, 'Unrelated participant body.', participants=['Needle Person'])
    data = search(client, 'Needle')
    assert {item['episode_id'] for item in data['items']} == {titled.id, named.id}
    assert all(item['start'] == 0 and 'Needle' not in item['quote'] for item in data['items'])
    assert 'Titel' in data['scope'] and 'Beteiligte' in data['scope']


def test_unicode_folding_before_the_match_keeps_original_quote_offsets(source_app):
    app, client = source_app
    body = ('ß ' * 400) + 'Straße' + (' afterwards' * 100)
    record(app, body)
    item = search(client, 'STRASSE')['items'][0]
    assert item['start'] == 603 and item['end'] == 1003
    assert item['quote'] == body[603:1003] and 'Straße' in item['quote']


def test_large_unicode_fold_match_still_starts_the_bounded_excerpt_at_the_match(source_app):
    app, client = source_app
    body = ('x ' * 300) + ('ffi' * 200) + ' after'
    record(app, body)
    item = search(client, 'ﬃ' * 200)['items'][0]
    assert item['start'] == 600 and item['end'] == 1000
    assert item['quote'] == body[600:1000]


def test_ignored_archived_superseded_and_lookup_sources_are_hidden(source_app):
    app, client = source_app
    ignored = record(app, 'needle ignored')
    app.state.episodes.ignore(ignored.id)
    archived = record(app, 'needle archived')
    app.state.episodes.mark_consolidated(archived.id)
    app.state.episodes.archive_before(datetime(2026, 10, 2, tzinfo=timezone.utc))
    record(app, 'needle old version', source_key='document:fixture')
    current = record(app, 'needle current version', source_key='document:fixture')
    record(app, 'needle own lookup', tags=[CHAT_LOOKUP_TAG])
    conversation = record(app, 'needle own chat', source_type=SourceType.CHAT)
    record(app, 'needle lookup chat', source_type=SourceType.CHAT, tags=[CHAT_LOOKUP_TAG])
    app.state.episodes.record(EpisodeKind.SUMMARY, 'needle summary', 'needle inferred text',
                             Provenance(source_type=SourceType.INFERENCE))
    data = search(client, 'needle')
    assert {item['episode_id'] for item in data['items']} == {current.id, conversation.id}
    assert next(item for item in data['items'] if item['episode_id'] == conversation.id)['source_type'] == 'chat'
    assert 'Gesprächseingaben' in data['scope']


@pytest.mark.parametrize('change', ['ignore', 'supersede'])
def test_current_support_is_rechecked_after_candidate_scan(source_app, monkeypatch, change):
    app, client = source_app
    episode = record(app, 'needle initial', source_key='document:racing')
    original_snapshot = app.state.episodes.support_snapshot
    changed = False

    def snapshot(identifier):
        nonlocal changed
        if not changed:
            changed = True
            if change == 'ignore':
                app.state.episodes.ignore(episode.id)
            else:
                record(app, 'Completely unrelated replacement.', source_key='document:racing')
        return original_snapshot(identifier)

    monkeypatch.setattr(app.state.episodes, 'support_snapshot', snapshot)
    assert search(client, 'needle')['items'] == []


def test_limit_more_and_newest_first_are_honest(source_app):
    app, client = source_app
    base = datetime(2026, 10, 1, tzinfo=timezone.utc)
    episodes = [record(app, f'needle row {i}', at=base + timedelta(seconds=i)) for i in range(3)]
    first = search(client, 'needle', limit=2)
    assert [item['episode_id'] for item in first['items']] == [episodes[2].id, episodes[1].id]
    assert first['truncated'] is True
    assert len(search(client, 'needle', limit=3)['items']) == 3
    assert search(client, 'needle', limit=3)['truncated'] is False


def test_a_shortened_original_capture_is_not_presented_as_complete(source_app):
    app, client = source_app
    record(app, 'needle partial original', tags=['source:truncated'])
    data = search(client, 'needle')
    assert len(data['items']) == 1 and data['truncated'] is True


def test_scan_cap_is_reported_even_when_no_match_is_found(source_app, monkeypatch):
    from icarus_memory import memory_source_search
    app, client = source_app
    monkeypatch.setattr(memory_source_search, 'SOURCE_SCAN_LIMIT', 2)
    base = datetime(2026, 10, 1, tzinfo=timezone.utc)
    record(app, 'needle older', at=base)
    record(app, 'Unrelated recent one', at=base + timedelta(seconds=1))
    record(app, 'Unrelated recent two', at=base + timedelta(seconds=2))
    data = search(client, 'needle')
    assert data['items'] == [] and data['truncated'] is True
    assert data['scanned'] == data['scan_limit'] == 2


def test_read_only_search_preserves_originals_and_does_not_call_a_model(source_app, monkeypatch):
    app, client = source_app
    episode = record(app, 'needle original preserved')
    before = '\n'.join(app.state.episodes._conn.iterdump())

    def forbidden(*args, **kwargs):
        raise AssertionError('Source search must not ask a model or use unconstrained search')

    monkeypatch.setattr(app.state.episodes, 'search', forbidden)
    provider = getattr(app.state.agent, '_provider', None)
    if provider is not None:
        monkeypatch.setattr(provider, 'complete', forbidden)
    assert search(client, 'needle')['items'][0]['episode_id'] == episode.id
    assert '\n'.join(app.state.episodes._conn.iterdump()) == before


def note(app, body, *, title='Meeting', at=None):
    return app.state.workspace.add_note(title, body, Provenance(source_type=SourceType.USER_STATED),
                                        at=at or datetime(2026, 10, 1, tzinfo=timezone.utc))


def test_search_finds_current_workspace_note_body_and_preserves_workspace(source_app, monkeypatch):
    app, client = source_app
    original = note(app, ('Earlier context ' * 100) + 'Redaktionsschluss am Freitag.')
    before = '\n'.join(app.state.workspace._conn.iterdump())
    monkeypatch.setattr(app.state.workspace, 'search_notes', lambda *a, **k: pytest.fail('No unsafe LIKE lookup'))
    data = search(client, 'Redaktionsschluss')
    assert data['items'] == [] and len(data['note_items']) == 1
    item = data['note_items'][0]
    assert set(item) == {'note_id', 'title', 'quote', 'start', 'end', 'source_type', 'occurred_at', 'recorded_at'}
    assert item['note_id'] == original.id and item['title'] == 'Meeting'
    assert item['start'] > 400 and 'Redaktionsschluss' in item['quote']
    assert item['quote'] == original.body[item['start']:item['end']] and len(item['quote']) <= 400
    assert item['source_type'] == 'workspace_note' and item['occurred_at'] is None
    assert datetime.fromisoformat(item['recorded_at']) == original.updated_at
    assert '\n'.join(app.state.workspace._conn.iterdump()) == before


def test_note_search_only_uses_current_revision(source_app):
    app, client = source_app
    original = note(app, 'old needle note')
    app.state.workspace.update_note(original.id, body='new current wording')
    assert search(client, 'needle')['note_items'] == []
    assert search(client, 'current')['note_items'][0]['quote'] == 'new current wording'


def test_lookup_tagged_workspace_question_is_not_a_note_search_result(source_app):
    app, client = source_app
    app.state.workspace.add_note('needle lookup question', 'needle derived lookup',
                                 Provenance(source_type=SourceType.CHAT), tags=[CHAT_LOOKUP_TAG])
    assert search(client, 'needle')['note_items'] == []


def test_original_is_rechecked_after_scanning_notes(source_app, monkeypatch):
    app, client = source_app
    episode = record(app, 'needle original')
    original = note(app, 'needle note')
    read_note = app.state.workspace.note

    def current(identifier):
        app.state.episodes.ignore(episode.id)
        return read_note(identifier)

    monkeypatch.setattr(app.state.workspace, 'note', current)
    data = search(client, 'needle')
    assert data['items'] == []
    assert data['note_items'][0]['note_id'] == original.id
    assert data['truncated'] is True


def test_participant_match_is_rechecked_after_scanning_notes(source_app, monkeypatch):
    app, client = source_app
    episode = record(app, 'Unrelated original', participants=['Needle Person'])
    note(app, 'needle note')
    read_note = app.state.workspace.note

    def current(identifier):
        latest = app.state.episodes.get(episode.id)
        latest.participants = []
        app.state.episodes._put(latest)
        return read_note(identifier)

    monkeypatch.setattr(app.state.workspace, 'note', current)
    assert search(client, 'needle')['items'] == []


def test_note_is_reread_after_candidate_scan(source_app, monkeypatch):
    app, client = source_app
    original = note(app, 'needle note candidate')
    read_note = app.state.workspace.note
    changed = False

    def current(identifier):
        nonlocal changed
        if not changed:
            changed = True
            app.state.workspace.update_note(identifier, body='Unrelated current revision')
        return read_note(identifier)

    monkeypatch.setattr(app.state.workspace, 'note', current)
    assert search(client, 'needle')['note_items'] == []
    assert read_note(original.id).body == 'Unrelated current revision'


def test_episode_and_notes_share_one_result_limit_with_explicit_order(source_app):
    app, client = source_app
    episode = record(app, 'needle original')
    old = note(app, 'needle old note')
    recent = note(app, 'needle recent note', at=datetime(2026, 10, 2, tzinfo=timezone.utc))
    data = search(client, 'needle', limit=2)
    assert [item['episode_id'] for item in data['items']] == [episode.id]
    assert [item['note_id'] for item in data['note_items']] == [recent.id]
    assert data['truncated'] is True and 'zuerst' in data['scope']
    assert len(search(client, 'needle', limit=3)['note_items']) == 2
    assert search(client, 'needle', limit=3)['truncated'] is False
    assert old.id != recent.id


def test_note_scan_budget_and_literal_unicode_are_honest(source_app, monkeypatch):
    from icarus_memory import memory_source_search
    app, client = source_app
    monkeypatch.setattr(memory_source_search, 'NOTE_SCAN_LIMIT', 2)
    old = note(app, 'needle older note')
    recent = note(app, 'ÖkOlOgIe costs 50%_fixed', at=datetime(2026, 10, 2, tzinfo=timezone.utc))
    note(app, 'Newest unrelated note', at=datetime(2026, 10, 3, tzinfo=timezone.utc))
    assert search(client, 'ökologie')['note_items'][0]['note_id'] == recent.id
    assert search(client, '50%_fixed')['note_items'][0]['note_id'] == recent.id
    data = search(client, 'needle')
    assert data['note_items'] == [] and data['truncated'] is True
    assert data['note_scanned'] == data['note_scan_limit'] == 2
    assert old.id != recent.id
