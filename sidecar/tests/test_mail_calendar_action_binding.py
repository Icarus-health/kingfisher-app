"""Mail-derived calendar previews stay source-bound through provider writes."""
from contextlib import contextmanager
import json
import pytest
from icarus_memory.calendar_actions import ActionError, CalendarActions
from tests.test_calendar_actions import action_service

BINDING={'id':'mp'+'a'*64,'stand':'b'*64}
INPUT=dict(kind='create',source_id='calendar-one',title='Synthetic appointment',
           start='2026-10-12T10:00:00+02:00',end='2026-10-12T11:00:00+02:00',send_updates='none')

def test_local_preparation_is_not_a_calendar_preview_or_executable(tmp_path):
    service,_,_,provider=action_service(tmp_path)
    record={'id':'local','status':'preparation','kind':'mail_preparation','stand':'c'*64,
            'preview':{'title':'Private original source'}}
    with service._db() as db:
        db.execute('INSERT INTO actions VALUES (?,?,?)',('local','preparation',json.dumps(record)))
    with pytest.raises(ActionError):service.get('local')
    with pytest.raises(ActionError):service.execute('local',confirmed=True,stand=record['stand'])
    assert provider.writes==[]

def test_same_mail_revision_has_one_preview_and_one_provider_write_after_restart(tmp_path):
    service,_,_,provider=action_service(tmp_path)
    seen=[]
    @contextmanager
    def guard(binding):
        assert binding==BINDING;seen.append(binding);yield
    service.source_guard=guard
    first=service.draft(**INPUT,mail_preparation=BINDING)
    restarted=CalendarActions(service.path,service.settings,service.oauth,provider)
    restarted.source_guard=guard
    second=restarted.draft(**INPUT,mail_preparation=BINDING)
    assert first['id']==second['id'] and first['stand']==second['stand']
    assert restarted.execute(first['id'],confirmed=True,stand=first['stand'])['status']=='done'
    assert restarted.execute(second['id'],confirmed=True,stand=second['stand'])['status']=='done'
    assert len(provider.writes)==1 and seen

def test_missing_mail_source_guard_blocks_external_effect(tmp_path):
    service,_,_,provider=action_service(tmp_path)
    draft=service.draft(**INPUT,mail_preparation=BINDING)
    with pytest.raises(ActionError):service.execute(draft['id'],confirmed=True,stand=draft['stand'])
    assert provider.writes==[]

def test_source_change_during_provider_read_is_rechecked_before_create(tmp_path):
    service,_,_,provider=action_service(tmp_path)
    state={'valid':True}
    @contextmanager
    def guard(binding):
        if not state['valid']:raise ActionError('Quelle geändert.',409)
        yield
    service.source_guard=guard
    draft=service.draft(**INPUT,mail_preparation=BINDING)
    def event(*args):state['valid']=False;return None
    provider.event=event
    with pytest.raises(ActionError):service.execute(draft['id'],confirmed=True,stand=draft['stand'])
    assert provider.writes==[]

def test_normal_calendar_get_does_not_disclose_changed_mail_preview(tmp_path):
    service,_,_,provider=action_service(tmp_path)
    draft=service.draft(**INPUT,mail_preparation=BINDING)
    @contextmanager
    def changed(binding):raise ActionError('Quelle geändert.',409);yield
    service.source_guard=changed
    with pytest.raises(ActionError):service.get(draft['id'])
    assert provider.writes==[]

def allow_source(service):
    @contextmanager
    def guard(binding):yield
    service.source_guard=guard


def reauthorize(service, keys):
    from icarus_memory import config
    key=config.integration_secret_name('calendar','calendar-one')
    grant=json.loads(keys.get(key));grant['grant_id']='grant-two'
    keys.set(key,json.dumps(grant))


