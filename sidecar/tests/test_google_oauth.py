import json
import threading
from urllib.parse import parse_qs, urlparse
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.testclient import TestClient

from icarus_memory import config
from icarus_memory.google_oauth import GoogleOAuth, GoogleError, SCOPES, TOKEN_URL, USER_URL, redirect_uri
from icarus_memory.google_routes import install_routes
from icarus_memory.google_calendar import GoogleCalendar
from icarus_memory.connectors.mail import MailConfig, MailConnector

CLIENT = {'installed': {'client_id': '123-test.apps.googleusercontent.com', 'client_secret': 'synthetic-secret'}}

class Keys:
    available = True
    def __init__(self): self.values = {}
    def get(self, key): return self.values.get(key)
    def set(self, key, value): self.values[key] = value
    def delete(self, key): self.values.pop(key, None)

class Google:
    def __init__(self, kind='mail', email='test@example.com'):
        self.kind, self.email, self.calls = kind, email, []
        self.scope = ' '.join(SCOPES[kind])
    def __call__(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if url == TOKEN_URL:
            return {'access_token': 'access-private', 'refresh_token': 'refresh-private', 'scope': self.scope}
        if url == USER_URL:
            return {'email': self.email, 'verified_email': True}
        return {'items': [{'id': 'a@example.com', 'summary': 'Privat', 'accessRole': 'owner'},
                          {'id': 'b@example.com', 'summary': 'Team', 'accessRole': 'reader'},
                          {'id': 'freebusy', 'accessRole': 'freeBusyReader'}]}

def ready(oauth, kind='mail'):
    started = oauth.begin(kind, 'http://127.0.0.1:8892')
    query = parse_qs(urlparse(started['url']).query)
    oauth.callback(query['state'][0], 'synthetic-code')
    return started, query


def test_pkce_one_use_state_and_no_secret_in_status():
    google, keys = Google(), Keys()
    oauth = GoogleOAuth(keys, google); oauth.configure(CLIENT)
    started, query = ready(oauth)
    assert query['code_challenge_method'] == ['S256']
    assert len(query['code_challenge'][0]) == 43
    assert 'client_secret' not in query
    assert google.calls[0][2]['data']['code_verifier']
    status = oauth.status(started['session_id'])
    assert status['status'] == 'ready' and status['email'] == 'test@example.com'
    assert 'private' not in json.dumps(status) and 'synthetic-secret' not in json.dumps(status)
    with pytest.raises(GoogleError): oauth.callback(query['state'][0], 'replayed')
    assert len(google.calls) == 2


@pytest.mark.parametrize('origin', ['https://evil.example', 'http://localhost:8892', 'http://127.0.0.1:8892/path', 'http://127.0.0.1:8892?x=y', 'http://user@127.0.0.1:8892', 'http://127.0.0.1:bad'])
def test_only_exact_loopback_redirect(origin):
    with pytest.raises(GoogleError): redirect_uri(origin)


def test_expiry_invalid_state_and_denied_permission_do_not_exchange():
    clock = [0]; google = Google(); oauth = GoogleOAuth(Keys(), google, lambda: clock[0]); oauth.configure(CLIENT)
    started = oauth.begin('mail', 'http://127.0.0.1:8892'); state = parse_qs(urlparse(started['url']).query)['state'][0]
    with pytest.raises(GoogleError): oauth.callback('wrong', 'code')
    with pytest.raises(GoogleError): oauth.callback('ü', 'code')
    clock[0] = 601
    with pytest.raises(GoogleError): oauth.callback(state, 'code')
    assert not google.calls and oauth.status(started['session_id'])['status'] == 'expired'
    started = oauth.begin('mail', 'http://127.0.0.1:8892'); state = parse_qs(urlparse(started['url']).query)['state'][0]
    with pytest.raises(GoogleError): oauth.callback(state, error='access_denied')
    assert not google.calls


def test_partial_scope_never_connects():
    google = Google(); google.scope = 'https://www.googleapis.com/auth/userinfo.email'
    oauth = GoogleOAuth(Keys(), google); oauth.configure(CLIENT)
    with pytest.raises(GoogleError): ready(oauth)
    assert list(oauth.pending.values())[0]['status'] == 'failed'
    assert len(google.calls) == 1


def test_client_must_be_desktop_and_secure_storage_required():
    oauth = GoogleOAuth(Keys())
    with pytest.raises(GoogleError): oauth.configure({'web': CLIENT['installed']})
    oauth.keychain.available = False
    with pytest.raises(GoogleError): oauth.configure(CLIENT)


@pytest.fixture
def routed(tmp_path):
    app = FastAPI(); keys = Keys()
    app.state.keychain = keys; app.state.settings = config.Settings(); app.state.conversation_lock = threading.Lock()
    def auth(x_icarus_token: str | None = Header(default=None)):
        if x_icarus_token != 'local-test': raise HTTPException(401)
    install_routes(app, [Depends(auth)], lambda: tmp_path, lambda: None)
    app.state.google_oauth.configure(CLIENT)
    with TestClient(app, base_url='http://127.0.0.1:8892', headers={'X-Icarus-Token':'local-test'}) as client:
        yield app, keys, client, tmp_path


def test_guard_callback_selection_persistence_and_replay(routed):
    app, keys, client, path = routed
    oauth = app.state.google_oauth; oauth.request = Google('calendar')
    with TestClient(app, base_url='http://127.0.0.1:8892') as unauth:
        assert unauth.post('/api/v1/google/begin', json={'kind':'mail','origin':'http://127.0.0.1:8892'}).status_code == 401
    result = client.post('/api/v1/google/begin', json={'kind':'calendar','origin':'http://evil.example'}); assert result.status_code == 422
    started = client.post('/api/v1/google/begin', json={'kind':'calendar','origin':'http://127.0.0.1:8892'}).json()
    state = parse_qs(urlparse(started['url']).query)['state'][0]
    with TestClient(app, base_url='http://127.0.0.1:8892') as unauth:
        response = unauth.get('/api/v1/google/callback', params={'state':state,'code':'private-code'})
        assert response.status_code == 200 and 'private-code' not in response.text
        assert response.headers['cache-control'] == 'no-store'
    sid = started['session_id']; available = client.get('/api/v1/google/sessions/'+sid).json()
    assert [c['id'] for c in available['calendars']] == ['a@example.com','b@example.com']
    assert client.post('/api/v1/google/sessions/'+sid+'/connect', json={'calendar_ids':['unlisted']}).status_code == 422
    assert client.post('/api/v1/google/sessions/'+sid+'/connect', json={'calendar_ids':['b@example.com']}).status_code == 200
    saved = config.load(path); assert len(saved.calendar_sources) == 1
    assert saved.calendar_sources[0].url == 'b@example.com' and saved.calendar_sources[0].kind == 'google'
    assert 'refresh-private' not in (path/'einstellungen.json').read_text()
    assert client.post('/api/v1/google/sessions/'+sid+'/connect', json={'calendar_ids':['b@example.com']}).status_code == 422
    again, _ = ready(oauth, 'calendar')
    assert client.post('/api/v1/google/sessions/'+again['session_id']+'/connect', json={'calendar_ids':['b@example.com']}).status_code == 409
    assert len(app.state.settings.calendar_sources) == 1


def test_calendar_write_upgrades_only_same_account_and_selected_calendar(routed):
    app, keys, client, _ = routed
    oauth = app.state.google_oauth
    oauth.request = Google('calendar')
    first, _ = ready(oauth, 'calendar')
    assert client.post('/api/v1/google/sessions/'+first['session_id']+'/connect',
        json={'calendar_ids':['a@example.com']}).status_code == 200
    source = app.state.settings.calendar_sources[0]
    key = config.integration_secret_name('calendar', source.id)
    old = keys.get(key)
    oauth.request = Google('calendar_write', email='other@example.com')
    foreign, _ = ready(oauth, 'calendar_write')
    assert client.post('/api/v1/google/sessions/'+foreign['session_id']+'/connect',
        json={'calendar_ids':['a@example.com']}).status_code == 409
    assert keys.get(key) == old
    oauth.request = Google('calendar_write')
    unselected, _ = ready(oauth, 'calendar_write')
    assert client.post('/api/v1/google/sessions/'+unselected['session_id']+'/connect',
        json={'calendar_ids':['b@example.com']}).status_code == 422
    assert keys.get(key) == old
    upgrade, _ = ready(oauth, 'calendar_write')
    result = client.post('/api/v1/google/sessions/'+upgrade['session_id']+'/connect',
        json={'calendar_ids':['a@example.com']})
    assert result.status_code == 200
    assert len(app.state.settings.calendar_sources) == 1
    assert 'https://www.googleapis.com/auth/calendar.events' in json.loads(keys.get(key))['scope']


def test_two_mail_accounts_grants_survive_manager_restart_and_removal(routed):
    app, keys, client, path = routed
    oauth = app.state.google_oauth
    for address in ['first@example.com', 'second@example.com']:
        oauth.request = Google(email=address); started, _ = ready(oauth)
        assert client.post('/api/v1/google/sessions/'+started['session_id']+'/connect', json={}).status_code == 200
    accounts = config.load(path).mail_accounts
    assert len(accounts) == 2 and all(a.auth_method == 'google_oauth' for a in accounts)
    assert not config.load(path).schedule.mail_accounts
    google = Google(); reopened = GoogleOAuth(keys, google)
    key = config.integration_secret_name('mail', accounts[0].id)
    assert reopened.access_token(key) == 'access-private'
    assert google.calls[0][2]['data']['grant_type'] == 'refresh_token'
    keys.delete(key)
    with pytest.raises(GoogleError): reopened.access_token(key)
    assert len(google.calls) == 1


def test_xoauth_imap_never_uses_password_and_error_challenge_is_empty():
    calls = []
    class IMAP:
        def authenticate(self, method, respond): calls.extend([method, respond(b''), respond(b'error')])
        def login(self, *args): pytest.fail('OAuth must never use password login')
    MailConnector(MailConfig('imap.gmail.com','a@example.com','', access_token=lambda:'secret-token'))._login(IMAP())
    assert calls == ['XOAUTH2', b'user=a@example.com\x01auth=Bearer secret-token\x01\x01', b'']


def test_google_calendar_pagination_timezone_cancelled_and_read_only():
    calls=[]
    def request(method,url,**kwargs):
        calls.append((method,url,kwargs))
        if len(calls)==1:
            return {'timeZone':'Europe/Berlin','nextPageToken':'next','items':[{'id':'cancelled','status':'cancelled'}, {'id':'all-day','summary':'Team','start':{'date':'2026-10-01'},'end':{'date':'2026-10-02'}}]}
        return {'items':[{'id':'timed','start':{'dateTime':'2026-10-01T12:00:00+02:00'},'end':{'dateTime':'2026-10-01T13:00:00+02:00'}}]}
    reader=GoogleCalendar('a/b@example.com', lambda:'token', request)
    events=reader.events(at=datetime(2026,10,1,tzinfo=timezone.utc))
    assert len(events)==2 and events[0].all_day and events[0].start.utcoffset().total_seconds()==7200
    assert all(c[0]=='GET' for c in calls) and 'a%2Fb%40example.com' in calls[0][1]
    assert calls[1][2]['params']['pageToken']=='next'
    assert not hasattr(reader, 'create')


# -- Zugriffstoken-Zwischenspeicher -------------------------------------------

GRANT = json.dumps({'client_id': 'c', 'client_secret': 's', 'refresh_token': 'r1'})


class Uhr:
    def __init__(self): self.jetzt = 1000.0
    def __call__(self): return self.jetzt


def token_manager(antwort=None, wert=GRANT):
    keys, uhr, aufrufe = Keys(), Uhr(), []
    keys.set('k', wert)
    def request(method, url, **kwargs):
        aufrufe.append(kwargs['data'])
        return dict(antwort or {'access_token': f'token-{len(aufrufe)}', 'expires_in': 3600})
    return GoogleOAuth(keys, request, uhr), keys, uhr, aufrufe


def test_token_wird_bis_kurz_vor_ablauf_wiederverwendet_dann_erneuert():
    oauth, _, uhr, aufrufe = token_manager()
    assert oauth.access_token('k') == 'token-1'
    uhr.jetzt += 3400                       # noch vor Ablauf minus Sicherheitsabstand (3600 - 120)
    assert oauth.access_token('k') == 'token-1'
    assert len(aufrufe) == 1
    uhr.jetzt += 100                        # jetzt innerhalb des Sicherheitsabstands
    assert oauth.access_token('k') == 'token-2'
    assert len(aufrufe) == 2


def test_ohne_laufzeitangabe_wird_nichts_zwischengespeichert():
    oauth, _, _, aufrufe = token_manager({'access_token': 'x'})
    oauth.access_token('k'); oauth.access_token('k')
    assert len(aufrufe) == 2


def test_entfernter_oder_neu_verbundener_zugang_trifft_nie_das_alte_token():
    oauth, keys, _, aufrufe = token_manager()
    oauth.access_token('k')
    keys.delete('k')
    with pytest.raises(GoogleError, match='entfernt'):
        oauth.access_token('k')
    keys.set('k', json.dumps({'client_id': 'c', 'client_secret': 's', 'refresh_token': 'r2'}))
    assert oauth.access_token('k') == 'token-2'
    assert aufrufe[-1]['refresh_token'] == 'r2'


def test_neu_verbundener_zugang_ohne_zwischenschritt_bekommt_neues_token():
    """Der Speicher gilt nur für genau diesen Zugang; wer neu verbindet, bekommt nie das alte Token."""
    oauth, keys, _, aufrufe = token_manager()
    assert oauth.access_token('k') == 'token-1'
    keys.set('k', json.dumps({'client_id': 'c', 'client_secret': 's', 'refresh_token': 'r2'}))
    assert oauth.access_token('k') == 'token-2'
    assert aufrufe[-1]['refresh_token'] == 'r2'


def test_getauschter_refresh_token_wird_gespeichert_und_token_bleibt_gueltig():
    oauth, keys, _, aufrufe = token_manager({'access_token': 'neu', 'expires_in': 3600, 'refresh_token': 'r9'})
    assert oauth.access_token('k') == 'neu'
    assert json.loads(keys.get('k'))['refresh_token'] == 'r9'
    assert oauth.access_token('k') == 'neu'
    assert len(aufrufe) == 1


def test_gleichzeitige_aufrufe_loesen_einen_refresh_aus():
    oauth, _, _, aufrufe = token_manager()
    los, ergebnisse = threading.Barrier(6), []
    def hole():
        los.wait(); ergebnisse.append(oauth.access_token('k'))
    threads = [threading.Thread(target=hole) for _ in range(6)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert len(aufrufe) == 1 and set(ergebnisse) == {'token-1'}


def test_netzaufruf_haelt_die_gemeinsame_sperre_nicht():
    keys, drin, weiter, fertig = Keys(), threading.Event(), threading.Event(), []
    keys.set('k', GRANT)
    def langsam(method, url, **kwargs):
        drin.set(); weiter.wait(5)
        return {'access_token': 't', 'expires_in': 3600}
    oauth = GoogleOAuth(keys, langsam, Uhr())
    thread = threading.Thread(target=lambda: fertig.append(oauth.access_token('k')))
    thread.start()
    assert drin.wait(5)
    try:
        # Während des Refresh bleibt die Anmeldeseite bedienbar.
        antwort = []
        seite = threading.Thread(target=lambda: antwort.append(oauth.status('unbekannt')))
        seite.start(); seite.join(1)
        assert antwort == [{'status': 'expired'}]   # ohne Warten auf den langsamen Netzaufruf
    finally:
        weiter.set(); thread.join()
    assert fertig == ['t']
