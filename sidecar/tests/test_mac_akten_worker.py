"""Der Mac-Helfer für „Akten als Ordner“: Auswahl, Abholen, Ablegen. Der Auswahldialog (osascript) ist ersetzt."""
from __future__ import annotations

import importlib.util
import io
import os
import urllib.error
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from icarus_memory import atomic
from tests.test_akten_export_routes import BITTE, abwarten, bestand, dateien_im_archiv  # noqa: F401
from tests.test_akten_routes import api  # noqa: F401 - Fixture
from tests.test_context_identity import core  # noqa: F401 - Fixture

spec = importlib.util.spec_from_file_location("mac_folder_worker", Path(__file__).parents[2] / "scripts" / "mac_folder_worker.py")
worker = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(worker)

URL = '/api/v1/akten/export'
MARKE = worker.AKTEN_MARKE


def archiv(dateien: dict[str, str]) -> bytes:
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, 'w') as zf:
        for name, text in dateien.items():
            zf.writestr(name, text)
    return puffer.getvalue()


GUT = {MARKE: '{}\n', 'index.md': '# Akten\n', 'Personen/Anna Keller.md': 'Anna\n'}


class TestApi:
    """Spricht dieselben Routen wie der echte Helfer, aber ohne Netz."""
    __test__ = False

    def __init__(self, client, prefix=URL):
        self.client, self.prefix = client, prefix

    def call(self, path='', body=None):
        antwort = self.client.post(self.prefix + path, json=body) if body is not None else self.client.get(self.prefix + path)
        if antwort.status_code >= 400:
            raise urllib.error.HTTPError(self.prefix + path, antwort.status_code, 'Fehler', {}, None)
        return antwort.json()

    def bytes(self, path=''):
        antwort = self.client.get(self.prefix + path)
        if antwort.status_code >= 400:
            raise urllib.error.HTTPError(self.prefix + path, antwort.status_code, 'Fehler', {}, None)
        return antwort.content, dict(antwort.headers)


# -- Ablegen --

def test_ablegen_legt_einen_unterordner_an_und_laesst_alles_andere_im_ordner_in_ruhe(tmp_path):
    (tmp_path / 'Meine Notiz.md').write_text('eigene Gedanken', encoding='utf-8')
    (tmp_path / 'Tagebuch').mkdir()
    (tmp_path / 'Tagebuch' / 'heute.md').write_text('privat', encoding='utf-8')
    assert worker.akten_ablegen(tmp_path, archiv(GUT)) == 3
    ziel = tmp_path / 'Kingfisher Akten'
    assert (ziel / 'Personen' / 'Anna Keller.md').read_text(encoding='utf-8') == 'Anna\n' and (ziel / MARKE).is_file()
    assert (tmp_path / 'Meine Notiz.md').read_text(encoding='utf-8') == 'eigene Gedanken'
    assert (tmp_path / 'Tagebuch' / 'heute.md').read_text(encoding='utf-8') == 'privat'
    assert sorted(p.name for p in tmp_path.iterdir()) == ['Kingfisher Akten', 'Meine Notiz.md', 'Tagebuch']   # keine Reste


def test_ein_zweites_ablegen_ersetzt_den_eigenen_ordner_vollstaendig_und_verwirft_eigene_aenderungen(tmp_path):
    worker.akten_ablegen(tmp_path, archiv(GUT))
    ziel = tmp_path / 'Kingfisher Akten'
    (ziel / 'index.md').write_text('vom Nutzer geändert', encoding='utf-8')
    (ziel / 'Dazu.md').write_text('vom Nutzer angelegt', encoding='utf-8')
    worker.akten_ablegen(tmp_path, archiv({MARKE: '{}\n', 'index.md': 'neu\n'}))
    assert sorted(str(p.relative_to(ziel)) for p in ziel.rglob('*') if p.is_file()) == [MARKE, 'index.md']
    assert (ziel / 'index.md').read_text(encoding='utf-8') == 'neu\n'


