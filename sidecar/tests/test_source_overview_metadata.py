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


@pytest.mark.parametrize('path', PATHS)
def test_each_source_metadata_endpoint_requires_the_existing_browser_session(browser,path):
    browser.cookies.clear()
    assert browser.get('/api/v1/'+path).status_code==401
