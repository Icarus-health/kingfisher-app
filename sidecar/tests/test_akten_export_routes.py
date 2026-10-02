"""Akten als Ordner, Routen: Einstellung, Wahl des Ordners über den Helfer, Schreiben, Drossel, Archiv, Übergabe."""
from __future__ import annotations

import io
import os
import threading
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from icarus_memory import akten_export_routes as export
from icarus_memory import akten_markdown, akten_routes, config
from icarus_memory.model import Provenance, SourceType
from tests.test_akten_routes import BITTE, abgleichen, api  # noqa: F401 - Fixture
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_mappe import _projekt, _quelle

URL = '/api/v1/akten/export'
MAC_ORDNER = '/Users/test/Documents/Kingfisher/Akten'


def abwarten(app):
    faden = app.state.akten_export_fluechtig['faden']
    if faden is not None:
        faden.join(15)
        assert not faden.is_alive()


def waehlen(client, app, ordner=MAC_ORDNER, modus='waehlen'):
    """Der Weg des Nutzers: Knopf „Ordner wählen“, der Mac-Helfer zeigt den Dialog und meldet den Ordner."""
    antwort = client.post(URL + '/ordner', json={'modus': modus}).json()
    assert antwort['pick_request']['modus'] == modus
    stand = client.post(URL + '/worker', json={'folder': ordner, 'picked': antwort['pick_request']['id']}).json()
    abwarten(app)
    return stand


def bestand(app, client):
    projekt = _projekt(app, 'Mainz')
    _quelle(app, 'Druckdaten', [(BITTE, 'request')], project=projekt.id, tage=3)
    abgleichen(client)
    return projekt


def dateien_im_archiv(client):
    antwort = client.get(URL + '/archiv')
    assert antwort.status_code == 200 and antwort.headers['content-type'] == 'application/zip'
    with zipfile.ZipFile(io.BytesIO(antwort.content)) as zf:
        return {n: zf.read(n).decode('utf-8') for n in zf.namelist()}, antwort.headers['X-Akten-Paket']


def test_vorgabe_ist_aus_und_ohne_ordner_schreibt_nichts(api):
    app, client = api
    bestand(app, client)
    stand = client.get(URL).json()
    assert (stand['aktiv'], stand['quellen'], stand['ordner'], stand['stand'], stand['angekommen']) == (False, False, None, None, False)
    assert stand['vorgabe'] == 'Dokumente/Kingfisher/Akten' and stand['ordnername'] == 'Kingfisher Akten'
    assert client.post(URL).status_code == 409
    assert client.put(URL, json={'aktiv': True}).status_code == 409
    assert client.get(URL + '/archiv').status_code == 404
    akten_routes.nachfuehren(app)
    assert not (app.state.akten_export_fluechtig['faden'])             # aus: nie ein Lauf


def test_zugang_nur_mit_token(api):
    _, client = api
    for methode, pfad in (('get', ''), ('post', ''), ('get', '/archiv'), ('post', '/worker'), ('put', '')):
        antwort = getattr(client, methode)(URL + pfad, headers={'X-Icarus-Token': 'falsch'}, **({'json': {}} if methode != 'get' else {}))
        assert antwort.status_code in (401, 403), (methode, pfad)


def test_ordner_waehlen_ueber_den_helfer_schaltet_ein_und_schreibt(api):
    app, client = api
    bestand(app, client)
    stand = waehlen(client, app)
    assert stand['ordner'] == MAC_ORDNER and stand['aktiv'] is True and stand['pick_request'] is None
    jetzt = client.get(URL).json()
    assert jetzt['stand']['dateien'] >= 6 and jetzt['stand']['akten'] >= 3 and jetzt['stand']['mit_quellen'] is False
    assert stand['abholen'] is None                                        # die erste Antwort kam vor dem Ende des Laufs
    folge = client.post(URL + '/worker', json={}).json()
    assert folge['abholen'] == client.get(URL + '/archiv').headers['X-Akten-Paket']
    dateien, paket = dateien_im_archiv(client)
    assert {'index.md', '_README.md', akten_markdown.MARKE, 'Projekte/Mainz.md'} <= set(dateien)
    assert not any(n.startswith('Quellen/') for n in dateien)
    # Der Helfer legt ab und meldet es: danach ist nichts mehr zu holen, und die Oberfläche sieht den Stand.
    antwort = client.post(URL + '/gespiegelt', json={'paket': paket, 'dateien': len(dateien)}).json()
    assert antwort['angekommen'] is True and antwort['gespiegelt']['dateien'] == len(dateien)
    assert client.post(URL + '/worker', json={}).json()['abholen'] is None


