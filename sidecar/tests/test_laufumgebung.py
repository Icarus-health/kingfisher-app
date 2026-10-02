"""Auf welchem System Kingfisher läuft (Fremdprobe, Befund 18): Erkennung und Auslieferung an die Oberfläche."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from icarus_memory import device_profile, laufumgebung
from icarus_memory.laufumgebung import beschreiben, system_art


@pytest.mark.parametrize(('plattform', 'container', 'wirt', 'erwartet'), [
    ('darwin', False, None, 'mac'),               # Sidecar direkt auf dem Mac
    ('linux', True, 'macos', 'mac'),              # Container, gestartet von der Mac-App (Bericht des Rechners)
    ('linux', True, None, 'docker'),              # Docker mit dem Browser, ohne Mac
    ('linux', True, 'linux', 'docker'),           # Docker auf einem Linux-Rechner
    ('linux', False, None, 'linux'),
    ('linux', False, 'macos', 'linux'),           # ein Bericht ohne Container ändert nichts am eigenen System
    ('win32', False, None, 'windows'),
    ('freebsd13', False, None, 'rechner'),
])
def test_system_art(plattform, container, wirt, erwartet):
    assert system_art(plattform=plattform, im_container=container, wirt=wirt) == erwartet


def test_beschreiben_liest_den_bericht_des_rechners(tmp_path, monkeypatch):
    monkeypatch.setattr(laufumgebung, '_im_container', lambda: True)
    monkeypatch.setattr(laufumgebung.sys, 'platform', 'linux')
    assert beschreiben(tmp_path) == {'art': 'docker', 'name': 'Docker im Browser', 'geraet': 'Rechner', 'mac_helfer': False}
    (tmp_path / 'device-profile.json').write_text(json.dumps(
        {'platform': 'macos', 'chip': 'Apple M3', 'memory_bytes': 16 * 1024**3}), encoding='utf-8')
    assert beschreiben(tmp_path) == {'art': 'mac', 'name': 'Mac-App', 'geraet': 'Mac', 'mac_helfer': True}


def test_route_und_setup_liefern_das_system(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('ICARUS_SIDECAR_TOKEN', raising=False)
    monkeypatch.setattr(laufumgebung, '_im_container', lambda: True)
    monkeypatch.setattr(laufumgebung.sys, 'platform', 'linux')
    from icarus_memory.server import create_app
    with TestClient(create_app()) as client:
        assert client.get('/api/v1/system').json()['art'] == 'docker'
        assert client.get('/api/v1/setup').json()['system'] == {
            'art': 'docker', 'name': 'Docker im Browser', 'geraet': 'Rechner', 'mac_helfer': False}


def test_hinweis_zur_ausstattung_nennt_docker_nur_im_container(tmp_path, monkeypatch):
    monkeypatch.setattr(device_profile, '_im_container', lambda: False)
    ausserhalb = device_profile.load_device_profile(tmp_path)['guidance']['note']
    assert ausserhalb == 'Der Rechner hat seine Ausstattung noch nicht gemeldet.'
    monkeypatch.setattr(device_profile, '_im_container', lambda: True)
    drinnen = device_profile.load_device_profile(tmp_path)['guidance']['note']
    assert 'Container' in drinnen and 'Docker-Speicher' not in drinnen and 'RAM' not in drinnen