def test_ein_fremder_ordner_gleichen_namens_wird_nie_ersetzt(tmp_path):
    fremd = tmp_path / 'Kingfisher Akten'
    fremd.mkdir()
    (fremd / 'wichtig.md').write_text('mein Vault', encoding='utf-8')
    with pytest.raises(ValueError, match='mit anderem Inhalt'):
        worker.akten_ablegen(tmp_path, archiv(GUT))
    assert (fremd / 'wichtig.md').read_text(encoding='utf-8') == 'mein Vault' and [p.name for p in fremd.iterdir()] == ['wichtig.md']
    assert sorted(p.name for p in tmp_path.iterdir()) == ['Kingfisher Akten']


def test_eine_datei_oder_ein_verweis_gleichen_namens_bleibt_unberuehrt(tmp_path):
    (tmp_path / 'Kingfisher Akten').write_text('ich bin eine Datei', encoding='utf-8')
    with pytest.raises(ValueError):
        worker.akten_ablegen(tmp_path, archiv(GUT))
    assert (tmp_path / 'Kingfisher Akten').read_text(encoding='utf-8') == 'ich bin eine Datei'
    ausserhalb = tmp_path / 'ausserhalb'
    ausserhalb.mkdir()
    ordner = tmp_path / 'Ziel'
    ordner.mkdir()
    (ordner / 'Kingfisher Akten').symlink_to(ausserhalb, target_is_directory=True)
    with pytest.raises(ValueError):
        worker.akten_ablegen(ordner, archiv(GUT))
    assert list(ausserhalb.iterdir()) == []                                # nichts durch den Verweis geschrieben


def test_ein_verweis_als_gewaehlter_ordner_wird_abgelehnt(tmp_path):
    echter = tmp_path / 'echt'
    echter.mkdir()
    verweis = tmp_path / 'verweis'
    verweis.symlink_to(echter, target_is_directory=True)
    with pytest.raises(ValueError, match='nicht erreichbar'):
        worker.akten_ablegen(verweis, archiv(GUT))
    with pytest.raises(ValueError, match='nicht erreichbar'):
        worker.akten_ablegen(tmp_path / 'gibtesnicht', archiv(GUT))
    assert list(echter.iterdir()) == []


@pytest.mark.parametrize('schlecht', ['../böse.md', '/etc/böse.md', 'a/../../böse.md', 'a\\b.md', 'a//b.md'])
def test_ein_archiv_mit_unsicheren_pfaden_schreibt_nichts(tmp_path, schlecht):
    with pytest.raises(ValueError, match='unsicheren Pfad'):
        worker.akten_ablegen(tmp_path, archiv({MARKE: '{}\n', schlecht: 'x'}))
    assert list(tmp_path.iterdir()) == []


def test_archive_ohne_marke_beschaedigte_und_zu_grosse_werden_abgelehnt(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match='unvollständig'):
        worker.akten_ablegen(tmp_path, archiv({'index.md': 'x'}))
    with pytest.raises(ValueError, match='beschädigt'):
        worker.akten_ablegen(tmp_path, b'kein zip')
    monkeypatch.setattr(worker, 'AKTEN_MAX_DATEI', 3)
    with pytest.raises(ValueError, match='zu groß'):
        worker.akten_ablegen(tmp_path, archiv(GUT))
    monkeypatch.setattr(worker, 'AKTEN_MAX_DATEI', 10_000)
    monkeypatch.setattr(worker, 'AKTEN_MAX_DATEIEN', 2)
    with pytest.raises(ValueError, match='zu groß'):
        worker.akten_ablegen(tmp_path, archiv(GUT))
    assert list(tmp_path.iterdir()) == []


def test_ein_fehler_mitten_im_ablegen_laesst_den_alten_ordner_und_keine_reste(tmp_path, monkeypatch):
    worker.akten_ablegen(tmp_path, archiv(GUT))
    echt = Path.write_bytes
    zaehler = {'n': 0}

    def bricht(self, daten):
        zaehler['n'] += 1
        if zaehler['n'] == 2:
            raise OSError('Platte voll')
        return echt(self, daten)

    monkeypatch.setattr(Path, 'write_bytes', bricht)
    with pytest.raises(OSError):
        worker.akten_ablegen(tmp_path, archiv({MARKE: '{}\n', 'index.md': 'neu', 'B.md': 'neu'}))
    monkeypatch.setattr(Path, 'write_bytes', echt)
    assert (tmp_path / 'Kingfisher Akten' / 'index.md').read_text(encoding='utf-8') == '# Akten\n'
    assert sorted(p.name for p in tmp_path.iterdir()) == ['Kingfisher Akten']


