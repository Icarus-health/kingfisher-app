#!/usr/bin/env python3
"""Kingfisher starten, ohne ein Terminal zu bedienen (Fremdprobe 2, Befund 1).

Aufgerufen von `Kingfisher starten.command` (Doppelklick im Finder) oder direkt mit `python3`. Das Programm macht
selbst, was früher in der README als Voraussetzung stand, und sagt, was fehlt, in einem Satz mit Link:

1. **Docker Desktop**: gefunden? Sonst ein Satz und die Downloadseite öffnet sich. Läuft es nicht, startet das
   Programm es selbst und wartet (Colima wird ebenfalls gestartet, wenn es der eingestellte Docker-Kontext ist).
2. **Token und Passphrase** (`.kingfisher.env`): einmal erzeugt, ohne `openssl`, nur für den Benutzer lesbar, und
   danach wiederverwendet (die Passphrase entschlüsselt die Schlüsseldatei im Datenvolume; siehe Makefile).
3. **Kingfisher bauen und starten** (`docker compose up -d --build`, derselbe Projektname wie `make start`), warten,
   bis `/health` antwortet.
4. **Ollama** (für Antworten in eigenen Worten): fehlt es, ein Satz mit Link; Kingfisher läuft trotzdem, das Briefing
   kommt ohne Modell. Das Laden der Modelle startet später im Assistenten mit einem Klick und läuft im Hintergrund.
5. Den Browser auf `http://127.0.0.1:8890/today` öffnen. Beim ersten Mal führt dort der Assistent weiter.

Git, `make` und `openssl` braucht dieser Weg nicht. Was nur auf einem Mac geprüft werden kann (Docker Desktop starten,
Gatekeeper beim ersten Doppelklick, das Öffnen des Browsers), steht in docs/51-fremdprobe-2.md als offen.
"""
from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from typing import Callable, Optional
from urllib.request import ProxyHandler, build_opener

WURZEL = Path(__file__).resolve().parents[1]
ADRESSE = 'http://127.0.0.1:8890'
ENVDATEI = '.kingfisher.env'
DOCKER_DOWNLOAD = 'https://www.docker.com/products/docker-desktop/'
OLLAMA_DOWNLOAD = 'https://ollama.com/download'
DOCKER_APP = Path('/Applications/Docker.app')
DOCKER_ORTE = ('/usr/local/bin/docker', '/opt/homebrew/bin/docker',
               '/Applications/Docker.app/Contents/Resources/bin/docker')

SATZ_DOCKER_FEHLT = ('Kingfisher braucht Docker Desktop, ein kostenloses Programm. Die Downloadseite öffnet sich jetzt: '
                     f'{DOCKER_DOWNLOAD} – installiere es, öffne es einmal und doppelklicke danach diesen Starter '
                     'noch einmal.')
SATZ_DOCKER_STARTET = 'Docker Desktop wird gestartet; das dauert beim ersten Mal bis zu zwei Minuten …'
SATZ_DOCKER_STUMM = ('Docker Desktop antwortet nicht. Öffne es einmal selbst (Programme → Docker), warte, bis der Wal '
                     'oben in der Menüleiste ruhig steht, und doppelklicke dann diesen Starter noch einmal.')
SATZ_COMPOSE_FEHLT = ('Diesem Docker fehlt „Compose“. Installiere die aktuelle Fassung von Docker Desktop: '
                      f'{DOCKER_DOWNLOAD}')
SATZ_BAUEN = 'Kingfisher wird eingerichtet. Beim ersten Mal dauert das einige Minuten; danach geht es in Sekunden.'
SATZ_NICHT_ERREICHBAR = ('Kingfisher ist gestartet, antwortet aber noch nicht. Doppelklicke den Starter in einer Minute '
                         'noch einmal; hilft das nicht, steht in der README unter „For developers“, wie man nachsieht.')
