#!/usr/bin/env python3
"""Mac-Arbeiter für Fahrzeiten über Apple Karten. Nur ausgehend, keine Adressen im Protokoll.

UNGEPRÜFT: In einer Linux-Umgebung geschrieben (nur Syntax und Ablauf mit einem Attrappen-Helfer geprüft),
nie auf einem Mac mit dem echten Swift-Helfer ausgeführt (siehe docs/33-briefing-und-vorbereitung.md).

Ablauf: Alle fünf Sekunden fragt der Arbeiter den Sidecar (`/api/v1/wegezeit/mac/anfragen`) nach offenen Fragen.
Der Sidecar gibt nur etwas heraus, wenn der Nutzer „Fahrzeiten berechnen“ eingeschaltet hat. Zu jeder Frage
(zwei Adressen, ein Verkehrsmittel) ruft der Arbeiter `build/kingfisher-route route` (macos/RouteReader.swift) und
liefert die Minuten zurück (`/api/v1/wegezeit/mac/antworten`). Fehlt der Helfer (nicht gebaut), bleibt der
Arbeiter still und meldet nichts, der Sidecar sagt dann ehrlich „Fahrzeit unbekannt“.
"""
import argparse
import fcntl
import json
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

TAKT_S = 5
FEHLER_KUERZEL = {'nicht_unterstuetzt', 'keine_route', 'adresse_unbekannt', 'dienst_nicht_erreichbar',
                  'zeitueberschreitung'}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def rechnen(binary, frage):
    """Eine Frage an den Swift-Helfer. Antwort: {'minuten': n} oder {'fehler': Kürzel}. Nie Adressen im Text."""
    try:
        ergebnis = subprocess.run(
            [str(binary), 'route'], text=True, capture_output=True, timeout=30,
            input=json.dumps({'von': frage['von'], 'nach': frage['nach'], 'verkehrsmittel': frage['verkehrsmittel'],
                              'abfahrt': frage.get('abfahrt')}))
        antwort = json.loads(ergebnis.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {'fehler': 'dienst_nicht_erreichbar'}
    if antwort.get('ok') and isinstance(antwort.get('minuten'), int):
        return {'minuten': antwort['minuten']}
    kuerzel = antwort.get('error')
    return {'fehler': kuerzel if kuerzel in FEHLER_KUERZEL else 'dienst_nicht_erreichbar'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8891')
    parser.add_argument('--env-file', required=True, type=Path)
    parser.add_argument('--helper', type=Path, default=Path(__file__).resolve().parents[1] / 'build/kingfisher-route')
    parser.add_argument('--once', action='store_true', help='Nur eine Runde (Prüfung).')
    args = parser.parse_args()
    url = urlparse(args.url)
    if url.scheme != 'http' or url.hostname != '127.0.0.1' or url.username or url.path not in ('', '/'):
        parser.error('Only an explicit 127.0.0.1 HTTP service is supported')
    lock = args.env_file.with_suffix('.maps.lock').open('w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    config = dict(line.split('=', 1) for line in args.env_file.read_text().splitlines()
                  if '=' in line and not line.startswith('#'))
    token = config.get('ICARUS_SIDECAR_TOKEN')
    if not token:
        parser.error('ICARUS_SIDECAR_TOKEN missing from private env file')
    opener = build_opener(ProxyHandler({}), NoRedirect())

    def api(route, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = Request(args.url.rstrip('/') + '/api/v1/wegezeit/mac' + route, data=data,
                          headers={'X-Icarus-Token': token, 'Content-Type': 'application/json'})
        with opener.open(request, timeout=30) as response:
            return json.load(response)

    while True:
        try:
            if args.helper.is_file():
                for frage in api('/anfragen').get('anfragen', []):
                    antwort = rechnen(args.helper, frage)
                    api('/antworten', {'id': frage['id'], 'minuten': antwort.get('minuten'),
                                       'fehler': antwort.get('fehler', '')})
        except HTTPError as error:
            print('Mac maps connection:', error.code, flush=True)
        except (OSError, ValueError):
            print('Mac maps temporarily unavailable; retrying.', flush=True)
        if args.once:
            return
        time.sleep(TAKT_S)


if __name__ == '__main__':
    main()
