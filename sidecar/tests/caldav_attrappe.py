"""Eine CalDAV-Attrappe für Tests und Browserproben: echter HTTPS-Dienst auf 127.0.0.1, kein Netz nach außen.

Aufbau wie bei einem echten Anbieter, damit Kingfisher den Kalender selbst finden muss (RFC 6764, RFC 4791):

* `/.well-known/caldav` leitet nach `/dav/` um;
* `PROPFIND /dav/` nennt den `current-user-principal` `/dav/principals/<benutzer>/`;
* der Principal nennt sein `calendar-home-set` `/dav/calendars/<benutzer>/`;
* darunter zwei Sammlungen: `privat/` (Termine, Anzeigename „Privat“) und `aufgaben/` (nur Aufgaben, VTODO);
* `REPORT` auf `privat/` liefert einen Termin.

`start` ist die Adresse, die der Katalog für den Probe-Anbieter nennt (`/dav/`). Verhalten je `modus`:

* `annehmen`: mit dem richtigen Passwort wie oben, sonst 401.
* `ablehnen`: jede Anfrage 401.
* `stumm`: nimmt die Anfrage an und antwortet nicht (Server, der nicht antwortet).
* `leer`: angemeldet, aber ohne Kalender unter dem Principal.

Das Zertifikat erzeugt `imap_attrappe._zertifikat` (selbst ausgestellt, zur Laufzeit). Wer sich verbinden will, setzt
`SSL_CERT_FILE=<attrappe.zertifikat>`; `httpx` liest das. Nur synthetische Zugänge.
"""
from __future__ import annotations

import base64
import ssl

import httpx
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tests.imap_attrappe import PASSWORT, _zertifikat

TERMIN = ('BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:probe-1@attrappe\r\nDTSTART:20261002T080000Z\r\n'
          'DTEND:20261002T090000Z\r\nSUMMARY:Probe-Termin beim Steuerbüro\r\nLOCATION:Musterstraße 2, Mainz\r\n'
          'END:VEVENT\r\nEND:VCALENDAR\r\n')


def _antwort(href: str, prop: str) -> str:
    return (f'<d:response><d:href>{href}</d:href><d:propstat><d:prop>{prop}</d:prop>'
            '<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>')


def _multistatus(*antworten: str) -> bytes:
    return ('<?xml version="1.0" encoding="utf-8"?><d:multistatus xmlns:d="DAV:" '
            'xmlns:c="urn:ietf:params:xml:ns:caldav">' + ''.join(antworten) + '</d:multistatus>').encode()


