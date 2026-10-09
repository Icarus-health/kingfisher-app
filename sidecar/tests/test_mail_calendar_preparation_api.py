"""Synthetic source-bound mail/calendar workflow; no live accounts or models."""
from dataclasses import replace
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from icarus_memory.server import create_app
from icarus_memory.mail_ingestion import remember
from tests.test_mail_thread import mail
from tests.test_calendar_actions import action_service


def setup(tmp_path,monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR',str(tmp_path))
    app=create_app()
    state={'mail':mail('1',mid='<meeting@example.invalid>',body='Treffen: 2026-10-12T10:00:00+02:00 bis 2026-10-12T11:00:00+02:00')}
    app.state.mail=SimpleNamespace(message=lambda uid:state['mail'])
    service,settings,keys,provider=action_service(tmp_path)
    # Keep the installed journal; substitute only synthetic provider/settings.
    app.state.calendar_actions.settings=lambda:settings
    app.state.calendar_actions.oauth=service.oauth
    app.state.calendar_actions.provider=provider
    provider.calendar=lambda *a: (_ for _ in ()).throw(AssertionError('No calendar reads during local preparation'))
    return app,state,provider,TestClient(app)


def prepare(client):
    opened=client.get('/api/v1/messages/work:1');assert opened.status_code==200
    return client.post('/api/v1/messages/work:1/calendar-preparation',json={'source_binding':opened.json()['calendar_source_digest']})


def test_local_prepare_is_source_bound_persistent_and_not_a_provider_action(tmp_path,monkeypatch):
    app,state,provider,client=setup(tmp_path,monkeypatch)
    first=prepare(client);assert first.status_code==201,first.text
    record=first.json();assert record['status']=='preparation' and record['reviewed'] is False
    assert record['fields']['start']=='2026-10-12T10:00:00+02:00'
    assert record['fields']['end']=='2026-10-12T11:00:00+02:00'
    assert prepare(client).json()['id']==record['id']
    assert client.get('/api/v1/mail-calendar-preparations/'+record['id']).json()==record
    assert client.get('/api/v1/calendar-actions/drafts/'+record['id']).status_code==409
    assert client.post('/api/v1/calendar-actions/drafts/'+record['id']+'/execute',json={'confirmed':True,'stand':record['stand']}).status_code==409
    assert provider.writes==[] and app.state.tasks.all_tasks()==[] and app.state.episodes.all_episodes()==[]


@pytest.mark.parametrize('change',[
    lambda m:replace(m,body='Termin abgesagt.'),
    lambda m:replace(m,recipients=({'email':'different@example.invalid','role':'an'},)),
    lambda m:replace(m,in_reply_to='<changed@example.invalid>'),
    lambda m:replace(m,date=None),
])
def test_opening_binding_detects_calendar_relevant_change(tmp_path,monkeypatch,change):
    app,state,provider,client=setup(tmp_path,monkeypatch)
    opened=client.get('/api/v1/messages/work:1').json()
    state['mail']=change(state['mail'])
    result=client.post('/api/v1/messages/work:1/calendar-preparation',json={'source_binding':opened['calendar_source_digest']})
    assert result.status_code==409 and provider.writes==[]


def test_new_known_reply_invalidates_saved_preparation_without_leaking_old_fields(tmp_path,monkeypatch):
    app,state,provider,client=setup(tmp_path,monkeypatch)
    record=prepare(client).json()
    remember(app.state.episodes,mail('2',mid='<cancel@example.invalid>',reply='<meeting@example.invalid>',body='Das Treffen entfällt.',day=2))
    result=client.get('/api/v1/mail-calendar-preparations/'+record['id'])
    assert result.status_code==409 and '2026-10-12T10:00' not in result.text
    assert provider.writes==[]


def test_ignore_reopen_requires_new_review_even_with_identical_original(tmp_path,monkeypatch):
    app,state,provider,client=setup(tmp_path,monkeypatch)
    episode=remember(app.state.episodes,state['mail'])['episode']
    record=prepare(client).json()
    app.state.episodes.ignore(episode['id']);app.state.episodes.reopen(episode['id'])
    assert client.get('/api/v1/mail-calendar-preparations/'+record['id']).status_code==409
    assert provider.writes==[]


def test_reviewed_local_draft_hands_off_once_and_rechecks_before_external_write(tmp_path,monkeypatch):
    app,state,provider,client=setup(tmp_path,monkeypatch)
    record=prepare(client).json()
    path='/api/v1/mail-calendar-preparations/'+record['id']
    assert client.post(path+'/preview',json={'stand':record['stand'],'source_id':'calendar-one','send_updates':'none'}).status_code==422
    reviewed=client.put(path,json={'stand':record['stand'],'fields':record['fields'],'reviewed':True})
    assert reviewed.status_code==200,reviewed.text
    record=reviewed.json();provider.calendar=lambda source,key:{'id':source.url,'accessRole':'owner'}
    body={'stand':record['stand'],'source_id':'calendar-one','send_updates':'none'}
    first=client.post(path+'/preview',json=body);assert first.status_code==201,first.text
    assert client.post(path+'/preview',json=body).json()['id']==first.json()['id']
    state['mail']=replace(state['mail'],body='Termin abgesagt.')
    result=client.post('/api/v1/calendar-actions/drafts/'+first.json()['id']+'/execute',json={'confirmed':True,'stand':first.json()['stand']})
    assert result.status_code==409 and provider.writes==[]


def test_reviewed_handoff_survives_app_restart_and_executes_once(tmp_path,monkeypatch):
    app,state,provider,client=setup(tmp_path,monkeypatch)
    record=prepare(client).json();path='/api/v1/mail-calendar-preparations/'+record['id']
    record=client.put(path,json={'stand':record['stand'],'fields':record['fields'],'reviewed':True}).json()
    provider.calendar=lambda source,key:{'id':source.url,'accessRole':'owner'}
    body={'stand':record['stand'],'source_id':'calendar-one','send_updates':'none'}
    first=client.post(path+'/preview',json=body).json()
    restarted,restarted_state,second_provider,second_client=setup(tmp_path,monkeypatch)
    second_provider.calendar=lambda source,key:{'id':source.url,'accessRole':'owner'}
    assert second_client.get(path).status_code==200
    second=second_client.post(path+'/preview',json=body).json()
    assert second['id']==first['id']
    url='/api/v1/calendar-actions/drafts/'+first['id']+'/execute'
    payload={'confirmed':True,'stand':first['stand']}
    assert second_client.post(url,json=payload).json()['status']=='done'
    # Successful execution rebuilds connectors from real saved settings. The
    # isolated fixture has no real mail account; restore its synthetic reader.
    restarted.state.mail=SimpleNamespace(message=lambda uid:restarted_state['mail'])
    replay=second_client.post(url,json=payload)
    assert replay.status_code==200,replay.text
    assert replay.json()['status']=='done'
    assert len(second_provider.writes)==1


def test_editing_local_preparation_invalidates_earlier_google_preview(tmp_path,monkeypatch):
    app,state,provider,client=setup(tmp_path,monkeypatch)
    record=prepare(client).json();path='/api/v1/mail-calendar-preparations/'+record['id']
    record=client.put(path,json={'stand':record['stand'],'fields':record['fields'],'reviewed':True}).json()
    provider.calendar=lambda source,key:{'id':source.url,'accessRole':'owner'}
    first=client.post(path+'/preview',json={'stand':record['stand'],'source_id':'calendar-one','send_updates':'none'}).json()
    fields={**record['fields'],'title':'User changed title'}
    assert client.put(path,json={'stand':record['stand'],'fields':fields,'reviewed':False}).status_code==200
    url='/api/v1/calendar-actions/drafts/'+first['id']+'/execute'
    assert client.post(url,json={'confirmed':True,'stand':first['stand']}).status_code==409
    assert provider.writes==[]


def test_removed_mail_connection_blocks_without_claiming_uncertain_provider_write(tmp_path,monkeypatch):
    app,state,provider,client=setup(tmp_path,monkeypatch)
    record=prepare(client).json();path='/api/v1/mail-calendar-preparations/'+record['id']
    record=client.put(path,json={'stand':record['stand'],'fields':record['fields'],'reviewed':True}).json()
    provider.calendar=lambda source,key:{'id':source.url,'accessRole':'owner'}
    draft=client.post(path+'/preview',json={'stand':record['stand'],'source_id':'calendar-one','send_updates':'none'}).json()
    app.state.mail=None
    result=client.post('/api/v1/calendar-actions/drafts/'+draft['id']+'/execute',json={'confirmed':True,'stand':draft['stand']})
    assert result.status_code==409
    assert provider.writes==[]
