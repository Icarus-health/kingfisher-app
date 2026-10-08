"""Global pause stays distinct from mailbox pause and keeps intake counts visible."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore, config
from icarus_memory.mail_intake import Intake
from icarus_memory.server import create_app


@pytest.fixture
def intake_client(tmp_path, monkeypatch):
    settings = config.Settings()
    settings.mail_accounts = [config.MailAccountSettings(
        id='probe', label='Probe', imap_host='127.0.0.1', user='probe@example.org')]
    config.save(tmp_path / 'app-data', settings)
    state = {'account_id': 'probe', 'started': True, 'paused': False,
             'step': 'capture', 'error': None, 'folders': [{
                 'folder': 'INBOX', 'inventory_complete': True, 'total': 100,
                 'captured': 20, 'duplicates': 0, 'filtered': 0,
                 'pending': 80, 'failed': 0, 'live_pending': 0}]}
    monkeypatch.setattr(Intake, 'status', lambda self, account: deepcopy(state))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='probe'))
    with TestClient(app) as client:
        app.state.scheduler.stop()
        app.state.scheduler.wecken = lambda: None
        app.state.mail = SimpleNamespace(reader_for=lambda _: object())
        app.state.settings.schedule.enabled = True
        app.state.settings.schedule.mail_accounts = ['probe']
        yield client, state


def snapshots(client):
    intake = client.get('/api/v1/mail/intake').json()
    direct = client.get('/api/v1/mail/stand').json()['accounts'][0]
    schedule = client.get('/api/v1/schedule').json()['mail_stand'][0]
    assert direct == schedule
    assert intake['accounts'][0]['stand'] == {
        k: v for k, v in direct.items() if k not in ('account_id', 'label')}
    return intake, direct


@pytest.mark.parametrize('total', [100, None])
def test_global_pause_preserves_counts_and_resume_route(intake_client, total):
    client, state = intake_client
    state['folders'][0].update(total=total, inventory_complete=total is not None)
    assert client.post('/api/v1/hintergrund/pause').json()['pausiert'] is True
    intake, stand = snapshots(client)
    assert stand['zustand'] == 'pausiert'
    assert (stand['gelesen'], stand['gesamt']) == (20, total)
    assert 'Heute' in stand['satz'] and 'Weiter' in stand['satz']
    assert 'wird gelesen' not in stand['satz']
    assert intake['background_paused'] is True
    assert intake['accounts'][0]['paused'] is False, 'global pause must not become mailbox pause'
    assert client.post('/api/v1/hintergrund/weiter').json()['pausiert'] is False
    intake, stand = snapshots(client)
    assert intake['background_paused'] is False
    assert stand['zustand'] == 'liest'
    assert stand['gelesen'] == 20


@pytest.mark.parametrize(('total', 'expected'), [(20, 'aktuell'), (0, 'leer')])
def test_global_pause_does_not_turn_finished_mail_into_unfinished_work(intake_client, total, expected):
    client, state = intake_client
    state['folders'][0].update(total=total, captured=total, pending=0)
    client.post('/api/v1/hintergrund/pause')
    intake, stand = snapshots(client)
    assert intake['background_paused'] is True
    assert stand['zustand'] == expected
    assert (stand['gelesen'], stand['gesamt']) == (total, total)


def test_global_pause_keeps_failure_visible(intake_client):
    client, state = intake_client
    state['error'] = 'inventory_unavailable'
    client.post('/api/v1/hintergrund/pause')
    assert snapshots(client)[1]['zustand'] == 'fehler'


def test_resume_global_pause_does_not_resume_a_paused_mailbox(intake_client):
    client, state = intake_client
    state['paused'] = True
    client.post('/api/v1/hintergrund/pause')
    client.post('/api/v1/hintergrund/weiter')
    intake, stand = snapshots(client)
    assert intake['background_paused'] is False
    assert intake['accounts'][0]['paused'] is True
    assert stand['zustand'] == 'pausiert'


@pytest.mark.parametrize('reason', ['akku', 'nutzer', 'antwort', 'energie_unbekannt'])
def test_temporary_wait_is_not_explicit_global_pause(intake_client, monkeypatch, reason):
    client, _ = intake_client
    monkeypatch.setattr(client.app.state.hintergrund, 'sperre', lambda: reason)
    intake, stand = snapshots(client)
    assert intake['background_paused'] is False
    assert stand['zustand'] == 'liest'
