"""Fassung und Update-Angebot (docs/53-download-und-updates.md).

Die Zusagen: genau eine GET-Anfrage ohne Kekse und ohne Kennung; ein Manifest zählt nur, wenn jede Angabe stimmt und
das Bild aus dem eigenen Paket mit der Fassung als Tag kommt; Fehler sind still und lassen `geprueft_um` stehen;
die Prüfung läuft im Faden des Zeitplans, auch wenn der Zeitplan selbst aus ist. Die Attrappe ist ein echter
HTTP-Server auf diesem Rechner, damit Kopfzeilen und Anzahl der Anfragen wirklich gemessen werden.
"""
from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from icarus_memory import fassung
from icarus_memory.fassung import (ABSTAND, ANLAUF_S, NACH_FEHLER_S, Fassungspruefung, abrufen, laufende_fassung,
                                   manifest_pruefen, neuer, semver)

WURZEL = Path(__file__).resolve().parents[2]
TOKEN = 'fassung-test'


def manifest(**aenderung) -> dict:
    daten = {'fassung': '1.2.0', 'datum': '2026-10-02', 'image': 'ghcr.io/icarus-health/kingfisher-app:1.2.0',
             'dmg': 'https://github.com/Icarus-health/kingfisher-app/releases/download/v1.2.0/Kingfisher.dmg',
             'hinweise': ['Briefing nennt Geburtstage.', 'Akten lassen sich als Ordner lesen.'],
             'app_mindestens': '1.0.0'}
    daten.update(aenderung)
    return daten


