"""The UI's six source reads stay authenticated, local and non-mutating.

Artificial originals only. This checks existing HTTP contracts, not a native
window, real accounts or actual throughput/model quality.
"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from tests.test_browser_feature_auth import browser  # existing isolated cookie fixture
from icarus_memory.config import MailAccountSettings, CalendarSourceSettings

PATHS = ('integrations', 'mail/intake', 'schedule', 'mac-calendar', 'folder-sync', 'transcript-sync')


def test_source_metadata_contracts_keep_originals_permissions_and_last_success(browser, monkeypatch):
    app = browser.app
    def forbidden(*_args, **_kwargs):
        pytest.fail('Source metadata must not fetch provider content, verify a model, or scan files')
    monkeypatch.setattr('socket.socket.connect', forbidden)
    monkeypatch.setattr('icarus_memory.local_model_guard.verify_local_model', forbidden)
    app.state.calendar = SimpleNamespace(events=forbidden)
    app.state.mail = SimpleNamespace(reader_for=lambda _id: None)
    app.state.settings.mail_accounts = [MailAccountSettings(id='qa-mail',label='Synthetic mailbox',imap_host='example.test',user='qa@example.test')]
    app.state.settings.calendar_sources = [CalendarSourceSettings(id='qa-cal',label='Synthetic external calendar',kind='ical',url='https://example.test/calendar.ics')]
    app.state.settings.mail_sync_status = {'qa-mail':{'last_attempt':'2026-10-09T10:00:00Z',
        'last_success':'2026-10-08T10:00:00Z','last_failure':'unavailable'}}
    app.state.hintergrund.pausieren(True)
    app.state.settings.schedule.enabled = False
    original = browser.post('/api/v1/sources/documents',json={'filename':'Synthetic.txt','body':'Synthetic immutable source.','project_id':None})
    assert original.status_code in (200,201), original.text
    ident = original.json()['id']
    before = browser.get(f'/api/v1/episodes/{ident}').json()
    settings_before = deepcopy(app.state.settings)
    counts_before = app.state.episodes.counts()
    calendar_before = app.state.mac_calendar.read()
    results = {}
    for path in PATHS:
        response = browser.get('/api/v1/'+path)
        assert response.status_code == 200, (path,response.text)
        results[path] = response.json()
    assert results['integrations']['calendar_sources'][0]['configured'] is True
    assert results['mail/intake']['accounts'][0]['started'] is False
    assert results['mail/intake']['background_paused'] is True
    assert results['schedule']['mail_status']['qa-mail']['last_success']=='2026-10-08T10:00:00Z'
    assert results['mac-calendar']['selected']==[]
    for path in ('folder-sync','transcript-sync'):
        assert results[path]['synced_at'] is None
        assert results[path]['files']==[]
    assert browser.get(f'/api/v1/episodes/{ident}').json()==before
    assert app.state.episodes.counts()==counts_before
    assert app.state.settings==settings_before
    assert app.state.mac_calendar.read()==calendar_before
    assert app.state.hintergrund.pausiert is True


@pytest.mark.parametrize('path', (*PATHS, 'folder-sync?summary=true', 'transcript-sync?summary=true'))
def test_each_source_metadata_endpoint_requires_the_existing_browser_session(browser,path):
    browser.cookies.clear()
    assert browser.get('/api/v1/'+path).status_code==401


@pytest.mark.parametrize('prefix,setting', [('folder-sync','folder_sync'),('transcript-sync','transcript_sync')])
def test_compact_folder_status_counts_refs_without_loading_bodies_or_exposing_file_names(browser,monkeypatch,prefix,setting):
    app=browser.app
    first=browser.post('/api/v1/sources/documents',json={'filename':'First.txt','body':'Synthetic first source.','project_id':None}).json()['id']
    old=browser.post('/api/v1/sources/documents',json={'filename':'Old.txt','body':'Synthetic old source.','project_id':None}).json()['id']
    assert browser.post(f'/api/v1/episodes/{old}/ignore').status_code==200
    setattr(app.state.settings,setting,{'enabled':False,'root_id':'test-root','files':{
        'private-A.txt':first,'private-alias.txt':first,'private-old.txt':old,'private-missing.txt':'missing-source'},
        'synced_at':'2026-10-08T12:00:00Z',
        'last_run':{'recorded':1,'duplicates':0,'changed':0,'removed':0,'errors':['private-file-error']*10000}})
    def no_body(*_args,**_kwargs): pytest.fail('Compact folder status must not load individual original bodies')
    with monkeypatch.context() as patch:
        patch.setattr(app.state.episodes,'get',no_body)
        response=browser.get(f'/api/v1/{prefix}?summary=true')
    assert response.status_code==200,response.text
    result=response.json()
    assert 'files' not in result
    assert result['file_counts']=={'recorded':4,'active':2,'ignored':1,'unknown':1}
    assert result['synced_at']=='2026-10-08T12:00:00Z'
    assert result['enabled'] is False
    assert result['last_run']['error_count']==10000
    assert 'errors' not in result['last_run']
    assert len(response.content)<2048
    assert 'private-' not in response.text


def test_compact_folder_status_uses_bounded_bulk_lookups_for_many_saved_references(browser):
    app=browser.app
    ident=browser.post('/api/v1/sources/documents',json={'filename':'One.txt','body':'Synthetic source.','project_id':None}).json()['id']
    app.state.settings.folder_sync={'enabled':False,'root_id':'test-root','files':{f'file-{n}.txt':ident for n in range(10000)}}
    queries=[]
    app.state.episodes._conn.set_trace_callback(queries.append)
    try:
        response=browser.get('/api/v1/folder-sync?summary=true')
        assert response.status_code==200,response.text
        assert response.json()['file_counts']=={'recorded':10000,'active':10000,'ignored':0,'unknown':0}
        selects=[q for q in queries if 'FROM episodes' in q]
        assert len(selects)<=1
        assert len(response.content)<2048
    finally: app.state.episodes._conn.set_trace_callback(None)
