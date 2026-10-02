"""Die echte Browser-Sitzung gilt nur unter /api, auch für neuere Funktionen."""
import pytest
from fastapi.testclient import TestClient
from icarus_memory.server import create_app


@pytest.fixture
def browser(tmp_path, monkeypatch):
    ui = tmp_path / 'ui'
    ui.mkdir()
    (ui / 'index.html').write_text('<!doctype html><title>Kingfisher</title>')
    monkeypatch.setenv('ICARUS_UI_DIR', str(ui))
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'synthetic-browser-token')
    with TestClient(create_app()) as client:
        page = client.get('/today')
        assert 'Path=/api' in page.headers['set-cookie']
        yield client


def test_goal_lifecycle_with_scoped_browser_cookie(browser):
    assert browser.get('/goals').status_code == 401
    assert browser.get('/api/v1/goals').status_code == 200
    response = browser.post('/api/v1/assertions', json={'statement': 'Testziel',
        'kind': 'goal', 'provenance': {'source_type': 'user_stated'}})
    assert response.status_code == 201
    goal = response.json()
    assert browser.get('/api/v1/goals').json()['items'][0]['id'] == goal['id']
    finished = browser.post(f'/api/v1/goals/{goal["id"]}/finish', json={'outcome':'achieved'})
    assert finished.status_code == 200
    reopened = browser.post(f'/api/v1/goals/{finished.json()["id"]}/reopen')
    assert reopened.status_code == 200
    ident = reopened.json()['id']
    history = browser.get(f'/api/v1/assertions/{ident}/history')
    assert history.status_code == 200 and len(history.json()) == 3
    assert browser.post(f'/api/v1/assertions/{ident}/retract').status_code == 200
    assert browser.get('/api/v1/goals').json()['items'] == []


def test_sources_and_schedule_with_scoped_browser_cookie(browser):
    doc = browser.post('/api/v1/sources/documents', json={
        'filename':'test.txt', 'body':'Eine belegte Testquelle.', 'project_id':None})
    assert doc.status_code in (200, 201)
    ident = doc.json()['id']
    assert browser.get(f'/api/v1/episodes/{ident}').json()['body'] == 'Eine belegte Testquelle.'
    assert browser.post(f'/api/v1/episodes/{ident}/ignore').status_code == 200
    # Eine vorhandene Arbeitsnotiz wird über den bisherigen Desktop-Endpunkt angelegt.
    note = browser.post('/notes', headers={'x-icarus-token':'synthetic-browser-token'},
        json={'title':'Notiz', 'body':'Testinhalt'}).json()
    assert browser.get(f'/api/v1/notes/{note["id"]}').json()['body'] == 'Testinhalt'
    assert browser.put('/api/v1/schedule', json={'enabled':False,
        'mail_accounts':[], 'interval_minutes':30}).status_code == 200
    assert browser.get('/api/v1/schedule').json()['interval_minutes'] == 30


@pytest.mark.parametrize('method,path', [
    ('GET','goals'), ('POST','assertions'), ('GET','assertions/missing/history'),
    ('POST','assertions/missing/retract'), ('POST','goals/missing/finish'),
    ('POST','goals/missing/reopen'), ('GET','episodes/missing'),
    ('POST','episodes/missing/ignore'), ('GET','notes/missing'),
    ('GET','schedule'), ('PUT','schedule'),
])
def test_browser_aliases_remain_guarded(browser, method, path):
    browser.cookies.clear()
    assert browser.request(method, '/api/v1/'+path).status_code == 401


def test_reopen_source_requires_browser_session(browser):
    source = browser.post('/api/v1/sources/documents', json={'filename': 'Beleg.txt', 'body': 'Rohtext'}).json()['id']
    assert browser.post(f'/api/v1/episodes/{source}/ignore').status_code == 200
    assert browser.post(f'/api/v1/episodes/{source}/reopen').status_code == 200
    assert browser.get(f'/api/v1/episodes/{source}').json()['state'] == 'new'
    browser.cookies.clear()
    assert browser.post(f'/api/v1/episodes/{source}/reopen').status_code == 401
