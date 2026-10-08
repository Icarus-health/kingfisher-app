"""Only fresh host measurements may authorize automatic work on a Mac."""
from datetime import datetime
import threading
import time

import pytest
from fastapi.testclient import TestClient

from icarus_memory.host_power import HostPower
from icarus_memory.hintergrund import Steuerung, ModellAmpel, als_hintergrund
from icarus_memory.scheduler import Scheduler, JobResult
from icarus_memory.server import create_app, TOKEN_ENV


class Clock:
    value = 100.0
    def __call__(self): return self.value


def test_mac_waits_for_fresh_ac_report_and_battery_blocks(tmp_path):
    clock = Clock()
    power = HostPower(tmp_path, expected=lambda: True, clock=clock)
    assert power.reason() == 'energie_unbekannt'
    power.report('ac')
    assert power.reason() is None
    power.report('battery')
    assert power.reason() == 'akku'
    power.report('ac')
    clock.value += 91
    assert power.reason() == 'energie_unbekannt'
    power.report('unknown')
    assert power.reason() == 'energie_unbekannt'
    power.report('ac')
    assert power.reason() is None


def test_missing_monitor_survives_restart_without_reusing_old_ac(tmp_path):
    clock = Clock()
    power = HostPower(tmp_path, expected=lambda: False, clock=clock)
    assert power.reason() is None  # unmanaged server is unaffected
    power.report('ac')
    reopened = HostPower(tmp_path, expected=lambda: False, clock=clock)
    assert reopened.reason() == 'energie_unbekannt'
    reopened.report('ac')
    assert reopened.reason() is None


def test_known_mac_keeps_power_requirement_even_if_profile_is_lost(tmp_path):
    power = HostPower(tmp_path, expected=lambda: True)
    assert power.reason() == 'energie_unbekannt'  # profile was checked before first report
    power.report('ac')
    reopened = HostPower(tmp_path, expected=lambda: False)
    assert reopened.reason() == 'energie_unbekannt'


def test_invalid_report_cannot_replace_battery_measurement(tmp_path):
    power = HostPower(tmp_path, expected=lambda: True)
    power.report('battery')
    for invalid in ['AC Power', '', None, 1, {'source':'ac'}]:
        with pytest.raises(ValueError): power.report(invalid)
        assert power.reason() == 'akku'


def test_energy_gate_never_overrides_manual_pause(tmp_path):
    power = HostPower(tmp_path, expected=lambda: True)
    control = Steuerung(None, lambda: None, ruhe_s=0, external_gate=power.reason)
    assert control.sperre() == 'energie_unbekannt'
    assert control.wartezeit() >= 20
    power.report('battery')
    assert control.sperre() == 'akku'
    control.pausieren(True); power.report('ac')
    assert control.sperre() == 'pausiert'
    control.pausieren(False)
    assert control.sperre() is None


def test_energy_wait_has_no_finish_prediction_even_with_a_measured_rate(tmp_path, monkeypatch):
    monkeypatch.setattr('icarus_memory.hintergrund.zaehlen', lambda _: {'gesamt':100, 'fertig':10})
    power = HostPower(tmp_path, expected=lambda: True)
    control = Steuerung(None, lambda: None, ruhe_s=0, external_gate=power.reason)
    control._zustand['proben'] = [[n * 60, n] for n in range(6)]
    control.schlange = lambda: []
    for source in ('battery', 'unknown'):
        power.report(source)
        stand = control.stand(freigegeben=True, mit_modell=True)
        assert stand['zustand'] == 'wartet' and stand['grund']
        assert stand['rate_pro_stunde'] == 60
        assert stand['schaetzung'] is None and stand['satz'] is None
    power.report('ac')
    assert control.stand(freigegeben=True, mit_modell=True)['schaetzung'] is not None


def test_battery_reason_is_visible_when_only_mail_intake_needs_work(tmp_path, monkeypatch):
    monkeypatch.setattr('icarus_memory.hintergrund.zaehlen', lambda _: {'gesamt':0, 'fertig':0})
    power = HostPower(tmp_path, expected=lambda: True)
    power.report('battery')
    control = Steuerung(None, lambda: None, ruhe_s=0, external_gate=power.reason)
    stand = control.stand(freigegeben=True, mit_modell=False)
    assert 'Akkubetrieb' in stand['grund']


def test_scheduler_does_not_start_intake_or_models_until_fresh_ac(tmp_path, monkeypatch):
    monkeypatch.setattr('icarus_memory.scheduler.TICK_SECONDS', 0.02)
    power = HostPower(tmp_path, expected=lambda: True)
    control = Steuerung(None, lambda: None, ruhe_s=0, external_gate=power.reason)
    control.probe = lambda: None
    control.dringend_offen = lambda: False
    control.naechste_quellen = lambda *args, **kwargs: ['synthetic-source']
    control.wartezeit = lambda: 0.02
    calls = []
    resumed = threading.Event()
    scheduler = Scheduler()
    def model(*args, **kwargs):
        calls.append('model')
        resumed.set()
        return JobResult('synthetic')
    scheduler._run_working_memory = model
    scheduler._run_mail_intake = lambda: calls.append('intake')
    scheduler.configure(enabled=True, with_model=True)
    scheduler.anschliessen(control)
    scheduler._last_at = datetime.now().astimezone()
    power.report('battery')
    scheduler.start()
    try:
        time.sleep(0.12)
        assert calls == []
        power.report('ac'); scheduler.wecken()
        assert resumed.wait(2)
        assert 'intake' in calls and 'model' in calls
    finally:
        scheduler.stop()


def test_model_gate_rechecks_power_between_background_steps(tmp_path):
    from icarus_memory.hintergrund import BackgroundInterrupted
    power = HostPower(tmp_path, expected=lambda: True)
    power.report('battery')
    ampel = ModellAmpel()
    with als_hintergrund(power.reason), pytest.raises(BackgroundInterrupted):
        with ampel.aufruf():
            pytest.fail('No background model may start on battery.')
    assert ampel.belegt() == {'vorne':0, 'hinten':0}
    # Direct answers remain available while automatic work is paused.
    with ampel.vordergrund():
        pass
    power.report('ac')
    with als_hintergrund(power.reason), ampel.aufruf():
        assert ampel.belegt()['hinten'] == 1


def test_main_application_authenticates_power_and_keeps_reads_available(tmp_path, monkeypatch):
    monkeypatch.setenv(TOKEN_ENV, 'synthetic-power-token')
    monkeypatch.setattr('icarus_memory.host_power.mac_expected', lambda path: True)
    app = create_app()
    headers = {'X-Icarus-Token':'synthetic-power-token'}
    with TestClient(app) as client:
        assert client.post('/api/v1/device/power', json={'source':'ac'}).status_code == 401
        assert app.state.hintergrund.sperre() == 'energie_unbekannt'
        assert client.post('/api/v1/device/power', headers=headers, json={'source':'battery'}).status_code == 200
        assert app.state.hintergrund.sperre() == 'akku'
        assert client.get('/api/v1/tasks', headers=headers).status_code == 200
        assert client.post('/api/v1/device/power', headers=headers, json={'source':'ac','timestamp':999999999999}).status_code == 422
        assert app.state.hintergrund.sperre() == 'akku'
        assert client.post('/api/v1/device/power', headers=headers, json={'source':'ac'}).status_code == 200
        assert app.state.hintergrund.sperre() is None
