from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from icarus_memory.episodes import EpisodeStore
from icarus_memory.mail_intake_routes import register
from icarus_memory.mail_intake import Intake
import threading

@pytest.fixture
def fixture(tmp_path,monkeypatch):
    app=FastAPI();ep=EpisodeStore(tmp_path/'episodes.sqlite3');app.state.episodes=ep
    app.state.settings=SimpleNamespace(mail_accounts=[SimpleNamespace(id='a',label='Test',configured=True)],schedule=SimpleNamespace(mail_accounts=[],enabled=False))
    reader=SimpleNamespace(folders=lambda:[dict(name='All Mail',historical=True)])
    app.state.mail=SimpleNamespace(reader_for=lambda account:reader)
    app.state.conversation_lock=threading.RLock()
    monkeypatch.setattr('icarus_memory.mail_intake_routes.config.save',lambda *args:None)
    register(app,[],lambda:tmp_path,lambda app:None)
    with TestClient(app) as client:yield app,client
    ep.close()


def test_preview_does_not_start_but_confirmed_scope_does(fixture):
    app,client=fixture
    preview=client.get('/api/v1/mail/intake/a/preview').json()
    assert preview['folders']==['All Mail']
    assert Intake(app.state.episodes).accounts()==[]
    assert client.post('/api/v1/mail/intake/a/start',json={'folders':['INBOX']}).status_code==409
    response=client.post('/api/v1/mail/intake/a/start',json={'folders':preview['folders']})
    assert response.status_code==200
    assert response.json()['accounts'][0]['started']
    assert app.state.settings.schedule.mail_accounts==['a']
    assert app.state.settings.schedule.enabled


def test_attachment_capability_is_per_reader_without_fetching_mail(fixture):
    app, client = fixture
    reader = app.state.mail.reader_for('a')
    assert client.get('/api/v1/mail/intake/a/preview').json()['attachments_supported'] is False
    reader.message_mit_anhaengen = lambda *args: (_ for _ in ()).throw(AssertionError('Must not fetch'))
    preview = client.get('/api/v1/mail/intake/a/preview').json()
    status = client.get('/api/v1/mail/intake').json()
    assert preview['attachments_supported'] is True
    assert status['accounts'][0]['attachments_supported'] is True
    assert 'höchstens 5' in preview['attachments_description']
    assert 'keine Anlagen' not in preview['attachments_description']


def test_attachment_capability_failure_is_not_reported_supported(fixture):
    app, client = fixture
    app.state.mail.reader_for = lambda _: (_ for _ in ()).throw(ValueError('No access'))
    status = client.get('/api/v1/mail/intake').json()
    assert status['attachments_supported'] is False
    assert status['accounts'][0]['attachments_supported'] is False


def test_pause_resume_and_save_failure(fixture,monkeypatch):
    app,client=fixture
    assert client.post('/api/v1/mail/intake/a/start',json={'folders':['All Mail']}).status_code==200
    assert client.post('/api/v1/mail/intake/a/pause',json={'paused':True}).json()['accounts'][0]['paused']
    assert not client.post('/api/v1/mail/intake/a/pause',json={'paused':False}).json()['accounts'][0]['paused']


def test_unconfigured_account_cannot_start(fixture):
    app,client=fixture;app.state.settings.mail_accounts[0].configured=False
    assert client.post('/api/v1/mail/intake/a/start',json={'folders':['All Mail']}).status_code==404


def test_failed_activation_stays_paused(fixture,monkeypatch):
    app,client=fixture
    def fail(*a):raise OSError('private secret')
    monkeypatch.setattr('icarus_memory.mail_intake_routes.config.save',fail)
    response=client.post('/api/v1/mail/intake/a/start',json={'folders':['All Mail']})
    assert response.status_code==503 and 'private' not in response.text
    assert not app.state.settings.schedule.enabled
    assert not app.state.settings.schedule.mail_accounts
    assert Intake(app.state.episodes).status('a')['paused']


def test_start_sets_local_only_without_enabling_model_work(fixture):
    app,client=fixture
    app.state.settings.schedule.with_model=False
    app.state.settings.schedule.local_model_only=False
    response=client.post('/api/v1/mail/intake/a/start',json={'folders':['All Mail']})
    assert response.status_code==200
    assert app.state.settings.schedule.local_model_only
    assert not app.state.settings.schedule.with_model
    assert not response.json()['analysis_active']


def test_mail_background_work_enters_restore_boundary():
    from contextlib import contextmanager
    from icarus_memory.scheduler import Scheduler
    entries=[]
    class Boundary:
        @contextmanager
        def operation(self):
            entries.append('enter')
            yield
            entries.append('leave')
    scheduler=Scheduler();scheduler.configure(enabled=True)
    scheduler._runtime_boundary=Boundary()
    scheduler._run_mail_intake=lambda:entries.append('intake')
    scheduler._run_background_mail_intake()
    assert entries==['enter','intake','leave']
    scheduler._stop.set();scheduler._run_background_mail_intake()
    assert entries[-2:]==['enter','leave']


def test_schweigendes_postfach_antwortet_mit_grund_in_der_zeitgrenze(fixture, monkeypatch):
    """Fremdprobe, Befund 4: „Wird gestartet …“ blieb minutenlang stehen. Jetzt kommt nach der Zeitgrenze ein Satz."""
    import time
    app, client = fixture
    monkeypatch.setattr('icarus_memory.mail_intake_routes.ZEITGRENZE', 0.5)
    entry = app.state.settings.mail_accounts[0]
    entry.imap_host = 'imap.web.de'
    reader = SimpleNamespace(folders=lambda: time.sleep(5))
    app.state.mail = SimpleNamespace(reader_for=lambda account: reader)
    start = time.monotonic()
    antwort = client.get('/api/v1/mail/intake/a/preview')
    assert time.monotonic() - start < 3
    assert antwort.status_code == 503
    assert antwort.json()['detail'].startswith('WEB.DE antwortet gerade nicht.')
    assert Intake(app.state.episodes).accounts() == []


def test_abgelehnte_anmeldung_beim_einlesen_nennt_den_grund(fixture):
    import imaplib
    from icarus_memory.connectors.mail import MailError
    app, client = fixture

    def abgelehnt():
        try:
            raise imaplib.IMAP4.error(b'[AUTHENTICATIONFAILED] Authentication failed')
        except imaplib.IMAP4.error as exc:
            raise MailError(f'IMAP-Zugriff fehlgeschlagen: {exc}') from exc
    app.state.mail = SimpleNamespace(reader_for=lambda account: SimpleNamespace(folders=abgelehnt))
    antwort = client.post('/api/v1/mail/intake/a/start', json={'folders': ['All Mail']})
    assert antwort.status_code == 503
    assert antwort.json()['detail'] == 'Test hat die Anmeldung abgelehnt: Adresse oder Passwort stimmen nicht.'
    assert 'AUTHENTICATIONFAILED' not in antwort.text
