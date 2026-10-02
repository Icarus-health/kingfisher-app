"""Der Mac-Helfer für den Mitschriften-Eingang: Auswahl, Trennen, Lesen mit Dateizeit (F3).

Der Auswahldialog selbst (osascript) läuft nur auf dem Mac und ist hier durch eine Funktion ersetzt.
"""
from __future__ import annotations

import importlib.util
import json
import os
import time
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from icarus_memory.calendar_memory import KalenderGedaechtnis, fenster
from icarus_memory.connectors.calendar import Event
from icarus_memory.episodes import EpisodeState
from icarus_memory.server import create_app

spec = importlib.util.spec_from_file_location("mac_folder_worker", Path(__file__).parents[2] / "scripts" / "mac_folder_worker.py")
worker = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(worker)

JETZT = datetime(2026, 9, 29, 8, 0, tzinfo=timezone.utc)
TAG = datetime(2026, 9, 28, 12, 30, tzinfo=timezone.utc)
MEETING = 'Anna Berg: Guten Tag.\nBert Kraus: Hallo.\nAnna Berg: Das Budget steht.\nBert Kraus: Gut.\n'


class TestApi:
    """Spricht dieselben Routen wie der echte Helfer, aber ohne Netz."""
    __test__ = False

    def __init__(self, client, prefix='/api/v1/transcript-sync'):
        self.client, self.prefix = client, prefix

    def call(self, path='', body=None):
        antwort = self.client.post(self.prefix + path, json=body) if body is not None else self.client.get(self.prefix + path)
        if antwort.status_code >= 400:
            raise urllib.error.HTTPError(self.prefix + path, antwort.status_code, 'Fehler', {}, None)
        return antwort.json()


def ablegen(ordner: Path, name: str, text: str = MEETING, alter: float = 10) -> Path:
    ordner.mkdir(parents=True, exist_ok=True)
    datei = ordner / name
    datei.write_text(text, encoding='utf-8')
    frueher = time.time() - alter
    os.utime(datei, (frueher, frueher))
    return datei


def test_nur_mitschriftformate_und_die_dateizeit_kommen_beim_server_an(tmp_path):
    ablegen(tmp_path, 'a.txt')
    ablegen(tmp_path, 'b.vtt', 'WEBVTT\n')
    ablegen(tmp_path, 'c.pdf', 'x')
    ablegen(tmp_path, 'd.csv', 'x')
    erhalten = []
    bericht = worker.scan(tmp_path, lambda name, daten, mtime: erhalten.append((name, mtime)),
                          supported=worker.TRANSKRIPTE, with_mtime=True)
    assert sorted(name for name, _ in erhalten) == ['a.txt', 'b.vtt']
    assert all(abs(mtime - (time.time() - 10)) < 5 for _, mtime in erhalten)
    assert {'c.pdf', 'd.csv'} <= set(bericht['observed'])          # gesehen, aber nicht gelesen


def test_der_dokumentenordner_bleibt_unveraendert(tmp_path):
    ablegen(tmp_path, 'a.txt')
    ablegen(tmp_path, 'c.pdf', 'x')
    erhalten = []
    worker.scan(tmp_path, lambda name, daten: erhalten.append(name))
    assert sorted(erhalten) == ['a.txt', 'c.pdf']


def test_vorgabe_legt_den_ordner_an_und_der_dialog_liefert_den_gewaehlten(tmp_path):
    ordner = worker.waehle_ordner('vorgabe', home=tmp_path)
    assert ordner == tmp_path / 'Documents' / 'Kingfisher' / 'Transkripte' and ordner.is_dir()
    assert worker.waehle_ordner('waehlen', dialog=lambda: tmp_path / 'Gewaehlt') == tmp_path / 'Gewaehlt'
    assert worker.waehle_ordner('anderes') is None


def test_gemerkte_wahl_ueberlebt_den_neustart_und_ist_privat(tmp_path):
    datei = tmp_path / 'privat.transkripte.json'
    auswahl = worker.Auswahl(datei)
    assert auswahl.folder is None
    auswahl.setzen(tmp_path / 'Meetings')
    assert worker.Auswahl(datei).folder == tmp_path / 'Meetings'
    assert oct(datei.stat().st_mode & 0o777) == '0o600'
    datei.write_text(json.dumps({'folder': 'relativ'}))
    assert worker.Auswahl(datei).folder is None                     # ein relativer Pfad ist keine Wahl


