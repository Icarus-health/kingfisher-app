"""Eine iCal-Attrappe für Tests und Browserproben: echter HTTPS-Dienst auf 127.0.0.1, kein Netz nach außen.

Steht für Google Kalender und seine „Geheime Adresse im iCal-Format“ (Fremdprobe, Befund 2). Pfade:

* `GEHEIM` (`/calendar/ical/…/private-…/basic.ics`): ein gültiges iCalendar mit Namen und zwei Terminen;
* `OEFFENTLICH` (`…/public/basic.ics`): 404, wie bei einem nicht öffentlichen Kalender;
* `/keine-datei`: 200 mit einer HTML-Seite (kein Kalender);
* `/umleitung`: 302 woandershin (wird nicht verfolgt);
* `/stumm`: nimmt die Anfrage an und antwortet nicht;
* alles andere: 404.

`google_transport()` ist ein `httpx`-Transport, der Anfragen an `calendar.google.com` hierher umlenkt (Pfad bleibt),
damit Kingfisher eine echte Google-Adresse erkennt und trotzdem nur diesen Dienst erreicht. Jede Anfrage steht in
`anfragen` (Methode, Pfad). Das Zertifikat ist selbst ausgestellt (`imap_attrappe._zertifikat`). Nur synthetische Daten.
"""
from __future__ import annotations

import ssl
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx

from tests.imap_attrappe import _zertifikat

GEHEIM = '/calendar/ical/lena.probe%40example.org/private-0123456789abcdef0123456789abcdef/basic.ics'
OEFFENTLICH = '/calendar/ical/lena.probe%40example.org/public/basic.ics'
GOOGLE_GEHEIM = 'https://calendar.google.com' + GEHEIM
GOOGLE_OEFFENTLICH = 'https://calendar.google.com' + OEFFENTLICH
KALENDER = ('BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Probe//Attrappe//DE\r\nX-WR-CALNAME:Lena Probe\r\n'
            'BEGIN:VEVENT\r\nUID:probe-a@attrappe\r\nDTSTART:20261002T080000Z\r\nDTEND:20261002T090000Z\r\n'
            'SUMMARY:Abstimmung Atlas\r\nEND:VEVENT\r\n'
            'BEGIN:VEVENT\r\nUID:probe-b@attrappe\r\nDTSTART;VALUE=DATE:20261005\r\nSUMMARY:Steuertermin\r\nEND:VEVENT\r\n'
            'END:VCALENDAR\r\n')


class IcalAttrappe:
    def __init__(self) -> None:
        self.anfragen: list[tuple[str, str]] = []
        self._halt = threading.Event()
        self._ordner = Path(tempfile.mkdtemp(prefix='ical-attrappe-'))
        self.zertifikat, schluessel = _zertifikat(self._ordner)
        kontext = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        kontext.load_cert_chain(self.zertifikat, schluessel)
        attrappe = self

        class Dienst(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *_: object) -> None:
                pass

            def _senden(self, status: int, koerper: bytes = b'', art: str = 'text/calendar; charset=utf-8',
                        kopf: dict[str, str] | None = None) -> None:
                self.send_response(status)
                for name, wert in (kopf or {}).items():
                    self.send_header(name, wert)
                self.send_header('Content-Type', art)
                self.send_header('Content-Length', str(len(koerper)))
                self.end_headers()
                self.wfile.write(koerper)

            def do_GET(self) -> None:  # noqa: N802 - Name aus http.server
                attrappe.anfragen.append(('GET', self.path))
                if self.path == '/stumm':
                    attrappe._halt.wait(60)
                    return
                if self.path == GEHEIM:
                    self._senden(200, KALENDER.encode())
                elif self.path == '/keine-datei':
                    self._senden(200, b'<html><body>Anmelden</body></html>', 'text/html')
                elif self.path == '/umleitung':
                    self._senden(302, kopf={'Location': 'https://127.0.0.1:1/woanders.ics'})
                else:
                    self._senden(404, b'Not Found', 'text/plain')

        self._server = ThreadingHTTPServer(('127.0.0.1', 0), Dienst)
        self._server.daemon_threads = True
        self._server.socket = kontext.wrap_socket(self._server.socket, server_side=True)
        self.port = self._server.server_address[1]
        self.basis = f'https://127.0.0.1:{self.port}'
        threading.Thread(target=self._server.serve_forever, name='ical-attrappe', daemon=True).start()

    def google_transport(self) -> httpx.BaseTransport:
        """Lenkt `calendar.google.com` auf diese Attrappe um; andere Hosts gehen unverändert hinaus."""
        attrappe = self
        innen = httpx.HTTPTransport(verify=ssl.create_default_context(cafile=str(self.zertifikat)))

        class Umleitung(httpx.BaseTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:
                if request.url.host == 'calendar.google.com':
                    request.url = request.url.copy_with(host='127.0.0.1', port=attrappe.port)
                return innen.handle_request(request)

            def close(self) -> None:
                """Bleibt offen: Kingfisher öffnet je Abruf einen eigenen Client, der den Transport schließt."""

        return Umleitung()

    def schliessen(self) -> None:
        self._halt.set()
        self._server.shutdown()
        self._server.server_close()

    def __enter__(self) -> 'IcalAttrappe':
        return self

    def __exit__(self, *_: object) -> None:
        self.schliessen()


__all__ = ['GEHEIM', 'GOOGLE_GEHEIM', 'GOOGLE_OEFFENTLICH', 'IcalAttrappe', 'KALENDER', 'OEFFENTLICH']
