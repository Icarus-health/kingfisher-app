"""Person projections cannot invent an assignee or an event date from import data."""
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from icarus_memory.episodes import EpisodeError, EpisodeKind
from icarus_memory.graph import person_id
from icarus_memory.model import Provenance, SourceType
from icarus_memory.person_digest_context import collect
from icarus_memory.person_digests import messages, validate
from icarus_memory.proposals import Evidence
from icarus_memory.server import create_app
from .test_conversation_retraction import _close_app

AT = datetime(2026, 9, 21, 10, tzinfo=timezone.utc)
OLD = datetime(2020, 3, 2, 9, tzinfo=timezone.utc)


@pytest.fixture
def app():
    instance = create_app()
    yield instance
    _close_app(instance)


def source(app, *, name='Lea', occurred_at=None, title='Undated original', project_id=None):
    return app.state.episodes.record(EpisodeKind.MESSAGE, title,
        'Wir treffen uns Freitag zur Planung. ' + title,
        Provenance(source_type=SourceType.EMAIL, source_ref='synthetic:' + title),
        participants=[name], occurred_at=occurred_at, at=AT, project_id=project_id)[0]


def test_person_profile_does_not_assign_tasks_from_title_substrings(app):
    source(app, name='Ann')
    other = app.state.tasks.add('Rückfrage an Joanna', Provenance(SourceType.USER_STATED), at=AT)
    direct = app.state.tasks.add('Budget prüfen', Provenance(SourceType.USER_STATED), at=AT)
    app.state.tasks.warten_auf(direct.id, 'Ann', at=AT)
    with TestClient(app) as client:
        card = client.get('/api/v1/memory/people/Ann').json()
        assert [task['id'] for task in card['person']['offene_aufgaben']] == [direct.id]
    assert app.state.tasks.get(other.id).wartet_auf is None


def test_undated_import_stays_unknown_in_person_and_project_http_profiles(app):
    project = app.state.workspace.add_project('Atlas', Provenance(SourceType.USER_STATED))
    episode = source(app, project_id=project.id)
    with TestClient(app) as client:
        card = client.get('/api/v1/memory/people/Lea').json()
        assert card['person']['letzter_kontakt'] is None
        assert card['person']['kontakt_text'] == ''
        assert card['interactions'][0]['occurred_at'] is None
        assert datetime.fromisoformat(card['interactions'][0]['recorded_at']) == AT
        assert card['contexts'][0]['last_interaction'] is None
        projected = client.get('/api/v1/memory/projects/' + project.id).json()
        assert projected['people'][0]['last_interaction'] is None
        assert projected['episodes'][0]['occurred_at'] is None
        assert datetime.fromisoformat(projected['episodes'][0]['recorded_at']) == AT
        raw = client.get('/api/v1/memory/graph').json()
        node = next(node for node in raw['nodes'] if node['id'] == 'episode:' + episode.id)
        assert node['attributes']['occurred_at'] is None
        assert datetime.fromisoformat(node['attributes']['recorded_at']) == AT
    assert app.state.episodes.get(episode.id).occurred_at is None


def test_unknown_new_import_does_not_replace_last_dated_contact(app):
    source(app, occurred_at=OLD, title='Dated original')
    source(app)
    with TestClient(app) as client:
        card = client.get('/api/v1/memory/people/Lea').json()
        assert datetime.fromisoformat(card['person']['letzter_kontakt']) == OLD
        assert '2020' in card['person']['kontakt_text']


def test_undated_digest_preserves_null_source_time_and_has_no_invented_period(app):
    source(app)
    context = collect(app, person_id('Lea'))
    packet = json.loads(messages(context)[2]['content'].split('\n', 1)[1])
    assert packet['occurred_at'] is None
    assert datetime.fromisoformat(packet['recorded_at']) == AT
    reply = SimpleNamespace(text=json.dumps({'points': [{'text': 'Laut Quelle geht es um Planung.',
        'citations': [{'source_id': 'S1', 'quote': 'Wir treffen uns Freitag zur Planung.'}]}],
        'questions': [], 'conflicts': []}), tool_calls=[])
    digest = validate(reply, context, 'synthetic')
    assert digest['source_period'] is None
    assert digest['points'][0]['citations'][0]['occurred_at'] is None
    assert datetime.fromisoformat(digest['points'][0]['citations'][0]['recorded_at']) == AT