# Eindeutig wie die README (Fremdprobe 3, S3): installieren, und was ohne Ollama trotzdem geht.
SATZ_OLLAMA_FEHLT = ('Installiere außerdem Ollama (kostenlos), damit Kingfisher deine Fragen beantworten kann: '
                     f'{OLLAMA_DOWNLOAD} – bis dahin kommen Mails, Termine und dein Briefing trotzdem.')
SATZ_FERTIG = 'Kingfisher läuft: {adresse}/today – der Browser öffnet sich. Dieses Fenster kannst du schließen.'

Lauf = Callable[..., subprocess.CompletedProcess]


class Abbruch(Exception):
    """Etwas fehlt, das das Programm nicht selbst beheben kann. `satz` ist für den Menschen."""

    def __init__(self, satz: str, link: str = '') -> None:
        super().__init__(satz)
        self.satz = satz
        self.link = link


def ausfuehren(*befehl: str, timeout: float = 30, ausgabe: bool = False) -> subprocess.CompletedProcess:
    if ausgabe:  # sichtbar im Fenster (etwa das Bauen beim ersten Mal)
        return subprocess.run(befehl, timeout=timeout, check=False)
    return subprocess.run(befehl, timeout=timeout, check=False, capture_output=True, text=True)


def finde_docker(which: Callable[[str], Optional[str]] = shutil.which, gibt_es: Callable[[str], bool] = os.path.exists) -> Optional[str]:
    gefunden = which('docker')
    if gefunden:
        return gefunden
    return next((ort for ort in DOCKER_ORTE if gibt_es(ort)), None)


