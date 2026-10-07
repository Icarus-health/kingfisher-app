"""Thread selections remain literal source quotes and unconfirmed classifications."""
import copy
import importlib
import importlib.util
import json
from threading import RLock
from types import SimpleNamespace

import pytest

from icarus_memory import local_model_guard, mail_briefing
from icarus_memory.providers import ProviderError, Reply, ToolCall


def subject():
    assert importlib.util.find_spec('icarus_memory.mail_thread_summary') is not None, 'Thread summary boundary is missing'
    return importlib.import_module('icarus_memory.mail_thread_summary')


def context():
    return {'uid': 'work:1.42', 'source_digest': 'original-mail-digest',
            'scope': 'stored_header_links', 'status': 'ready', 'limited': False,
            'detail': 'Nur gespeicherte Antwortbezüge, keine vollständige Mailhistorie.',
            'items': [
                {'episode_id': 'e-old', 'current': False, 'title': 'Aurora',
                 'sender': 'Mira <mira@example.invalid>', 'occurred_at': '2026-10-01T09:00:00+00:00',
                 'recorded_at': '2026-10-02T09:00:00+00:00', 'truncated': False,
                 'text': 'Ich prüfe Aurora, sofern die Freigabe kommt.\n\nBitte warte auf die Rückmeldung.'},
                {'episode_id': 'e-new', 'current': True, 'title': 'Re: Aurora',
                 'sender': 'Jan <jan@example.invalid>', 'occurred_at': '2026-10-03T09:00:00+00:00',
                 'recorded_at': '2026-10-04T09:00:00+00:00', 'truncated': False,
                 'text': 'Die Prüfung ist abgesagt. Bitte nichts versenden.'}]}


class Model:
    is_local = True
    model = 'synthetic:local'
    base_url = 'http://127.0.0.1:11434/v1'

    def __init__(self):
        self.calls = []
        self.effect = None
        self.reply = None

    def complete_json(self, messages, **kwargs):
        self.calls.append((copy.deepcopy(messages), copy.deepcopy(kwargs)))
        if self.effect:
            self.effect()
        if self.reply is not None:
            return self.reply
        sources = json.loads(messages[1]['content'])['sources']
        identifier = sources[0]['passages'][0]['id']
        return Reply(text=json.dumps({'selections': [{'kind': 'cancellation', 'passage_ids': [identifier]}]}))


@pytest.fixture
def setup(monkeypatch):
    model = Model()
    app = SimpleNamespace(state=SimpleNamespace(conversation_lock=RLock(), mail=object()))
    monkeypatch.setattr(mail_briefing, '_provider', lambda app: model)
    monkeypatch.setattr(local_model_guard, 'verify_local_model', lambda provider, **kwargs:
                        local_model_guard.LocalModelIdentity(provider.model, 'a' * 64))
    return app, model


def test_summary_selects_literal_quotes_and_marks_category_as_unconfirmed(setup):
    app, model = setup
    original = context()
    before = copy.deepcopy(original)
    result = subject().summarize(app, original)
    assert result['status'] == 'ready' and result['available']
    assert result['selection_review'] == 'proposed' and result['semantic_validation'] is False
    assert result['context_fingerprint'] == subject().fingerprint(original)
    item, = result['items']
    assert item['quote'] == original['items'][1]['text']
    assert item['kind'] == 'cancellation' and item['label'] == 'Absage'
    assert item['interpretation'] == 'unconfirmed'
    for field in ('episode_id', 'current', 'title', 'sender', 'occurred_at', 'recorded_at', 'truncated'):
        assert item[field] == original['items'][1][field]
    assert original == before and len(model.calls) == 1
    assert result['model_attempted'] is True
    assert model.calls[0][1]['max_tokens'] <= 768
    assert 'unbestätigt' in result['detail']
    assert 'tasks' not in result and 'approvals' not in result


def test_all_context_fields_are_bound_but_dictionary_key_order_is_irrelevant():
    module = subject()
    original = context()
    digest = module.fingerprint(original)
    assert module.fingerprint(dict(reversed(list(original.items())))) == digest
    for key, value in [('sender', 'Other'), ('recorded_at', None), ('text', 'Changed'),
                       ('episode_id', None), ('truncated', True), ('current', False),
                       ('occurred_at', None), ('title', 'Different')]:
        changed = copy.deepcopy(original)
        changed['items'][1][key] = value
        assert module.fingerprint(changed) != digest
    changed = copy.deepcopy(original)
    changed['detail'] = 'Changed scope detail'
    assert module.fingerprint(changed) != digest
    changed = copy.deepcopy(original)
    changed['reader_revision'] = 2
    assert module.fingerprint(changed) != digest


def test_unknown_time_and_unstored_open_mail_keep_unknown_source_identity(setup):
    app, model = setup
    value = context()
    value['items'] = [dict(value['items'][1], episode_id=None, occurred_at=None, recorded_at=None)]
    result = subject().summarize(app, value)
    row, = result['items']
    assert row['episode_id'] is None and row['occurred_at'] is None and row['recorded_at'] is None
    assert any('Quellenzeit' in warning for warning in result['warnings'])


