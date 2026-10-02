"""Opening a saved sourced draft must check its opaque server binding first."""

from dataclasses import replace
from datetime import datetime, timezone
import time

import pytest

from tests.test_mail_conversation_flow import memory_reply_app, suggest_memory_reply, index_prior_mail
from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.working_memory_store import WorkingMemoryStore


@pytest.fixture
def berlin_time(monkeypatch):
    # Der Entwurf nennt die Ortszeit des Rechners. CI läuft in UTC, der Mac in
    # Europe/Berlin; die Erwartung darf nicht von der Maschine abhängen.
    monkeypatch.setenv('TZ', 'Europe/Berlin')
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def validation(client, token, uid='work:1'):
    return client.post(f'/api/v1/messages/{uid}/reply-suggestion/validate',
                       json={'context_token': token})


def test_saved_draft_token_validates_without_another_mail_fetch(tmp_path, monkeypatch):
    app, first, second, _, client = memory_reply_app(tmp_path, monkeypatch)
    token = suggest_memory_reply(client)['context_token']
    def unexpected_mail_fetch(uid):
        raise AssertionError('editor validation must use the local binding')
    monkeypatch.setattr(app.state.mail, 'message', unexpected_mail_fetch)
    assert validation(client, token).json() == {'valid': True}
    assert validation(client, token, 'work:other').status_code == 409
    assert first.sent == second.sent == []


@pytest.mark.parametrize('change', ['ignore', 'correction', 'restart'])
def test_saved_draft_token_fails_closed_after_source_or_app_change(tmp_path, monkeypatch, change):
    app, first, second, episode, client = memory_reply_app(tmp_path, monkeypatch)
    token = suggest_memory_reply(client)['context_token']
    if change == 'ignore':
        app.state.episodes.ignore(episode.id)
    elif change == 'correction':
        index_prior_mail(app, 'Korrektur zu Projekt Atlas Rechnung: Der Versand erfolgt erst nach neuer Freigabe.')
    else:
        app.state.mail_reply_bindings.clear()
    response = validation(client, token)
    assert response.status_code == 409
    assert 'Wenn die Rechnung' not in response.text
    assert first.sent == second.sent == []


def test_unrelated_index_addition_keeps_saved_draft_binding(tmp_path, monkeypatch):
    app, _, _, _, client = memory_reply_app(tmp_path, monkeypatch)
    token = suggest_memory_reply(client)['context_token']
    index_prior_mail(app, 'Gartenstuhl und Fahrrad stehen im Keller.', title='Haushalt')
    assert validation(client, token).json() == {'valid': True}


def test_sourced_reply_quotes_full_condition_with_historical_date_and_author_without_draft_model(tmp_path, monkeypatch, berlin_time):
    app, first, second, old, client = memory_reply_app(tmp_path, monkeypatch)
    app.state.episodes.ignore(old.id)
    second.item = replace(second.item, date=datetime(2026, 9, 23, 9, tzinfo=timezone.utc))
    body = 'Projekt Atlas Rechnung: Morgen sende ich sie, aber nur falls die Freigabe bis dahin eintrifft.'
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, 'Projekt Atlas: Frist', body,
        Provenance(SourceType.EMAIL, source_ref='work:<dated@example.invalid>'),
        participants=['Alex <sender@example.invalid>'],
        occurred_at=datetime(2026, 9, 20, 14, tzinfo=timezone.utc),
    )
    store = WorkingMemoryStore(app.state.episodes)
    pending = store.pending(episode_ids=[episode.id])[0]
    assert store.commit(pending, [{'start': 0, 'end': len(body), 'kind': 'conditional'}], model='local-test')
    provider = app.state.agent.provider
    original = provider.complete_json
    selection_calls = []
    def only_select(messages, **kwargs):
        if not kwargs.get('schema'):
            raise AssertionError('sourced reply must not ask the model to draft facts')
        selection_calls.append(messages)
        return original(messages, **kwargs)
    provider.complete_json = only_select
    response = client.post('/api/v1/messages/work:1/reply-suggestion', json={
        'instruction': 'Bitte die Bedingung und den unklaren Zeitpunkt im Blick behalten.'})
    assert response.status_code == 200, response.text
    assert response.json()['sources'][0]['episode_id'] == episode.id
    assert response.json()['basis'] == 'source_quotes'
    draft = response.json()['body']
    assert draft == ('In einer früheren Nachricht von Alex <sender@example.invalid> vom 20.09.2026 um 16:00 Uhr steht:\n\n'
                     f'„{body}“\n\nBitte gib mir Bescheid, ob dieser Stand noch gilt.')
    assert '23.09.2026' not in draft
    assert len(selection_calls) == 1
    assert first.sent == second.sent == []