def test_late_accepted_claim_keeps_original_event_and_import_times_in_digest(app):
    episode = source(app, occurred_at=OLD)
    proposal, _ = app.state.knowledge_service.propose(subject_ref=person_id('Lea'),
        predicate='observed_email', value=episode.body, statement=episode.body, rationale='Synthetic',
        evidence=[Evidence(episode.id, episode.body, episode.digest)])
    claim = app.state.knowledge_service.accept(proposal.id, supersedes=[], at=AT+timedelta(days=1))
    context = collect(app, person_id('Lea'))
    row = next(row for row in context['sources'] if row['ref'] == 'claim:' + claim.id)
    assert datetime.fromisoformat(row['occurred_at']) == OLD
    assert datetime.fromisoformat(row['recorded_at']) == AT
    assert datetime.fromisoformat(row['claim_created_at']) == AT+timedelta(days=1)


@pytest.mark.parametrize('change', ['ignored', 'removed'])
def test_digest_primary_lookup_fails_closed_if_source_disappears_after_validation(app, monkeypatch, change):
    from icarus_memory import person_digest_context
    episode = source(app, occurred_at=OLD)
    proposal, _ = app.state.knowledge_service.propose(subject_ref=person_id('Lea'),
        predicate='observed_email', value=episode.body, statement=episode.body, rationale='Synthetic',
        evidence=[Evidence(episode.id, episode.body, episode.digest)])
    claim = app.state.knowledge_service.accept(proposal.id, supersedes=[])
    original = person_digest_context._evidence_available

    def withdraw_after_check(instance, current):
        result = original(instance, current)
        if change == 'ignored':
            instance.state.episodes.ignore(episode.id)
        else:
            get = instance.state.episodes.get
            def removed(identifier):
                if identifier == episode.id:
                    raise EpisodeError('Synthetic concurrent removal')
                return get(identifier)
            monkeypatch.setattr(instance.state.episodes, 'get', removed)
        return result

    monkeypatch.setattr(person_digest_context, '_evidence_available', withdraw_after_check)
    context = collect(app, person_id('Lea'))
    assert all(row['ref'] != 'claim:' + claim.id for row in context['sources'])
    assert all(episode.id not in row['episode_ids'] for row in context['sources'])


def test_digest_drops_collected_raw_source_withdrawn_before_claim_check_before_model_input(app, monkeypatch):
    from icarus_memory import person_digest_context
    from .test_person_digests import Local
    episode = source(app, occurred_at=OLD, title='WITHDRAWN_MARKER')
    safe = source(app, occurred_at=OLD, title='Safe independent source')
    proposal, _ = app.state.knowledge_service.propose(subject_ref=person_id('Lea'),
        predicate='observed_email', value=episode.body, statement=episode.body, rationale='Synthetic',
        evidence=[Evidence(episode.id, episode.body, episode.digest)])
    claim = app.state.knowledge_service.accept(proposal.id, supersedes=[])
    original = person_digest_context._evidence_available

    def withdraw_before_check(instance, current):
        if current.id == claim.id:
            instance.state.episodes.ignore(episode.id)
        return original(instance, current)

    monkeypatch.setattr(person_digest_context, '_evidence_available', withdraw_before_check)
    provider = Local()
    app.state.agent = SimpleNamespace(provider=provider)
    with TestClient(app) as client:
        response = client.post('/api/v1/memory/person-digests/' + person_id('Lea'), json={})
    assert 'WITHDRAWN_MARKER' not in json.dumps(provider.context)
    assert provider.calls == 1
    assert [row['episode_ids'] for row in provider.context['sources']] == [[safe.id]]
    assert response.status_code == 200
    assert response.json()['status'] == 'ready'
