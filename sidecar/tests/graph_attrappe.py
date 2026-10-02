"""Eine Attrappe von Microsoft Entra ID und Microsoft Graph für Tests und Browserprobe: HTTP auf 127.0.0.1, kein Netz.

Sie spielt, was Kingfisher von Microsoft braucht, mit synthetischen Daten (Konto `lena.probe@hochschule.example`):

* Anmeldung mit Gerätecode: `POST /<mandant>/oauth2/v2.0/devicecode` und `…/token`. Die Antworten auf das Nachfragen
  stehen in `ablauf` (je Nachfrage eine): `pending` (authorization_pending), `slow_down`, `ok`, `abgelaufen`
  (expired_token), `abgelehnt` (authorization_declined), `admin` (invalid_grant mit AADSTS65001), `admin90094`.
  Ist die Liste leer, gilt `ok`. Der Refresh-Token wird bei jedem Erneuern getauscht (wie bei Microsoft).
* `GET /<domain>/v2.0/.well-known/openid-configuration`: für `hochschule.example` ein Mandant, sonst 400 (AADSTS90002).
* Graph unter `/v1.0`: `me`, Postordner mit Delta-Abfrage in Seiten (`@odata.nextLink`, danach `@odata.deltaLink`;
  neue Post über `neue_post`), Einzelabruf, `calendarView` (zwei Seiten), `onlineMeetings` mit Filter auf die
  Teilnahme-Adresse, `transcripts` und deren Inhalt als VTT.

`modus` schaltet Fehler: `mitschriften_verboten` (403 auf Mitschriften), `drosseln` (einmal 429 mit Retry-After).
Jede Anfrage steht in `anfragen` (Methode, Pfad, ob ein Bearer-Token dabei war, Scope der Tokenanfrage).
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

ADRESSE = 'lena.probe@hochschule.example'
MANDANT = '11111111-2222-3333-4444-555555555555'
CLIENT_ID = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
USER_CODE = 'PROB-ECOD'
JOIN_URL = 'https://teams.microsoft.com/l/meetup-join/19%3ameeting_probe%40thread.v2/0'

VTT = ('WEBVTT\n\n00:00:03.000 --> 00:00:06.000\n<v Anna Keller>Guten Morgen, wir beginnen mit dem Haushalt.</v>\n\n'
       '00:01:10.000 --> 00:01:15.000\n<v Lena Probe>Der Antrag geht bis Freitag an das Dekanat.</v>\n\n'
       '00:02:00.000 --> 00:02:04.000\n<v Anna Keller>Dann übernehme ich die Tabelle.</v>\n\n'
       '00:03:30.000 --> 00:03:35.000\n<v Lena Probe>Danke, so machen wir es.</v>\n')


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.0000000')


class GraphAttrappe:
    def __init__(self, posteingang: int = 7, gesendet: int = 2, seite: int = 3) -> None:
        self.ablauf: list[str] = []
        self.modus: set[str] = set()
        self.anfragen: list[dict] = []
        self.seite = seite
        self.zugriff = 'zugriff-1'
        self.refresh = 'erneuern-1'
        self.scope_erteilt = 'https://graph.microsoft.com/User.Read https://graph.microsoft.com/Mail.Read ' \
                             'https://graph.microsoft.com/Calendars.Read https://graph.microsoft.com/OnlineMeetings.Read ' \
                             'openid profile email offline_access'
        jetzt = datetime.now(timezone.utc).replace(microsecond=0)
        self.post = {'inbox': [], 'sentitems': []}
        for i in range(posteingang):
            self.post['inbox'].append(self._mail(f'in-{i}', jetzt - timedelta(days=posteingang - i), i))
        for i in range(gesendet):
            self.post['sentitems'].append(self._mail(f'out-{i}', jetzt - timedelta(days=gesendet - i, hours=1), i, eigen=True))
        self.delta_stand = {'inbox': len(self.post['inbox']), 'sentitems': len(self.post['sentitems'])}
        gestern = (jetzt - timedelta(days=1)).replace(hour=9, minute=0, second=0)
        morgen = (jetzt + timedelta(days=1)).replace(hour=14, minute=0, second=0)
        self.termine = [
            {'id': 'ev-1', 'iCalUId': 'ical-teams-1', 'subject': 'Haushalt Fakultät', 'isAllDay': False, 'isCancelled': False,
             'start': {'dateTime': _iso(gestern), 'timeZone': 'UTC'},
             'end': {'dateTime': _iso(gestern + timedelta(hours=1)), 'timeZone': 'UTC'},
             'location': {'displayName': 'Microsoft Teams-Besprechung'}, 'bodyPreview': 'Haushalt besprechen',
             'attendees': [{'emailAddress': {'name': 'Anna Keller', 'address': 'anna.keller@hochschule.example'}}],
             'organizer': {'emailAddress': {'name': 'Lena Probe', 'address': ADRESSE}},
             'isOnlineMeeting': True, 'onlineMeeting': {'joinUrl': JOIN_URL}},
            {'id': 'ev-2', 'iCalUId': 'ical-2', 'subject': 'Sprechstunde', 'isAllDay': False, 'isCancelled': False,
             'start': {'dateTime': _iso(morgen), 'timeZone': 'UTC'},
             'end': {'dateTime': _iso(morgen + timedelta(minutes=30)), 'timeZone': 'UTC'},
             'location': {'displayName': 'Raum 2.14'}, 'bodyPreview': '', 'attendees': [],
             'organizer': {'emailAddress': {'name': 'Lena Probe', 'address': ADRESSE}}, 'isOnlineMeeting': False},
        ]
        self.transkript_beginn = gestern + timedelta(minutes=2)
        self._halt = threading.Event()
        attrappe = self

        class Dienst(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *_: object) -> None:
                pass

            def _senden(self, status: int, inhalt=None, art: str = 'application/json', kopf: dict | None = None) -> None:
                koerper = inhalt if isinstance(inhalt, bytes) else json.dumps(inhalt or {}).encode()
                self.send_response(status)
                for name, wert in (kopf or {}).items():
                    self.send_header(name, wert)
                self.send_header('Content-Type', art)
                self.send_header('Content-Length', str(len(koerper)))
                self.end_headers()
                self.wfile.write(koerper)

            def _merken(self, methode: str, scope: str = '') -> None:
                attrappe.anfragen.append({'methode': methode, 'pfad': urlsplit(self.path).path,
                                          'bearer': self.headers.get('Authorization', '').startswith('Bearer '),
                                          'token': self.headers.get('Authorization', '')[7:], 'scope': scope,
                                          'prefer': self.headers.get('Prefer', '')})

            def do_POST(self) -> None:  # noqa: N802
                laenge = int(self.headers.get('Content-Length') or 0)
                daten = {k: v[0] for k, v in parse_qs(self.rfile.read(laenge).decode()).items()}
                self._merken('POST', daten.get('scope', ''))
                pfad = urlsplit(self.path).path
                if pfad.endswith('/oauth2/v2.0/devicecode'):
                    if daten.get('client_id') != CLIENT_ID:
                        self._senden(400, {'error': 'unauthorized_client', 'error_codes': [700016],
                                           'error_description': 'AADSTS700016: Application not found.'})
                        return
                    attrappe.scope_angefragt = daten.get('scope', '')
                    self._senden(200, {'device_code': 'geraet-geheim', 'user_code': USER_CODE,
                                       'verification_uri': 'https://microsoft.com/devicelogin', 'expires_in': 900,
                                       'interval': 0, 'message': 'synthetisch'})
                    return
                if pfad.endswith('/oauth2/v2.0/token'):
                    if daten.get('grant_type') == 'refresh_token':
                        if 'refresh_abgelaufen' in attrappe.modus or daten.get('refresh_token') != attrappe.refresh:
                            self._senden(400, {'error': 'invalid_grant', 'error_codes': [700082],
                                               'error_description': 'AADSTS700082: The refresh token has expired.'})
                            return
                        nummer = int(attrappe.zugriff.rsplit('-', 1)[1]) + 1
                        attrappe.zugriff, attrappe.refresh = f'zugriff-{nummer}', f'erneuern-{nummer}'
                        self._senden(200, {'access_token': attrappe.zugriff, 'refresh_token': attrappe.refresh,
                                           'expires_in': 3600, 'scope': attrappe.scope_erteilt, 'token_type': 'Bearer'})
                        return
                    if daten.get('device_code') != 'geraet-geheim':
                        self._senden(400, {'error': 'invalid_grant'})
                        return
                    schritt = attrappe.ablauf.pop(0) if attrappe.ablauf else 'ok'
                    fehler = {'pending': ('authorization_pending', 70016), 'slow_down': ('slow_down', 0),
                              'abgelaufen': ('expired_token', 70019), 'abgelehnt': ('authorization_declined', 0),
                              'admin': ('invalid_grant', 65001), 'admin90094': ('invalid_grant', 90094)}
                    if schritt in fehler:
                        name, code = fehler[schritt]
                        self._senden(400, {'error': name, 'error_codes': [code] if code else [],
                                           'error_description': f'AADSTS{code}: synthetisch' if code else name})
                        return
                    if ('OnlineMeetingTranscript.Read.All' in attrappe.scope_angefragt
                            and 'OnlineMeetingTranscript' not in attrappe.scope_erteilt):
                        attrappe.scope_erteilt += ' https://graph.microsoft.com/OnlineMeetingTranscript.Read.All'
                    self._senden(200, {'access_token': attrappe.zugriff, 'refresh_token': attrappe.refresh,
                                       'expires_in': 3600, 'scope': attrappe.scope_erteilt, 'token_type': 'Bearer'})
                    return
                self._senden(404)

            def do_GET(self) -> None:  # noqa: N802
                self._merken('GET')
                teile = urlsplit(self.path)
                pfad, frage = unquote(teile.path), {k: v[0] for k, v in parse_qs(teile.query).items()}
                if pfad.endswith('/v2.0/.well-known/openid-configuration'):
                    domain = pfad.split('/')[1]
                    if domain == ADRESSE.split('@')[1]:
                        self._senden(200, {'issuer': f'https://login.microsoftonline.com/{MANDANT}/v2.0'})
                    else:
                        self._senden(400, {'error': 'invalid_tenant', 'error_codes': [90002],
                                           'error_description': 'AADSTS90002: Tenant not found.'})
                    return
                if not pfad.startswith('/v1.0/'):
                    self._senden(404)
                    return
                if self.headers.get('Authorization') != f'Bearer {attrappe.zugriff}':
                    self._senden(401, {'error': {'code': 'InvalidAuthenticationToken'}})
                    return
                if 'drosseln' in attrappe.modus:
                    attrappe.modus.discard('drosseln')
                    self._senden(429, {'error': {'code': 'TooManyRequests'}}, kopf={'Retry-After': '7'})
                    return
                self._graph(pfad[len('/v1.0/'):], frage)

            def _graph(self, pfad: str, frage: dict) -> None:
                basis = f'http://127.0.0.1:{attrappe.port}/v1.0/'
                if pfad == 'me':
                    self._senden(200, {'id': 'nutzer-1', 'mail': ADRESSE, 'userPrincipalName': ADRESSE,
                                       'displayName': 'Lena Probe'})
                    return
                if pfad == 'me/mailFolders/inbox':
                    self._senden(200, {'id': 'inbox-id'})
                    return
                if pfad.startswith('me/mailFolders/') and pfad.endswith('/messages/delta'):
                    ordner = pfad.split('/')[2]
                    liste = attrappe.post.get(ordner, [])
                    if 'deltatoken' in frage:
                        alt = int(frage['deltatoken'])
                        neu = liste[alt:]
                        self._senden(200, {'value': [{'id': m['id'], 'receivedDateTime': m['receivedDateTime']} for m in neu],
                                           '@odata.deltaLink': f'{basis}{pfad}?deltatoken={len(liste)}'})
                        return
                    ab = int(frage.get('skiptoken', 0))
                    stueck = list(reversed(liste))[ab:ab + attrappe.seite]  # neueste zuerst, wie Graph meistens
                    antwort = {'value': [{'id': m['id'], 'receivedDateTime': m['receivedDateTime']} for m in stueck]}
                    if ab + attrappe.seite < len(liste):
                        antwort['@odata.nextLink'] = f'{basis}{pfad}?skiptoken={ab + attrappe.seite}'
                    else:
                        antwort['@odata.deltaLink'] = f'{basis}{pfad}?deltatoken={len(liste)}'
                    self._senden(200, antwort)
                    return
                if pfad == 'me/mailFolders/inbox/messages':
                    liste = sorted(attrappe.post['inbox'], key=lambda m: m['receivedDateTime'], reverse=True)
                    self._senden(200, {'value': liste[:int(frage.get('$top', 10))]})
                    return
                if pfad.startswith('me/messages/'):
                    kennung = pfad.split('/', 2)[2]
                    for m in attrappe.post['inbox'] + attrappe.post['sentitems']:
                        if m['id'] == kennung:
                            self._senden(200, m)
                            return
                    self._senden(404, {'error': {'code': 'ErrorItemNotFound'}})
                    return
                if pfad == 'me/calendarView':
                    if 'seite2' in frage:
                        self._senden(200, {'value': attrappe.termine[1:]})
                        return
                    self._senden(200, {'value': attrappe.termine[:1],
                                       '@odata.nextLink': f'{basis}me/calendarView?seite2=1'})
                    return
                if pfad == 'me/onlineMeetings':
                    treffer = frage.get('$filter', '') == f"JoinWebUrl eq '{JOIN_URL}'"
                    self._senden(200, {'value': [{'id': 'besprechung-1', 'joinWebUrl': JOIN_URL}] if treffer else []})
                    return
                if pfad.startswith('me/onlineMeetings/besprechung-1/transcripts'):
                    if 'mitschriften_verboten' in attrappe.modus:
                        self._senden(403, {'error': {'code': 'Forbidden'}})
                        return
                    if pfad.endswith('/content'):
                        self._senden(200, VTT.encode(), art='text/vtt')
                        return
                    self._senden(200, {'value': [{'id': 'mitschrift-1', 'createdDateTime': _iso(attrappe.transkript_beginn) + 'Z'}]})
                    return
                self._senden(404, {'error': {'code': 'NotFound'}})

        self.scope_angefragt = ''
        self._server = ThreadingHTTPServer(('127.0.0.1', 0), Dienst)
        self.port = self._server.server_address[1]
        self.login = f'http://127.0.0.1:{self.port}'
        self.graph = f'http://127.0.0.1:{self.port}/v1.0'
        threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()

    def _mail(self, kennung: str, eingang: datetime, nummer: int, eigen: bool = False) -> dict:
        absender = {'emailAddress': {'name': 'Lena Probe', 'address': ADRESSE}} if eigen else \
            {'emailAddress': {'name': 'Anna Keller', 'address': 'anna.keller@hochschule.example'}}
        empfaenger = [{'emailAddress': {'name': 'Anna Keller', 'address': 'anna.keller@hochschule.example'}}] if eigen else \
            [{'emailAddress': {'name': 'Lena Probe', 'address': ADRESSE}}]
        return {'id': kennung, 'subject': f'Probe-Nachricht {nummer}', 'from': absender, 'sender': absender,
                'toRecipients': empfaenger, 'ccRecipients': [], 'bccRecipients': [], 'replyTo': [],
                'receivedDateTime': eingang.strftime('%Y-%m-%dT%H:%M:%SZ'), 'sentDateTime': eingang.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'isRead': nummer % 2 == 0, 'internetMessageId': f'<{kennung}@hochschule.example>',
                'internetMessageHeaders': [{'name': 'List-Id', 'value': 'rundbrief'}] if nummer == 0 else [],
                'body': {'contentType': 'text', 'content': f'Hallo, das ist die synthetische Nachricht {nummer}.'},
                'bodyPreview': f'Hallo, das ist die synthetische Nachricht {nummer}.'}

    def neue_post(self, ordner: str = 'inbox') -> str:
        kennung = f'neu-{len(self.post[ordner])}'
        self.post[ordner].append(self._mail(kennung, datetime.now(timezone.utc), 99))
        return kennung

    def stop(self) -> None:
        self._halt.set()
        self._server.shutdown()
