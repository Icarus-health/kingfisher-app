"""Dieser Rechner (Fremdprobe, Befunde 10 und 11): Ausstattung selbst ermitteln, „Anderes Modell nehmen“."""
from __future__ import annotations

import pytest

from icarus_memory import device_profile
from icarus_memory.model_recommendation import Geraet, ausweichwahl, empfehle_alle
from tests.test_model_roles_routes import app_und_client, bereit, einrichten, geraet  # noqa: F401 - Fixture

EIGENE_AUSSTATTUNG = device_profile.eigene_ausstattung  # vor dem autouse-Ersatz in conftest.py gemerkt


def test_eigene_messung_ausserhalb_des_containers(monkeypatch):
    monkeypatch.setattr(device_profile.os, 'sysconf', lambda name: {'SC_PAGE_SIZE': 4096, 'SC_PHYS_PAGES': 4 * 1024 * 1024}[name])
    monkeypatch.setattr(device_profile, '_cgroup_grenze', lambda: None)
    monkeypatch.setattr(device_profile, '_im_container', lambda: False)
    monkeypatch.setattr(device_profile.sys, 'platform', 'linux')
    assert EIGENE_AUSSTATTUNG() == {'memory_gb': 16.0, 'platform': 'linux', 'untergrenze': False}


def test_im_container_ist_die_messung_eine_untergrenze(monkeypatch):
    monkeypatch.setattr(device_profile.os, 'sysconf', lambda name: {'SC_PAGE_SIZE': 4096, 'SC_PHYS_PAGES': 8 * 1024 * 1024}[name])
    monkeypatch.setattr(device_profile, '_cgroup_grenze', lambda: 8 * 1024**3)
    monkeypatch.setattr(device_profile, '_im_container', lambda: True)
    # Die Grenze des Containers gilt (8 statt 32 GB), die Plattform des Rechners ist unbekannt.
    assert EIGENE_AUSSTATTUNG() == {'memory_gb': 8.0, 'platform': 'unknown', 'untergrenze': True}


def test_ohne_bericht_misst_kingfisher_selbst_und_fragt_niemanden(app_und_client, monkeypatch):
    app, client = app_und_client
    bereit(app)
    monkeypatch.setattr(device_profile, 'eigene_ausstattung', lambda: {'memory_gb': 16.0, 'platform': 'linux', 'untergrenze': False})
    daten = client.get('/api/v1/models/recommendation').json()['geraet']
    assert (daten['bekannt'], daten['stufe_gb'], daten['arbeitsspeicher_gb'], daten['quelle']) == (True, 16, 16.0, 'eigene')
    monkeypatch.setattr(device_profile, 'eigene_ausstattung', lambda: {'memory_gb': 8.0, 'platform': 'unknown', 'untergrenze': True})
    assert client.get('/api/v1/models/recommendation').json()['geraet']['quelle'] == 'untergrenze'
    # Ein Bericht des Helfers geht vor.
    geraet(client, 32)
    daten = client.get('/api/v1/models/recommendation').json()['geraet']
    assert (daten['quelle'], daten['stufe_gb']) == ('bericht', 32)


def test_ausweichwahl_passt_und_wiederholt_nichts():
    g16 = Geraet(arbeitsspeicher_gb=16)
    empfohlen = empfehle_alle(g16)['frage'].modell.name
    namen = [e.name for e in ausweichwahl('frage', g16, (empfohlen,))]
    assert empfohlen not in namen and len(namen) == len(set(namen)) and namen
    assert namen[0] == 'lfm2.5:8b' and 'qwen3.5:2b' in namen  # erst die Alternative, dann das kleinere
    # Auf 8 GB bleiben mindestens 6 GB für System und andere Programme frei.
    g8 = Geraet(arbeitsspeicher_gb=8)
    for rolle in ('frage', 'antwort', 'pruefung', 'hintergrund', 'einbettung'):
        for eintrag in ausweichwahl(rolle, g8):
            assert eintrag.speicher_gb <= 2, (rolle, eintrag.name)
    assert ausweichwahl('pruefung', g8, ('tev1:0.8b',)) == ()
    # Separater GPU-Speicher behält sein eigenes Budget; dort passen beide Alternativen.
    gpu8 = Geraet('linux', None, 8, 8)
    assert [e.name for e in ausweichwahl('pruefung', gpu8, ('tev1:0.8b',))] == ['tev1:4b', 'bespoke-minicheck:7b']


def test_anderes_modell_nehmen_ist_erlaubt_und_die_empfehlung_nennt_es(app_und_client):
    app, client = app_und_client
    geraet(client, 16)
    bereit(app)
    rollen = {z['rolle']: z for z in client.get('/api/v1/models/recommendation').json()['rollen']}
    ausweich = [a['name'] for a in rollen['frage']['ausweich']]
    assert ausweich and rollen['frage']['empfohlen']['name'] not in ausweich
    r, stand = einrichten(client, app, 'frage', modell=ausweich[-1])
    assert r.status_code == 202 and stand['phase'] == 'fertig'
    # Was nicht auf der Liste steht, bleibt verboten.
    assert client.post('/api/v1/models/pull', json={'rolle': 'frage', 'modell': 'qwen3.6:35b', 'bestaetigt': True}).status_code == 422


def test_nicht_bestanden_sagt_was_zu_tun_ist_ohne_fachwort(app_und_client):
    app, client = app_und_client
    bereit(app, bestanden=False)
    _, stand = einrichten(client, app)
    assert stand['phase'] == 'fehler'
    assert 'Messlatte' not in stand['fehler']['naechster_schritt'] and 'Alternativen' not in stand['fehler']['naechster_schritt']
    assert 'anderes Modell' in stand['fehler']['naechster_schritt'] and stand['fehler']['art'] == 'pruefung'


@pytest.mark.parametrize('roh,erwartet', [('max', None), ('9223372036854771712', None), ('8589934592', 8 * 1024**3)])
def test_cgroup_grenze(tmp_path, monkeypatch, roh, erwartet):
    datei = tmp_path / 'memory.max'
    datei.write_text(roh + '\n')
    echte = device_profile.Path

    def umgeleitet(pfad, *a, **k):
        return echte(datei) if str(pfad) == '/sys/fs/cgroup/memory.max' else echte(tmp_path / 'fehlt')
    monkeypatch.setattr(device_profile, 'Path', umgeleitet)
    assert device_profile._cgroup_grenze() == erwartet
