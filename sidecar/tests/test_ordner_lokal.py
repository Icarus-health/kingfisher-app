"""Ordner ohne Mac-Helfer (Fremdprobe, Befund 6): im Browser wählen, vom Sidecar selbst lesen.

Zusicherung: Gelesen wird nur ein Ordner, den der Mensch eben gewählt hat; ein angezeigter Ort ist keine Freigabe.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from icarus_memory import folder_sync, ordner_lokal
from icarus_memory.server import create_app

MEETING = 'Anna Berg: Guten Tag.\nBert Kraus: Hallo.\nAnna Berg: Das Budget steht.\nBert Kraus: Gut.\n'
T = '/api/v1/transcript-sync'
D = '/api/v1/folder-sync'


def alt(pfad: Path) -> Path:
    """Eine Datei, die nicht mehr geschrieben wird (älter als zwei Sekunden)."""
    vorher = time.time() - 60
    os.utime(pfad, (vorher, vorher))
    return pfad


@pytest.fixture
def zuhause(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    home.mkdir()
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path / 'daten'))
    monkeypatch.delenv('ICARUS_SIDECAR_TOKEN', raising=False)
    monkeypatch.delenv('KINGFISHER_ORDNER', raising=False)
    monkeypatch.setattr(ordner_lokal, 'im_container', lambda: False)
    monkeypatch.setattr(folder_sync, 'TAKT_S', 3600)  # der Takt läuft in Tests nicht von selbst
    return home


@pytest.fixture
def client(zuhause):
    app = create_app()
    with TestClient(app) as http:
        yield app, http


# -- Orte und Prüfung -----------------------------------------------------------------------------------------------

def test_bekannte_orte_ohne_container_und_mit_eingebundenem_ordner(tmp_path, zuhause):
    eingebunden = tmp_path / 'ordner'
    (eingebunden / 'Mitschriften').mkdir(parents=True)
    (eingebunden / 'Mitschriften' / 'a.txt').write_text(MEETING)
    (eingebunden / '.versteckt').mkdir()
    (eingebunden / 'verweis').symlink_to(tmp_path)
    orte = ordner_lokal.bekannte_orte('Transkripte', {'.txt'}, home=zuhause,
                                      umgebung={'KINGFISHER_ORDNER': str(eingebunden)}, container=False)
    assert orte[0] == {'pfad': str(zuhause / 'Documents/Kingfisher/Transkripte'), 'name': '~/Documents/Kingfisher/Transkripte',
                       'da': False, 'vorgabe': True, 'dateien': 0}
    assert [o['pfad'] for o in orte[1:]] == [str(eingebunden), str(eingebunden / 'Mitschriften')]
    assert orte[2]['dateien'] == 1
    # Im Container ist das Benutzerverzeichnis nicht das des Menschen: kein Vorgabeordner, nur Eingebundenes.
    im_container = ordner_lokal.bekannte_orte('Transkripte', {'.txt'}, home=zuhause,
                                              umgebung={'KINGFISHER_ORDNER': str(eingebunden)}, container=True)
    assert not any(o['vorgabe'] for o in im_container)


def test_ein_getippter_pfad_wird_geprueft_und_die_antwort_ist_ein_satz(tmp_path):
    datei = tmp_path / 'notiz.txt'
    datei.write_text('x')
    (tmp_path / 'verweis').symlink_to(tmp_path)
    for eingabe, satz in ((str(tmp_path / 'fehlt'), 'gibt es hier nicht'), (str(datei), 'eine Datei, kein Ordner'),
                          (str(tmp_path / 'verweis'), 'nur ein Verweis'), ('Dokumente/Mitschriften', 'ganzen Pfad'),
                          ('', 'Bitte gib den Ordner an')):
        with pytest.raises(ordner_lokal.OrdnerFehler) as fehler:
            ordner_lokal.pruefe_ordner(eingabe)
        assert satz in fehler.value.satz, eingabe
        assert '\n' not in fehler.value.satz
    assert ordner_lokal.pruefe_ordner(str(tmp_path)) == tmp_path.resolve()


# -- Freigabe über die Routen ---------------------------------------------------------------------------------------

def test_ein_angezeigter_ort_ist_keine_freigabe(client, tmp_path, monkeypatch):
    app, http = client
    eingebunden = tmp_path / 'ordner'
    eingebunden.mkdir()
    (eingebunden / 'Jour fixe.txt').write_text(MEETING)
    alt(eingebunden / 'Jour fixe.txt')
    monkeypatch.setenv('KINGFISHER_ORDNER', str(eingebunden))
    orte = http.get(f'{T}/orte').json()
    assert orte['helfer'] is False and str(eingebunden) in [o['pfad'] for o in orte['orte']]
    zustand = http.get(T).json()
    assert zustand['enabled'] is False and zustand['folder'] is None and zustand['lokal'] is False
    assert app.state.episodes.tagged('transkript') == []


def test_gewaehlter_ordner_wird_sofort_gelesen_mit_einem_satz(client, tmp_path):
    app, http = client
    ordner = tmp_path / 'mitschriften'
    ordner.mkdir()
    (ordner / '2026-09-28 Jour fixe.txt').write_text(MEETING)
    alt(ordner / '2026-09-28 Jour fixe.txt')
    (ordner / 'bild.png').write_bytes(b'\x89PNG')
    antwort = http.post(f'{T}/lokal', json={'pfad': str(ordner)})
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    assert daten['satz'] == f'Freigegeben: {ordner}. 1 Datei gelesen; neue kommen etwa einmal pro Minute dazu.'
    assert daten['enabled'] is True and daten['lokal'] is True and daten['running'] is True
    assert http.get('/api/v1/transkripte').json()['stand']['aufgenommen'] == 1
    # Eine neue Datei kommt mit dem nächsten Lauf (der Takt ruft dasselbe auf).
    (ordner / 'zweites.txt').write_text(MEETING.replace('Budget', 'Plakat'))
    alt(ordner / 'zweites.txt')
    http.post(f'{T}/run')
    assert http.get('/api/v1/transkripte').json()['stand']['aufgenommen'] == 2


def test_ein_falscher_pfad_gibt_nichts_frei(client, tmp_path):
    app, http = client
    antwort = http.post(f'{T}/lokal', json={'pfad': str(tmp_path / 'gibt-es-nicht')})
    assert antwort.status_code == 422 and 'gibt es hier nicht' in antwort.json()['detail']
    zustand = http.get(T).json()
    assert zustand['enabled'] is False and zustand['folder'] is None


def test_vorgabeordner_ohne_fenster(client, zuhause, monkeypatch):
    _, http = client
    antwort = http.post(f'{T}/lokal', json={'vorgabe': True}).json()
    ziel = zuhause / 'Documents' / 'Kingfisher' / 'Transkripte'
    assert ziel.is_dir() and antwort['folder'] == str(ziel.resolve()) and antwort['enabled'] is True
    assert antwort['satz'].startswith('Freigegeben: ~/Documents/Kingfisher/Transkripte. Noch keine passenden Dateien')
    # Im Container gibt es den Ordner des Menschen nicht: kein Anlegen, ein Satz mit Grund.
    monkeypatch.setattr(ordner_lokal, 'im_container', lambda: True)
    abgelehnt = http.post(f'{T}/lokal', json={'vorgabe': True})
    assert abgelehnt.status_code == 422 and 'Container' in abgelehnt.json()['detail']


def test_wechsel_entzieht_den_alten_ordner_und_ein_helfer_aendert_ihn_nicht(client, tmp_path):
    app, http = client
    erster, zweiter = tmp_path / 'a', tmp_path / 'b'
    for ordner in (erster, zweiter):
        ordner.mkdir()
        (ordner / f'{ordner.name}.txt').write_text(MEETING + ordner.name)
        alt(ordner / f'{ordner.name}.txt')
    http.post(f'{T}/lokal', json={'pfad': str(erster)})
    [alt_episode] = app.state.episodes.tagged('transkript')
    # Ein Helfer, der sich ohne neue Wahl meldet, ändert den im Browser gewählten Ordner nicht.
    nach_helfer = http.post(f'{T}/worker', json={'root_id': 'mac-root', 'folder': '/Users/x/Mitschriften'}).json()
    assert nach_helfer['folder'] == str(erster.resolve()) and nach_helfer['enabled'] is True and nach_helfer['helfer'] is True
    http.post(f'{T}/lokal', json={'pfad': str(zweiter)})
    assert app.state.episodes.get(alt_episode.id).state.value == 'ignored'
    assert http.get('/api/v1/transkripte').json()['stand']['aufgenommen'] == 1


def test_dokumente_auch_im_browser(client, tmp_path):
    app, http = client
    ordner = tmp_path / 'dokumente'
    ordner.mkdir()
    (ordner / 'Vertrag.md').write_text('# Vertrag\nKündbar bis 30.11.')
    alt(ordner / 'Vertrag.md')
    antwort = http.post(f'{D}/lokal', json={'pfad': str(ordner)}).json()
    assert antwort['enabled'] is True and antwort['last_run']['recorded'] == 1
    (ordner / 'Rechnung.txt').write_text('Rechnung vom September')
    alt(ordner / 'Rechnung.txt')
    nachher = http.post(f'{D}/run').json()
    assert nachher['last_run']['recorded'] == 1 and len(nachher['files']) == 2


# -- Ordner durchsehen statt tippen (Fremdprobe 2, Befund 30) -----------------------------------------------------

def test_unterordner_ab_dem_benutzerordner_nur_ordner_ohne_versteckte_und_verweise(zuhause, tmp_path):
    (zuhause / 'Documents' / 'Mitschriften').mkdir(parents=True)
    (zuhause / 'Desktop').mkdir()
    (zuhause / '.ssh').mkdir()
    (zuhause / 'notiz.txt').write_text('keine Ordner')
    (tmp_path / 'draussen').mkdir()
    (zuhause / 'Verweis').symlink_to(tmp_path / 'draussen')
    anfang = ordner_lokal.unterordner(None)
    assert anfang['pfad'] == str(zuhause.resolve()) and anfang['oben'] is None
    assert [o['name'] for o in anfang['ordner']] == ['Desktop', 'Documents']
    tiefer = ordner_lokal.unterordner(str(zuhause / 'Documents'))
    assert tiefer['name'] == '~/Documents' and tiefer['oben'] == str(zuhause.resolve())
    assert [o['name'] for o in tiefer['ordner']] == ['Mitschriften']


def test_unterordner_nicht_ausserhalb_der_wurzeln(zuhause, tmp_path):
    (tmp_path / 'fremd').mkdir()
    for ausserhalb in (str(tmp_path / 'fremd'), '/', str(zuhause / '..'), 'relativ/pfad'):
        with pytest.raises(ordner_lokal.OrdnerFehler):
            ordner_lokal.unterordner(ausserhalb)


def test_im_container_nur_die_eingebundenen_ordner(zuhause, tmp_path, monkeypatch):
    monkeypatch.setattr(ordner_lokal, 'im_container', lambda: True)
    with pytest.raises(ordner_lokal.OrdnerFehler) as fehler:
        ordner_lokal.unterordner(None)
    assert 'Container' in fehler.value.satz
    a, b = tmp_path / 'ordner-a', tmp_path / 'ordner-b'
    (a / 'Protokolle').mkdir(parents=True)
    b.mkdir()
    monkeypatch.setenv('KINGFISHER_ORDNER', f'{a}{os.pathsep}{b}')
    anfang = ordner_lokal.unterordner(None)
    assert anfang['pfad'] == '' and [o['pfad'] for o in anfang['ordner']] == [str(a), str(b)]
    assert ordner_lokal.unterordner(str(a))['oben'] == ''
    with pytest.raises(ordner_lokal.OrdnerFehler):
        ordner_lokal.unterordner(str(zuhause))


def test_durchsehen_gibt_nichts_frei(client, zuhause):
    app, http = client
    (zuhause / 'Documents' / 'Mitschriften').mkdir(parents=True)
    antwort = http.get(f'{T}/unterordner', params={'pfad': str(zuhause / 'Documents')})
    assert antwort.status_code == 200 and [o['name'] for o in antwort.json()['ordner']] == ['Mitschriften']
    assert http.get(f'{D}/unterordner').status_code == 200
    assert http.get(f'{T}/unterordner', params={'pfad': '/'}).status_code == 422
    zustand = http.get(T).json()
    assert zustand['enabled'] is False and zustand['folder'] is None
