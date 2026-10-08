"""Der Vertrag der Compose-Dateien (docs/53-download-und-updates.md).

Eine bestehende Installation findet ihre Daten über drei Namen: das Projekt `kingfisher`, das Volume `kingfisher-data`
(zusammen `kingfisher_kingfisher-data`) und den Port 8890 nur an 127.0.0.1. Ändert sich einer davon, startet
Kingfisher nach einem Update leer. `deploy/compose.app.yaml` (für die Mac-App) muss außerdem in allem außer `build:`
und der Vorgabe des Bildes mit `compose.yaml` übereinstimmen.

Die Prüfung liest die Zeilen selbst (im Sidecar gibt es kein YAML-Paket); wo Docker da ist, vergleicht sie zusätzlich
die von `docker compose config` aufgelöste Form.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[2]
QUELLE = WURZEL / 'compose.yaml'
APP = WURZEL / 'deploy' / 'compose.app.yaml'
BILD = re.compile(r'^    image: \$\{KINGFISHER_IMAGE:-(?P<vorgabe>[^}]+)\}$')


def zeilen(pfad: Path) -> list[str]:
    """Die bedeutsamen Zeilen: ohne Kommentarzeilen, Leerzeilen und `build:`; die Bildvorgabe vereinheitlicht."""
    ergebnis = []
    for zeile in pfad.read_text(encoding='utf-8').splitlines():
        if not zeile.strip() or zeile.lstrip().startswith('#') or zeile.strip().startswith('build:'):
            continue
        ergebnis.append(BILD.sub('    image: ${KINGFISHER_IMAGE:-…}', zeile))
    return ergebnis


def bildvorgabe(pfad: Path) -> str:
    treffer = [BILD.match(z) for z in pfad.read_text(encoding='utf-8').splitlines()]
    gefunden = [t.group('vorgabe') for t in treffer if t]
    assert len(gefunden) == 1, f'{pfad.name}: genau eine Zeile image: ${{KINGFISHER_IMAGE:-…}}'
    return gefunden[0]


@pytest.mark.parametrize('pfad', [QUELLE, APP], ids=['compose.yaml', 'compose.app.yaml'])
def test_projekt_volume_und_port_bleiben(pfad):
    text = pfad.read_text(encoding='utf-8')
    assert re.search(r'^name: kingfisher$', text, re.M)
    assert re.search(r'^services:\n  kingfisher:$', text, re.M)
    assert re.search(r'^    ports:\n      - "127\.0\.0\.1:8890:8890"$', text, re.M)
    assert len(re.findall(r'^      - "[^"]*:\d+:\d+"$', text, re.M)) == 1, 'genau ein Port, nur an 127.0.0.1'
    assert re.search(r'^    volumes:\n      - kingfisher-data:/data$', text, re.M)
    assert re.search(r'^volumes:\n  kingfisher-data:$', text, re.M)
    # Token und Passphrase bleiben Pflicht; ohne sie startet nichts.
    assert '- ICARUS_SIDECAR_TOKEN=${ICARUS_SIDECAR_TOKEN:?bitte setzen}' in text
    assert '- ICARUS_SECRETS_PASSPHRASE=${ICARUS_SECRETS_PASSPHRASE:?bitte setzen}' in text


def test_bilder():
    assert re.search(r'^    build: \.$', QUELLE.read_text(encoding='utf-8'), re.M)
    assert not re.search(r'^\s*build:', APP.read_text(encoding='utf-8'), re.M)
    # Ohne KINGFISHER_IMAGE: die Arbeitskopie baut ihr Bild wie bisher, die App nimmt die neueste Fassung.
    assert bildvorgabe(QUELLE) == 'kingfisher:local'
    assert bildvorgabe(APP) == 'ghcr.io/icarus-health/kingfisher-app:latest'


def test_beide_dateien_stimmen_ueberein_ausser_build():
    assert zeilen(APP) == zeilen(QUELLE)


def _aufgeloest(pfad: Path, bild: str | None) -> dict:
    umgebung = {**os.environ, 'ICARUS_SIDECAR_TOKEN': 't', 'ICARUS_SECRETS_PASSPHRASE': 'p'}
    umgebung.pop('KINGFISHER_IMAGE', None)
    umgebung['KINGFISHER_DURABLE_MEMORY_SEARCH'] = '1'
    umgebung['ICARUS_MEMORY_SEMANTIC'] = ''
    if bild:
        umgebung['KINGFISHER_IMAGE'] = bild
    try:
        lauf = subprocess.run(['docker', 'compose', '-p', 'kingfisher', '-f', str(pfad), 'config', '--format', 'json'],
                              capture_output=True, text=True, timeout=60, env=umgebung, cwd=pfad.parent)
    except (OSError, subprocess.SubprocessError):
        pytest.skip('docker compose nicht verfügbar')
    if lauf.returncode != 0:
        pytest.skip('docker compose config lief nicht: ' + lauf.stderr[:200])
    return json.loads(lauf.stdout)


@pytest.mark.skipif(shutil.which('docker') is None, reason='Docker fehlt')
def test_docker_loest_beide_gleich_auf():
    quelle = _aufgeloest(QUELLE, 'ghcr.io/icarus-health/kingfisher-app:1.2.0')
    app = _aufgeloest(APP, 'ghcr.io/icarus-health/kingfisher-app:1.2.0')
    dienst = quelle['services']['kingfisher']
    assert dienst['image'] == app['services']['kingfisher']['image'] == 'ghcr.io/icarus-health/kingfisher-app:1.2.0'
    assert quelle['volumes']['kingfisher-data']['name'] == 'kingfisher_kingfisher-data'
    assert [(p['host_ip'], p['published'], p['target']) for p in dienst['ports']] == [('127.0.0.1', '8890', 8890)]
    assert dienst['environment']['KINGFISHER_DURABLE_MEMORY_SEARCH'] == '1'
    assert dienst['environment']['ICARUS_MEMORY_SEMANTIC'] == ''
    dienst.pop('build')
    assert quelle == app
    assert _aufgeloest(QUELLE, None)['services']['kingfisher']['image'] == 'kingfisher:local'