def test_done_replay_rechecks_source_without_changing_done_journal(tmp_path):
    service,_,_,provider=action_service(tmp_path)
    allow_source(service)
    draft=service.draft(**INPUT,mail_preparation=BINDING)
    service.execute(draft['id'],confirmed=True,stand=draft['stand'])
    @contextmanager
    def withdrawn(binding):raise ActionError('Quelle entzogen.',409);yield
    service.source_guard=withdrawn
    with pytest.raises(ActionError):service.execute(draft['id'],confirmed=True,stand=draft['stand'])
    with service._db() as db:
        assert db.execute('SELECT status FROM actions WHERE id=?',(draft['id'],)).fetchone()['status']=='done'
    assert len(provider.writes)==1


def test_reauthorization_repreviews_unexecuted_mail_and_invalidates_old_confirmation(tmp_path):
    service,_,keys,provider=action_service(tmp_path)
    allow_source(service)
    old=service.draft(**INPUT,mail_preparation=BINDING)
    reauthorize(service,keys)
    with pytest.raises(ActionError):service.execute(old['id'],confirmed=True,stand=old['stand'])
    restarted=CalendarActions(service.path,service.settings,service.oauth,provider)
    allow_source(restarted)
    new=restarted.draft(**INPUT,mail_preparation=BINDING)
    assert new['id']==old['id'] and new['stand']!=old['stand'] and new['status']=='draft'
    with pytest.raises(ActionError):restarted.execute(old['id'],confirmed=True,stand=old['stand'])
    assert restarted.execute(new['id'],confirmed=True,stand=new['stand'])['status']=='done'
    assert len(provider.writes)==1


def test_reauthorization_after_done_never_creates_another_event(tmp_path):
    service,_,keys,provider=action_service(tmp_path)
    allow_source(service)
    old=service.draft(**INPUT,mail_preparation=BINDING)
    service.execute(old['id'],confirmed=True,stand=old['stand'])
    reauthorize(service,keys)
    new=service.draft(**INPUT,mail_preparation=BINDING)
    assert new['id']==old['id'] and new['status']=='done'
    assert service.execute(new['id'],confirmed=True,stand=new['stand'])['status']=='done'
    assert len(provider.writes)==1


def test_reauthorization_after_uncertain_never_rearms_external_create(tmp_path):
    service,_,keys,provider=action_service(tmp_path)
    allow_source(service)
    old=service.draft(**INPUT,mail_preparation=BINDING)
    provider.fail_after_create=True
    assert service.execute(old['id'],confirmed=True,stand=old['stand'])['status']=='uncertain'
    reauthorize(service,keys)
    new=service.draft(**INPUT,mail_preparation=BINDING)
    assert new['id']==old['id'] and new['status']=='uncertain'
    with pytest.raises(ActionError):service.execute(new['id'],confirmed=True,stand=new['stand'])
    again=service.draft(**INPUT,mail_preparation=BINDING)
    assert again['status']!='draft'
    assert len(provider.writes)==1

@pytest.mark.parametrize('outcome',['existing','missing','error'])
def test_reconciliation_public_return_rechecks_source_after_provider_read(tmp_path,outcome):
    service,_,_,provider=action_service(tmp_path)
    valid={'value':True}
    @contextmanager
    def guard(binding):
        if not valid['value']:raise ActionError('Quelle entzogen.',409)
        yield
    service.source_guard=guard
    draft=service.draft(**INPUT,mail_preparation=BINDING)
    # Simulate the durable uncertainty after a lost response.
    with service._db() as db:
        raw=json.loads(db.execute('SELECT record FROM actions WHERE id=?',(draft['id'],)).fetchone()['record'])
        raw['status']='uncertain';raw['write_attempted']=True
        db.execute('UPDATE actions SET status=?,record=? WHERE id=?',('uncertain',json.dumps(raw),draft['id']))
    def event(*args):
        valid['value']=False
        if outcome=='error':raise OSError('read failed')
        return {**raw['body']} if outcome=='existing' else None
    provider.event=event
    with pytest.raises(ActionError):service.execute(draft['id'],confirmed=True,stand=draft['stand'])
    with service._db() as db:
        status=db.execute('SELECT status FROM actions WHERE id=?',(draft['id'],)).fetchone()['status']
    assert status==('done' if outcome=='existing' else 'uncertain')
    assert provider.writes==[]