def test_ohne_wahl_meldet_der_helfer_keinen_ordner_und_liest_nichts(tmp_path):
    with TestClient(create_app()) as client:
        api = TestApi(client)
        zustand = worker.transkript_schritt(api, worker.Auswahl(tmp_path / 'x.json'))
        assert zustand['root_id'] is None and zustand['enabled'] is False and zustand['running'] is True


def test_auswahl_am_mac_gibt_genau_diesen_ordner_frei_und_die_aufnahme_laeuft(tmp_path):
    app = create_app()
    with TestClient(app) as client:
        von, bis = fenster(JETZT)
        KalenderGedaechtnis(app.state.episodes, app.state.claims).abgleichen(
            'k', 'Arbeit', [Event(uid='a', summary='Jour fixe Winter', start=TAG, end=TAG + timedelta(hours=1),
                                  attendees=['Anna Berg <anna.berg@winter.example>'])], von, bis, at=JETZT)
        meetings = tmp_path / 'Meetings'
        ablegen(meetings, '2026-09-28 14.30 Jour fixe Winter.txt')
        api, auswahl = TestApi(client), worker.Auswahl(tmp_path / 'x.json')
        client.post('/api/v1/transkripte/ordner', json={'modus': 'waehlen'})
        zustand = worker.transkript_schritt(api, auswahl, waehle=lambda modus: meetings)
        assert zustand['enabled'] is True and zustand['folder'] == str(meetings)
        assert worker.Auswahl(tmp_path / 'x.json').folder == meetings
        report = worker.synchronize(api, meetings, zustand, supported=worker.TRANSKRIPTE, with_mtime=True)
        assert report['last_run']['recorded'] == 1 and not report['last_run']['errors']
        (eintrag,) = client.get('/api/v1/transkripte').json()['eintraege']
        assert eintrag['status'] == 'zugeordnet' and eintrag['termin']['titel'] == 'Jour fixe Winter'


def test_abbruch_im_dialog_gibt_nichts_frei(tmp_path):
    with TestClient(create_app()) as client:
        client.post('/api/v1/transkripte/ordner', json={'modus': 'waehlen'})
        auswahl = worker.Auswahl(tmp_path / 'x.json')
        zustand = worker.transkript_schritt(TestApi(client), auswahl, waehle=lambda modus: None)
        assert zustand['pick_request'] is None and zustand['enabled'] is False and zustand['folder'] is None
        assert auswahl.folder is None


def test_nach_dem_trennen_vergisst_der_helfer_den_ordner(tmp_path):
    app = create_app()
    with TestClient(app) as client:
        meetings = tmp_path / 'Meetings'
        meetings.mkdir()
        api, auswahl = TestApi(client), worker.Auswahl(tmp_path / 'x.json')
        client.post('/api/v1/transkripte/ordner', json={'modus': 'waehlen'})
        worker.transkript_schritt(api, auswahl, waehle=lambda modus: meetings)
        assert auswahl.folder == meetings
        client.delete('/api/v1/transkripte/ordner')
        zustand = worker.transkript_schritt(api, auswahl)
        assert zustand['getrennt'] is True and zustand['folder'] is None
        assert auswahl.folder is None and not (tmp_path / 'x.json').exists()
        # Auch danach bleibt es getrennt, bis der Nutzer erneut wählt.
        assert worker.transkript_schritt(api, auswahl)['enabled'] is False


def test_getrennte_mitschriften_sind_entzogen_und_die_dateien_bleiben(tmp_path):
    app = create_app()
    with TestClient(app) as client:
        meetings = tmp_path / 'Meetings'
        datei = ablegen(meetings, 'notiz.txt')
        api, auswahl = TestApi(client), worker.Auswahl(tmp_path / 'x.json')
        client.post('/api/v1/transkripte/ordner', json={'modus': 'waehlen'})
        zustand = worker.transkript_schritt(api, auswahl, waehle=lambda modus: meetings)
        worker.synchronize(api, meetings, zustand, supported=worker.TRANSKRIPTE, with_mtime=True)
        (episode,) = app.state.episodes.tagged('transkript')
        client.delete('/api/v1/transkripte/ordner')
        assert app.state.episodes.get(episode.id).state is EpisodeState.IGNORED
        assert datei.exists()                                       # die Originaldatei bleibt unberührt
