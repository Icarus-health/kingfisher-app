"""Kleine Lernaufträge reservieren nicht den großen Gesprächskontext."""
from contextlib import nullcontext
import json
import httpx
import pytest
from icarus_memory.providers import OpenAICompatible, ProviderError
from icarus_memory.local_model_guard import LocalModelIdentity
from icarus_memory.procedure_model import draft
from icarus_memory.procedures import ProcedureError, Spec, validate
from icarus_memory.providers import Reply
from tests.test_procedures import spec


# Die erste echte synthetische Qwen-Probe vom 31.10.: gültiges JSON, aber
# interne Prüfschritte statt Nutzertätigkeit und nur gebeugte Beispielwörter.
BAD_TRIGGER_DRAFT = {'name':'zunftmail-check', 'title':'Zunftmail-Entwurf prüfen',
    'description':'Ablauf zur Prüfung von Zunftmail-Entwürfen vor dem Absenden, um den Anlass zu validieren und den Text gegenzulesen.',
    'area':'mail', 'contexts':['Zunft'],
    'triggers':['Anlass prüfen','Entwurf gegenlesen'],
    'steps':['Anlass des Mails prüfen','Entwurf gegenlesen','Ergebnis prüfen'],
    'positive':'Zunftmail-Entwurf mit geprüftem Anlass und gegengelesenem Text im Kontext Zunft',
    'negative':'Zunftmail-Entwurf ohne Prüfung des Anlass oder ohne Gegenlesen'}
GOOD_TRIGGER_DRAFT = {**spec(), 'contexts':['Zunft'], 'category':'communication',
    'triggers':['zunftmail','zunftmails','zunft'],
    'positive':'Schreibe eine Zunftmail für die Zunft.',
    'negative':'Schreibe eine private Mail zur Urlaubsplanung.'}


class DraftSequence:
    is_local = True
    def __init__(self, replies):
        self.replies = iter(replies)
        self.seen = []
        self.during = lambda: None
    def complete_json(self, messages, **kwargs):
        self.seen.append((messages, kwargs))
        self.during()
        result = next(self.replies)
        if isinstance(result, Exception): raise result
        return Reply(text=result)


def learning_messages():
    return [{'role':'system','content':'Nur ein unbestätigter Ablaufentwurf.'},
            {'role':'user','content':'Bei Zunftmails bitte künftig zuerst Anlass prüfen, dann den Entwurf gegenlesen.'}]


def test_valid_draft_stays_one_call_and_preserves_original_instruction():
    provider = DraftSequence([json.dumps(GOOD_TRIGGER_DRAFT)])
    messages = learning_messages()
    result = draft(provider, messages, Spec.model_json_schema())
    assert validate(json.loads(result.text))['triggers'] == GOOD_TRIGGER_DRAFT['triggers']
    assert len(provider.seen) == 1
    assert provider.seen[0][0][-1] == messages[-1]
    assert messages == learning_messages()
    assert 'Nutzertätigkeit' in provider.seen[0][0][0]['content']


@pytest.mark.parametrize('bad', [json.dumps(BAD_TRIGGER_DRAFT), '{not-json'])
def test_exact_live_failure_gets_one_validator_informed_repair_with_shared_deadline(bad):
    from icarus_memory.providers import _JSON_DEADLINE
    provider = DraftSequence([bad, json.dumps(GOOD_TRIGGER_DRAFT)])
    deadlines = []
    provider.during = lambda: deadlines.append(_JSON_DEADLINE.get())
    result = draft(provider, learning_messages(), Spec.model_json_schema(), permitted=lambda: True)
    assert validate(json.loads(result.text))['contexts'] == ['Zunft']
    assert len(provider.seen) == 2 and deadlines[0] == deadlines[1] and deadlines[0] is not None
    first, second = (entry[0] for entry in provider.seen)
    assert second[-1] == first[-1] == learning_messages()[-1]
    assert second[0]['content'].startswith(first[0]['content'])
    assert 'Validierungsprüfung' in second[0]['content']
    assert bad not in json.dumps(second), 'Fehlerhafte Modellausgabe ist keine vertrauenswürdige Reparaturanweisung.'
    assert provider.seen[0][1] == provider.seen[1][1]


def test_second_invalid_result_stops_without_third_call():
    provider = DraftSequence([json.dumps(BAD_TRIGGER_DRAFT)] * 3)
    with pytest.raises(ProcedureError):
        draft(provider, learning_messages(), Spec.model_json_schema(), permitted=lambda: True)
    assert len(provider.seen) == 2


