"""Der Starter zum Doppelklicken (Fremdprobe 2, Befund 1): erkennt fehlende Voraussetzungen und sagt sie in einem Satz
mit Link, statt dass die README sie voraussetzt. Ohne Docker, ohne Netz: Befehle und Antworten sind Attrappen."""
from __future__ import annotations

import importlib.util
import stat
import subprocess
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('kingfisher_starten', WURZEL / 'scripts' / 'kingfisher_starten.py')
starter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(starter)


class Docker:
    """Merkt jeden Befehl; `laeuft` wird nach `bereit_nach` Abfragen wahr (Docker Desktop startet)."""

    def __init__(self, bereit_nach: int = 0, compose: bool = True, bauen_ok: bool = True) -> None:
        self.befehle: list[tuple[str, ...]] = []
        self.bereit_nach, self.compose, self.bauen_ok = bereit_nach, compose, bauen_ok

    def __call__(self, *befehl: str, timeout: float = 30, ausgabe: bool = False) -> subprocess.CompletedProcess:
        self.befehle.append(befehl)
        code = 0
        if befehl[1:2] == ('info',):
            code = 0 if self.bereit_nach <= 0 else 1
            self.bereit_nach -= 1
        elif befehl[1:3] == ('compose', 'version'):
            code = 0 if self.compose else 1
        elif 'up' in befehl:
            code = 0 if self.bauen_ok else 1
        return subprocess.CompletedProcess(befehl, code, stdout='desktop-linux\n', stderr='')


def lauf(tmp_path, docker, *, gibt_docker=True, health=True, ollama=True, mac=True):
    gesagt: list[str] = []
    (tmp_path / 'compose.yaml').write_text('services: {}\n')

    def pruefe(url: str) -> bool:
        return health if url.endswith('/health') else ollama
    adresse = starter.starten(wurzel=tmp_path, lauf=docker, sagen=gesagt.append,
                              which=lambda name: '/usr/local/bin/docker' if gibt_docker and name == 'docker' else None,
                              gibt_es=lambda pfad: False, pruefe=pruefe, warten=lambda s: None, mac=mac)
    return adresse, gesagt


def test_ohne_docker_ein_satz_mit_link(tmp_path):
    with pytest.raises(starter.Abbruch) as fehler:
        lauf(tmp_path, Docker(), gibt_docker=False)
    assert fehler.value.link == starter.DOCKER_DOWNLOAD
    assert 'Docker Desktop' in fehler.value.satz and starter.DOCKER_DOWNLOAD in fehler.value.satz
    assert not (tmp_path / '.kingfisher.env').exists()


def test_docker_desktop_wird_gestartet_und_dann_kingfisher(tmp_path, monkeypatch):
    (tmp_path / 'Docker.app').mkdir()
    monkeypatch.setattr(starter, 'DOCKER_APP', tmp_path / 'Docker.app')
    docker = Docker(bereit_nach=3)
    adresse, gesagt = lauf(tmp_path, docker)
    assert adresse == 'http://127.0.0.1:8890/today'
    assert ('open', '-g', '-a', 'Docker') in docker.befehle
    assert starter.SATZ_DOCKER_STARTET in gesagt and starter.SATZ_FERTIG.format(adresse=starter.ADRESSE) in gesagt
    hoch = next(b for b in docker.befehle if 'up' in b)
    assert hoch[:4] == ('/usr/local/bin/docker', 'compose', '-p', 'kingfisher') and '--build' in hoch
    assert ('open', 'http://127.0.0.1:8890/today') in docker.befehle  # der Browser öffnet sich


def test_docker_bleibt_stumm(tmp_path):
    with pytest.raises(starter.Abbruch) as fehler:
        lauf(tmp_path, Docker(bereit_nach=10_000))
    assert fehler.value.satz == starter.SATZ_DOCKER_STUMM


def test_ohne_compose(tmp_path):
    with pytest.raises(starter.Abbruch) as fehler:
        lauf(tmp_path, Docker(compose=False))
    assert 'Compose' in fehler.value.satz and fehler.value.link == starter.DOCKER_DOWNLOAD


