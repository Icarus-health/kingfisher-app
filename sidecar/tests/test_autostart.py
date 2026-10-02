"""Autostart beim Anmelden: eine Frage, keine stille Vorgabe; die Datei entsteht nur nach einem Klick.

Der Mac-Helfer (`scripts/mac_autostart.py`) wird gegen einen temporären Ordner geprüft; einen Mac braucht es nicht.
"""
import importlib.util
import plistlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from icarus_memory.backends import MemoryBackend
from icarus_memory.server import create_app
from icarus_memory.store import SelfModelStore

spec = importlib.util.spec_from_file_location('mac_autostart', Path(__file__).parents[2] / 'scripts/mac_autostart.py')
helfer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helfer)

AUFRUF = helfer.programm('/usr/bin/python3', Path('/Programme/Kingfisher/scripts'), 'kingfisher-synth',
                         Path('/Benutzer/synth/.kingfisher.env'), 'http://127.0.0.1:8891')


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path / 'daten'))
    monkeypatch.delenv('ICARUS_SIDECAR_TOKEN', raising=False)
    anwendung = create_app(SelfModelStore(MemoryBackend(), 'test'))
    yield anwendung
    anwendung.state.scheduler.stop()


def test_plist_startet_kingfisher_ohne_fenster_und_ohne_dauerlauf(tmp_path):
    datei = helfer.pfad(tmp_path)
    assert helfer.anwenden(True, tmp_path, AUFRUF, tmp_path / 'autostart.log') is True
    inhalt = plistlib.loads(datei.read_bytes())
    assert inhalt['Label'] == 'local.kingfisher.start'
    assert inhalt['RunAtLoad'] is True
    assert inhalt['ProgramArguments'][1].endswith('start_mac_app.py')
    assert inhalt['ProgramArguments'][-1] == '--no-browser'
    assert 'KeepAlive' not in inhalt  # wer Kingfisher beendet, beendet es
    assert datei.stat().st_mode & 0o777 == 0o644


def test_ohne_antwort_wird_nichts_geschrieben_und_nichts_entfernt(tmp_path):
    assert helfer.anwenden(None, tmp_path, AUFRUF, tmp_path / 'log') is False
    assert list(tmp_path.iterdir()) == []
    helfer.pfad(tmp_path).write_bytes(b'vorhanden')
    assert helfer.anwenden(None, tmp_path, AUFRUF, tmp_path / 'log') is True
    assert helfer.pfad(tmp_path).read_bytes() == b'vorhanden'


def test_aus_entfernt_nur_die_eigene_datei(tmp_path):
    fremd = tmp_path / 'com.example.anderes.plist'
    fremd.write_bytes(b'fremd')
    helfer.anwenden(True, tmp_path, AUFRUF, tmp_path / 'log')
    assert helfer.anwenden(False, tmp_path, AUFRUF, tmp_path / 'log') is False
    assert not helfer.pfad(tmp_path).exists()
    assert fremd.read_bytes() == b'fremd'


def test_route_vorgabe_ist_keine_antwort_und_ohne_helfer_nicht_verfuegbar(app):
    client = TestClient(app)
    stand = client.get('/api/v1/autostart').json()
    assert stand == {'gewuenscht': None, 'verfuegbar': False, 'eingerichtet': None, 'plattform': None}


def test_datei_entsteht_erst_nach_dem_klick(app, tmp_path):
    """Der ganze Weg: Helfer meldet sich, bekommt ohne Klick keine Antwort und schreibt nichts; nach dem Klick schon."""
    client = TestClient(app)
    ordner = tmp_path / 'LaunchAgents'
    wunsch = client.post('/api/v1/autostart/helfer', json={'plattform': 'macos', 'eingerichtet': False}).json()['gewuenscht']
    helfer.anwenden(wunsch, ordner, AUFRUF, tmp_path / 'log')
    assert not helfer.pfad(ordner).exists()
    assert client.get('/api/v1/autostart').json()['verfuegbar'] is True

    assert client.put('/api/v1/autostart', json={'an': True}).json()['gewuenscht'] is True
    wunsch = client.post('/api/v1/autostart/helfer', json={'plattform': 'macos', 'eingerichtet': False}).json()['gewuenscht']
    assert helfer.anwenden(wunsch, ordner, AUFRUF, tmp_path / 'log') is True
    client.post('/api/v1/autostart/helfer', json={'plattform': 'macos', 'eingerichtet': True})
    assert client.get('/api/v1/autostart').json()['eingerichtet'] is True

    assert client.put('/api/v1/autostart', json={'an': False}).json()['gewuenscht'] is False
    wunsch = client.post('/api/v1/autostart/helfer', json={'plattform': 'macos', 'eingerichtet': True}).json()['gewuenscht']
    assert helfer.anwenden(wunsch, ordner, AUFRUF, tmp_path / 'log') is False


def test_die_api_nimmt_nur_ja_oder_nein(app):
    client = TestClient(app)
    assert client.put('/api/v1/autostart', json={'an': True, 'programm': ['/bin/sh']}).status_code == 422
    assert client.post('/api/v1/autostart/helfer', json={'plattform': 'windows', 'eingerichtet': True}).status_code == 422


def test_einrichtung_kennt_den_schritt(app):
    client = TestClient(app)
    stand = client.put('/api/v1/einrichtung', json={'schritt': {'id': 'autostart', 'stand': 'uebersprungen'}}).json()
    assert stand['schritte']['autostart'] == 'uebersprungen'


def test_mac_start_startet_den_helfer():
    text = (Path(__file__).parents[2] / 'scripts/start_mac_app.py').read_text()
    assert "('mac_autostart.py', ['--container', container])" in text