@pytest.mark.parametrize('failure', [ProviderError('transport failed'), ProviderError('context budget exceeded')])
def test_provider_failure_never_starts_repair(failure):
    provider = DraftSequence([failure, json.dumps(GOOD_TRIGGER_DRAFT)])
    with pytest.raises(ProviderError): draft(provider, learning_messages(), Spec.model_json_schema())
    assert len(provider.seen) == 1


def test_preexisting_shorter_deadline_is_not_extended():
    import time
    from icarus_memory.providers import _JSON_DEADLINE, json_request_deadline
    provider = DraftSequence([json.dumps(BAD_TRIGGER_DRAFT), json.dumps(GOOD_TRIGGER_DRAFT)])
    seen = []
    provider.during = lambda: seen.append(_JSON_DEADLINE.get())
    deadline = time.monotonic() + 10
    with json_request_deadline(deadline):
        draft(provider, learning_messages(), Spec.model_json_schema())
    assert seen == [deadline, deadline]


def test_tool_call_never_becomes_a_repair_instruction():
    provider = DraftSequence([])
    def forbidden(messages, **kwargs):
        provider.seen.append(messages)
        return Reply(text='{}', tool_calls=[object()])
    provider.complete_json = forbidden
    with pytest.raises(ProviderError): draft(provider, learning_messages(), Spec.model_json_schema())
    assert len(provider.seen) == 1


@pytest.mark.parametrize('gate', ['source','permission','deadline'])
def test_source_withdrawal_permission_and_shared_deadline_never_retry(monkeypatch, gate):
    import time
    permitted = [True]
    clock = [time.monotonic()]
    monkeypatch.setattr('icarus_memory.procedure_model.time.monotonic', lambda: clock[0])
    provider = DraftSequence([json.dumps(BAD_TRIGGER_DRAFT), json.dumps(GOOD_TRIGGER_DRAFT)])
    provider._verified_local_permitted = lambda: permitted[0] if gate == 'permission' else True
    def changed():
        if gate == 'deadline': clock[0] += 61
        else: permitted[0] = False
    provider.during = changed
    with pytest.raises(ProviderError):
        draft(provider, learning_messages(), Spec.model_json_schema(),
              permitted=lambda: permitted[0] if gate == 'source' else True)
    assert len(provider.seen) == 1


def test_native_learning_bounds_context_tokens_and_does_not_change_provider(monkeypatch):
    provider = OpenAICompatible('synthetic:9b', base_url='http://127.0.0.1:11434/v1')
    monkeypatch.setattr('icarus_memory.procedure_model.verify_local_model', lambda p: LocalModelIdentity('synthetic:9b','a'*64))
    monkeypatch.setattr(provider, '_ampel', nullcontext)
    seen=[]
    def handle(request):
        seen.append((str(request.url),json.loads(request.content)))
        return httpx.Response(200,json={'model':'synthetic:9b','done':True,'done_reason':'stop',
                                       'message':{'content':'{"example":true}'}})
    monkeypatch.setattr(provider, '_client', lambda timeout:httpx.Client(transport=httpx.MockTransport(handle)))
    assert draft(provider,[{'role':'user','content':'Ein künstlicher Ablauf.'}],{'type':'object'}).text == '{"example":true}'
    url,body=seen[0]
    assert url == 'http://127.0.0.1:11434/api/chat'
    assert body['options']['num_ctx'] == 8192 and body['options']['num_predict'] == 1200
    assert body['think'] is False and body['stream'] is False
    assert 'tools' not in body
    assert provider.model == 'synthetic:9b' and provider.base_url.endswith('/v1')


def test_unverified_model_receives_no_learning_text(monkeypatch):
    provider=OpenAICompatible('remote:cloud',base_url='http://127.0.0.1:11434/v1')
    def reject(_):raise ProviderError('Not local')
    monkeypatch.setattr('icarus_memory.procedure_model.verify_local_model',reject)
    monkeypatch.setattr(provider,'_client',lambda _:pytest.fail('No source submission'))
    with pytest.raises(ProviderError):draft(provider,[{'role':'user','content':'PRIVATE'}],{})


@pytest.mark.parametrize('change',[{'done':False},{'done_reason':'length'},{'message':{'content':'{}','tool_calls':[{}]}}])
def test_incomplete_native_learning_is_not_accepted(monkeypatch,change):
    provider=OpenAICompatible('synthetic:9b',base_url='http://127.0.0.1:11434/v1')
    monkeypatch.setattr('icarus_memory.procedure_model.verify_local_model',lambda p:LocalModelIdentity('synthetic:9b','a'*64))
    monkeypatch.setattr(provider,'_ampel',nullcontext)
    data={'done':True,'done_reason':'stop','message':{'content':'{}'},**change}
    monkeypatch.setattr(provider,'_client',lambda _:httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=data))))
    with pytest.raises(ProviderError):draft(provider,[{'role':'user','content':'Probe'}],{})