def test_schluessel_einmal_nur_fuer_den_benutzer_und_wiederverwendet(tmp_path):
    lauf(tmp_path, Docker())
    datei = tmp_path / '.kingfisher.env'
    erst = datei.read_text()
    assert stat.S_IMODE(datei.stat().st_mode) == 0o600
    werte = dict(z.split('=', 1) for z in erst.splitlines() if '=' in z and not z.startswith('#'))
    assert set(werte) == {'ICARUS_SIDECAR_TOKEN', 'ICARUS_SECRETS_PASSPHRASE'} and all(len(w) == 64 for w in werte.values())
    lauf(tmp_path, Docker())
    assert datei.read_text() == erst  # eine neue Passphrase machte gespeicherte Passwörter unlesbar


def test_ohne_ollama_ein_satz_aber_kingfisher_laeuft(tmp_path):
    adresse, gesagt = lauf(tmp_path, Docker(), ollama=False)
    assert adresse.endswith('/today') and starter.SATZ_OLLAMA_FEHLT in gesagt
    assert starter.OLLAMA_DOWNLOAD in starter.SATZ_OLLAMA_FEHLT
    _, gesagt = lauf(tmp_path, Docker(), ollama=True)
    assert starter.SATZ_OLLAMA_FEHLT not in gesagt


def test_antwortet_nicht(tmp_path):
    with pytest.raises(starter.Abbruch) as fehler:
        lauf(tmp_path, Docker(), health=False)
    assert fehler.value.satz == starter.SATZ_NICHT_ERREICHBAR


def test_der_doppelklick_starter_ruft_das_programm_und_ist_ausfuehrbar():
    command = WURZEL / 'Kingfisher starten.command'
    text = command.read_text(encoding='utf-8')
    assert command.stat().st_mode & stat.S_IXUSR
    assert text.startswith('#!/bin/bash') and 'scripts/kingfisher_starten.py' in text and 'xcode-select --install' in text
    # Kein Werkzeug, das ein Nicht-Techniker erst installieren müsste.
    programm = (WURZEL / 'scripts' / 'kingfisher_starten.py').read_text(encoding='utf-8')
    assert 'openssl' not in programm.split('"""', 2)[2] and "'make'" not in programm and "'git'" not in programm


def test_readme_startweg_deutsch_gatekeeper_und_ollama_eindeutig():
    """Fremdprobe 3, S1 bis S3: der Startweg auch auf Deutsch, der Weg an Gatekeeper vorbei ab macOS 15, und Ollama als
    klare Empfehlung mit dem, was ohne geht."""
    readme = (WURZEL / 'README.md').read_text(encoding='utf-8')
    assert '### Kingfisher starten (auf Deutsch)' in readme and '(#kingfisher-starten-auf-deutsch)' in readme
    deutsch = readme.split('### Kingfisher starten (auf Deutsch)', 1)[1].split('\n### ', 1)[0]
    englisch = readme.split('## Start Kingfisher', 1)[1].split('### Kingfisher starten (auf Deutsch)', 1)[0]
    assert 'Systemeinstellungen → Datenschutz & Sicherheit' in deutsch and '**Dennoch öffnen**' in deutsch
    assert 'System Settings → Privacy & Security' in englisch and '**Open Anyway**' in englisch
    assert '**Installiere es**' in deutsch and '**Install it**' in englisch
    # Was ohne Ollama geht, steht in beiden Sprachen, und der Satz des Starters sagt dasselbe.
    assert 'Without Ollama' in englisch and 'Ohne Ollama' in deutsch
    assert starter.SATZ_OLLAMA_FEHLT.startswith('Installiere außerdem Ollama')


def test_mit_fertigem_bild_wird_nicht_gebaut(tmp_path):
    # `make aktualisieren` setzt KINGFISHER_IMAGE; danach baut der Starter nicht aus dem Quelltext unter fremdem Namen.
    docker = Docker()
    lauf(tmp_path, docker)
    assert any('up' in b and '--build' in b for b in docker.befehle)
    env = tmp_path / '.kingfisher.env'
    env.write_text(env.read_text() + 'KINGFISHER_IMAGE=ghcr.io/icarus-health/kingfisher-app:1.2.0\n')
    docker = Docker()
    lauf(tmp_path, docker)
    hoch = [b for b in docker.befehle if 'up' in b]
    assert hoch and all('--build' not in b for b in hoch)