def test_capture_cut_excludes_incomplete_last_paragraph(setup):
    app, model = setup
    value = context()
    value['limited'] = True
    value['items'] = [dict(value['items'][0], truncated=True,
        text='Bitte warte auf die Freigabe.\n\nEine Zusage gilt nur, wenn')]
    result = subject().summarize(app, value)
    assert result['items'][0]['quote'] == 'Bitte warte auf die Freigabe.'
    assert 'Eine Zusage gilt nur' not in str(model.calls)
    assert result['limited'] and result['status'] == 'incomplete'
    assert any('gekürzt' in warning for warning in result['warnings'])


def test_single_cut_paragraph_uses_no_model_and_explains_gap(setup):
    app, model = setup
    value = context()
    value['items'] = [dict(value['items'][0], truncated=True, text='Falls die Freigabe')]
    result = subject().summarize(app, value)
    assert result['items'] == [] and result['status'] == 'incomplete'
    assert not model.calls and result['limited']


def test_overlong_paragraph_is_not_sliced_into_evidence(setup):
    app, model = setup
    value = context()
    value['items'] = [dict(value['items'][0], text='X' * 1201 + '\n\nDie Prüfung ist abgesagt.')]
    result = subject().summarize(app, value)
    assert result['items'][0]['quote'] == 'Die Prüfung ist abgesagt.'
    assert result['limited'] and 'X' * 50 not in str(model.calls)


def test_total_model_payload_budget_prefers_latest_known_sources(setup):
    app, model = setup
    value = context()
    template = value['items'][0]
    value['items'] = [dict(template, episode_id=f'e-{i}', occurred_at=f'2026-10-{i + 1:02d}T09:00:00+00:00',
                           text=('Old paragraph ' + str(i) + ' ' + 'x' * 900 + '\n\n') * 5) for i in range(12)]
    newest = dict(template, episode_id='e-cancel', occurred_at='2026-10-20T09:00:00+00:00',
                  text='Die neueste Nachricht sagt die Lieferung ab.')
    value['items'].append(newest)
    result = subject().summarize(app, value)
    payload = model.calls[0][0][1]['content']
    assert len(payload) <= 12000 and newest['text'] in payload
    assert result['limited'] and result['status'] == 'incomplete'
    assert result['items'][0]['episode_id'] == 'e-cancel'


def test_passage_count_is_bounded_and_complete_originals_preserve_newlines(setup):
    app, model = setup
    value = context()
    value['items'] = [dict(value['items'][0], text='\n\n'.join(f'Zeile {i}.\nBedingung bleibt erhalten.' for i in range(70)))]
    result = subject().summarize(app, value)
    data = json.loads(model.calls[0][0][1]['content'])
    assert sum(len(source['passages']) for source in data['sources']) <= 64
    assert result['limited']
    assert result['items'][0]['quote'] in value['items'][0]['text']
    assert '\nBedingung bleibt erhalten.' in result['items'][0]['quote']


@pytest.mark.parametrize('text', [
    'not JSON', 'null', '{"selections":null}', '{"selections":[{}]}',
    '{"selections":[],"facts":"invented"}', '{"selections":[],"selections":[]}',
    '{"selections":[{"kind":"owner","passage_ids":["P1.1"]}]}',
    '{"selections":[{"kind":"agreement","passage_ids":[]}]}',
    '{"selections":[{"kind":"agreement","passage_ids":[true]}]}',
    '{"selections":[{"kind":"agreement","passage_ids":["unknown"]}]}',
    '{"selections":[{"kind":"agreement","passage_ids":["P1.1"],"quote":"Invented"}]}',
    '{"selections":[{"kind":"agreement","passage_ids":["P1.1","P1.1"]}]}',
    '{"selections":[{"kind":"agreement","passage_ids":["P1.1"]},{"kind":"change","passage_ids":["P1.1"]}]}',
    '{"selections":NaN}', 'x' * 4097, '[' * 1100 + ']' * 1100,
])
def test_invalid_selection_is_rejected_whole_without_source_output(setup, text):
    app, model = setup
    model.reply = Reply(text=text)
    result = subject().summarize(app, context())
    assert result['status'] == 'unavailable' and result['items'] == []
    assert not result['available'] and len(model.calls) == 1
    assert 'Invented' not in str(result)


def test_tool_request_is_not_accepted_or_executed(setup):
    app, model = setup
    model.reply = Reply(text='{"selections":[]}', tool_calls=[ToolCall('x', 'send_mail', {'body': 'injected'})])
    result = subject().summarize(app, context())
    assert result['items'] == [] and result['status'] == 'unavailable'


