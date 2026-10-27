"""Sicherung in der Oberfläche wiederherstellen (Persona-Prüfung, Paket P, D7). Nur synthetische Daten."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from icarus_memory import sicherung_zurueck
from icarus_memory.backup import BACKUP_DATA_FILES
from icarus_memory.model import Provenance, SourceType

from .test_conversation_retraction import StubAgent, _close_app


class Agent(StubAgent):
    def reset(self) -> None:
        pass


def _make_app(tmp_path, monkeypatch):
    from icarus_memory import MemoryBackend, SelfModelStore
    from icarus_memory.server import create_app
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('ICARUS_SIDECAR_TOKEN', raising=False)
    return create_app(SelfModelStore(MemoryBackend(), subject_id='test'), agent=Agent())


def _summen(ordner: Path) -> dict[str, str]:
    return {n: hashlib.sha256((ordner / n).read_bytes()).hexdigest()
            for n in sicherung_zurueck.WIEDERHERGESTELLT if (ordner / n).exists()}


def _titel(app) -> set[str]:
    return {t.title for t in app.state.tasks.open_tasks(limit=None)}


@pytest.fixture
def stand(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = TestClient(app)
    app.state.tasks.add('Vor der Sicherung', Provenance(SourceType.USER_STATED))
    (tmp_path / 'einstellungen.json').write_text('{"stand": "heute"}', encoding='utf-8')
    alt = client.post('/backups').json()['name']
    app.state.tasks.add('Nach der Sicherung', Provenance(SourceType.USER_STATED))
    (tmp_path / 'einstellungen.json').write_text('{"stand": "neuer"}', encoding='utf-8')
    yield app, client, alt, tmp_path
    _close_app(app)


def test_jede_datei_ist_entweder_gedaechtnis_oder_bleibt():
    assert set(sicherung_zurueck.WIEDERHERGESTELLT) | set(sicherung_zurueck.BLEIBT) == set(BACKUP_DATA_FILES)
    assert not set(sicherung_zurueck.WIEDERHERGESTELLT) & set(sicherung_zurueck.BLEIBT)
    # Befugnisse und Protokolle kommen nie aus einer alten Sicherung zurück.
    for name in ('einstellungen.json', 'schluessel.icarus', 'regeln.sqlite3', 'audit.sqlite3'):
        assert name in sicherung_zurueck.BLEIBT


def test_liste_zeigt_sicherungen_ohne_pfad(stand):
    app, client, alt, _ = stand
    antwort = client.get('/api/v1/sicherungen').json()
    assert [s['name'] for s in antwort['sicherungen']] == [alt]
    assert antwort['sicherungen'][0]['erstellt'] and antwort['sicherungen'][0]['art'] == 'regelmaessig'
    assert 'path' not in json.dumps(antwort) and str(stand[3]) not in json.dumps(antwort)
    assert antwort['zuletzt'] is None


def test_wiederherstellen_gilt_sofort_und_bleibt_bedienbar(stand):
    app, client, alt, ordner = stand
    assert _titel(app) == {'Vor der Sicherung', 'Nach der Sicherung'}
    antwort = client.post('/api/v1/sicherungen/wiederherstellen', json={'name': alt})
    assert antwort.status_code == 200, antwort.text
    ergebnis = antwort.json()
    assert ergebnis['name'] == alt and ergebnis['stand'] and ergebnis['rueckgaengig'].startswith('vor-wiederherstellung-')
    # Der Stand der Sicherung gilt, ohne Neustart und ohne Prüfmodus.
    assert _titel(app) == {'Vor der Sicherung'}
    assert not (ordner / 'restore-state.json').exists()
    assert client.get('/api/v1/sicherungen').status_code == 200
    app.state.tasks.add('Danach weiter', Provenance(SourceType.USER_STATED))
    # Einstellungen (Befugnisse) bleiben auf dem heutigen Stand.
    assert json.loads((ordner / 'einstellungen.json').read_text())['stand'] == 'neuer'
    # Nichts Halbes liegt herum.
    assert not (ordner / sicherung_zurueck.JOURNAL).exists()
    assert not list(ordner.glob('.*vor-wiederherstellung*')) and not list(ordner.glob('.wiederherstellung-*'))
    assert client.get('/api/v1/sicherungen').json()['zuletzt']['name'] == alt


def test_rueckgaengig_bringt_den_stand_von_vorher(stand):
    app, client, alt, _ = stand
    zurueck = client.post('/api/v1/sicherungen/wiederherstellen', json={'name': alt}).json()['rueckgaengig']
    assert _titel(app) == {'Vor der Sicherung'}
    antwort = client.post('/api/v1/sicherungen/wiederherstellen', json={'name': zurueck})
    assert antwort.status_code == 200, antwort.text
    assert _titel(app) == {'Vor der Sicherung', 'Nach der Sicherung'}
    namen = [s['name'] for s in client.get('/api/v1/sicherungen').json()['sicherungen']]
    assert zurueck in namen and alt in namen


@pytest.mark.parametrize('name', ['../einstellungen.json', '/etc/passwd', 'kingfisher-20261027T120000Z/../../x',
                                  'kingfisher-../../etc', 'beliebig', 'kingfisher-20261027T120000Z\x00',
                                  '..', 'sicherungen/kingfisher-20261027T120000Z'])
def test_kein_pfad_von_aussen(stand, name):
    app, client, alt, ordner = stand
    vorher = _summen(ordner)
    antwort = client.post('/api/v1/sicherungen/wiederherstellen', json={'name': name})
    assert antwort.status_code in (404, 422)
    assert _summen(ordner) == vorher
    assert _titel(app) == {'Vor der Sicherung', 'Nach der Sicherung'}


def test_verweis_nach_aussen_wird_nicht_angenommen(stand, tmp_path_factory):
    app, client, alt, ordner = stand
    fremd = tmp_path_factory.mktemp('fremd') / 'kingfisher-20200101T000000Z'
    import shutil
    shutil.copytree(ordner / 'sicherungen' / alt, fremd)
    os.symlink(fremd, ordner / 'sicherungen' / 'kingfisher-20200101T000000Z')
    assert 'kingfisher-20200101T000000Z' not in [s['name'] for s in client.get('/api/v1/sicherungen').json()['sicherungen']]
    antwort = client.post('/api/v1/sicherungen/wiederherstellen', json={'name': 'kingfisher-20200101T000000Z'})
    assert antwort.status_code == 404
    # Eine Datei darin, die nach außen zeigt, ebenso nicht.
    innen = ordner / 'sicherungen' / alt
    (innen / 'tasks.sqlite3').unlink()
    os.symlink(fremd / 'tasks.sqlite3', innen / 'tasks.sqlite3')
    assert client.post('/api/v1/sicherungen/wiederherstellen', json={'name': alt}).status_code == 409
    assert _titel(app) == {'Vor der Sicherung', 'Nach der Sicherung'}


def test_veraenderte_sicherung_wird_abgewiesen(stand):
    app, client, alt, ordner = stand
    with open(ordner / 'sicherungen' / alt / 'tasks.sqlite3', 'ab') as datei:
        datei.write(b'verfaelscht')
    vorher = _summen(ordner)
    antwort = client.post('/api/v1/sicherungen/wiederherstellen', json={'name': alt})
    assert antwort.status_code == 409 and 'nichts verändert' in antwort.json()['detail']
    # (Das Neuöffnen legt in der Testanwendung eine leere Selbstmodell-Datei an; die zählt nicht als Bestand.)
    assert {k: v for k, v in _summen(ordner).items() if k in vorher} == vorher


def test_abbruch_mittendrin_laesst_den_alten_stand(stand, monkeypatch):
    app, client, alt, ordner = stand
    _close_app(app)
    vorher = _summen(ordner)
    echt = os.replace
    zaehler = {'n': 0}

    def bricht(quelle, ziel):
        zaehler['n'] += 1
        if zaehler['n'] == 5:
            raise OSError('Platte voll (Probe)')
        return echt(quelle, ziel)
    monkeypatch.setattr(sicherung_zurueck.os, 'replace', bricht)
    with pytest.raises(OSError):
        sicherung_zurueck.einspielen(ordner / 'sicherungen' / alt, ordner)
    monkeypatch.setattr(sicherung_zurueck.os, 'replace', echt)
    assert _summen(ordner) == vorher
    assert not (ordner / sicherung_zurueck.JOURNAL).exists()
    assert not list(ordner.glob('.*vor-wiederherstellung*'))


def test_absturz_mittendrin_wird_beim_start_zurueckgenommen(stand, monkeypatch):
    """Strom weg nach dem dritten Umhängen: Beim nächsten Start gilt der alte Stand."""
    app, client, alt, ordner = stand
    _close_app(app)
    vorher = _summen(ordner)
    echt = os.replace
    zaehler = {'n': 0}

    class Strom(BaseException):
        pass

    def bricht(quelle, ziel):
        zaehler['n'] += 1
        if zaehler['n'] == 4:
            raise Strom()
        return echt(quelle, ziel)
    monkeypatch.setattr(sicherung_zurueck.os, 'replace', bricht)
    monkeypatch.setattr(sicherung_zurueck, 'nach_abbruch_aufraeumen', lambda d: False)
    with pytest.raises(Strom):
        sicherung_zurueck.einspielen(ordner / 'sicherungen' / alt, ordner)
    monkeypatch.undo()
    assert (ordner / sicherung_zurueck.JOURNAL).exists()
    assert _summen(ordner) != vorher
    monkeypatch.setenv('ICARUS_DATA_DIR', str(ordner))
    from icarus_memory.server import create_app
    from icarus_memory import MemoryBackend, SelfModelStore
    neu = create_app(SelfModelStore(MemoryBackend(), subject_id='test'), agent=Agent())
    try:
        assert not (ordner / sicherung_zurueck.JOURNAL).exists()
        assert _summen(ordner) == vorher
        assert _titel(neu) == {'Vor der Sicherung', 'Nach der Sicherung'}
    finally:
        _close_app(neu)


def test_alte_route_bleibt_im_pruefmodus(stand):
    """Der Rückweg nach einem Update (`/backups/restore`) bleibt, wie er war: Prüfmodus."""
    app, client, alt, ordner = stand
    assert client.post('/backups/restore', json={'name': alt}).json()['mode'] == 'inspection'
