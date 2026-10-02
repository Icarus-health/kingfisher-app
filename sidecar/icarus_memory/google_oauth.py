"""Google Desktop OAuth: PKCE, one-use state, encrypted grants, no password flow.

Only fixed Google endpoints are contacted. The external browser returns to the
explicit loopback callback; its authorization code is removed from access logs.
Nothing is imported or scheduled by connecting an account.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import threading
import time
from urllib.parse import urlencode, urlparse

import httpx

CLIENT_KEY = 'ICARUS_GOOGLE_DESKTOP_CLIENT'
AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
USER_URL = 'https://www.googleapis.com/oauth2/v2/userinfo'
CALENDAR_URL = 'https://www.googleapis.com/calendar/v3'
SCOPES = {
    'mail': {'https://www.googleapis.com/auth/userinfo.email', 'https://mail.google.com/'},
    'calendar': {'https://www.googleapis.com/auth/userinfo.email',
                 'https://www.googleapis.com/auth/calendar.calendarlist.readonly',
                 'https://www.googleapis.com/auth/calendar.events.readonly'},
}
TTL = 600


class GoogleError(ValueError):
    pass


def google_request(method, url, **kwargs):
    try:
        with httpx.Client(timeout=25, follow_redirects=False) as client:
            response = client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError):
        # Provider response bodies may contain tokens and are never surfaced.
        raise GoogleError('Google-Zugriff fehlgeschlagen. Bitte erneut anmelden oder die Verbindung prüfen.') from None


def client_config(document):
    value = document.get('installed') if isinstance(document, dict) else None
    if not isinstance(value, dict):
        raise GoogleError('Bitte die JSON-Datei eines Google OAuth-Clients vom Typ Desktop-App verwenden.')
    client_id, secret = value.get('client_id'), value.get('client_secret')
    if not isinstance(client_id, str) or not re.fullmatch(r'[a-zA-Z0-9._-]+\.apps\.googleusercontent\.com', client_id):
        raise GoogleError('Ungültige Google-Client-ID.')
    if not isinstance(secret, str) or not 1 <= len(secret) <= 1000:
        raise GoogleError('Google-Client-Konfiguration ist unvollständig.')
    return {'client_id': client_id, 'client_secret': secret}


def redirect_uri(origin):
    parsed = urlparse(origin)
    try:
        port = parsed.port
    except ValueError:
        port = None
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or not port
            or parsed.username or parsed.password or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment):
        raise GoogleError('Die Anmeldung benötigt die lokale Kingfisher-Adresse auf 127.0.0.1.')
    return f'http://127.0.0.1:{port}/api/v1/google/callback'


#: So viele Sekunden vor Ablauf gilt ein Zugriffstoken schon als abgelaufen.
TOKEN_MARGIN = 120


class GoogleOAuth:
    def __init__(self, keychain, request=google_request, clock=time.time):
        self.keychain = keychain
        self.request = request
        self.clock = clock
        self.lock = threading.RLock()
        self.pending = {}
        self.tokens = {}         # Konto -> {raw, token, until}
        self.refresh_locks = {}  # Konto -> Sperre nur für dessen Refresh

    def configure(self, document):
        selected = client_config(document)
        if not self.keychain.available:
            raise GoogleError('Für Google-Zugänge wird ein geschützter Schlüsselspeicher benötigt.')
        with self.lock:
            self.keychain.set(CLIENT_KEY, json.dumps(selected))
            self.pending.clear()

    def configured(self):
        return bool(self.keychain.available and self.keychain.get(CLIENT_KEY))

    def _prune(self):
        self.pending = {k: v for k, v in self.pending.items() if v['expires'] > self.clock()}

    def begin(self, kind, origin):
        if kind not in SCOPES:
            raise GoogleError('Unbekannter Google-Zugang.')
        redirect = redirect_uri(origin)
        with self.lock:
            self._prune()
            if not self.configured():
                raise GoogleError('Zuerst die Google-Desktop-App-Konfiguration hinterlegen.')
            if len(self.pending) >= 8:
                raise GoogleError('Bitte eine laufende Anmeldung abschließen oder zehn Minuten warten.')
            client = json.loads(self.keychain.get(CLIENT_KEY))
            state, verifier, session_id = secrets.token_urlsafe(32), secrets.token_urlsafe(48), secrets.token_urlsafe(24)
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
            self.pending[session_id] = {'state': state, 'verifier': verifier, 'client': client,
                'kind': kind, 'redirect': redirect, 'expires': self.clock() + TTL, 'status': 'waiting'}
            return {'session_id': session_id, 'url': AUTH_URL + '?' + urlencode({
                'client_id': client['client_id'], 'redirect_uri': redirect, 'response_type': 'code',
                'scope': ' '.join(sorted(SCOPES[kind])), 'state': state,
                'code_challenge': challenge, 'code_challenge_method': 'S256',
                'access_type': 'offline', 'prompt': 'consent select_account',
            })}

    def callback(self, state, code=None, error=None):
        if not isinstance(state, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", state):
            raise GoogleError("Ungültige Google-Anmeldung.")
        with self.lock:
            self._prune()
            match = next(((sid, item) for sid, item in self.pending.items()
                          if item['status'] == 'waiting' and secrets.compare_digest(item['state'], state)), None)
            if not match:
                raise GoogleError('Diese Anmeldung ist abgelaufen oder wurde bereits verwendet.')
            sid, item = match
            item['status'] = 'processing'  # consume state before any external call
        try:
            if error or not code or len(code) > 4096:
                raise GoogleError('Google-Anmeldung wurde nicht abgeschlossen.')
            token = self.request('POST', TOKEN_URL, data={**item['client'], 'code': code,
                'code_verifier': item['verifier'], 'redirect_uri': item['redirect'], 'grant_type': 'authorization_code'})
            if not SCOPES[item['kind']].issubset(set(str(token.get('scope', '')).split())):
                raise GoogleError('Die benötigten Berechtigungen wurden nicht vollständig freigegeben.')
            if not token.get('access_token') or not token.get('refresh_token'):
                raise GoogleError('Dauerhafte Anmeldung fehlt. Bitte Google-Zugriff erneut erlauben.')
            headers = {'Authorization': 'Bearer ' + token['access_token']}
            user = self.request('GET', USER_URL, headers=headers)
            address = user.get('email', '')
            if not user.get('verified_email') or not isinstance(address, str) or not re.fullmatch(r'[^\s@\x00-\x1f]+@[^\s@\x00-\x1f]+', address):
                raise GoogleError('Google hat keine bestätigte Mailadresse geliefert.')
            calendars = []
            if item['kind'] == 'calendar':
                page = None
                for _ in range(20):
                    result = self.request('GET', CALENDAR_URL + '/users/me/calendarList', headers=headers,
                        params={'maxResults': 250, **({'pageToken': page} if page else {})})
                    calendars.extend({'id': c['id'], 'name': c.get('summary', c['id'])}
                        for c in result.get('items', []) if c.get('accessRole') in {'reader', 'writer', 'owner'} and c.get('id') and not c.get('deleted'))
                    page = result.get('nextPageToken')
                    if not page:
                        break
                else:
                    raise GoogleError('Zu viele Kalender. Bitte den Zugriff zunächst eingrenzen.')
            with self.lock:
                if sid not in self.pending or item['expires'] <= self.clock():
                    raise GoogleError('Diese Anmeldung ist abgelaufen.')
                item.update(status='ready', email=address, calendars=calendars,
                    grant={**item['client'], 'refresh_token': token['refresh_token'], 'scope': token['scope']})
            return sid
        except Exception:
            with self.lock:
                item['status'] = 'failed'
                item.pop('grant', None)
            raise GoogleError('Anmeldung nicht abgeschlossen. Bitte Berechtigungen und Google-Konfiguration prüfen und erneut versuchen.') from None
        finally:
            item.pop('verifier', None)

    def status(self, sid):
        with self.lock:
            self._prune()
            item = self.pending.get(sid)
            if not item:
                return {'status': 'expired'}
            return {key: item[key] for key in ('status', 'kind', 'email', 'calendars') if key in item}

    def consume(self, sid, calendar_ids):
        # Caller holds this lock through configuration persistence.
        self._prune()
        item = self.pending.get(sid)
        if not item or item['status'] != 'ready':
            raise GoogleError('Anmeldung ist nicht zur Übernahme bereit.')
        selected = list(dict.fromkeys(calendar_ids))
        available = {c['id']: c['name'] for c in item['calendars']}
        if item['kind'] == 'calendar' and (not selected or set(selected) - available.keys()):
            raise GoogleError('Bitte mindestens einen angezeigten Kalender auswählen.')
        if item['kind'] == 'mail' and selected:
            raise GoogleError('Für Mail werden keine Kalender ausgewählt.')
        return item, [(cid, available[cid]) for cid in selected]

    def access_token(self, secret_name):
        """Zugriffstoken für ein Konto; wird bis kurz vor Ablauf wiederverwendet.

        Ohne Zwischenspeicher ginge bei jeder Anmeldung (bei der Mailaufnahme
        Tausende je Stunde) ein HTTPS-Aufruf an Google, das bremst und riskiert
        die Ratengrenze. Der gemeinsame Sperrschutz `self.lock` bleibt frei vom
        Netzaufruf: Nur Aufrufer desselben Kontos warten aufeinander, damit ein
        Ablauf genau einen Refresh auslöst.
        """
        with self._refresh_lock(secret_name):
            with self.lock:
                raw = self.keychain.get(secret_name)
                if not raw:
                    self.tokens.pop(secret_name, None)
                    raise GoogleError('Google-Zugang wurde entfernt. Bitte erneut verbinden.')
                cached = self.tokens.get(secret_name)
                # Gilt nur für genau diesen Zugang: Neu verbunden oder Refresh-Token getauscht = anderer Inhalt.
                if cached and cached['raw'] == raw and self.clock() < cached['until']:
                    return cached['token']
            try:
                grant = json.loads(raw)
                token = self.request('POST', TOKEN_URL, data={'grant_type': 'refresh_token',
                    'client_id': grant['client_id'], 'client_secret': grant['client_secret'], 'refresh_token': grant['refresh_token']})
                if not token.get('access_token'):
                    raise GoogleError('Google-Zugang ist abgelaufen. Bitte erneut verbinden.')
                with self.lock:
                    if token.get('refresh_token'):
                        grant['refresh_token'] = token['refresh_token']
                        raw = json.dumps(grant)
                        self.keychain.set(secret_name, raw)
                    self._remember_token(secret_name, raw, token)
                return token['access_token']
            except (KeyError, ValueError):
                raise GoogleError('Google-Zugang ist nicht mehr verfügbar. Bitte erneut verbinden.') from None

    def _refresh_lock(self, secret_name):
        with self.lock:
            return self.refresh_locks.setdefault(secret_name, threading.Lock())

    def _remember_token(self, secret_name, raw, token):
        """Merkt das Token bis `TOKEN_MARGIN` Sekunden vor Ablauf; ohne Laufzeitangabe gar nicht."""
        lifetime = token.get('expires_in')
        if isinstance(lifetime, (int, float)) and lifetime > TOKEN_MARGIN:
            self.tokens[secret_name] = {'raw': raw, 'token': token['access_token'],
                                        'until': self.clock() + lifetime - TOKEN_MARGIN}
        else:
            self.tokens.pop(secret_name, None)
