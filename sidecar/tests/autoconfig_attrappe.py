"""Eine Autoconfig-Attrappe für Tests und Browserproben: echter HTTPS-Dienst auf 127.0.0.1, kein Netz nach außen.

Steht für den Webserver einer eigenen Domain, der seine Mail-Einstellungen im Thunderbird-Format veröffentlicht
(`server_finden.py`, Fremdprobe 2, Befund 2). `transport()` ist ein `httpx`-Transport, der jede Anfrage hierher lenkt
(Host und Pfad bleiben in der Anfrage erhalten); die Attrappe antwortet je Host:

* `autoconfig.<domain>/mail/config-v1.1.xml` für jede Domain in `autoconfig` (Vorgabe: `example.org`),
* `<domain>/.well-known/autoconfig/mail/config-v1.1.xml` für jede Domain in `well_known` (Vorgabe:
  `wellknown-probe.example`, nur dort, nicht unter `autoconfig.`),
* `umleitung-probe.example`: 302 woandershin (wird nicht verfolgt), `riesig-probe.example`: 200 KB,
  `doctype-probe.example`: eine Datei mit DOCTYPE und Entität, `starttls-probe.example`: IMAP nur mit STARTTLS,
* alles andere: 404.

Jede Anfrage steht in `anfragen` als (Host, Pfad mit Abfrage). Nur synthetische Daten.
"""
from __future__ import annotations

import ssl
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx

from tests.imap_attrappe import _zertifikat


def config_xml(domain: str, imap_host: str, imap_port: int = 993, smtp_host: str = '', smtp_port: int = 587,
               benutzer: str = '%EMAILADDRESS%', socket_typ: str = 'SSL') -> str:
    ausgang = (f'<outgoingServer type="smtp"><hostname>{smtp_host}</hostname><port>{smtp_port}</port>'
               '<socketType>STARTTLS</socketType><username>%EMAILADDRESS%</username>'
               '<authentication>password-cleartext</authentication></outgoingServer>') if smtp_host else ''
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<clientConfig version="1.1">'
            f'<emailProvider id="{domain}"><domain>{domain}</domain><displayName>Probe</displayName>'
            '<incomingServer type="pop3"><hostname>pop.falsch.example</hostname><port>995</port>'
            '<socketType>SSL</socketType></incomingServer>'
            f'<incomingServer type="imap"><hostname>{imap_host}</hostname><port>{imap_port}</port>'
            f'<socketType>{socket_typ}</socketType><username>{benutzer}</username>'
            '<authentication>password-cleartext</authentication></incomingServer>'
            f'{ausgang}</emailProvider></clientConfig>\n')


DOCTYPE = ('<?xml version="1.0"?><!DOCTYPE lol [<!ENTITY a "aaaaaaaaaa">]><clientConfig version="1.1">'
           '<emailProvider id="x"><incomingServer type="imap"><hostname>&a;.example</hostname><port>993</port>'
           '<socketType>SSL</socketType></incomingServer></emailProvider></clientConfig>')
PFAD = '/mail/config-v1.1.xml'
WELL_KNOWN = '/.well-known/autoconfig/mail/config-v1.1.xml'


def kein_netz() -> httpx.BaseTransport:
    """Für Browserproben ohne Autoconfig-Attrappe: Die Suche nach dem Server einer Domain geht nie hinaus."""
    class KeinNetz(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError('kein Netz in der Probe', request=request)
    return KeinNetz()


class AutoconfigAttrappe:
    def __init__(self, autoconfig: dict[str, str] | None = None, well_known: dict[str, str] | None = None) -> None:
        self.autoconfig = {'example.org': config_xml('example.org', 'mail.example.org', smtp_host='mail.example.org')}
        self.autoconfig.update(autoconfig or {})
        self.well_known = {'wellknown-probe.example': config_xml('wellknown-probe.example', 'imap.wellknown-probe.example',
                                                                 benutzer='%EMAILLOCALPART%'),
                           'starttls-probe.example': config_xml('starttls-probe.example', 'imap.starttls-probe.example',
                                                                143, socket_typ='STARTTLS'),
                           'doctype-probe.example': DOCTYPE}
        self.well_known.update(well_known or {})
        self.anfragen: list[tuple[str, str]] = []
        self._ordner = Path(tempfile.mkdtemp(prefix='autoconfig-attrappe-'))
        self.zertifikat, schluessel = _zertifikat(self._ordner)
        kontext = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        kontext.load_cert_chain(self.zertifikat, schluessel)
        attrappe = self

        class Dienst(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *_: object) -> None:
                pass

            def _senden(self, status: int, koerper: bytes = b'', kopf: dict[str, str] | None = None) -> None:
                self.send_response(status)
                for name, wert in (kopf or {}).items():
                    self.send_header(name, wert)
                self.send_header('Content-Type', 'text/xml; charset=utf-8')
                self.send_header('Content-Length', str(len(koerper)))
                self.end_headers()
                self.wfile.write(koerper)

            def do_GET(self) -> None:  # noqa: N802 - Name aus http.server
                host = (self.headers.get('Host') or '').split(':')[0].lower()
                attrappe.anfragen.append((host, self.path))
                pfad = self.path.split('?')[0]
                domain = host.removeprefix('autoconfig.')
                if host.startswith('autoconfig.') and pfad == PFAD and domain in attrappe.autoconfig:
                    self._senden(200, attrappe.autoconfig[domain].encode())
                elif pfad == WELL_KNOWN and host in attrappe.well_known:
                    self._senden(200, attrappe.well_known[host].encode())
                elif host.endswith('umleitung-probe.example'):
                    self._senden(302, kopf={'Location': 'https://127.0.0.1:1/anderswo.xml'})
                elif host.endswith('riesig-probe.example'):
                    # Eine gültige Datei, nur zu groß: ohne Grenze würde sie gefunden.
                    gueltig = config_xml('riesig-probe.example', 'mail.riesig-probe.example')
                    self._senden(200, gueltig.replace('<clientConfig', '<!--' + ' ' * 200_000 + '--><clientConfig').encode())
                else:
                    self._senden(404, b'Not Found')

        self._server = ThreadingHTTPServer(('127.0.0.1', 0), Dienst)
        self._server.daemon_threads = True
        self._server.socket = kontext.wrap_socket(self._server.socket, server_side=True)
        self.port = self._server.server_address[1]
        threading.Thread(target=self._server.serve_forever, name='autoconfig-attrappe', daemon=True).start()

    def transport(self) -> httpx.BaseTransport:
        """Lenkt jede HTTPS-Anfrage hierher; der ursprüngliche Host bleibt im Kopf `Host`."""
        attrappe = self
        innen = httpx.HTTPTransport(verify=ssl.create_default_context(cafile=str(self.zertifikat)))

        class Umleitung(httpx.BaseTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:
                host = request.url.host
                request.headers['Host'] = host
                request.url = request.url.copy_with(host='127.0.0.1', port=attrappe.port)
                return innen.handle_request(request)

            def close(self) -> None:
                """Bleibt offen: Kingfisher öffnet je Abruf einen eigenen Client, der den Transport schließt."""

        return Umleitung()

    def schliessen(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def __enter__(self) -> 'AutoconfigAttrappe':
        return self

    def __exit__(self, *_: object) -> None:
        self.schliessen()


__all__ = ['AutoconfigAttrappe', 'DOCTYPE', 'kein_netz', 'PFAD', 'WELL_KNOWN', 'config_xml']
