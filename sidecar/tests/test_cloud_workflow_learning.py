"""Own corrections require a separate, bounded cloud approval before transmission."""
import json

import httpx
import pytest

from icarus_memory.providers import ProviderError
from icarus_memory.secrets import PASSPHRASE_ENV
from icarus_memory.mistral_import_provider import MistralImportProvider
from tests.test_workflow_learning import flow, feedback
from tests.test_procedures import spec

ROOT = '/api/v1/procedure-learning'


def seed(flow):
    provider = flow[2]
    provider.complete = lambda *_: (_ for _ in ()).throw(ProviderError('Synthetic local unavailable'))
    return [feedback(flow, n) for n in range(3)]


def configure(flow, monkeypatch):
    monkeypatch.setenv(PASSPHRASE_ENV, 'synthetic-learning-secret')
    # Constructing the app precedes this test helper; install an isolated file keychain.
    from icarus_memory.secrets import Keychain
    flow[0].state.keychain = Keychain(data_dir=flow[0].state.episodes._path.parent)
    client = flow[1]
    response = client.put('/api/v1/models/cloud-access/mistral', json={'api_key':'synthetic-key', 'model':'mistral-small-2603'})
    assert response.status_code == 200, response.text
    budget = client.get('/api/v1/memory/cloud/budget?provider=mistral').json()
    response = client.put('/api/v1/memory/cloud/budget', json={'provider':'mistral', 'consent':True,
        'cap_microusd':1000000, 'expected_revision':budget['revision']})
    assert response.status_code == 200, response.text


