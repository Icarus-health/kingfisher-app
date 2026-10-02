"""Erststart-Assistent: der Merkzettel in den Einstellungen und was vom Wesentlichen schon da ist."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore, config
from icarus_memory.audit import AuditLog
from icarus_memory.episodes import EpisodeStore
from icarus_memory.morning import compose
from icarus_memory.providers_mail import catalogue
from icarus_memory.server import create_app
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore

ENV = ("ICARUS_PROVIDER", "ICARUS_MODEL", "ICARUS_BASE_URL", "KINGFISHER_USER_NAME", "OPENAI_API_KEY",
       "ANTHROPIC_API_KEY", "LLM_API_KEY")


@pytest.fixture
def api(tmp_path, monkeypatch):
    for name in ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ICARUS_SIDECAR_TOKEN", "local-owner-token")
    app = create_app(SelfModelStore(MemoryBackend(), subject_id="test"), audit=AuditLog(tmp_path / "audit.sqlite3"),
                     tasks=TaskStore(tmp_path / "tasks.sqlite3"), workspace=WorkspaceStore(tmp_path / "workspace.sqlite3"),
                     episodes=EpisodeStore(tmp_path / "episodes.sqlite3"))
    with TestClient(app, headers={"X-Icarus-Token": "local-owner-token"}) as client:
        yield app, client, tmp_path


def test_frischer_bestand_zeigt_den_assistenten(api) -> None:
    _, client, _ = api
    stand = client.get('/api/v1/einrichtung').json()
    assert stand['zeigen'] is True
    assert stand['abgeschlossen'] is False and stand['schritte'] == {} and stand['name'] == ''
    assert stand['vorhanden'] == {'mail': False, 'kalender': False, 'modell': False}


def test_der_stand_nennt_die_zeitzone_zum_anzeigen(api, monkeypatch) -> None:
    _, client, _ = api
    monkeypatch.delenv('KINGFISHER_TIMEZONE', raising=False)
    assert client.get('/api/v1/einrichtung').json()['zeitzone'] == 'Europe/Berlin'
    monkeypatch.setenv('KINGFISHER_TIMEZONE', 'Europe/Vienna')
    assert client.get('/api/v1/einrichtung').json()['zeitzone'] == 'Europe/Vienna'


def test_route_verlangt_die_anmeldung(api) -> None:
    app, _, _ = api
    with TestClient(app) as fremd:
        assert fremd.get('/api/v1/einrichtung').status_code in (401, 403)
        assert fremd.put('/api/v1/einrichtung', json={'name': 'X'}).status_code in (401, 403)
        assert fremd.get('/api/v1/einrichtung/lernt').status_code in (401, 403)


def test_stand_wird_gemerkt_und_ueberlebt_den_neustart(api) -> None:
    app, client, tmp_path = api
    client.put('/api/v1/einrichtung', json={'name': '  Lea  '})
    client.put('/api/v1/einrichtung', json={'schritt': {'id': 'name', 'stand': 'erledigt'}})
    stand = client.put('/api/v1/einrichtung', json={'schritt': {'id': 'mail', 'stand': 'uebersprungen'}}).json()
    assert stand['name'] == 'Lea'
    assert stand['schritte'] == {'name': 'erledigt', 'mail': 'uebersprungen'}
    # Auf der Platte, nicht nur im Speicher.
    geladen = config.load(tmp_path)
    assert geladen.einrichtung['name'] == 'Lea' and geladen.einrichtung['schritte']['mail'] == 'uebersprungen'
    # Ein Schritt lässt sich wieder öffnen.
    stand = client.put('/api/v1/einrichtung', json={'schritt': {'id': 'mail', 'stand': 'offen'}}).json()
    assert 'mail' not in stand['schritte']


def test_unbekannter_schritt_und_fremde_felder_werden_abgewiesen(api) -> None:
    _, client, _ = api
    assert client.put('/api/v1/einrichtung', json={'schritt': {'id': 'ufo', 'stand': 'erledigt'}}).status_code == 422
    assert client.put('/api/v1/einrichtung', json={'schritt': {'id': 'mail', 'stand': 'fertig'}}).status_code == 422
    assert client.put('/api/v1/einrichtung', json={'passwort': 'x'}).status_code == 422
    assert client.put('/api/v1/einrichtung', json={'name': 'x' * 81}).status_code == 422


def test_abgeschlossen_beendet_das_von_selbst_erscheinen_und_neu_beginnen_holt_es_zurueck(api) -> None:
    _, client, _ = api
    stand = client.put('/api/v1/einrichtung', json={'abgeschlossen': True}).json()
    assert stand['zeigen'] is False and stand['vorhanden']['mail'] is False
    stand = client.put('/api/v1/einrichtung', json={'neu_beginnen': True}).json()
    assert stand['zeigen'] is True and stand['schritte'] == {}


def test_nichts_zeigen_wenn_alles_da_ist(api) -> None:
    app, client, _ = api
    app.state.settings.model = 'llama3.1'
    app.state.settings.calendar_sources.append(config.CalendarSourceSettings(
        id='k1', label='Privat', kind='ical', url='https://example.org/a.ics'))
    app.state.settings.mail_accounts.append(config.MailAccountSettings(
        id='m1', label='Google', imap_host='imap.gmail.com', user='lea@example.org', auth_method='google_oauth'))
    stand = client.get('/api/v1/einrichtung').json()
    assert stand['vorhanden'] == {'mail': True, 'kalender': True, 'modell': True}
    assert stand['zeigen'] is False


def test_mailzugang_ohne_passwort_zaehlt_nicht(api) -> None:
    app, client, _ = api
    app.state.settings.mail_accounts.append(config.MailAccountSettings(
        id='m2', label='Arbeit', imap_host='imap.example.org', user='lea@example.org'))
    assert client.get('/api/v1/einrichtung').json()['vorhanden']['mail'] is False


def test_kaputte_datei_bringt_den_assistenten_nicht_zum_absturz(api) -> None:
    app, client, _ = api
    app.state.settings.einrichtung = {'name': 5, 'schritte': {'mail': 'kaputt', 'ufo': 'erledigt', 'name': 'erledigt'},
                                      'abgeschlossen': 'ja'}
    stand = client.get('/api/v1/einrichtung').json()
    assert stand['schritte'] == {'name': 'erledigt'} and stand['abgeschlossen'] is False and stand['name'] == '5'


def test_lernt_meldet_nichts_wenn_nichts_offen_ist(api) -> None:
    _, client, _ = api
    assert client.get('/api/v1/einrichtung/lernt').json() == {'akten': None}


def test_lernt_meldet_offene_berechnung_der_akten(api, monkeypatch) -> None:
    app, client, _ = api
    from icarus_memory import akten_routes
    bezuege, _ = akten_routes.bausteine(app)
    monkeypatch.setattr(bezuege, 'stand', lambda: {'quellen': 40, 'offen': 12})
    monkeypatch.setattr(akten_routes, 'nachfuehren', lambda app_, **kw: {'offen': 12, 'berechnet': 0})
    assert client.get('/api/v1/einrichtung/lernt').json() == {'akten': {'offen': 12, 'gesamt': 40}}


def test_name_aus_dem_assistenten_steht_im_gruss(monkeypatch) -> None:
    monkeypatch.delenv('KINGFISHER_USER_NAME', raising=False)
    jetzt = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
    leer = {'briefing': {'punkte': []}, 'calendar': {'items': []}, 'mail': {'items': []}, 'tasks': {},
            'episodes': {}, 'proposals': {}}
    assert compose(leer, now=jetzt, target=date(2026, 9, 1), nutzername='Lea')['greeting'] == 'Guten Morgen, Lea.'
    assert compose(leer, now=jetzt, target=date(2026, 9, 1), nutzername='  ')['greeting'] == 'Guten Morgen.'
    monkeypatch.setenv('KINGFISHER_USER_NAME', 'Anna')  # Umgebung schlägt Datei
    assert compose(leer, now=jetzt, target=date(2026, 9, 1), nutzername='Lea')['greeting'] == 'Guten Morgen, Anna.'


def test_briefing_route_gruesst_mit_dem_gespeicherten_namen(api) -> None:
    _, client, _ = api
    client.put('/api/v1/einrichtung', json={'name': 'Lea'})
    assert ', Lea.' in client.get('/api/v1/morning-briefing').json()['greeting']


def test_anbieterkatalog_nennt_die_adressendungen_fuer_die_erkennung() -> None:
    gmail = next(p for p in catalogue() if p['id'] == 'gmail')
    assert 'gmail.com' in gmail['domains']


def test_beim_anmelden_nur_wo_ein_helfer_ihn_einrichten_kann(api) -> None:
    """Befund 26: Ohne Helfer (Browser, Docker) meldet der Stand den Autostart als nicht verfügbar; der Assistent
    blendet den Schritt dann aus. Meldet sich der Mac-Helfer, ist die Frage wieder da."""
    _, client, _ = api
    assert client.get('/api/v1/einrichtung').json()['autostart_verfuegbar'] is False
    client.post('/api/v1/autostart/helfer', json={'plattform': 'macos', 'eingerichtet': False})
    assert client.get('/api/v1/einrichtung').json()['autostart_verfuegbar'] is True