def docker_bereit(docker: str, lauf: Lauf = ausfuehren) -> bool:
    try:
        return lauf(docker, 'info', timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def docker_starten(docker: str, *, lauf: Lauf = ausfuehren, mac: bool = sys.platform == 'darwin',
                   docker_app: bool | None = None, warten: Callable[[float], None] = time.sleep,
                   sekunden: int = 120, sagen: Callable[[str], None] = print) -> None:
    """Startet die Docker-Laufzeit, wenn sie nicht läuft, und wartet auf sie. Wirft `Abbruch` mit einem Satz."""
    if docker_bereit(docker, lauf):
        return
    sagen(SATZ_DOCKER_STARTET)
    kontext = ''
    try:
        kontext = lauf(docker, 'context', 'show', timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError, AttributeError):
        pass
    try:
        if kontext == 'colima' and shutil.which('colima'):
            lauf('colima', 'start', timeout=300)
        elif mac and (DOCKER_APP.is_dir() if docker_app is None else docker_app):
            lauf('open', '-g', '-a', 'Docker', timeout=20)
    except (OSError, subprocess.SubprocessError):
        pass
    for _ in range(max(1, sekunden // 2)):
        if docker_bereit(docker, lauf):
            return
        warten(2)
    raise Abbruch(SATZ_DOCKER_STUMM)


def compose_da(docker: str, lauf: Lauf = ausfuehren) -> bool:
    try:
        return lauf(docker, 'compose', 'version', timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def schluessel_anlegen(wurzel: Path = WURZEL) -> Path:
    """Token und Passphrase einmal erzeugen (wie `make start`), danach wiederverwenden. Nur für den Benutzer lesbar."""
    datei = wurzel / ENVDATEI
    if datei.exists() and datei.stat().st_size > 0:
        return datei
    inhalt = ("# Vom Kingfisher-Starter erzeugt — nicht ins Git, nicht weitergeben.\n"
              "#\n"
              "# Beide Werte müssen erhalten bleiben. Die Passphrase entschlüsselt die Schlüsseldatei im Datenvolume;\n"
              "# ist sie weg, sind die dort hinterlegten API- und Mailpasswörter unlesbar.\n"
              f"ICARUS_SIDECAR_TOKEN={secrets.token_hex(32)}\n"
              f"ICARUS_SECRETS_PASSPHRASE={secrets.token_hex(32)}\n")
    alt = os.umask(0o077)
    try:
        fd = os.open(datei, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as aus:
            aus.write(inhalt)
    finally:
        os.umask(alt)
    return datei


def fertiges_bild(env: Path) -> str:
    """Das fertige Bild aus `KINGFISHER_IMAGE` in der Schlüsseldatei (gesetzt von `make aktualisieren`), sonst leer.

    Mit einem fertigen Bild wird nichts gebaut: Sonst entstünde aus dem Quelltext ein Bild unter dem Namen der
    veröffentlichten Fassung, und die Fassungsnummer stimmte nicht mehr mit dem Inhalt überein.
    """
    try:
        for zeile in env.read_text(encoding='utf-8').splitlines():
            if zeile.startswith('KINGFISHER_IMAGE='):
                return zeile.split('=', 1)[1].strip()
    except OSError:
        pass
    return ''


def antwortet(url: str, timeout: float = 1.0) -> bool:
    try:
        with build_opener(ProxyHandler({})).open(url, timeout=timeout) as antwort:
            return 200 <= antwort.status < 500
    except OSError:
        return False


def warte_auf(url: str, *, sekunden: int = 180, pruefe: Callable[[str], bool] = antwortet,
              warten: Callable[[float], None] = time.sleep) -> bool:
    for _ in range(max(1, sekunden)):
        if pruefe(url):
            return True
        warten(1)
    return False


def oeffnen(url: str, *, mac: bool = sys.platform == 'darwin', lauf: Lauf = ausfuehren) -> None:
    try:
        if mac:
            lauf('open', url, timeout=10)
        else:
            webbrowser.open(url)
    except (OSError, subprocess.SubprocessError):
        pass  # die Adresse steht im Fenster


def starten(*, wurzel: Path = WURZEL, lauf: Lauf = ausfuehren, sagen: Callable[[str], None] = print,
            which: Callable[[str], Optional[str]] = shutil.which, gibt_es: Callable[[str], bool] = os.path.exists,
            pruefe: Callable[[str], bool] = antwortet, warten: Callable[[float], None] = time.sleep,
            mac: bool = sys.platform == 'darwin', browser: bool = True) -> str:
    """Der ganze Weg. Gibt die Adresse zurück; wirft `Abbruch`, wenn etwas fehlt, das nur der Mensch beheben kann."""
    docker = finde_docker(which, gibt_es)
    if docker is None:
        raise Abbruch(SATZ_DOCKER_FEHLT, DOCKER_DOWNLOAD)
    docker_starten(docker, lauf=lauf, mac=mac, warten=warten, sagen=sagen)
    if not compose_da(docker, lauf):
        raise Abbruch(SATZ_COMPOSE_FEHLT, DOCKER_DOWNLOAD)
    env = schluessel_anlegen(wurzel)
    sagen(SATZ_BAUEN)
    bauen = () if fertiges_bild(env) else ('--build',)
    ergebnis = lauf(docker, 'compose', '-p', 'kingfisher', '--env-file', str(env), '-f', str(wurzel / 'compose.yaml'),
                    'up', '-d', *bauen, timeout=1800, ausgabe=True)
    if ergebnis.returncode != 0:
        raise Abbruch('Kingfisher ließ sich nicht starten. Sieh oben im Fenster nach, was Docker dazu sagt, und '
                      'doppelklicke den Starter dann noch einmal.')
    if not warte_auf(f'{ADRESSE}/health', pruefe=pruefe, warten=warten):
        raise Abbruch(SATZ_NICHT_ERREICHBAR)
    if not pruefe('http://127.0.0.1:11434/api/tags'):
        sagen(SATZ_OLLAMA_FEHLT)
    adresse = f'{ADRESSE}/today'
    sagen(SATZ_FERTIG.format(adresse=ADRESSE))
    if browser:
        oeffnen(adresse, mac=mac, lauf=lauf)
    return adresse


def main() -> int:
    try:
        starten(browser='--ohne-browser' not in sys.argv)
    except Abbruch as fehler:
        print()
        print(fehler.satz)
        if fehler.link:
            oeffnen(fehler.link)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