class CaldavAttrappe:
    def __init__(self, modus: str = 'annehmen', passwort: str = PASSWORT) -> None:
        self.modus = modus
        self.passwort = passwort
        self.anmeldungen: list[tuple[str, str]] = []
        self.anfragen_an: list[tuple[str, str, bool]] = []
        self._ordner = Path(tempfile.mkdtemp(prefix='caldav-attrappe-'))
        self.zertifikat, schluessel = _zertifikat(self._ordner)
        kontext = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        kontext.load_cert_chain(self.zertifikat, schluessel)
        attrappe = self
        self._halt = threading.Event()

        class Dienst(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *_: object) -> None:
                pass

            def _senden(self, status: int, koerper: bytes = b'', art: str = 'application/xml; charset=utf-8',
                        kopf: dict[str, str] | None = None) -> None:
                self.send_response(status)
                for name, wert in (kopf or {}).items():
                    self.send_header(name, wert)
                self.send_header('Content-Type', art)
                self.send_header('Content-Length', str(len(koerper)))
                self.end_headers()
                self.wfile.write(koerper)

            def _benutzer(self) -> str | None:
                roh = self.headers.get('Authorization', '')
                if not roh.startswith('Basic '):
                    return None
                benutzer, _, passwort = base64.b64decode(roh[6:]).decode().partition(':')
                attrappe.anmeldungen.append((benutzer, passwort))
                if attrappe.modus == 'ablehnen' or passwort != attrappe.passwort:
                    return None
                return benutzer

            def _laenge_lesen(self) -> None:
                laenge = int(self.headers.get('Content-Length') or 0)
                if laenge:
                    self.rfile.read(laenge)

            def do_PROPFIND(self) -> None:  # noqa: N802 - Name aus http.server
                self._laenge_lesen()
                if attrappe.modus == 'stumm':
                    attrappe._halt.wait(60)
                    return
                if self.path.rstrip('/') == '/.well-known/caldav':
                    self._senden(301, kopf={'Location': '/dav/'})
                    return
                benutzer = self._benutzer()
                if benutzer is None:
                    self._senden(401, kopf={'WWW-Authenticate': 'Basic realm="Probe"'})
                    return
                ich = benutzer.split('@')[0]
                principal, heim = f'/dav/principals/{ich}/', f'/dav/calendars/{ich}/'
                pfad = self.path
                if pfad == '/dav/':
                    koerper = _multistatus(_antwort(pfad, f'<d:current-user-principal><d:href>{principal}</d:href>'
                                                          '</d:current-user-principal><d:resourcetype><d:collection/>'
                                                          '</d:resourcetype>'))
                elif pfad == principal:
                    koerper = _multistatus(_antwort(pfad, f'<c:calendar-home-set><d:href>{heim}</d:href>'
                                                          '</c:calendar-home-set>'))
                elif pfad == heim:
                    eintraege = [_antwort(heim, '<d:resourcetype><d:collection/></d:resourcetype>')]
                    if attrappe.modus != 'leer':
                        eintraege += [
                            _antwort(heim + 'privat/', '<d:resourcetype><d:collection/><c:calendar/></d:resourcetype>'
                                     '<d:displayname>Privat</d:displayname><c:supported-calendar-component-set>'
                                     '<c:comp name="VEVENT"/></c:supported-calendar-component-set>'),
                            _antwort(heim + 'aufgaben/', '<d:resourcetype><d:collection/><c:calendar/></d:resourcetype>'
                                     '<d:displayname>Aufgaben</d:displayname><c:supported-calendar-component-set>'
                                     '<c:comp name="VTODO"/></c:supported-calendar-component-set>')]
                    koerper = _multistatus(*eintraege)
                else:
                    self._senden(404)
                    return
                self._senden(207, koerper)

            def do_REPORT(self) -> None:  # noqa: N802
                self._laenge_lesen()
                if attrappe.modus == 'stumm':
                    attrappe._halt.wait(60)
                    return
                if self._benutzer() is None:
                    self._senden(401, kopf={'WWW-Authenticate': 'Basic realm="Probe"'})
                    return
                if not self.path.endswith('/privat/'):
                    self._senden(207, _multistatus())
                    return
                daten = TERMIN.replace('&', '&amp;').replace('<', '&lt;')
                self._senden(207, _multistatus(f'<d:response><d:href>{self.path}probe-1.ics</d:href><d:propstat>'
                                               f'<d:prop><c:calendar-data>{daten}</c:calendar-data></d:prop>'
                                               '<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>'))

        self._server = ThreadingHTTPServer(('127.0.0.1', 0), Dienst)
        self._server.daemon_threads = True
        self._server.socket = kontext.wrap_socket(self._server.socket, server_side=True)
        self.port = self._server.server_address[1]
        self.start = f'https://127.0.0.1:{self.port}/dav/'
        threading.Thread(target=self._server.serve_forever, name='caldav-attrappe', daemon=True).start()

    def transport(self, *hosts: str) -> httpx.BaseTransport:
        """Lenkt Anfragen an `hosts` (etwa den Mailserver einer eigenen Domain) hierher; `anfragen_an` merkt sie samt
        der Frage, ob ein Passwort mitging. Andere Hosts bekommen eine Verbindungsablehnung, nie das Netz."""
        attrappe = self
        innen = httpx.HTTPTransport(verify=ssl.create_default_context(cafile=str(self.zertifikat)))

        class Umleitung(httpx.BaseTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:
                attrappe.anfragen_an.append((request.url.host, request.url.path, 'Authorization' in request.headers))
                if request.url.host not in hosts and request.url.host != '127.0.0.1':
                    raise httpx.ConnectError('nicht erreichbar', request=request)
                request.url = request.url.copy_with(host='127.0.0.1', port=attrappe.port)
                return innen.handle_request(request)

            def close(self) -> None:
                """Bleibt offen: je Abruf ein eigener Client."""

        return Umleitung()

    def schliessen(self) -> None:
        self._halt.set()
        self._server.shutdown()
        self._server.server_close()

    def __enter__(self) -> 'CaldavAttrappe':
        return self

    def __exit__(self, *_: object) -> None:
        self.schliessen()


__all__ = ['CaldavAttrappe', 'PASSWORT', 'TERMIN']
