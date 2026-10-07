"""A compact overview remains tied to the exact local mail, never model text."""
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from icarus_memory import mail_briefing, local_model_guard
from icarus_memory.connectors.mail import Message
from icarus_memory.providers import Reply
from icarus_memory.server import create_app
from icarus_memory.mail_task_suggestions import source_digest


BODY = 'Hallo Lea,\n\nBitte sende Tom den Bericht bis Freitag.\n\nDas Hotel ist noch nicht gebucht.'


class Model:
    is_local = True
    model = 'kingfisher-qwen3.5:9b-32k'
    base_url = 'http://127.0.0.1:11434/v1'
    def __init__(self):
        self.calls = []
        self.payload = {'passages': [1, 2], 'tasks': [{'title': 'Bericht an Tom senden', 'passage': 1}]}
        self.effect = None
        self.review = None
    def complete_json(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if self.effect:
            self.effect()
        if 'reviews' in kwargs.get('schema', {}).get('properties', {}):
            candidates = json.loads(messages[1]['content'])['candidates']
            return Reply(text=json.dumps({'reviews': self.review if self.review is not None else [
                {'id': item['id'], 'kind': 'request_to_recipient', 'title_supported': True} for item in candidates]}))
        return Reply(text=json.dumps(self.payload))


@pytest.fixture
def setup(monkeypatch):
    app = create_app()
    model = Model()
    message = Message(uid='work:1.42', account_id='work', subject='Bericht', sender='Tom <tom@example.test>',
                      date=None, preview='', unread=False, body=BODY)
    mail = SimpleNamespace(current=message)
    mail.message = lambda uid: mail.current
    app.state.mail = mail
    monkeypatch.setattr(mail_briefing, '_provider', lambda app: model)
    monkeypatch.setattr(local_model_guard, 'verify_local_model',
                        lambda provider, **kw: local_model_guard.LocalModelIdentity(provider.model, 'weight-1'))
    with TestClient(app) as client:
        yield app, model, mail, client


def post(setup, **body):
    return setup[3].post('/api/v1/messages/work:1.42/briefing', json=body)


def test_literal_complete_passages_and_task_digest(setup):
    result = post(setup)
    assert result.status_code == 200
    data = result.json()
    assert data['quotes'] == ['Bitte sende Tom den Bericht bis Freitag.', 'Das Hotel ist noch nicht gebucht.']
    assert data['tasks'] == [{'title': 'Bericht an Tom senden', 'quote': 'Bitte sende Tom den Bericht bis Freitag.'}]
    assert data['source_digest'] == source_digest(setup[2].current)
    assert data['status'] == 'ready' and data['uid'] == 'work:1.42'
    assert len(setup[0].state.tasks.open_tasks()) == 0
    assert sum(setup[0].state.episodes.counts().values()) == 0


@pytest.mark.parametrize('kind,supported', [('information', True), ('marketing', True),
    ('other_person', True), ('request_to_recipient', False)])
def test_source_equality_alone_does_not_offer_news_or_unsupported_tasks(setup, kind, supported):
    setup[1].review = [{'id': 0, 'kind': kind, 'title_supported': supported}]
    data = post(setup).json()
    assert data['quotes']
    assert data['tasks'] == []
    assert data['task_review'] == 'completed'


def test_failed_task_screening_keeps_original_overview_and_shows_gap(setup):
    setup[1].review = []
    data = post(setup).json()
    assert data['quotes'] and data['available']
    assert data['tasks'] == []
    assert data['task_review'] == 'unavailable'
    assert 'Aufgabenprüfung' in data['detail']


def test_truncated_mail_never_gets_tasks_from_incomplete_context(setup):
    setup[2].current = replace(setup[2].current, truncated=True)
    data = post(setup).json()
    assert data['quotes'] and not data['tasks']


def test_short_quote_stays_visible_but_only_saveable_tasks_are_proposed(setup):
    setup[2].current = replace(setup[2].current, body='Ruf an.\n\nBitte sende Tom den Bericht bis Freitag.')
    setup[1].payload = {'passages': [0, 1], 'tasks': [
        {'title': 'Anrufen', 'passage': 0}, {'title': 'Bericht senden', 'passage': 1}]}
    data = post(setup).json()
    assert data['status'] == 'ready'
    assert data['quotes'] == ['Ruf an.', 'Bitte sende Tom den Bericht bis Freitag.']
    assert data['tasks'] == [{'title': 'Bericht senden', 'quote': 'Bitte sende Tom den Bericht bis Freitag.'}]
    for task in data['tasks']:
        saved = setup[3].post('/api/v1/messages/work:1.42/task', json={
            'title': task['title'], 'source_quote': task['quote'], 'source_digest': data['source_digest']})
        assert saved.status_code == 201, saved.text


@pytest.mark.parametrize('quote, saveable', [('Ruf an.', False), ('Ruf an.!', True)])
def test_task_evidence_matches_seven_eight_character_save_boundary(setup, quote, saveable):
    setup[2].current = replace(setup[2].current, body=quote)
    setup[1].payload = {'passages': [0], 'tasks': [{'title': 'Anrufen', 'passage': 0}]}
    data = post(setup).json()
    assert data['quotes'] == [quote]
    assert data['tasks'] == ([{'title': 'Anrufen', 'quote': quote}] if saveable else [])
    if saveable:
        result = setup[3].post('/api/v1/messages/work:1.42/task', json={
            'title': data['tasks'][0]['title'], 'source_quote': quote, 'source_digest': data['source_digest']})
        assert result.status_code == 201, result.text


def test_cache_reuses_model_only_for_unchanged_mail(setup):
    first = post(setup).json()
    assert post(setup).json() == first
    assert len(setup[1].calls) == 2
    setup[2].current = replace(setup[2].current, body=BODY.replace('Freitag', 'Montag'))
    assert post(setup).json()['source_digest'] != first['source_digest']
    assert len(setup[1].calls) == 4


def test_refresh_is_explicit_and_does_not_create_tasks(setup):
    post(setup)
    post(setup, refresh=True)
    assert len(setup[1].calls) == 4
    assert sum(setup[0].state.episodes.counts().values()) == 0


@pytest.mark.parametrize('passages', [[99], [-1], [True], ['Hotel ist gebucht'], [0, 99]])
def test_forged_or_ambiguous_passage_identifiers_are_never_rendered(setup, passages):
    setup[1].payload = {'passages': passages, 'tasks': []}
    data = post(setup).json()
    assert data['status'] == 'incomplete'
    assert all(quote in BODY for quote in data['quotes'])
    assert 'Hotel ist gebucht' not in data['quotes']


def test_unchanged_verbatim_quote_keeps_negation(setup):
    setup[1].payload = {'passages': [2], 'tasks': []}
    assert post(setup).json()['quotes'] == ['Das Hotel ist noch nicht gebucht.']


def test_empty_mail_skips_model(setup):
    setup[2].current = replace(setup[2].current, body='', preview='')
    assert post(setup).json()['status'] == 'empty'
    assert not setup[1].calls


def test_remote_provider_never_called(setup):
    setup[1].is_local = False
    assert post(setup).json()['status'] == 'unavailable'
    assert not setup[1].calls


def test_message_changed_during_inference_discards_result(setup):
    setup[1].effect = lambda: setattr(setup[2], 'current', replace(setup[2].current, body='Andere Grundlage.'))
    assert post(setup).status_code == 409


def test_account_replaced_during_inference_discards_result(setup):
    setup[1].effect = lambda: setattr(setup[0].state, 'mail', SimpleNamespace())
    assert post(setup).status_code == 409


def test_provider_reconfigured_during_inference_discards_result(setup):
    setup[1].effect = lambda: setattr(setup[1], 'model', 'another-model')
    assert post(setup).status_code == 409


def test_truncated_mail_is_explicit(setup):
    setup[2].current = replace(setup[2].current, truncated=True)
    result = post(setup).json()
    assert result['status'] == 'incomplete' and result['truncated']


def test_cache_is_bounded(setup):
    state = mail_briefing.Briefings()
    for i in range(100):
        state.put(str(i), {'quotes': []})
    assert len(state.cache) == 64


def test_parallel_request_does_not_duplicate_model_work(setup):
    state = mail_briefing._state(setup[0])
    assert state.lock.acquire(blocking=False)
    try:
        assert post(setup).status_code == 429
        assert not setup[1].calls
    finally:
        state.lock.release()


def test_overlong_unbroken_text_is_not_silently_presented_as_complete(setup):
    setup[2].current = replace(setup[2].current, body='x' * 1600, preview='')
    data = post(setup).json()
    assert data['status'] == 'incomplete'
    assert data['quotes'] == []


def test_analysis_cannot_mix_mail_identifiers(setup):
    setup[2].current = replace(setup[2].current, uid='work:1.99')
    assert post(setup).status_code == 409
    assert not setup[1].calls


def test_loaded_mail_carries_same_digest_as_briefing(setup):
    current = setup[3].get('/api/v1/messages/work:1.42')
    assert current.status_code == 200
    assert current.json()['source_digest'] == post(setup).json()['source_digest']


def test_crlf_paragraphs_are_not_lost(setup):
    setup[2].current = replace(setup[2].current, body=BODY.replace('\n', '\r\n'))
    assert post(setup).json()['quotes'] == ['Bitte sende Tom den Bericht bis Freitag.', 'Das Hotel ist noch nicht gebucht.']


def test_bad_model_format_is_explicit_unavailable(setup):
    setup[1].payload = {'quotes': ['Es ist gebucht.']}
    result = post(setup).json()
    assert result['status'] == 'unavailable' and not result['quotes']


def test_account_revoked_while_rechecking_mail_discards_result(setup):
    calls = 0
    def read(uid):
        nonlocal calls
        calls += 1
        if calls == 2:
            setup[0].state.mail = SimpleNamespace()
        return setup[2].current
    setup[2].message = read
    assert post(setup).status_code == 409


def test_non_text_model_content_is_unavailable(setup):
    setup[1].complete_json = lambda *a, **kw: SimpleNamespace(text=None, tool_calls=[])
    assert post(setup).json()['status'] == 'unavailable'


def test_unverified_weights_are_never_called(setup, monkeypatch):
    from icarus_memory.providers import ProviderError
    def unavailable(provider, **kw):
        raise ProviderError('not local')
    monkeypatch.setattr(local_model_guard, 'verify_local_model', unavailable)
    assert post(setup).json()['status'] == 'unavailable'
    assert not setup[1].calls


def test_cached_result_rechecks_source_after_initial_read(setup):
    post(setup)
    original = setup[2].current
    calls = 0
    def read(uid):
        nonlocal calls
        calls += 1
        if calls == 1:
            setup[2].current = replace(original, body='Geänderte Nachricht ohne alte Bitte.')
            return original
        return setup[2].current
    setup[2].message = read
    assert post(setup).status_code == 409
    assert len(setup[1].calls) == 2


def test_later_reply_updates_cached_overview_without_another_model_call(setup):
    from datetime import datetime, timedelta, timezone
    from icarus_memory.mail_ingestion import remember
    app,model,mail,client=setup
    mail.current.date=datetime.now(timezone.utc)-timedelta(hours=1)
    mail.current.message_id='<first@example.test>'
    assert post(setup).json()['temporal_status']=='recent'
    later=Message(uid='work:1.43',account_id='work',subject='Re: Bericht',sender='Tom <tom@example.test>',
        date=datetime.now(timezone.utc),preview='',unread=True,body='Bitte nichts mehr schicken.',
        message_id='<later@example.test>',in_reply_to='<first@example.test>')
    remember(app.state.episodes,later)
    data=post(setup).json()
    assert data['temporal_status']=='followup'
    assert data['followup_episode_id']
    assert len(model.calls)==2
    assert data['recorded_at'] is None  # opening the first mail did not import it
