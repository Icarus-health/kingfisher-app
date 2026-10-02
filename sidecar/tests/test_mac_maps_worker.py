"""Mac-Arbeiter für Fahrzeiten: Ablauf mit einem Attrappen-Helfer und einem Attrappen-Sidecar.

Der echte Swift-Helfer (Apple Karten) läuft nur auf einem Mac und wurde hier nicht ausgeführt.
"""
import importlib.util
import json
import stat
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

SKRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'mac_maps_worker.py'
spec = importlib.util.spec_from_file_location('mac_maps_worker', SKRIPT)
modul = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modul)


def helfer(tmp_path, ausgabe: str, code: int = 0):
    pfad = tmp_path / 'kingfisher-route'
    pfad.write_text(f"#!/bin/sh\ncat > /dev/null\nprintf '%s' '{ausgabe}'\nexit {code}\n")
    pfad.chmod(pfad.stat().st_mode | stat.S_IXUSR)
    return pfad


FRAGE = {'id': 'a1', 'von': 'Musterstraße 1, Wiesbaden', 'nach': 'Uferweg 7, Wiesbaden', 'verkehrsmittel': 'auto'}


def test_rechnen_liefert_minuten_oder_ein_fehlerkuerzel_nie_adressen(tmp_path):
    assert modul.rechnen(helfer(tmp_path, '{"ok": true, "minuten": 28}'), FRAGE) == {'minuten': 28}
    assert modul.rechnen(helfer(tmp_path, '{"ok": false, "error": "nicht_unterstuetzt"}', 1), FRAGE) == {
        'fehler': 'nicht_unterstuetzt'}
    fremd = modul.rechnen(helfer(tmp_path, '{"ok": false, "error": "Musterstraße 1 nicht gefunden"}', 1), FRAGE)
    assert fremd == {'fehler': 'dienst_nicht_erreichbar'}
    assert modul.rechnen(helfer(tmp_path, 'kein json'), FRAGE) == {'fehler': 'dienst_nicht_erreichbar'}
    assert modul.rechnen(tmp_path / 'fehlt', FRAGE) == {'fehler': 'dienst_nicht_erreichbar'}


def test_eine_runde_holt_fragen_und_liefert_antworten(tmp_path, monkeypatch, capsys):
    empfangen = []

    class Sidecar(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _senden(self, daten):
            koerper = json.dumps(daten).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(koerper)))
            self.end_headers()
            self.wfile.write(koerper)

        def do_GET(self):
            assert self.headers['X-Icarus-Token'] == 'token-test'
            self._senden({'aktiv': True, 'anfragen': [FRAGE]})

        def do_POST(self):
            empfangen.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            self._senden({'angenommen': True})

    server = HTTPServer(('127.0.0.1', 0), Sidecar)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = tmp_path / 'privat.env'
    env.write_text('ICARUS_SIDECAR_TOKEN=token-test\n')
    monkeypatch.setattr(sys, 'argv', ['w', '--env-file', str(env), '--url', f'http://127.0.0.1:{server.server_port}',
                                      '--helper', str(helfer(tmp_path, '{"ok": true, "minuten": 41}')), '--once'])
    try:
        modul.main()
    finally:
        server.shutdown()
    assert empfangen == [{'id': 'a1', 'minuten': 41, 'fehler': ''}]
    assert 'Wiesbaden' not in capsys.readouterr().out


def test_nur_loopback_ist_erlaubt(tmp_path, monkeypatch):
    env = tmp_path / 'privat.env'
    env.write_text('ICARUS_SIDECAR_TOKEN=x\n')
    monkeypatch.setattr(sys, 'argv', ['w', '--env-file', str(env), '--url', 'http://example.org:8891', '--once'])
    with pytest.raises(SystemExit):
        modul.main()


def test_syntax_der_skripte():
    for datei in (SKRIPT, SKRIPT.parent / 'test_route_reader.py'):
        subprocess.run([sys.executable, '-m', 'py_compile', str(datei)], check=True)
