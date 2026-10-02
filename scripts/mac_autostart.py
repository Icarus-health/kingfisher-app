#!/usr/bin/env python3
"""Helfer auf dem Mac: setzt die Antwort auf „Kingfisher beim Anmelden starten?“ um.

Der Sidecar merkt sich nur Ja oder Nein (`/api/v1/autostart`). Dieser Helfer
fragt die Antwort ab und legt dann einen Launch Agent an oder nimmt ihn weg:

* Ja: `~/Library/LaunchAgents/local.kingfisher.start.plist` schreiben. Beim
  nächsten Anmelden startet macOS damit `start_mac_app.py --no-browser`, also
  Container und Helfer, ohne ein Fenster aufzudrängen.
* Nein: die Datei entfernen (nur diese eine, an ihrem festen Namen).
* Keine Antwort: nichts schreiben, nichts entfernen.

Was gestartet wird, bestimmt dieser Helfer aus seinem eigenen Aufruf (Python,
Skriptpfad, Container, Konfigurationsdatei), nie die API. `launchctl` wird nicht
aufgerufen: Die Datei wirkt beim nächsten Anmelden; bis dahin ändert sich nichts.
Kein `KeepAlive`: Wer Kingfisher beendet, beendet es.

Die Funktionen `plist_inhalt`, `anwenden` und `pfad` sind ohne Mac prüfbar
(`sidecar/tests/test_autostart.py`, gegen einen temporären Ordner).
"""
from __future__ import annotations

import argparse
import json
import plistlib
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import ProxyHandler, Request, build_opener

LABEL = 'local.kingfisher.start'
TAKT_S = 10


def pfad(ordner: Path) -> Path:
    return Path(ordner) / f'{LABEL}.plist'


def programm(python: str, skripte: Path, container: str, env_file: Path, url: str) -> list[str]:
    """Der Aufruf beim Anmelden: derselbe Start wie aus der App, nur ohne Browser."""
    return [python, str(Path(skripte) / 'start_mac_app.py'), '--container', container,
            '--env-file', str(env_file), '--url', url, '--no-browser']


def plist_inhalt(aufruf: list[str], protokoll: Path) -> bytes:
    if not aufruf or not all(isinstance(teil, str) and teil for teil in aufruf):
        raise ValueError('Ungültiger Aufruf für den Autostart.')
    return plistlib.dumps({
        'Label': LABEL,
        'ProgramArguments': aufruf,
        'RunAtLoad': True,
        'ProcessType': 'Background',
        'StandardOutPath': str(protokoll),
        'StandardErrorPath': str(protokoll),
    })


def anwenden(gewuenscht: bool | None, ordner: Path, aufruf: list[str], protokoll: Path) -> bool:
    """Bringt die Datei auf die Antwort; gibt zurück, ob sie danach da ist.

    `None` heißt: noch niemand hat gefragt. Dann bleibt alles, wie es ist.
    """
    datei = pfad(ordner)
    if gewuenscht is True:
        inhalt = plist_inhalt(aufruf, protokoll)
        if not datei.exists() or datei.read_bytes() != inhalt:
            datei.parent.mkdir(parents=True, exist_ok=True)
            zwischen = datei.with_suffix('.plist.neu')
            zwischen.write_bytes(inhalt)
            zwischen.chmod(0o644)
            zwischen.replace(datei)
    elif gewuenscht is False and datei.exists():
        datei.unlink()
    return datei.exists()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8891')
    parser.add_argument('--env-file', required=True, type=Path)
    parser.add_argument('--container', required=True)
    args = parser.parse_args()
    if sys.platform != 'darwin':
        return  # Nur der Mac hat Launch Agents; anderswo sagt die Oberfläche „noch nicht verfügbar“.
    import fcntl
    sperre = args.env_file.with_suffix('.autostart.lock').open('w')
    try:
        fcntl.flock(sperre, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return  # Ein Helfer genügt.
    url = urlparse(args.url)
    if url.scheme != 'http' or url.hostname != '127.0.0.1' or url.username or url.path not in ('', '/'):
        parser.error('Only an explicit 127.0.0.1 HTTP service is supported')
    config = dict(line.split('=', 1) for line in args.env_file.read_text().splitlines()
                  if '=' in line and not line.startswith('#'))
    token = config.get('ICARUS_SIDECAR_TOKEN')
    if not token:
        parser.error('ICARUS_SIDECAR_TOKEN missing from private env file')
    env_file = args.env_file.resolve()
    ordner = Path.home() / 'Library' / 'LaunchAgents'
    aufruf = programm(sys.executable, Path(__file__).resolve().parent, args.container, env_file, args.url)
    protokoll = env_file.parent / 'autostart.log'
    opener = build_opener(ProxyHandler({}))
    while True:
        try:
            body = json.dumps({'plattform': 'macos', 'eingerichtet': pfad(ordner).exists()}).encode()
            request = Request(args.url.rstrip('/') + '/api/v1/autostart/helfer', data=body,
                              headers={'X-Icarus-Token': token, 'Content-Type': 'application/json'})
            with opener.open(request, timeout=10) as response:
                gewuenscht = json.load(response).get('gewuenscht')
            anwenden(gewuenscht if isinstance(gewuenscht, bool) else None, ordner, aufruf, protokoll)
        except (OSError, ValueError):
            pass  # Der Sidecar startet noch oder ist beendet; der nächste Takt versucht es erneut.
        time.sleep(TAKT_S)


if __name__ == '__main__':
    main()
