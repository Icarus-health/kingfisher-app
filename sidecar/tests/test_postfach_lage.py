"""Posteingang ohne Warten, wenn das Postfach schweigt (Fremdprobe, Befunde 14 und 22)."""
from __future__ import annotations

import threading
import time

import pytest
from fastapi.testclient import TestClient

from icarus_memory import postfach_lage, server
from icarus_memory.mail_anmeldung import Anmeldefehler
from icarus_memory.postfach_lage import PostfachLage


class Uhr:
    def __init__(self) -> None:
        self.jetzt = 1000.0

    def __call__(self) -> float:
        return self.jetzt


def test_schweigt_einmal_dann_sofort_mit_grund():
    uhr = Uhr()
    lage = PostfachLage(uhr)
    freigabe = threading.Event()
    aufrufe = []

    def haengt():
        aufrufe.append(1)
        freigabe.wait(5)
        return ['mail']

    beginn = time.monotonic()
    with pytest.raises(Anmeldefehler) as erst:
        lage.lesen('alle', haengt, host='imap.web.de', name='WEB.DE', sekunden=0.2)
    assert time.monotonic() - beginn < 1.5
    assert erst.value.satz.startswith('WEB.DE antwortet gerade nicht.')
    # Gleich danach: sofort derselbe Satz, ohne die Zeitgrenze abzuwarten.
    beginn = time.monotonic()
    with pytest.raises(Anmeldefehler) as zweit:
        lage.lesen('alle', haengt, host='imap.web.de', name='WEB.DE', sekunden=5)
    assert time.monotonic() - beginn < 0.1
    assert zweit.value.grund == 'nicht_erreichbar'
    freigabe.set()


def test_hintergrundversuch_macht_das_postfach_wieder_erreichbar():
    lage = PostfachLage(Uhr())
    with pytest.raises(Anmeldefehler):
        lage.lesen('alle', lambda: (_ for _ in ()).throw(OSError('weg')), host='', name='Probe-Post', sekunden=1)
    with pytest.raises(Anmeldefehler):
        lage.lesen('alle', lambda: ['neu'], host='', name='Probe-Post', sekunden=1)  # sofort, stößt neuen Versuch an
    for _ in range(50):
        if lage.gemerkt('alle') is None:
            break
        time.sleep(0.05)
    assert lage.lesen('alle', lambda: ['neu'], host='', name='Probe-Post', sekunden=1) == ['neu']


def test_gemerkt_nur_eine_weile():
    uhr = Uhr()
    lage = PostfachLage(uhr)
    with pytest.raises(Anmeldefehler):
        lage.lesen('a', lambda: (_ for _ in ()).throw(TimeoutError()), host='', name='X', sekunden=1)
    assert lage.gemerkt('a') is not None and lage.gemerkt('b') is None
    uhr.jetzt += postfach_lage.MERKEN + 1
    assert lage.gemerkt('a') is None


def test_nachrichten_nennen_das_postfach_und_den_weg_dorthin(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('ICARUS_SIDECAR_TOKEN', raising=False)
    monkeypatch.setattr(server, 'POSTFACH_ZEITGRENZE', 0.3)
    freigabe = threading.Event()

    class Schweigt:
        def inbox(self, **_kwargs):
            freigabe.wait(5)
            return []

    with TestClient(server.create_app()) as client:
        client.app.state.mail = Schweigt()
        try:
            beginn = time.monotonic()
            erst = client.get('/api/v1/messages').json()
            dauer_erst = time.monotonic() - beginn
            beginn = time.monotonic()
            zweit = client.get('/api/v1/messages').json()
            dauer_zweit = time.monotonic() - beginn
            heute = client.get('/api/v1/morning-briefing').json()
            schnell = client.get('/api/v1/morning-briefing', params={'post': 'false'}).json()
        finally:
            freigabe.set()
    fehler = erst['partial_failure']
    assert fehler['code'] == 'unavailable' and fehler['grund'] == 'nicht_erreichbar'
    assert fehler['message'].startswith('Ein Postfach antwortet gerade nicht.')
    assert 'lokale Posteingang' not in fehler['message']
    assert fehler['ziel'] == '/settings#zugaenge'
    assert dauer_erst < 2 and dauer_zweit < 0.25, (dauer_erst, dauer_zweit)
    assert zweit['partial_failure']['message'] == fehler['message']
    # Heute: der Grund steht bei den Teilausfällen; ohne Post gibt es keinen Ausfall und keine Wartezeit.
    assert any(f['section'] == 'mail' and 'antwortet gerade nicht' in f['message'] for f in heute['partial_failures'])
    assert not any(f['section'] == 'mail' for f in schnell['partial_failures'])
    assert schnell['greeting']