def test_empty_selection_never_claims_no_open_obligation(setup):
    app, model = setup
    model.reply = Reply(text='{"selections":[]}')
    result = subject().summarize(app, context())
    assert result['items'] == [] and result['status'] == 'empty'
    assert 'keine offenen' not in result['detail'].lower()
    assert 'keine aufgaben' not in result['detail'].lower()


@pytest.mark.parametrize('case', ['remote', 'missing', 'unverified'])
def test_only_verified_local_models_receive_any_content(setup, monkeypatch, case):
    app, model = setup
    if case == 'remote':
        model.is_local = False
    elif case == 'missing':
        monkeypatch.setattr(mail_briefing, '_provider', lambda app: None)
    else:
        def blocked(*args, **kwargs):
            raise ProviderError('PRIVATE_MODEL_DETAILS')
        monkeypatch.setattr(local_model_guard, 'verify_local_model', blocked)
    result = subject().summarize(app, context())
    assert result['status'] == 'unavailable' and not model.calls
    assert 'PRIVATE_MODEL_DETAILS' not in str(result)


@pytest.mark.parametrize('change', ['permission', 'reader', 'settings', 'source', 'weights'])
def test_change_during_selection_discards_all_output(setup, monkeypatch, change):
    app, model = setup
    original = context()
    before = subject().fingerprint(original)
    allowed = [True]
    if change == 'permission':
        model.effect = lambda: allowed.__setitem__(0, False)
    elif change == 'reader':
        model.effect = lambda: setattr(app.state, 'mail', object())
    elif change == 'settings':
        model.effect = lambda: setattr(model, 'model', 'changed:local')
    elif change == 'source':
        model.effect = lambda: original['items'][0].update(sender='Changed sender')
    else:
        weights = ['a' * 64]
        monkeypatch.setattr(local_model_guard, 'verify_local_model', lambda provider, **kwargs:
                            local_model_guard.LocalModelIdentity(provider.model, weights[0]))
        model.effect = lambda: weights.__setitem__(0, 'b' * 64)
    result = subject().summarize(app, original, still_current=lambda: allowed[0])
    assert result['status'] == 'changed' and result['items'] == [] and not result['available']
    assert result['context_fingerprint'] == before


def test_permission_is_checked_before_local_verification_or_completion(setup, monkeypatch):
    app, model = setup
    monkeypatch.setattr(local_model_guard, 'verify_local_model', lambda *args, **kwargs: pytest.fail('No verification allowed'))
    result = subject().summarize(app, context(), still_current=lambda: False)
    assert result['status'] == 'changed' and result['items'] == [] and not model.calls


def test_context_exclusion_and_empty_text_never_call_model(setup):
    app, model = setup
    excluded = context()
    excluded.update(status='excluded', items=[])
    result = subject().summarize(app, excluded)
    assert result['status'] == 'excluded' and result['items'] == []
    empty = context()
    empty['items'] = []
    assert subject().summarize(app, empty)['status'] == 'empty'
    assert not model.calls


def test_more_than_eight_selected_passages_is_rejected(setup):
    app, model = setup
    value = context()
    value['items'] = [dict(value['items'][0], text='\n\n'.join(f'Passage {i}.' for i in range(9)))]
    model.reply = Reply(text=json.dumps({'selections': [{'kind': 'agreement',
        'passage_ids': [f'P1.{i+1}' for i in range(9)]}]}))
    result = subject().summarize(app, value)
    assert result['items'] == [] and result['status'] == 'unavailable'


def test_unknown_date_does_not_hide_the_latest_dated_cancellation(setup):
    app, model = setup
    value = context()
    value['items'].append(dict(value['items'][0], episode_id='undated', occurred_at=None,
                               text='Eine undatierte Quelle sagt etwas anderes.'))
    result = subject().summarize(app, value)
    assert result['items'][0]['episode_id'] == 'e-new'
    assert any('Quellenzeit' in warning for warning in result['warnings'])


def test_returned_model_category_is_never_promoted_to_verified_semantics(setup):
    app, model = setup
    # Even a wrong classification can only label the exact cancellation quote
    # as unconfirmed; ID validation makes no semantic verification claim.
    model.reply = Reply(text='{"selections":[{"kind":"agreement","passage_ids":["P2.1"]}]}')
    result = subject().summarize(app, context())
    assert result['items'][0]['quote'] == 'Die Prüfung ist abgesagt. Bitte nichts versenden.'
    assert result['items'][0]['interpretation'] == 'unconfirmed'
    assert result['semantic_validation'] is False


def test_transient_weight_replacement_does_not_pass_final_original_digest(setup, monkeypatch):
    app, model = setup
    digests = iter(['a' * 64, 'b' * 64, 'a' * 64])
    monkeypatch.setattr(local_model_guard, 'verify_local_model', lambda *args, **kwargs:
                        local_model_guard.LocalModelIdentity(model.model, next(digests)))
    result = subject().summarize(app, context())
    assert result['status'] == 'changed' and result['items'] == []
