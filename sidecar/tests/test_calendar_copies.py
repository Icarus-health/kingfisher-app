"""Collapse proven mirror copies for reading while retaining each source reference."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from icarus_memory.connectors.calendar import Event, parse_events
from icarus_memory.connectors.collections import CalendarCollection, NamedCalendar
from icarus_memory.mac_calendar import MacCalendar, WorkerUpdate

START=datetime(2026,10,10,18,tzinfo=timezone.utc)
class Reader:
    def __init__(self,events):self.items=events
    def events(self,**kwargs):return self.items

def event(uid,external='same@example.test',start=START,summary='Konzert',location='Saal, Haus 1'):
    e=Event(uid,summary,start,start+timedelta(hours=1),location=location)
    e.external_uid=external
    return e

def collection(*items):
    return CalendarCollection([NamedCalendar(source,source,Reader(events)) for source,events in items])

def test_mac_and_ical_copy_are_one_visible_event_with_both_original_refs():
    mac=event('opaque-local');ical=event('provider-uid')
    result=collection(('mac-calendar',[mac]),('ical',[ical])).events()
    assert len(result)==1
    record=result[0].to_dict()
    assert record['uid']=='ical:provider-uid'  # retain existing connected-feed links
    assert {c['uid'] for c in record['source_copies']}=={'mac-calendar:opaque-local','ical:provider-uid'}
    assert mac.uid=='opaque-local' and ical.uid=='provider-uid'  # no reader-cache mutation


def test_similar_title_and_time_without_shared_external_id_stays_separate():
    assert len(collection(('a',[event('a','first')]),('b',[event('b','second')])).events())==2
    assert len(collection(('a',[event('a','')]),('b',[event('b','')])).events())==2


def test_recurring_instances_and_disagreeing_copies_are_not_hidden():
    a=event('a');later=event('b',start=START+timedelta(days=7))
    assert len(collection(('a',[a]),('b',[later])).events())==2
    for field,value in [('summary','Anderer Titel'),('location','Anderer Ort'),('end',START+timedelta(hours=2)),('attendees',['someone@example.test']),('all_day',True)]:
        changed=replace(a,uid='changed',**{field:value});changed.external_uid=a.external_uid
        assert len(collection(('a',[a]),('b',[changed])).events())==2,field


def test_naive_dates_and_same_source_duplicates_are_not_merged():
    a=event('a',start=START.replace(tzinfo=None));b=event('b',start=START.replace(tzinfo=None))
    assert len(collection(('a',[a]),('b',[b])).events())==2
    assert len(collection(('a',[event('a'),event('b')])).events())==2


def test_ical_text_unescaping_and_external_identity_are_retained():
    records=parse_events('BEGIN:VEVENT\nUID:copy@example.test\nSUMMARY:Konzert\\, Band\nLOCATION:Saal\\, Haus 1\nDTSTART:20261010T180000Z\nDTEND:20261010T190000Z\nEND:VEVENT')
    assert records[0].summary=='Konzert, Band' and records[0].location=='Saal, Haus 1'
    assert records[0].external_uid=='copy@example.test'


def test_mac_live_snapshot_retains_external_identifier(tmp_path):
    mac=MacCalendar(tmp_path/'mac.sqlite3');mac.enable()
    mac.update(WorkerUpdate(generation=1,status='granted',calendars=[{'id':'cal','name':'Test'}]))
    mac.select(['cal'])
    mac.update(WorkerUpdate(generation=2,status='granted',range_from=START,range_to=START+timedelta(days=1),calendars=[{'id':'cal','name':'Test'}],events=[{
        'uid':'local','external_uid':'server@example.test','summary':'Termin','source_id':'cal','start':START,'end':START+timedelta(hours=1)}]))
    result=mac.events(days=1,at=START)
    assert result[0].external_uid=='server@example.test'


def test_original_reference_stays_usable_and_revoked_alias_disappears(tmp_path,monkeypatch):
    from tests.test_multi_integrations import _client
    client=_client(tmp_path,monkeypatch)
    client.app.state.calendar=collection(('mac-calendar',[event('local')]),('ical',[event('remote')]))
    for uid in ['mac-calendar:local','ical:remote']:
        assert client.get('/api/v1/calendar/zuordnung',params={'uid':uid,'start':START.isoformat()}).status_code==200
    client.app.state.calendar=collection(('ical',[event('remote')]))
    assert client.get('/api/v1/calendar/zuordnung',params={'uid':'mac-calendar:local','start':START.isoformat()}).status_code==404


def test_new_external_identity_does_not_change_persisted_event_shape(tmp_path):
    mac=MacCalendar(tmp_path/'mac.sqlite3');mac.enable()
    mac.update(WorkerUpdate(generation=1,status='granted',calendars=[{'id':'cal','name':'Test'}]));mac.select(['cal'])
    mac.update(WorkerUpdate(generation=2,status='granted',calendars=[{'id':'cal','name':'Test'}],events=[{
        'uid':'local','external_uid':'server@example.test','summary':'Termin','source_id':'cal','start':START,'end':START+timedelta(hours=1)}]))
    assert 'external_uid' not in mac.read()['events'][0]  # prior wrapper/backend can still read its old cache
    assert 'external_uids' not in mac.public()  # identity map is internal metadata


def test_alias_project_is_preserved_conflicts_are_visible_and_choice_resolves(tmp_path,monkeypatch):
    from tests.test_multi_integrations import _client
    client=_client(tmp_path,monkeypatch)
    client.app.state.calendar=collection(('mac-calendar',[event('local')]),('ical',[event('remote')]))
    workspace=client.app.state.workspace
    first=client.post('/api/v1/projects',json={'name':'Atlas'}).json()['id']
    second=client.post('/api/v1/projects',json={'name':'Boreal'}).json()['id']
    workspace.set_event_project('mac-calendar:local',first)
    params={'uid':'ical:remote','start':START.isoformat()}
    assert client.get('/api/v1/calendar/zuordnung',params=params).json()['projekt']['id']==first
    workspace.set_event_project('ical:remote',second)
    conflict=client.get('/api/v1/calendar/zuordnung',params=params).json()
    assert conflict['projekt'] is None and conflict['zuordnungskonflikt'] is True
    result=client.put('/api/v1/calendar/zuordnung',json={**params,'project_id':first})
    assert result.status_code==200 and result.json()['projekt']['id']==first
    assert not result.json()['zuordnungskonflikt']
    assert workspace.event_project('mac-calendar:local')==(True,first)
    workspace.set_event_project('mac-calendar:local',None)
    workspace.set_event_project('ical:remote',None)
    result=client.get('/api/v1/calendar/zuordnung',params=params).json()
    assert result['festgelegt'] and result['projekt'] is None


def test_alias_followup_is_not_asked_again_and_reopens_all_nothing_copies(tmp_path,monkeypatch):
    from tests.test_multi_integrations import _client
    from icarus_memory.nachbereitung import offene,schluessel
    client=_client(tmp_path,monkeypatch)
    start=datetime.now(timezone.utc)-timedelta(hours=2)
    a=event('local',start=start);a.attendees=['guest@example.test']
    b=replace(a,uid='remote')
    client.app.state.calendar=collection(('mac-calendar',[a]),('ical',[b]))
    items=[e.to_dict() for e in client.app.state.calendar.events()]
    key=schluessel('mac-calendar:local',start)
    client.app.state.workspace.set_event_followup(key,None)
    assert offene(items,jetzt=datetime.now(timezone.utc),eigene=[],erledigt={key:None})==[]
    assert offene(items,jetzt=datetime.now(timezone.utc),eigene=[],erledigt={},hat_mitschrift=lambda k:k==key)==[]
    params={'uid':'ical:remote','start':start.isoformat()}
    assert client.get('/api/v1/calendar/nachbereitung',params=params).json()['stand']=='nichts'
    result=client.put('/api/v1/calendar/nachbereitung/stand',json={**params,'nichts':False})
    assert result.status_code==200 and result.json()['stand']=='offen'
    client.app.state.workspace.set_event_followup(key,'source-old')
    client.put('/api/v1/calendar/nachbereitung/stand',json={**params,'nichts':True})
    assert client.get('/api/v1/calendar/nachbereitung',params=params).json()['episode_id']=='source-old'


def test_followup_explicit_project_choice_resolves_alias_conflict_even_when_primary_agrees(tmp_path,monkeypatch):
    from tests.test_multi_integrations import _client
    client=_client(tmp_path,monkeypatch)
    start=datetime.now(timezone.utc)-timedelta(hours=2)
    client.app.state.calendar=collection(('mac-calendar',[event('local',start=start)]),('ical',[event('remote',start=start)]))
    first=client.post('/api/v1/projects',json={'name':'Atlas'}).json()['id']
    second=client.post('/api/v1/projects',json={'name':'Boreal'}).json()['id']
    client.app.state.workspace.set_event_project('ical:remote',first)
    client.app.state.workspace.set_event_project('mac-calendar:local',second)
    result=client.post('/api/v1/calendar/nachbereitung',json={'uid':'ical:remote','start':start.isoformat(),'text':'Besprochen.','format':'text','project_id':first})
    assert result.status_code==200
    assert client.app.state.workspace.event_project('mac-calendar:local')==(True,first)
