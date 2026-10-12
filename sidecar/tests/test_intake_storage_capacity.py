"""Capacity loss must not contact more mail or advance its checkpoint."""
from contextlib import contextmanager
from types import SimpleNamespace
import os

import pytest

from icarus_memory.episodes import EpisodeStore
from icarus_memory.mail_intake import Intake
from .test_mail_intake import Reader
from .test_mail_intake_routes import fixture


def measurement(byte_count=2 * 1024**3, inodes=10000):
    return SimpleNamespace(f_frsize=1, f_bavail=byte_count,
                           f_files=100000, f_favail=inodes)


@pytest.fixture
def intake(tmp_path):
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    store = Intake(ep)
    store.start('probe', ['INBOX'])
    yield store
    ep.close()


@pytest.mark.parametrize('capacity', [measurement(90 * 1024**2), measurement(inodes=10)])
def test_insufficient_capacity_prevents_even_opening_mail_session(intake, monkeypatch, capacity):
    monkeypatch.setattr(os, 'statvfs', lambda _: capacity)
    contacts = []
    class Observed(Reader):
        @contextmanager
        def session(self):
            contacts.append('login')
            yield
    intake.step('probe', Observed())
    assert contacts == []
    assert not intake.status('probe')['folders'][0]['inventory_complete']
    assert sum(intake.episodes.counts().values()) == 0


def test_capacity_lost_during_inventory_keeps_cursor_and_retry(intake, monkeypatch):
    space = [measurement()]
    monkeypatch.setattr(os, 'statvfs', lambda _: space[0])
    class Losing(Reader):
        def inventory_page(self, *args, **kwargs):
            page = super().inventory_page(*args, **kwargs)
            space[0] = measurement(90 * 1024**2)
            return page
    intake.step('probe', Losing())
    row = intake.db.execute('SELECT scan_uid, generation, error FROM mail_intake_folders').fetchone()
    assert tuple(row) == (0, None, None)
    assert intake.db.execute('SELECT COUNT(*) FROM mail_intake_items').fetchone()[0] == 0
    space[0] = measurement()
    intake.step('probe', Reader(), batch=1)
    assert sum(intake.episodes.counts().values()) == 1


def test_capacity_lost_during_message_does_not_commit_or_fail_source(intake, monkeypatch):
    space = [measurement()]
    monkeypatch.setattr(os, 'statvfs', lambda _: space[0])
    fetched = []
    class Losing(Reader):
        def message_in_folder(self, folder, uid):
            fetched.append(uid)
            message = super().message_in_folder(folder, uid)
            space[0] = measurement(90 * 1024**2)
            return message
    intake.step('probe', Losing(), batch=3)
    assert fetched == ['7.6']
    assert sum(intake.episodes.counts().values()) == 0
    assert intake.db.execute("SELECT COUNT(*) FROM mail_intake_items WHERE status='pending' AND attempts=0").fetchone()[0] == 6
    space[0] = measurement()
    intake.step('probe', Reader(), batch=3)
    assert sum(intake.episodes.counts().values()) == 3


def test_unreadable_capacity_does_not_contact_mail_or_leak_exception(intake, monkeypatch):
    def unavailable(_):
        raise OSError('private filesystem detail')
    monkeypatch.setattr(os, 'statvfs', unavailable)
    class Forbidden(Reader):
        def inventory_page(self, *args, **kwargs):
            pytest.fail('Storage could not be measured; no remote contact allowed.')
    assert intake.step('probe', Forbidden()) == []
    assert intake.status('probe')['error'] is None


def test_start_rejects_low_capacity_before_discovery_or_config(fixture, monkeypatch):
    app, client = fixture
    monkeypatch.setattr(os, 'statvfs', lambda _: measurement(90 * 1024**2))
    contacts = []
    def forbidden():
        contacts.append('folders')
        raise OSError('Artificial unavailable mailbox')
    app.state.mail.reader_for('a').folders = forbidden
    response = client.post('/api/v1/mail/intake/a/start', json={'folders': ['All Mail']})
    assert response.status_code == 507
    assert contacts == []
    assert 'Speicher' in response.json()['detail']
    assert Intake(app.state.episodes).accounts() == []
    assert not app.state.settings.schedule.enabled


def test_resume_rejects_low_capacity_and_keeps_pause_and_schedule(fixture, monkeypatch):
    app, client = fixture
    store = Intake(app.state.episodes)
    store.start('a', ['All Mail']); store.pause('a', True)
    monkeypatch.setattr(os, 'statvfs', lambda _: measurement(90 * 1024**2))
    response = client.post('/api/v1/mail/intake/a/pause', json={'paused': False})
    assert response.status_code == 507
    assert store.status('a')['paused'] and not app.state.settings.schedule.enabled
    # Pause remains available; a capacity failure cannot remove user control.
    assert client.post('/api/v1/mail/intake/a/pause', json={'paused': True}).status_code == 200
    monkeypatch.setattr(os, 'statvfs', lambda _: measurement())
    assert client.post('/api/v1/mail/intake/a/pause', json={'paused': False}).status_code == 200
    assert not store.status('a')['paused']