class Attrappe:
    """Ein HTTP-Server, der eine feste Antwort gibt und jede Anfrage mit Kopfzeilen aufschreibt."""

    def __init__(self, rumpf: bytes = b'', status: int = 200, verzoegerung: float = 0.0) -> None:
        self.rumpf, self.status, self.verzoegerung = rumpf, status, verzoegerung
        self.anfragen: list[dict] = []
        attrappe = self

        class Handler(BaseHTTPRequestHandler):
            def _antworten(self):
                attrappe.anfragen.append({'methode': self.command, 'pfad': self.path,
                                          'kopf': {k.lower(): v for k, v in self.headers.items()}})
                time.sleep(attrappe.verzoegerung)
                self.send_response(attrappe.status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Set-Cookie', 'spur=1')
                self.end_headers()
                self.wfile.write(attrappe.rumpf)

            do_GET = do_POST = do_HEAD = _antworten

            def log_message(self, *args):  # still
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}/latest.json'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def json(self, daten) -> 'Attrappe':
        self.rumpf = json.dumps(daten).encode()
        return self

    def schliessen(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def attrappe():
    a = Attrappe().json(manifest())
    yield a
    a.schliessen()


# -- Fassungsnummern ------------------------------------------------------------


def test_semver_streng():
    assert semver('1.2.0') == (1, 2, 0)
    assert semver('10.0.12') == (10, 0, 12)
    for falsch in ('v1.2.0', '1.2', '1.2.0-rc1', '01.2.0', ' 1.2.0', '1.2.0\n', 'entwicklung', '', None, 120, [1, 2, 0]):
        assert semver(falsch) is None, falsch


def test_neuer_vergleicht_zahlen_nicht_text():
    assert neuer('1.10.0', '1.9.0')
    assert neuer('2.0.0', '1.99.99')
    assert not neuer('1.2.0', '1.2.0')
    assert not neuer('1.1.9', '1.2.0')
    assert not neuer('1.2.0', 'entwicklung') and not neuer('entwicklung', '1.0.0')


def test_laufende_fassung_aus_bild_dann_datei_dann_entwicklung(tmp_path):
    datei = tmp_path / 'VERSION'
    datei.write_text('1.4.2\n', encoding='utf-8')
    assert laufende_fassung({'KINGFISHER_FASSUNG': '1.5.0'}, (datei,)) == '1.5.0'
    assert laufende_fassung({'KINGFISHER_FASSUNG': ''}, (datei,)) == '1.4.2'
    assert laufende_fassung({}, (tmp_path / 'fehlt',)) == 'entwicklung'


def test_version_im_repo_ist_eine_fassungsnummer():
    inhalt = (WURZEL / 'VERSION').read_text(encoding='utf-8')
    assert semver(inhalt.strip()) is not None and inhalt.endswith('\n')
    # Im Arbeitsbaum ohne Bild gilt die Datei.
    assert laufende_fassung({}) == inhalt.strip()


# -- Manifest ---------------------------------------------------------------------


def test_gueltiges_manifest_bleibt_und_unbekanntes_faellt_weg():
    gut = manifest(extra='nicht übernehmen')
    geprueft = manifest_pruefen(gut)
    assert geprueft is not None and 'extra' not in geprueft
    assert geprueft['image'] == 'ghcr.io/icarus-health/kingfisher-app:1.2.0'


@pytest.mark.parametrize('aenderung', [
    {'image': 'ghcr.io/fremd/kingfisher:1.2.0'},
    {'image': 'ghcr.io/icarus-health/kingfisher-app:1.1.0'},         # Tag ist nicht die Fassung
    {'image': 'ghcr.io/icarus-health/kingfisher-app:latest'},
    {'image': 'docker.io/icarus-health/kingfisher:1.2.0'},
    {'fassung': 'v1.2.0', 'image': 'ghcr.io/icarus-health/kingfisher-app:v1.2.0'},
    {'fassung': 1.2},
    {'datum': '2.10.2026'}, {'datum': '2026-13-01'}, {'datum': 20261002},
    {'dmg': 'http://github.com/x/Kingfisher.dmg'}, {'dmg': 'javascript:alert(1)'}, {'dmg': None},
    {'hinweise': 'Ein Satz'}, {'hinweise': ['ok', 3]}, {'hinweise': ['']}, {'hinweise': ['x' * 301]},
    {'hinweise': ['h'] * 21},
    {'app_mindestens': '1.0'}, {'app_mindestens': None},
])
def test_manifest_wird_verworfen(aenderung):
    assert manifest_pruefen(manifest(**aenderung)) is None


@pytest.mark.parametrize('feld', ['fassung', 'datum', 'image', 'dmg', 'hinweise', 'app_mindestens'])
def test_manifest_ohne_pflichtangabe_wird_verworfen(feld):
    daten = manifest()
    del daten[feld]
    assert manifest_pruefen(daten) is None
    assert manifest_pruefen([daten]) is None


# -- Der eine Abruf -----------------------------------------------------------------


def test_genau_eine_get_anfrage_ohne_kekse_und_ohne_kennung(attrappe):
    ergebnis = abrufen(attrappe.url)
    assert ergebnis == manifest_pruefen(manifest())
    assert len(attrappe.anfragen) == 1
    anfrage = attrappe.anfragen[0]
    assert anfrage['methode'] == 'GET' and anfrage['pfad'] == '/latest.json'
    kopf = anfrage['kopf']
    assert 'cookie' not in kopf and 'authorization' not in kopf
    assert kopf['user-agent'] == 'Kingfisher'   # nicht „Python-urllib/3.x“, keine Fassung, kein Rechnername
    assert not re.search(r'\d', kopf['user-agent'])
    # Ein zweiter Abruf schickt den Keks der ersten Antwort nicht zurück.
    abrufen(attrappe.url)
    assert 'cookie' not in attrappe.anfragen[1]['kopf']


@pytest.mark.parametrize('rumpf,status', [(b'{kaputt', 200), (b'', 200), (json.dumps(manifest()).encode(), 500),
                                          (json.dumps(manifest()).encode(), 404)])
def test_fehler_sind_still(rumpf, status):
    a = Attrappe(rumpf, status)
    try:
        assert abrufen(a.url) is None
    finally:
        a.schliessen()


def test_zu_grosse_antwort_wird_nicht_gelesen():
    a = Attrappe(b'{"x": "' + b'a' * (70 * 1024) + b'"}')
    try:
        assert abrufen(a.url) is None
    finally:
        a.schliessen()


def test_kurze_zeitgrenze():
    a = Attrappe(json.dumps(manifest()).encode(), verzoegerung=2.0)
    try:
        begonnen = time.monotonic()
        assert abrufen(a.url, zeitgrenze=0.3) is None
        assert time.monotonic() - begonnen < 1.5
    finally:
        a.schliessen()


def test_nur_https_oder_dieser_rechner():
    assert fassung.url_erlaubt('https://icarus-health.github.io/kingfisher-app/latest.json')
    assert fassung.url_erlaubt('http://127.0.0.1:9/latest.json')
    assert not fassung.url_erlaubt('http://icarus-health.github.io/kingfisher-app/latest.json')
    assert not fassung.url_erlaubt('file:///etc/passwd')
    assert abrufen('file:///etc/passwd') is None


def test_download_seite_aus_der_manifest_adresse():
    assert fassung.download_seite('https://icarus-health.github.io/kingfisher-app/latest.json') == 'https://icarus-health.github.io/kingfisher-app/'
    assert fassung.download_seite('http://127.0.0.1:9/latest.json') is None
    assert fassung.download_seite('https://x.example/manifest.json') is None
    assert fassung.download_seite('') is None


def test_vorgabe_url_und_leer_heisst_aus():
    assert fassung.manifest_url({}) == 'https://icarus-health.github.io/kingfisher-app/latest.json'
    assert fassung.manifest_url({'KINGFISHER_UPDATE_URL': ''}) == ''
    assert fassung.manifest_url({'KINGFISHER_UPDATE_URL': 'https://x.example/l.json'}) == 'https://x.example/l.json'


# -- Zustand und Fälligkeit -------------------------------------------------------------


class Uhr:
    def __init__(self):
        self.jetzt = datetime(2026, 10, 2, 8, 0, tzinfo=timezone.utc)
        self.mono = 1000.0


def pruefung(tmp_path, ergebnisse, uhr):
    abrufe = []

    def abruf(url):
        abrufe.append(url)
        return ergebnisse.pop(0) if ergebnisse else None
    return Fassungspruefung(tmp_path / 'fassung.json', abruf=abruf, uhr=lambda: uhr.jetzt,
                            monoton=lambda: uhr.mono), abrufe


def test_erfolg_merkt_manifest_fehler_laesst_alles_stehen(tmp_path, monkeypatch):
    monkeypatch.setenv('KINGFISHER_UPDATE_URL', 'https://x.example/latest.json')
    monkeypatch.setenv('KINGFISHER_FASSUNG', '1.0.0')
    uhr = Uhr()
    p, abrufe = pruefung(tmp_path, [manifest_pruefen(manifest()), None], uhr)
    assert p.stand()['geprueft_um'] is None and p.stand()['pruefen'] is True
    assert p.jetzt_pruefen() is True
    stand = p.stand()
    assert stand['geprueft_um'] == '2026-10-02T08:00:00+00:00'
    assert stand['neueste']['fassung'] == '1.2.0' and stand['update_verfuegbar'] is True
    uhr.jetzt += timedelta(days=2)
    assert p.jetzt_pruefen() is False
    assert p.stand() == stand   # nur geprueft_um bleibt alt, und das Manifest von vorher gilt weiter
    assert abrufe == ['https://x.example/latest.json'] * 2


def test_faellig_einmal_am_tag_nach_anlauf_und_nach_fehler_erst_in_einer_stunde(tmp_path, monkeypatch):
    monkeypatch.setenv('KINGFISHER_UPDATE_URL', 'https://x.example/latest.json')
    uhr = Uhr()
    p, abrufe = pruefung(tmp_path, [None, manifest_pruefen(manifest())], uhr)
    p.im_takt()
    assert abrufe == []                          # Anlauf
    uhr.mono += ANLAUF_S
    p.im_takt()
    assert len(abrufe) == 1                      # Fehler
    p.im_takt()
    uhr.mono += NACH_FEHLER_S - 1
    p.im_takt()
    assert len(abrufe) == 1                      # nicht im Takt wiederholen
    uhr.mono += 1
    p.im_takt()
    assert len(abrufe) == 2 and p.stand()['geprueft_um'] is not None
    uhr.mono += 10 * NACH_FEHLER_S
    uhr.jetzt += ABSTAND - timedelta(minutes=1)
    p.im_takt()
    assert len(abrufe) == 2                      # erst nach einem Tag
    uhr.jetzt += timedelta(minutes=1)
    p.im_takt()
    assert len(abrufe) == 3


def test_ausgeschaltet_fragt_nie(tmp_path, monkeypatch):
    monkeypatch.setenv('KINGFISHER_UPDATE_URL', 'https://x.example/latest.json')
    uhr = Uhr()
    p, abrufe = pruefung(tmp_path, [], uhr)
    assert p.schalten(False)['pruefen'] is False
    uhr.mono += 10 * NACH_FEHLER_S
    p.im_takt()
    assert abrufe == []
    assert json.loads((tmp_path / 'fassung.json').read_text())['pruefen'] is False


def test_leere_url_fragt_nie(tmp_path, monkeypatch):
    monkeypatch.setenv('KINGFISHER_UPDATE_URL', '')
    uhr = Uhr()
    p, abrufe = pruefung(tmp_path, [manifest_pruefen(manifest())], uhr)
    uhr.mono += 10 * NACH_FEHLER_S
    p.im_takt()
    assert p.jetzt_pruefen() is False and abrufe == []


def test_manipulierte_datei_wird_nicht_angeboten(tmp_path, monkeypatch):
    monkeypatch.setenv('KINGFISHER_FASSUNG', '1.0.0')
    (tmp_path / 'fassung.json').write_text(json.dumps({'pruefen': True, 'neueste': manifest(image='ghcr.io/fremd/x:1.2.0')}))
    stand = pruefung(tmp_path, [], Uhr())[0].stand()
    assert stand['neueste'] is None and stand['update_verfuegbar'] is False


@pytest.mark.parametrize('laeuft,app_mindestens,verfuegbar,app_noetig', [
    ('1.0.0', '1.0.0', True, False),
    ('1.0.0', '1.1.0', True, True),
    ('1.1.0', '1.1.0', True, False),
    ('1.2.0', '1.2.0', False, False),
    ('1.3.0', '1.0.0', False, False),
    ('entwicklung', '1.0.0', False, False),
])
def test_angebot_und_app_update(tmp_path, monkeypatch, laeuft, app_mindestens, verfuegbar, app_noetig):
    monkeypatch.setenv('KINGFISHER_FASSUNG', laeuft)
    p, _ = pruefung(tmp_path, [manifest_pruefen(manifest(app_mindestens=app_mindestens))], Uhr())
    monkeypatch.setenv('KINGFISHER_UPDATE_URL', 'https://x.example/latest.json')
    p.jetzt_pruefen()
    stand = p.stand()
    assert (stand['update_verfuegbar'], stand['app_update_noetig']) == (verfuegbar, app_noetig)


# -- Zeitplan ------------------------------------------------------------------------


def test_nebenbei_laeuft_im_faden_auch_wenn_der_plan_aus_ist(monkeypatch):
    from icarus_memory import scheduler
    monkeypatch.setattr(scheduler, 'TICK_SECONDS', 0.01)
    gerufen = threading.Event()
    plan = scheduler.Scheduler(run_backup=lambda: pytest.fail('der Plan ist aus'))
    plan.nebenbei_setzen(gerufen.set)
    plan.start()
    try:
        assert gerufen.wait(2)
        assert plan.state()['running'] is False   # der Faden läuft, der Plan nicht
        assert plan.state()['last_run'] is None
    finally:
        plan.stop()


def test_ein_fehler_nebenbei_beendet_den_faden_nicht(monkeypatch):
    from icarus_memory import scheduler
    monkeypatch.setattr(scheduler, 'TICK_SECONDS', 0.01)
    zaehler = []

    def kaputt():
        zaehler.append(1)
        raise RuntimeError('kaputt')
    plan = scheduler.Scheduler()
    plan.nebenbei_setzen(kaputt)
    plan.start()
    try:
        ende = time.monotonic() + 2
        while len(zaehler) < 3 and time.monotonic() < ende:
            time.sleep(0.01)
        assert len(zaehler) >= 3 and plan._thread.is_alive()  # noqa: SLF001
    finally:
        plan.stop()


# -- Über die Schnittstelle -------------------------------------------------------------


@pytest.fixture
def app_mit(tmp_path, monkeypatch):
    from icarus_memory.server import create_app
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', TOKEN)
    monkeypatch.setenv('KINGFISHER_FASSUNG', '1.0.0')
    apps = []

    def bauen(url: str):
        monkeypatch.setenv('KINGFISHER_UPDATE_URL', url)
        app = create_app()
        apps.append(app)
        return app, TestClient(app, headers={'x-icarus-token': TOKEN})
    yield bauen
    for app in apps:
        app.state.scheduler.stop()


def test_endpunkte_mit_token(app_mit, attrappe):
    app, client = app_mit(attrappe.url)
    assert TestClient(app).get('/api/v1/fassung').status_code == 401
    stand = client.get('/api/v1/fassung').json()
    assert stand == {'fassung': '1.0.0', 'neueste': None, 'update_verfuegbar': False, 'app_update_noetig': False,
                     'geprueft_um': None, 'pruefen': True, 'download_seite': None}   # Attrappe ohne HTTPS
    assert attrappe.anfragen == []                 # Lesen fragt nie nach außen
    neu = client.post('/api/v1/fassung/pruefen').json()
    assert neu['erreicht'] is True and neu['update_verfuegbar'] is True and neu['neueste']['fassung'] == '1.2.0'
    assert neu['geprueft_um'] and len(attrappe.anfragen) == 1
    assert client.put('/api/v1/fassung', json={'pruefen': False}).json()['pruefen'] is False
    assert client.get('/api/v1/fassung').json()['pruefen'] is False
    assert client.put('/api/v1/fassung', json={'pruefen': 'vielleicht'}).status_code == 422
    assert client.put('/api/v1/fassung', json={'pruefen': True, 'mehr': 1}).status_code == 422


def test_nicht_erreichbar_sagt_es_und_aendert_nichts(app_mit):
    _, client = app_mit('http://127.0.0.1:9/latest.json')
    stand = client.post('/api/v1/fassung/pruefen').json()
    assert stand['erreicht'] is False and stand['geprueft_um'] is None


def test_faden_laeuft_fuer_die_pruefung_und_stoppt_wenn_sie_aus_ist(app_mit, attrappe):
    app, client = app_mit(attrappe.url)
    plan = app.state.scheduler
    assert app.state.settings.schedule.enabled is False
    assert plan._thread is not None and plan._thread.is_alive()  # noqa: SLF001
    assert client.get('/schedule').json()['running'] is False
    client.put('/api/v1/fassung', json={'pruefen': False})
    assert plan._thread is None or not plan._thread.is_alive()  # noqa: SLF001
    client.put('/api/v1/fassung', json={'pruefen': True})
    assert plan._thread is not None and plan._thread.is_alive()  # noqa: SLF001


def test_ohne_url_kein_faden(app_mit):
    app, _ = app_mit('')
    plan = app.state.scheduler
    assert plan._thread is None or not plan._thread.is_alive()  # noqa: SLF001
