"""Google-Kalender ohne Cloud-Projekt über die geheime iCal-Adresse (Fremdprobe, Befund 2). Nur Attrappen, kein Netz."""
from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore, kalender_abo
from icarus_memory.audit import AuditLog
from icarus_memory.episodes import EpisodeStore
from icarus_memory.mail_anmeldung import Anmeldefehler
from icarus_memory.server import create_app
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore
from tests.ical_attrappe import GEHEIM, GOOGLE_GEHEIM, GOOGLE_OEFFENTLICH, IcalAttrappe


@pytest.fixture
def attrappe():
    with IcalAttrappe() as dienst:
        yield dienst


@pytest.fixture
def client(tmp_path, monkeypatch, attrappe):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    app = create_app(
        SelfModelStore(MemoryBackend(), subject_id='test'),
        audit=AuditLog(tmp_path / 'audit.sqlite3'), tasks=TaskStore(tmp_path / 'tasks.sqlite3'),
        workspace=WorkspaceStore(tmp_path / 'workspace.sqlite3'), episodes=EpisodeStore(tmp_path / 'episodes.sqlite3'),
    )
    app.state.ical_transport = attrappe.google_transport()
    with TestClient(app) as c:
        c.app_state = app.state
        yield c


@pytest.mark.parametrize(('adresse', 'art'), [
    (GOOGLE_GEHEIM, 'google_geheim'),
    (GOOGLE_GEHEIM.replace('https://', 'webcal://'), 'google_geheim'),
    (GOOGLE_OEFFENTLICH, 'google_oeffentlich'),
    ('https://calendar.google.com/calendar/embed?src=lena.probe%40example.org', 'google_falsch'),
    ('https://calendar.google.com/calendar/r/settings', 'google_falsch'),
    ('https://kalender.example.org/privat.ics', 'abo'),
    ('http://calendar.google.com' + GEHEIM, 'ungueltig'),
    ('lena.probe@example.org', 'ungueltig'),
])
def test_google_adresse_wird_erkannt(adresse, art):
    einordnung = kalender_abo.einordnen(adresse)
    assert einordnung.art == art
    if art == 'google_geheim':
        assert einordnung.url == GOOGLE_GEHEIM


def test_geheime_adresse_verbindet_nur_lesend_und_nur_mit_diesem_abruf(client, attrappe):
    antwort = client.post('/api/v1/integrations/calendar/abo', json={'url': GOOGLE_GEHEIM})
    assert antwort.status_code == 201, antwort.text
    daten = antwort.json()
    assert daten['gefunden'] == 'Google: Lena Probe' and daten['termine'] == 2 and daten['neu'] == 1
    quelle, = daten['calendar_sources']
    assert quelle['kind'] == 'ical' and quelle['label'] == 'Google: Lena Probe' and quelle['secret_present'] is True
    # Hinaus ging genau ein Abruf, und zwar dieser Adresse.
    assert attrappe.anfragen == [('GET', GEHEIM)]
    # Die geheime Adresse liegt nicht in den Einstellungen und nicht in der Antwort.
    assert 'private-' not in antwort.text
    settings = client.app_state.settings
    assert [e.url for e in settings.calendar_sources] == [kalender_abo.GOOGLE_ANZEIGE]
    assert client.get('/api/v1/einrichtung').json()['vorhanden']['kalender'] is True
    # Dieselbe Adresse noch einmal: kein zweiter Kalender.
    nochmal = client.post('/api/v1/integrations/calendar/abo', json={'url': GOOGLE_GEHEIM.replace('https', 'webcal', 1)})
    assert nochmal.status_code == 201 and nochmal.json()['neu'] == 0
    assert len(nochmal.json()['calendar_sources']) == 1
    # Der Kalender liest danach über dieselbe Adresse (aus dem Schlüsselbund), nur lesend.
    termine = client.app_state.calendar.events(days=30, at=datetime(2026, 10, 1, tzinfo=timezone.utc))
    assert {t.summary for t in termine} >= {'Abstimmung Atlas'}


@pytest.mark.parametrize(('adresse', 'grund', 'teil'), [
    (GOOGLE_OEFFENTLICH, 'abgelehnt', 'öffentliche Adresse nicht heraus'),
    ('https://calendar.google.com/calendar/ical/lena.probe%40example.org/private-ffffffffffffffffffff/basic.ics',
     'abgelehnt', 'Google kennt diese Adresse nicht (mehr)'),
    ('https://calendar.google.com/calendar/embed?src=x', 'google_falsch', 'Geheime Adresse im iCal-Format'),
    ('http://example.org/a.ics', 'ungueltig', 'beginnt mit https://'),
])
def test_falsche_adresse_ein_satz_und_nichts_gespeichert(client, adresse, grund, teil):
    antwort = client.post('/api/v1/integrations/calendar/abo', json={'url': adresse})
    assert antwort.status_code == 422, antwort.text
    assert antwort.json()['grund'] == grund and teil in antwort.json()['detail']
    assert antwort.json()['detail'].endswith('.') and '. ' not in antwort.json()['detail']
    assert client.get('/api/v1/integrations').json()['calendar_sources'] == []


def test_keine_kalenderdatei_und_umleitung_werden_nicht_angenommen(attrappe):
    # Ein anderes Kalender-Abo (nicht Google): Die Adresse wird abgerufen und muss selbst ein Kalender sein.
    transport = attrappe.google_transport()
    for pfad, teil in (('/keine-datei', 'liegt kein Kalender'), ('/umleitung', 'Antwort 302')):
        with pytest.raises(Anmeldefehler) as fehler:
            kalender_abo.pruefe(attrappe.basis + pfad, transport=transport)
        assert fehler.value.grund == 'kein_kalender' and teil in fehler.value.satz
    # Die Umleitung wurde nicht verfolgt: Es gab keine Anfrage an ein anderes Ziel.
    assert attrappe.anfragen == [('GET', '/keine-datei'), ('GET', '/umleitung')]
    # Eine Google-Seite, die kein Kalender ist, wird gar nicht erst abgerufen.
    with pytest.raises(Anmeldefehler) as fehler:
        kalender_abo.pruefe('https://calendar.google.com/calendar/r/settings', transport=transport)
    assert fehler.value.grund == 'google_falsch' and len(attrappe.anfragen) == 2


def test_schweigender_dienst_hat_eine_zeitgrenze(attrappe, monkeypatch):
    monkeypatch.setattr(kalender_abo, 'ZEITGRENZE', 1.0)
    beginn = time.monotonic()
    with pytest.raises(Anmeldefehler) as fehler:
        kalender_abo.pruefe(attrappe.basis + '/stumm', transport=attrappe.google_transport(), sekunden=1.0)
    assert fehler.value.grund == 'nicht_erreichbar' and fehler.value.status == 503
    assert time.monotonic() - beginn < 3