def test_shared_mail_status_reports_capacity_wait_without_changing_progress(fixture, monkeypatch):
    app, client = fixture
    store = Intake(app.state.episodes)
    store.start('a', ['INBOX']); store.step('a', Reader(), batch=1)
    app.state.settings.schedule.enabled = True
    app.state.settings.schedule.mail_accounts = ['a']
    monkeypatch.setattr(os, 'statvfs', lambda _: measurement(90 * 1024**2))
    status = client.get('/api/v1/mail/intake').json()
    assert status['storage_blocked'] == 'storage_low'
    assert 'Speicher' in status['storage_message']
    stand = status['accounts'][0]['stand']
    assert stand['zustand'] == 'wartet' and stand['gelesen'] == 1 and stand['gesamt'] == 6
    assert status['accounts'][0]['paused'] is False


def test_app_background_gate_interrupts_storage_wait_and_preserves_manual_pause(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory import MemoryBackend, SelfModelStore
    from icarus_memory.server import create_app
    from icarus_memory.hintergrund import ModellAmpel, als_hintergrund, BackgroundInterrupted
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='probe'))
    with TestClient(app):
        app.state.scheduler.stop()
        control = app.state.hintergrund
        monkeypatch.setattr(os, 'statvfs', lambda _: measurement(90 * 1024**2))
        assert control.sperre() == 'storage_low'
        state = control.stand(freigegeben=True, mit_modell=False)
        assert 'Speicher' in state['grund'] and state['schaetzung'] is None
        ampel = ModellAmpel()
        with als_hintergrund(control.external_gate), pytest.raises(BackgroundInterrupted):
            with ampel.aufruf():
                pytest.fail('No background model should start while disk reserve is low.')
        assert ampel.belegt() == {'vorne': 0, 'hinten': 0}
        with ampel.vordergrund():
            pass
        control.pausieren(True)
        monkeypatch.setattr(os, 'statvfs', lambda _: measurement())
        assert control.sperre() == 'pausiert'
        control.pausieren(False)
        assert control.sperre() is None


def test_manual_full_run_also_waits_for_storage(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory import MemoryBackend, SelfModelStore
    from icarus_memory.server import create_app
    from icarus_memory.scheduler import JobResult
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='probe'))
    with TestClient(app) as client:
        app.state.scheduler.stop()
        calls = []
        def ingest():
            calls.append('ingest')
            return [JobResult('aufnahme')]
        app.state.scheduler._run_ingest = ingest
        previous_run_at = app.state.scheduler._last_at
        monkeypatch.setattr(os, 'statvfs', lambda _: measurement(90 * 1024**2))
        report = client.post('/schedule/run').json()
        assert calls == []
        assert any(not job['ok'] and 'Speicher' in job['detail'] for job in report['jobs'])
        assert app.state.scheduler._last_at == previous_run_at


def test_capacity_gate_is_installed_before_first_worker_start(tmp_path, monkeypatch):
    from icarus_memory import config
    from icarus_memory.server import create_app
    from icarus_memory.scheduler import Scheduler
    settings = config.Settings()
    settings.schedule.enabled = True
    config.save(tmp_path / 'app-data', settings)
    starts = []
    monkeypatch.setattr(Scheduler, 'start', lambda self: starts.append(self._capacity_gate()))
    monkeypatch.setattr(os, 'statvfs', lambda _: measurement(90 * 1024**2))
    create_app()
    assert starts and all(reason == 'storage_low' for reason in starts)


def test_full_run_capacity_loss_skips_next_job_and_does_not_mark_full_pass_finished():
    from icarus_memory.scheduler import Scheduler, JobResult
    blocked = [None]
    calls = []
    def ingest():
        calls.append('ingest'); blocked[0] = 'storage_low'
        return [JobResult('aufnahme')]
    def working(_):
        calls.append('working'); return JobResult('gedaechtnis')
    scheduler = Scheduler(run_ingest=ingest, run_working_memory=working)
    scheduler._capacity_gate = lambda: blocked[0]
    report = scheduler.run_once()
    assert calls == ['ingest']
    assert any(not job.ok and 'Speicher' in job.detail for job in report.jobs)
    assert scheduler._last_at is None


@pytest.mark.parametrize('path,capacity,expected', [
    ('/', measurement(511 * 1024**2), 'storage_low'),
    ('data', measurement(511 * 1024**2), 'storage_low'),
    ('data', measurement(512 * 1024**2, 1024), None),
    ('data', measurement(512 * 1024**2, 1023), 'storage_low'),
    ('/', SimpleNamespace(f_frsize=1, f_bavail=0, f_files=0, f_favail=0), 'storage_unknown'),
    ('data', SimpleNamespace(f_frsize=1, f_bavail=True, f_files=10000, f_favail=10000), 'storage_unknown'),
])
def test_separate_root_and_data_filesystem_capacity(monkeypatch, path, capacity, expected):
    from icarus_memory.storage_capacity import reason
    monkeypatch.setattr(os, 'statvfs', lambda p: capacity if p == path else measurement())
    assert reason('data') == expected