# -- Tausch: Helfer und Sidecar verhalten sich gleich --

@pytest.mark.parametrize('tauschen', [worker.akten_ordner_tauschen, atomic.ordner_tauschen], ids=['helfer', 'sidecar'])
def test_der_tausch_verhaelt_sich_in_helfer_und_sidecar_gleich(tmp_path, monkeypatch, tauschen):
    ziel = tmp_path / 'Akten'
    ziel.mkdir()
    (ziel / 'index.md').write_text('alt', encoding='utf-8')
    neu = tmp_path / 'neu'
    neu.mkdir()
    (neu / 'index.md').write_text('neu', encoding='utf-8')
    echt = os.replace

    def stoert(von, nach):
        if Path(von) == neu:
            raise OSError('gestört')
        return echt(von, nach)

    with monkeypatch.context() as kurz:
        kurz.setattr(os, 'replace', stoert)
        with pytest.raises(OSError):
            tauschen(neu, ziel)
    assert (ziel / 'index.md').read_text(encoding='utf-8') == 'alt'          # Abbruch beim Einsetzen: alt bleibt
    tauschen(neu, ziel)
    assert (ziel / 'index.md').read_text(encoding='utf-8') == 'neu' and [p.name for p in tmp_path.iterdir()] == ['Akten']
    # Zustand nach einem Absturz zwischen den Umbenennungen: Ziel fehlt, `.alt` liegt da.
    (tmp_path / '.Akten.alt').mkdir()
    (tmp_path / '.Akten.alt' / 'index.md').write_text('gerettet', encoding='utf-8')
    import shutil
    shutil.rmtree(ziel)
    nochmal = tmp_path / 'nochmal'
    nochmal.mkdir()
    (nochmal / 'index.md').write_text('nochmal', encoding='utf-8')
    tauschen(nochmal, ziel)
    assert (ziel / 'index.md').read_text(encoding='utf-8') == 'nochmal' and not (tmp_path / '.Akten.alt').exists()


# -- Zusammenspiel mit dem Server --

def helfer(client, tmp_path, *, ordner_name='Vault'):
    """Ein Helfer mit gemerkter Auswahl im Verzeichnis `tmp_path`."""
    wahl = tmp_path / ordner_name
    wahl.mkdir(exist_ok=True)
    return (TestApi(client), worker.Auswahl(tmp_path / 'privat.akten.json'),
            lambda modus: wahl if modus == 'waehlen' else worker.waehle_akten_ordner(modus, home=tmp_path), wahl)


def test_von_der_auswahl_bis_zu_den_dateien_auf_dem_mac(api, tmp_path):
    app, client = api
    bestand(app, client)
    schnittstelle, auswahl, waehle, wahl = helfer(client, tmp_path)
    client.post(URL + '/ordner', json={'modus': 'waehlen'})
    schritt = worker.akten_schritt(schnittstelle, auswahl, waehle)
    abwarten(app)
    assert schritt['ordner'] == str(wahl) and auswahl.folder == wahl and schritt['aktiv'] is True
    state = worker.akten_schritt(schnittstelle, auswahl, waehle)
    assert state['abholen'] and state['ordner'] == str(auswahl.folder)
    ergebnis = worker.akten_spiegeln(schnittstelle, auswahl.folder)
    assert ergebnis['angekommen'] is True and ergebnis['gespiegelt']['dateien'] >= 6 and ergebnis['fehler'] is None
    ziel = wahl / 'Kingfisher Akten'
    assert (ziel / 'index.md').is_file() and (ziel / 'Projekte' / 'Mainz.md').is_file() and (ziel / MARKE).is_file()
    assert BITTE in (ziel / 'Projekte' / 'Mainz.md').read_text(encoding='utf-8')
    assert worker.akten_schritt(schnittstelle, auswahl, waehle)['abholen'] is None