def test_eine_fremde_oder_abgelaufene_wahl_wird_nicht_uebernommen(api):
    app, client = api
    bestand(app, client)
    antwort = client.post(URL + '/ordner', json={'modus': 'vorgabe'}).json()
    falsch = client.post(URL + '/worker', json={'folder': MAC_ORDNER, 'picked': 'nicht-die-anfrage'}).json()
    assert falsch['ordner'] is None and falsch['pick_request'] is not None
    ohne_wahl = client.post(URL + '/worker', json={'folder': MAC_ORDNER}).json()
    assert ohne_wahl['ordner'] is None
    relativ = client.post(URL + '/worker', json={'folder': 'Documents/x', 'picked': antwort['pick_request']['id']}).json()
    assert relativ['ordner'] is None
    app.state.akten_export_fluechtig['pick_request']['at'] = (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()
    abgelaufen = client.post(URL + '/worker', json={'folder': MAC_ORDNER, 'picked': antwort['pick_request']['id']}).json()
    assert abgelaufen['ordner'] is None and abgelaufen['pick_request'] is None
    assert client.post(URL + '/ordner', json={'modus': 'getippt'}).status_code == 422


def test_wahl_abbrechen_und_abbruch_im_dialog(api):
    app, client = api
    antwort = client.post(URL + '/ordner', json={'modus': 'waehlen'}).json()
    assert client.delete(URL + '/ordner/auswahl').json()['pick_request'] is None
    antwort = client.post(URL + '/ordner', json={'modus': 'waehlen'}).json()
    assert client.post(URL + '/worker', json={'cancelled': antwort['pick_request']['id']}).json()['pick_request'] is None


def test_quellen_mitschreiben_ist_ein_schalter_der_den_ordner_neu_schreibt(api):
    app, client = api
    bestand(app, client)
    waehlen(client, app)
    aus, _ = dateien_im_archiv(client)
    assert not any(n.startswith('Quellen/') for n in aus)
    client.put(URL, json={'quellen': True})
    abwarten(app)
    an, paket_an = dateien_im_archiv(client)
    assert any(n.startswith('Quellen/') for n in an) and client.get(URL).json()['stand']['mit_quellen'] is True
    assert BITTE in ''.join(v for n, v in an.items() if n.startswith('Quellen/'))
    client.put(URL, json={'quellen': False})
    abwarten(app)
    wieder_aus, paket_aus = dateien_im_archiv(client)
    assert not any(n.startswith('Quellen/') for n in wieder_aus) and paket_aus != paket_an
    assert BITTE not in ''.join(v for n, v in wieder_aus.items() if n.startswith('Quellen/'))


def test_jetzt_schreiben_bietet_den_ordner_erneut_an_und_meldet_das_ergebnis(api):
    app, client = api
    bestand(app, client)
    waehlen(client, app)
    _, paket = dateien_im_archiv(client)
    client.post(URL + '/gespiegelt', json={'paket': paket, 'dateien': 9})
    assert client.get(URL).json()['angekommen'] is True
    antwort = client.post(URL).json()                                      # gleicher Inhalt, der Knopf holt ihn trotzdem neu
    assert antwort['laeuft'] is False and antwort['stand']['dateien'] >= 6 and antwort['angekommen'] is False
    assert client.post(URL + '/worker', json={}).json()['abholen'] == paket


def test_veraltete_meldung_des_helfers_zaehlt_nicht_und_ein_fehler_wird_gezeigt_ohne_endlosschleife(api):
    app, client = api
    bestand(app, client)
    waehlen(client, app)
    _, paket = dateien_im_archiv(client)
    assert client.post(URL + '/gespiegelt', json={'paket': 'altes-paket', 'dateien': 3}).json()['angekommen'] is False
    assert app.state.settings.akten_export.get('gespiegelt') is None       # nicht einmal vorgemerkt
    antwort = client.post(URL + '/gespiegelt', json={'paket': paket, 'dateien': 0,
                                                     'fehler': 'Im Ordner liegt schon etwas anderes.'}).json()
    assert antwort['angekommen'] is False and antwort['fehler'] == 'Im Ordner liegt schon etwas anderes.'
    assert client.post(URL + '/worker', json={}).json()['abholen'] is None        # kein Dauerfeuer bei gleichem Paket
    client.post(URL)                                                        # „Jetzt schreiben“ versucht es wieder
    assert client.post(URL + '/worker', json={}).json()['abholen'] == paket
    assert client.get(URL).json()['fehler'] is None


def test_trennen_loescht_nichts_beim_nutzer_und_raeumt_den_sidecar_auf(api, tmp_path):
    app, client = api
    bestand(app, client)
    waehlen(client, app)
    staging = export.staging(lambda: tmp_path / 'source-answer-api')
    assert staging.is_dir()
    client.put(URL, json={'quellen': True})
    abwarten(app)
    stand = client.delete(URL + '/ordner').json()
    assert stand['ordner'] is None and stand['aktiv'] is False and stand['stand'] is None
    assert stand['quellen'] is True                                        # die Wahl „Quellen“ bleibt, der Ordner ist weg
    assert not staging.exists() and client.get(URL + '/archiv').status_code == 404
    assert client.put(URL, json={'aktiv': True}).status_code == 409        # ohne Ordner nicht wieder einschaltbar


def test_schalter_aus_haelt_die_automatik_an_ohne_den_ordner_zu_vergessen(api, monkeypatch):
    app, client = api
    bestand(app, client)
    waehlen(client, app)
    monkeypatch.setattr(export, 'DROSSEL_S', 0.0)                          # die Drossel soll hier nicht der Grund sein
    antwort = client.put(URL, json={'aktiv': False}).json()
    assert antwort['aktiv'] is False and antwort['ordner'] == MAC_ORDNER
    paket = client.get(URL + '/archiv').headers['X-Akten-Paket']
    _quelle(app, 'Nachtrag', [('Bitte um Rückruf zur Sache.', 'request')], tage=1)
    akten_routes.nachfuehren(app, warten=True)
    abwarten(app)
    assert client.get(URL + '/archiv').headers['X-Akten-Paket'] == paket   # aus: kein selbsttätiges Schreiben
    # Gegenprobe: Mit eingeschaltetem Schalter führt genau dieser Ablauf zu einem neuen Stand.
    client.put(URL, json={'aktiv': True})
    abwarten(app)
    assert client.get(URL + '/archiv').headers['X-Akten-Paket'] != paket


def test_nach_dem_nachfuehren_wird_geschrieben_aber_nur_wenn_sich_etwas_aendert(api, monkeypatch):
    app, client = api
    bestand(app, client)
    waehlen(client, app)
    laeufe = []
    echt = export.lauf
    monkeypatch.setattr(export, 'lauf', lambda *a, **k: laeufe.append(1) or echt(*a, **k))
    monkeypatch.setattr(export, 'DROSSEL_S', 0.0)
    akten_routes.nachfuehren(app, warten=True)
    abwarten(app)
    assert not laeufe                                                       # nichts geändert, nichts geschrieben
    _quelle(app, 'Nachtrag', [('Bitte um Rückruf zur Sache.', 'request')], tage=1)
    akten_routes.nachfuehren(app, warten=True)
    abwarten(app)
    assert len(laeufe) == 1
    _, paket = dateien_im_archiv(client)
    assert client.get(URL).json()['stand']['dateien'] >= 6 and 'Rückruf' in ''.join(dateien_im_archiv(client)[0].values())
    akten_routes.nachfuehren(app, warten=True)
    abwarten(app)
    assert len(laeufe) == 1


def test_die_drossel_haelt_zurueck_und_holt_einmal_nach(api, monkeypatch):
    app, client = api
    bestand(app, client)
    waehlen(client, app)
    zeitgeber = []

    class Zeitgeber:
        def __init__(self, rest, aufruf):
            self.rest, self.aufruf, self.daemon = rest, aufruf, False
            zeitgeber.append(self)

        def start(self):
            pass

    monkeypatch.setattr(export.threading, 'Timer', Zeitgeber)
    laeufe = []
    echt = export.lauf
    monkeypatch.setattr(export, 'lauf', lambda *a, **k: laeufe.append(1) or echt(*a, **k))
    _quelle(app, 'Nachtrag', [('Bitte um Rückruf zur Sache.', 'request')], tage=1)
    for _ in range(3):
        akten_routes.nachfuehren(app, warten=True)
    abwarten(app)
    assert not laeufe                                                       # innerhalb der Drossel: nichts
    assert len(zeitgeber) == 1 and 0 < zeitgeber[0].rest <= export.DROSSEL_S + 1   # genau ein Nachholen vorgemerkt
    app.state.akten_export_fluechtig['letzter_start'] = time.monotonic() - export.DROSSEL_S - 1
    zeitgeber[0].aufruf()
    abwarten(app)
    assert len(laeufe) == 1


def test_nie_zwei_laeufe_gleichzeitig(api, monkeypatch):
    app, client = api
    bestand(app, client)
    waehlen(client, app)
    tritt_ein, weiter = threading.Event(), threading.Event()
    echt = akten_markdown.sammeln
    zaehler = []

    def langsam(*args, **kwargs):
        zaehler.append(1)
        tritt_ein.set()
        assert weiter.wait(10)
        return echt(*args, **kwargs)

    monkeypatch.setattr(akten_markdown, 'sammeln', langsam)
    daten = Path(os.environ['ICARUS_DATA_DIR'])
    erster = export.starten(app, lambda: daten)
    assert tritt_ein.wait(10)
    zweiter = export.starten(app, lambda: daten)
    assert zweiter is erster and export.lauf(app, lambda: daten) is False   # ein laufender Lauf lässt keinen zweiten zu
    assert client.get(URL).json()['laeuft'] is True
    weiter.set()
    erster.join(15)
    assert len(zaehler) == 1 and client.get(URL).json()['laeuft'] is False


def test_ein_fehler_beim_schreiben_wird_gemeldet_ohne_akteninhalt_und_der_alte_stand_bleibt(api, monkeypatch):
    app, client = api
    bestand(app, client)
    waehlen(client, app)
    vorher, paket = dateien_im_archiv(client)

    def kaputt(*args, **kwargs):
        raise OSError('/pfad/mit/Anna Keller und dem Vertrag')

    _quelle(app, 'Nachtrag', [('Bitte um Rückruf zur Sache.', 'request')], tage=1)
    with monkeypatch.context() as kurz:
        kurz.setattr(akten_markdown, 'schreiben', kaputt)
        antwort = client.post(URL).json()
    assert antwort['fehler'] and 'Anna' not in antwort['fehler'] and 'Vertrag' not in antwort['fehler']
    nachher, paket_nachher = dateien_im_archiv(client)
    assert nachher == vorher and paket_nachher == paket
    assert client.post(URL).json()['fehler'] is None


def test_einstellung_ueberlebt_den_neustart(api, tmp_path):
    app, client = api
    bestand(app, client)
    waehlen(client, app)
    client.put(URL, json={'quellen': True})
    abwarten(app)
    geladen = config.load(tmp_path / 'source-answer-api').akten_export
    assert geladen['ordner'] == MAC_ORDNER and geladen['aktiv'] is True and geladen['quellen'] is True
    assert geladen['stand']['dateien'] >= 6
    assert config.Settings.from_dict({'akten_export': 'kaputt'}).akten_export == {}


def test_kein_weg_fuehrt_aus_dem_ordner_in_den_bestand(api):
    """Die Schnittstelle kennt keine Route, die Dateien oder Text aus dem Ordner annimmt."""
    app, _ = api
    pfade = {(m, r.path) for r in app.routes if getattr(r, 'path', '').startswith('/api/v1/akten/export')
             for m in getattr(r, 'methods', ())}
    angenommen = {p for p in pfade if p[0] in ('POST', 'PUT')}
    assert {p[1] for p in angenommen} == {URL, URL + '/ordner', URL + '/worker', URL + '/gespiegelt'}
    from icarus_memory.akten_export_routes import GespiegeltIn, WorkerIn
    felder = set(GespiegeltIn.model_fields) | set(WorkerIn.model_fields)
    assert not {'body', 'text', 'content', 'datei', 'dateien_inhalt'} & felder