def transport(monkeypatch, during=lambda: None):
    calls = []
    def handle(request):
        calls.append(request)
        if request.method == 'GET':
            return httpx.Response(200, json={'data':[{'id':'mistral-small-2603', 'max_context_length':16000,
                'capabilities':{'completion_chat':True}}]})
        payload = json.loads(request.content)
        data = json.loads(payload['messages'][-1]['content'])
        during()
        result = {'kind':'workflow','supporting_ids':[x['id'] for x in data['corrections']],
                  'reason':'Drei Arbeitskorrekturen beschreiben denselben Ablauf.', 'spec':spec()}
        return httpx.Response(200, json={'model':'mistral-small-2603',
            'usage':{'prompt_tokens':200,'completion_tokens':80,'total_tokens':280},
            'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(result)}}]})
    monkeypatch.setattr(MistralImportProvider, '_client', lambda _:httpx.Client(transport=httpx.MockTransport(handle)))
    return calls


def preview(client):
    response = client.post(ROOT+'/preview', json={'area':'mail'})
    assert response.status_code == 200, response.text
    return response.json()


def start(client, packet, consent=True):
    return client.post(ROOT+'/start', json={'preview_id':packet['preview_id'],'consent':consent})


def finish(flow):
    manager = flow[0].state.cloud_workflow_learning
    manager._thread.join(5)
    assert not manager._thread.is_alive()
    response = flow[1].get(ROOT+'/status')
    assert response.status_code == 200, response.text
    return response.json()


def test_preview_without_key_is_offline_and_discloses_exact_learning_input(flow, monkeypatch):
    seed(flow)
    calls = transport(monkeypatch)
    packet = preview(flow[1])
    assert len(packet['payload']['corrections']) == 3
    assert packet['payload']['existing'] == []
    assert not packet['available'] and calls == []
    assert 'Künstlicher Entwurf' not in json.dumps(packet)
    assert start(flow[1], packet).status_code == 409
    assert calls == [] and not flow[0].state.procedures.items()


def test_explicit_cloud_review_creates_pending_skill_once_using_shared_budget(flow, monkeypatch):
    seed(flow); configure(flow, monkeypatch)
    calls = transport(monkeypatch)
    packet = preview(flow[1]); ledger = flow[0].state.mistral_source_budget
    assert start(flow[1], packet, False).status_code == 422
    assert calls == []
    response = start(flow[1], packet)
    assert response.status_code == 200, response.text
    done = finish(flow)
    assert done['job']['state'] == 'complete', done
    identifier = done['job']['result']['proposal_id']
    assert flow[0].state.procedures.get(identifier)['state'] == 'pending'
    assert start(flow[1], packet).status_code in (200,409)
    finish(flow)
    assert len(calls) == 2
    assert all(str(call.url).startswith('https://api.eu.mistral.ai/v1/') for call in calls)
    assert flow[0].state.mistral_source_budget is ledger
    assert done['budget']['spent_microusd'] == 86 and done['budget']['held_microusd'] == 0
    assert flow[1].post(f'/api/v1/procedures/{identifier}/accept').status_code == 200
    assert flow[0].state.procedures.select('Schreibe eine Zunftmail.',area='mail')['contextual']


def test_changed_correction_invalidates_review_without_any_cloud_request(flow, monkeypatch):
    records = seed(flow); configure(flow,monkeypatch); calls = transport(monkeypatch)
    packet = preview(flow[1])
    row = records[0][0]['meldung']
    flow[1].post(f"/api/v1/rueckmeldungen/{row['id']}/arbeitsweise-zuruecknehmen")
    assert start(flow[1],packet).status_code == 409
    assert calls == [] and not flow[0].state.procedures.items()


def test_withdrawal_during_cloud_response_keeps_charge_but_discards_skill(flow, monkeypatch):
    records = seed(flow); configure(flow,monkeypatch)
    row = records[0][0]['meldung']
    calls = transport(monkeypatch,lambda:flow[1].post(f"/api/v1/rueckmeldungen/{row['id']}/arbeitsweise-zuruecknehmen"))
    response = start(flow[1],preview(flow[1]))
    assert response.status_code == 200, response.text
    done = finish(flow)
    assert done['job']['state'] != 'complete'
    assert done['budget']['spent_microusd'] == 86 and done['budget']['held_microusd'] == 0
    assert len(calls) == 2 and not flow[0].state.procedures.items()


@pytest.mark.parametrize('change',['catalog','credential','cap','expiry'])
def test_changed_preview_binding_never_dispatches(flow,monkeypatch,change):
    seed(flow); configure(flow,monkeypatch); calls = transport(monkeypatch)
    packet = preview(flow[1])
    if change == 'catalog':
        flow[0].state.procedures.propose(spec())
    elif change == 'credential':
        flow[1].put('/api/v1/models/cloud-access/mistral',json={'api_key':'another-synthetic-key','model':'mistral-small-2603'})
    elif change == 'cap':
        flow[1].put('/api/v1/memory/cloud/budget',json={'provider':'mistral','cap_microusd':900000,
            'expected_revision':packet['budget']['revision'],'consent':True})
    else:
        flow[0].state.cloud_workflow_learning._previews[packet['preview_id']].expires = 0
    assert start(flow[1],packet).status_code == 409
    assert calls == []


def test_remote_payload_ceiling_applies_even_when_answer_model_is_local(flow,monkeypatch):
    from icarus_memory import Kind, Provenance, SourceType, Sensitivity
    seed(flow); configure(flow,monkeypatch); calls = transport(monkeypatch)
    text = 'Bitte zuerst Anlass und Empfänger prüfen, danach den Entwurf gegenlesen.'
    flow[0].state.agent._store.record(text,Kind.PREFERENCE,Provenance(SourceType.USER_STATED),sensitivity=Sensitivity.SENSITIVE)
    assert flow[0].state.agent.provider.is_local
    response = start(flow[1],preview(flow[1]))
    assert response.status_code == 200
    done = finish(flow)
    assert done['job']['state'] == 'failed' and calls == []
    assert done['budget']['spent_microusd'] == 0


def test_cancel_during_response_accounts_once_and_never_admits_result(flow,monkeypatch):
    seed(flow); configure(flow,monkeypatch)
    calls = transport(monkeypatch,lambda:flow[1].post(ROOT+'/revoke',json={
        'job_id':flow[1].get(ROOT+'/status').json()['job']['id']}))
    assert start(flow[1],preview(flow[1])).status_code == 200
    result = finish(flow)
    assert result['job']['state'] == 'cancelled'
    assert result['budget']['spent_microusd'] == 86 and len(calls) == 2
    assert not flow[0].state.procedures.items()


def test_restart_consumed_preview_cannot_dispatch_again(flow,monkeypatch):
    from icarus_memory.cloud_workflow_learning import CloudWorkflowLearning
    seed(flow); configure(flow,monkeypatch); calls = transport(monkeypatch)
    packet = preview(flow[1])
    service = flow[0].state.cloud_workflow_learning
    # Simulate process death after the durable start marker but before HTTP.
    monkeypatch.setattr(service,'_run',lambda *args:None)
    assert start(flow[1],packet).status_code == 200
    service._thread.join(5)
    resumed = CloudWorkflowLearning(flow[0],service.path.parent)
    flow[0].state.cloud_workflow_learning = resumed
    result = start(flow[1],packet)
    assert result.status_code == 200 and result.json()['job']['state'] == 'interrupted'
    assert calls == []


def test_learning_status_reuses_inflight_import_budget_instance(flow,monkeypatch):
    from icarus_memory.cloud_import_budget import MODEL
    seed(flow); configure(flow,monkeypatch); calls = transport(monkeypatch)
    ledger = flow[0].state.mistral_source_budget
    before = ledger.status()
    reservation = ledger.reserve('synthetic-import',MODEL,16000,1200,
        budget_id=before['budget_id'],revision=before['revision'],price_id=before['price_id'])
    held = ledger.status()['held_microusd']
    packet = preview(flow[1])
    assert start(flow[1],packet).status_code == 409
    assert not flow[1].get(ROOT+'/status').json()['budget']['reconciliation_required']
    assert ledger.status()['held_microusd'] == held and flow[0].state.mistral_source_budget is ledger
    assert calls == []
    ledger.cancel_unsent(reservation)


def test_transport_respects_existing_shorter_learning_deadline():
    import time
    from icarus_memory.providers import json_request_deadline
    provider = object.__new__(MistralImportProvider)
    with json_request_deadline(time.monotonic()+2):
        with provider._client() as client:
            assert 0 < client.timeout.read <= 2


def test_accepted_cloud_skill_is_invalidated_by_its_own_withdrawn_correction(flow,monkeypatch):
    records = seed(flow); configure(flow,monkeypatch); transport(monkeypatch)
    assert start(flow[1],preview(flow[1])).status_code == 200
    result = finish(flow)
    identifier = result['job']['result']['proposal_id']
    path = f'/api/v1/procedures/{identifier}'
    assert flow[1].get(path).json()['synthesis'] == {'provider':'mistral','model':'mistral-small-2603'}
    assert flow[1].post(path+'/accept').status_code == 200
    record = records[0][0]['meldung']['id']
    assert flow[1].post(f'/api/v1/rueckmeldungen/{record}/arbeitsweise-zuruecknehmen').status_code == 200
    assert not flow[1].get(path).json()['current']
    assert not flow[0].state.procedures.select('Schreibe eine Zunftmail.',area='mail')['contextual']
    assert flow[1].get(ROOT+'/status').json()['job']['result'] == {'status':'changed'}


@pytest.mark.parametrize('route,body',[
    ('preview',{'area':'mail','unexpected':'synthetic-private-api-key'}),
    ('start',{'preview_id':'synthetic-private-api-key','consent':True}),
    ('revoke',{'job_id':'synthetic-private-api-key'}),
])
def test_bad_cloud_control_input_does_not_reflect_private_values(flow,route,body):
    response = flow[1].post(ROOT+'/'+route,json=body)
    assert response.status_code == 422
    assert 'synthetic-private-api-key' not in response.text


def test_local_negative_does_not_prevent_explicit_mistral_second_opinion(flow,monkeypatch):
    from icarus_memory.providers import Reply
    flow[2].complete = lambda *_: Reply(text=json.dumps({'kind':'none','supporting_ids':[],
        'reason':'Künstlicher lokaler Fehlentscheid.', 'spec':None}))
    for n in range(3):
        feedback(flow,n)
    configure(flow,monkeypatch); calls = transport(monkeypatch)
    packet = preview(flow[1])
    assert start(flow[1],packet).status_code == 200
    assert finish(flow)['job']['result']['status'] == 'proposed'
    assert len(calls) == 2


@pytest.mark.parametrize('state',['pending','active'])
def test_reusing_manual_skill_preserves_authorship_and_current_state(flow,monkeypatch,state):
    seed(flow); configure(flow,monkeypatch); transport(monkeypatch)
    app,client,_ = flow
    original = app.state.procedures.propose(spec())
    if state == 'active':
        app.state.procedures.accept(original['id'])
    assert start(client,preview(client)).status_code == 200
    result = finish(flow)['job']['result']
    assert result['proposal_id'] == original['id']
    assert result['status'] == ('active' if state == 'active' else 'proposed')
    assert result['reused'] is True
    stored = client.get('/api/v1/procedures/'+original['id']).json()
    assert not stored.get('synthesis')
    assert stored['sources'] == {} and stored['state'] == state


def test_proposal_synthesis_origin_survives_standard_backup_restore(flow,monkeypatch,tmp_path):
    from icarus_memory.backup import snapshot_all, restore_all
    from icarus_memory.procedures import ProcedureStore
    seed(flow); configure(flow,monkeypatch); transport(monkeypatch)
    app,client,_ = flow
    assert start(client,preview(client)).status_code == 200
    identifier = finish(flow)['job']['result']['proposal_id']
    service = app.state.cloud_workflow_learning
    snapshot = snapshot_all(service.path.parent,tmp_path/'backups')
    restored_dir = tmp_path/'restored'
    restore_all(snapshot,restored_dir)
    assert not (restored_dir/service.path.name).exists()
    assert not (restored_dir/'mistral-source-budget.sqlite3').exists()
    restored = ProcedureStore(restored_dir/'procedures.sqlite3',dependency=app.state.procedures.dependency)
    try:
        assert restored.get(identifier).get('synthesis') == {'provider':'mistral','model':'mistral-small-2603'}
    finally:
        restored.close()


@pytest.mark.parametrize('action,expected',[('accept','active'),('reject','dismissed'),('revoke','dismissed')])
def test_cloud_receipt_reads_current_proposal_activation(flow,monkeypatch,action,expected):
    seed(flow); configure(flow,monkeypatch); calls = transport(monkeypatch)
    app,client,_ = flow
    assert start(client,preview(client)).status_code == 200
    identifier = finish(flow)['job']['result']['proposal_id']
    path = '/api/v1/procedures/'+identifier
    if action == 'revoke':
        assert client.post(path+'/accept').status_code == 200
    assert client.post(path+'/'+action).status_code == 200
    result = client.get(ROOT+'/status').json()['job']['result']
    assert result['status'] == expected
    assert len(calls) == 2