def test_die_vorgabe_legt_den_ordner_an(api, tmp_path):
    app, client = api
    schnittstelle, auswahl, waehle, _ = helfer(client, tmp_path)
    client.post(URL + '/ordner', json={'modus': 'vorgabe'})
    worker.akten_schritt(schnittstelle, auswahl, waehle)
    assert auswahl.folder == tmp_path / 'Documents' / 'Kingfisher' / 'Akten' and auswahl.folder.is_dir()


def test_abbruch_im_dialog_und_trennen_lassen_den_helfer_vergessen(api, tmp_path):
    app, client = api
    bestand(app, client)
    schnittstelle, auswahl, _, wahl = helfer(client, tmp_path)
    client.post(URL + '/ordner', json={'modus': 'waehlen'})
    stand = worker.akten_schritt(schnittstelle, auswahl, lambda modus: None)       # Nutzer bricht den Dialog ab
    assert stand['pick_request'] is None and stand['ordner'] is None and auswahl.folder is None
    client.post(URL + '/ordner', json={'modus': 'waehlen'})
    worker.akten_schritt(schnittstelle, auswahl, lambda modus: wahl)
    abwarten(app)
    assert auswahl.folder == wahl
    client.delete(URL + '/ordner')
    worker.akten_schritt(schnittstelle, auswahl, lambda modus: wahl)
    assert auswahl.folder is None and not (tmp_path / 'privat.akten.json').exists()


def test_ein_fremder_ordner_wird_dem_server_als_satz_gemeldet_und_nicht_wiederholt(api, tmp_path):
    app, client = api
    bestand(app, client)
    schnittstelle, auswahl, waehle, wahl = helfer(client, tmp_path)
    (wahl / 'Kingfisher Akten').mkdir()
    (wahl / 'Kingfisher Akten' / 'mein.md').write_text('meins', encoding='utf-8')
    client.post(URL + '/ordner', json={'modus': 'waehlen'})
    worker.akten_schritt(schnittstelle, auswahl, waehle)
    abwarten(app)
    worker.akten_schritt(schnittstelle, auswahl, waehle)
    ergebnis = worker.akten_spiegeln(schnittstelle, auswahl.folder)
    assert ergebnis['angekommen'] is False and 'mit anderem Inhalt' in ergebnis['fehler']
    assert (wahl / 'Kingfisher Akten' / 'mein.md').read_text(encoding='utf-8') == 'meins'
    assert worker.akten_schritt(schnittstelle, auswahl, waehle)['abholen'] is None


def test_der_helfer_schreibt_nur_in_den_ordner_den_der_server_kennt(api, tmp_path, monkeypatch):
    app, client = api
    bestand(app, client)
    schnittstelle, auswahl, waehle, wahl = helfer(client, tmp_path)
    client.post(URL + '/ordner', json={'modus': 'waehlen'})
    worker.akten_schritt(schnittstelle, auswahl, waehle)
    abwarten(app)
    auswahl.setzen(tmp_path / 'anderer')                                   # gemerkt ist ein anderer Ordner als der freigegebene
    (tmp_path / 'anderer').mkdir()
    aufgerufen = []
    monkeypatch.setattr(worker, 'akten_spiegeln', lambda *a: aufgerufen.append(a))
    monkeypatch.setattr(worker.time, 'sleep', lambda s: (_ for _ in ()).throw(KeyboardInterrupt))
    monkeypatch.setattr(worker.fcntl, 'flock', lambda *a: None)
    args = SimpleNamespace(env_file=tmp_path / 'privat.env', url='http://127.0.0.1:8891')
    monkeypatch.setattr(worker, 'Api', lambda *a, **k: schnittstelle)
    with pytest.raises(KeyboardInterrupt):
        worker.main_akten(args, 'token')
    assert aufgerufen == [] and not (tmp_path / 'anderer' / 'Kingfisher Akten').exists()


def test_der_start_der_mac_app_startet_den_akten_helfer_ohne_pfad():
    spec = importlib.util.spec_from_file_location("start_mac_app", Path(__file__).parents[2] / "scripts" / "start_mac_app.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    assert modul.akten_jobs() == [("mac_folder_worker.py", ["--role", "akten"])]
