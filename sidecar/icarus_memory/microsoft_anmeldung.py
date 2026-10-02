"""Mit Microsoft anmelden: Gerätecode statt Passwort (OAuth 2.0 Device Authorization Grant, RFC 8628).

Hochschulen und Firmen mit Microsoft 365 lassen oft kein einfaches Postfach-Passwort mehr zu. Die Anmeldung über
Microsoft (Entra ID) bringt Outlook-Post, Kalender, Teams-Mitschriften und OneDrive über einen Zugang. Der Weg ist
der für Geräte ohne eigenes Anmeldefenster: Kingfisher zeigt einen kurzen Code und den Link
`https://microsoft.com/devicelogin`, der Mensch meldet sich dort im Browser an (mit seinem gewohnten Konto, auch
mit zweitem Faktor), und Kingfisher fragt in Abständen nach, ob es so weit ist. Kein Passwort berührt Kingfisher,
keine Rücksprungadresse muss stimmen, und die App ist ein öffentlicher Client ohne Geheimnis.

**Nur lesen.** Angefragt werden ausschließlich delegierte Leserechte (`GRUND_SCOPES`, `MITSCHRIFT_SCOPE`); die
Liste ist fest, und `nur_lesend` weist alles andere ab, bevor eine Anfrage hinausgeht. Kingfisher kann über diesen
Zugang nichts schreiben, nichts versenden und nichts löschen.

**Teams-Mitschriften getrennt.** `OnlineMeetingTranscript.Read.All` verlangt bei Microsoft immer die Zustimmung
eines Administrators. Stünde es in der ersten Anmeldung, scheiterte an einer Hochschule ohne diese Freigabe die
ganze Anmeldung, auch für Post und Kalender. Darum fragt die erste Anmeldung nur `GRUND_SCOPES`; die Mitschriften
sind ein zweiter Klick („Teams-Mitschriften dazunehmen“), der bei fehlender Freigabe ehrlich sagt, warum nicht.

**Was den Rechner verlässt, und wann.** Beim Tippen der Adresse nichts an Microsoft: Ob eine Domain zu Microsoft 365
gehört, steht in ihrem DNS-Eintrag; das erkennt die eine Anbieter-Erkennung (`anbieter_erkennen.erkennen`, über den
Namensdienst des Rechners), dieselbe, die auch Google Workspace erkennt. Erst der Klick „Mit Microsoft
anmelden“ fragt Microsoft nach dem Mandanten der Domain (`mandant`) und holt den Code. Die Zugangsschlüssel
(Refresh-Token) liegen nur im Schlüsselspeicher dieses Rechners (`secrets.Keychain`), das kurzlebige Zugriffstoken
nur im Arbeitsspeicher. Keine Antwort und kein Statusbericht enthält eines davon.

Die Gründe (`Anmeldefehler.grund`), jeweils ein Satz für den Menschen, sind in `GRUENDE`.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
import time
from typing import Any, Callable

import httpx

from .anbieter_erkennen import MICROSOFT_PRIVAT
from .mail_anmeldung import Anmeldefehler

#: Umgebungsvariablen: Vorgabe der App-Kennung und Adressen der Dienste (Tests und Attrappen setzen sie auf 127.0.0.1).
CLIENT_ENV = 'KINGFISHER_MS_CLIENT_ID'
TENANT_ENV = 'KINGFISHER_MS_TENANT'
LOGIN_ENV = 'KINGFISHER_MS_LOGIN_URL'
GRAPH_ENV = 'KINGFISHER_MS_GRAPH_URL'
LOGIN_VORGABE = 'https://login.microsoftonline.com'
GRAPH_VORGABE = 'https://graph.microsoft.com/v1.0'
DEVICELOGIN = 'https://microsoft.com/devicelogin'

#: Schlüssel der gespeicherten App-Kennung (Einstellung hinter „Für Techniker“).
CLIENT_KEY = 'KINGFISHER_MS_CLIENT'

#: Die erste Anmeldung: Post, Kalender, Besprechungsangaben, dauerhafte Anmeldung, wer angemeldet ist. Alle delegiert
#: und nur lesend; keines verlangt bei Microsoft die Zustimmung eines Administrators. `Files.Read` (OneDrive) fehlt mit
#: Absicht: Kingfisher liest OneDrive noch nicht über Microsoft, und eine Berechtigung ohne Nutzung wird nicht erbeten
#: (docs/50-microsoft-365.md, „OneDrive“).
GRUND_SCOPES = ('User.Read', 'Mail.Read', 'Calendars.Read', 'OnlineMeetings.Read', 'offline_access')
#: Teams-Mitschriften lesen (delegiert); verlangt bei Microsoft stets die Zustimmung eines Administrators.
MITSCHRIFT_SCOPE = 'OnlineMeetingTranscript.Read.All'
#: Ohne diese drei ist eine Anmeldung nichts wert (Post, Kalender, wer).
PFLICHT = frozenset({'User.Read', 'Mail.Read', 'Calendars.Read'})
ERLAUBT = frozenset(GRUND_SCOPES) | {MITSCHRIFT_SCOPE}
#: Was nie angefragt werden darf, auch wenn jemand die Liste oben erweitert.
_SCHREIBEND = re.compile(r'write|send|manage|create|delete|full|impersonat|\.all$', re.I)

#: So lange gilt ein Code höchstens, wenn Microsoft nichts sagt (Sekunden); und das kürzeste Nachfrage-Intervall.
CODE_DAUER = 900
INTERVALL = 5
#: So viele Anmeldungen dürfen gleichzeitig offen sein.
OFFEN_HOECHSTENS = 4
#: So viele Sekunden vor Ablauf gilt ein Zugriffstoken schon als abgelaufen.
TOKEN_MARGIN = 120
NETZ_ZEITGRENZE = 10.0

#: Domains der privaten Microsoft-Konten. Für sie gibt es keinen Mandanten; angemeldet wird über `consumers`.
#: Dieselbe Liste wie in der einen Anbieter-Erkennung (`anbieter_erkennen.py`).
PRIVATE_DOMAINS = MICROSOFT_PRIVAT

GRUENDE = {
    'admin': 'Deine Hochschule oder Firma muss Kingfisher erst freigeben: Microsoft verlangt dafür die Zustimmung '
             'ihrer IT. Bis dahin geht die Post nur mit Adresse und Passwort, falls die IT das erlaubt.',
    'admin_mitschriften': 'Teams-Mitschriften gibt Microsoft erst frei, wenn die IT deiner Hochschule oder Firma '
                          'zugestimmt hat. Post und Kalender bleiben verbunden.',
    'abgebrochen': 'Die Anmeldung wurde bei Microsoft abgelehnt oder abgebrochen. Du kannst sie jederzeit neu starten.',
    'abgelaufen': 'Der Code ist abgelaufen, er gilt nur eine Viertelstunde. Starte die Anmeldung neu, dann gibt es '
                  'einen neuen.',
    'app_unbekannt': 'Microsoft kennt die hinterlegte Kennung der App nicht. Ein Techniker prüft sie unter '
                     '„Für Techniker“.',
    'kein_code_weg': 'Die App ist bei Microsoft nicht für die Anmeldung mit Code eingerichtet. Ein Techniker schaltet '
                     'das in der App-Registrierung ein („Öffentliche Clientflows zulassen“).',
    'nicht_zugewiesen': 'Deine IT hat Kingfisher nur für bestimmte Personen freigegeben, und du gehörst noch nicht dazu.',
    'richtlinie': 'Deine IT lässt diese Anmeldung von diesem Gerät nicht zu. Frag sie, ob Kingfisher erlaubt ist.',
    'unbekannte_domain': 'Microsoft kennt diese Adresse nicht als Konto einer Hochschule oder Firma.',
    'unvollstaendig': 'Bei der Anmeldung wurden nicht alle nötigen Rechte erteilt (Post, Kalender). Starte sie neu und '
                      'stimme bei Microsoft zu.',
    'nicht_erreichbar': 'Microsoft antwortet gerade nicht. Prüfe die Internetverbindung und versuche es gleich noch '
                        'einmal.',
    'keine_app': 'Für die Anmeldung bei Microsoft fehlt noch die Kennung der App. Ein Techniker trägt sie unter '
                 '„Für Techniker“ ein.',
    'kein_speicher': 'Auf diesem Rechner fehlt der geschützte Speicher für Zugänge; die Anmeldung bei Microsoft ist '
                     'deshalb gesperrt.',
    'abgemeldet': 'Die Anmeldung bei Microsoft ist abgelaufen oder wurde zurückgezogen. Melde dich unter Zugänge '
                  'noch einmal an.',
    'verboten': 'Microsoft verweigert Kingfisher diesen Zugriff; die Berechtigung fehlt oder die IT hat ihn gesperrt.',
    'fehlt': 'Das gibt es bei Microsoft nicht (mehr).',
    'gedrosselt': 'Microsoft bremst gerade die Abrufe. Kingfisher macht in ein paar Minuten von selbst weiter.',
    'unbekannt': 'Microsoft hat die Anmeldung nicht abgeschlossen. Starte sie neu; klappt es wieder nicht, hilft ein '
                 'Techniker.',
}

#: AADSTS-Nummern aus `error_codes` bzw. `error_description` und ihr Grund. Geprüft gegen die Liste der
#: Entra-Fehlercodes (learn.microsoft.com/entra/identity-platform/reference-error-codes); nur, was hier vorkommt.
_CODES = {
    65001: 'admin',            # The user or administrator has not consented to use the application
    90094: 'admin',            # Admin consent is required for the permissions requested by this application
    90095: 'admin',            # Admin consent workflow: Anfrage an die IT gestellt, noch nicht erteilt
    65004: 'abgebrochen',      # User declined to consent
    70019: 'abgelaufen',       # Verification code expired
    700016: 'app_unbekannt',   # Application not found in the directory
    700038: 'app_unbekannt',   # Client-ID ist keine gültige Anwendung
    7000218: 'kein_code_weg',  # Request body must contain client_assertion or client_secret (kein öffentlicher Client)
    50105: 'nicht_zugewiesen',  # User not assigned to a role for the application
    53003: 'richtlinie',       # Blocked by Conditional Access
    53000: 'richtlinie',       # Device not compliant / not managed
    90002: 'unbekannte_domain',  # Tenant not found
    700082: 'abgemeldet',      # Refresh token expired due to inactivity
    50173: 'abgemeldet',       # Grant expired (Passwort geändert)
    50078: 'abgemeldet',       # Zweiter Faktor abgelaufen, neu anmelden
    50076: 'abgemeldet',       # Zweiter Faktor verlangt (beim Erneuern ohne Menschen nicht möglich)
}
_FEHLER = {
    'authorization_declined': 'abgebrochen', 'expired_token': 'abgelaufen', 'bad_verification_code': 'abgelaufen',
    'consent_required': 'admin', 'unauthorized_client': 'kein_code_weg', 'invalid_client': 'app_unbekannt',
}


class MicrosoftFehler(Anmeldefehler):
    """Ein Fehler beim Anmelden oder beim Erneuern; `grund` für Oberfläche und Tests, `satz` für den Menschen."""

    def __init__(self, grund: str) -> None:
        super().__init__(grund, GRUENDE.get(grund, GRUENDE['unbekannt']))

    @property
    def status(self) -> int:
        return 503 if self.grund == 'nicht_erreichbar' else 422


def login_basis() -> str:
    return (os.environ.get(LOGIN_ENV) or LOGIN_VORGABE).rstrip('/')


def graph_basis() -> str:
    return (os.environ.get(GRAPH_ENV) or GRAPH_VORGABE).rstrip('/')


def nur_lesend(scopes: tuple[str, ...] | list[str]) -> str:
    """Die Scopes als Zeichenkette; wirft, wenn einer nicht ausdrücklich erlaubt oder schreibend ist."""
    for scope in scopes:
        if scope not in ERLAUBT or (scope != MITSCHRIFT_SCOPE and _SCHREIBEND.search(scope)):
            raise ValueError(f'Nicht erlaubte Berechtigung: {scope}')
    return ' '.join(scopes)


def scopes_fuer(mitschriften: bool) -> tuple[str, ...]:
    return GRUND_SCOPES + ((MITSCHRIFT_SCOPE,) if mitschriften else ())


def erteilt(scope_text: str) -> set[str]:
    """Die erteilten Scopes aus der Token-Antwort, ohne die Vorsilbe `https://graph.microsoft.com/`."""
    return {teil.rsplit('/', 1)[-1] for teil in str(scope_text or '').split() if teil}


def konto_schluessel(adresse: str) -> str:
    """Name des Schlüsselspeicher-Eintrags eines Microsoft-Kontos; die Adresse selbst steht nicht darin."""
    digest = hashlib.sha256(adresse.strip().casefold().encode('utf-8')).hexdigest()[:24]
    return f'ICARUS_MICROSOFT_TOKEN_{digest}'


def domain_von(adresse: str) -> str:
    teil = (adresse or '').strip().rpartition('@')[2].strip().lower().rstrip('.')
    return teil if re.fullmatch(r'[a-z0-9-]+(\.[a-z0-9-]+)+', teil or '') else ''


def gueltige_client_id(wert: str) -> bool:
    return bool(re.fullmatch(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', wert or ''))


# -- Netz ---------------------------------------------------------------------------------------------------------

def ms_request(method: str, url: str, **kwargs: Any) -> tuple[int, Any]:
    """Eine Anfrage an Microsoft; (Status, JSON). Antworttexte werden nie weitergereicht, nur ausgewertet."""
    try:
        with httpx.Client(timeout=NETZ_ZEITGRENZE, follow_redirects=False) as client:
            antwort = client.request(method, url, **kwargs)
    except httpx.HTTPError:
        raise MicrosoftFehler('nicht_erreichbar') from None
    try:
        inhalt = antwort.json()
    except ValueError:
        inhalt = {}
    return antwort.status_code, inhalt if isinstance(inhalt, dict) else {}


def grund_aus(fehler: dict[str, Any]) -> str:
    """Der Grund zu einer Fehlerantwort von Entra: erst die AADSTS-Nummer, dann der OAuth-Fehlername."""
    codes = [c for c in fehler.get('error_codes') or [] if isinstance(c, int)]
    codes += [int(n) for n in re.findall(r'AADSTS(\d+)', str(fehler.get('error_description') or ''))]
    for code in codes:
        if code in _CODES:
            return _CODES[code]
    return _FEHLER.get(str(fehler.get('error') or ''), 'unbekannt')


# -- Die Anmeldung ------------------------------------------------------------------------------------------------

class MicrosoftAnmeldung:
    """Offene Anmeldungen mit Gerätecode, die App-Kennung und das Erneuern der Zugriffstoken je Konto."""

    def __init__(self, keychain: Any, request: Callable[..., tuple[int, Any]] = ms_request,
                 clock: Callable[[], float] = time.time) -> None:
        self.keychain = keychain
        self.request = request
        self.clock = clock
        self.lock = threading.RLock()
        self.offen: dict[str, dict[str, Any]] = {}
        self.tokens: dict[str, dict[str, Any]] = {}
        self.refresh_locks: dict[str, threading.Lock] = {}

    # App-Kennung -------------------------------------------------------------------------------------------------

    def client_id(self) -> tuple[str, str]:
        """(Kennung, Herkunft): aus der Einstellung (`einstellung`), sonst der Umgebung (`umgebung`), sonst leer."""
        gespeichert = self.keychain.get(CLIENT_KEY) if self.keychain.available else None
        if gespeichert:
            try:
                wert = json.loads(gespeichert).get('client_id', '')
            except (ValueError, AttributeError):
                wert = ''
            if gueltige_client_id(wert):
                return wert, 'einstellung'
        wert = (os.environ.get(CLIENT_ENV) or '').strip()
        return (wert, 'umgebung') if gueltige_client_id(wert) else ('', '')

    def client_setzen(self, wert: str) -> None:
        wert = (wert or '').strip()
        if not self.keychain.available:
            raise MicrosoftFehler('kein_speicher')
        if not wert:
            self.keychain.delete(CLIENT_KEY)
            return
        if not gueltige_client_id(wert):
            raise ValueError('Die Kennung der App hat die Form 00000000-0000-0000-0000-000000000000.')
        self.keychain.set(CLIENT_KEY, json.dumps({'client_id': wert.lower()}))

    def stand(self) -> dict[str, Any]:
        kennung, herkunft = self.client_id()
        return {'configured': bool(kennung), 'quelle': herkunft or None, 'secure_storage': bool(self.keychain.available),
                'client_id': kennung or None}

    # Mandant -----------------------------------------------------------------------------------------------------

    def mandant(self, adresse: str) -> str:
        """Der Mandant für die Anmeldung: Vorgabe, sonst die Kennung aus der OpenID-Beschreibung der Domain."""
        vorgabe = (os.environ.get(TENANT_ENV) or '').strip()
        if vorgabe:
            return vorgabe
        domain = domain_von(adresse)
        if not domain:
            return 'organizations'
        if domain in PRIVATE_DOMAINS:
            return 'consumers'
        status, inhalt = self.request('GET', f'{login_basis()}/{domain}/v2.0/.well-known/openid-configuration')
        if status == 200:
            treffer = re.search(r'/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/',
                                str(inhalt.get('issuer') or ''))
            if treffer:
                return treffer.group(1)
        if status == 400 and grund_aus(inhalt) == 'unbekannte_domain':
            raise MicrosoftFehler('unbekannte_domain')
        return 'organizations'

    # Gerätecode --------------------------------------------------------------------------------------------------

    def _aufraeumen(self) -> None:
        jetzt = self.clock()
        self.offen = {k: v for k, v in self.offen.items() if v['ablauf'] + 600 > jetzt}

    def beginnen(self, adresse: str = '', mitschriften: bool = False) -> dict[str, Any]:
        """Holt einen Code bei Microsoft. Gibt nur zurück, was der Mensch sehen soll; der Gerätecode bleibt hier."""
        kennung, _ = self.client_id()
        if not self.keychain.available:
            raise MicrosoftFehler('kein_speicher')
        if not kennung:
            raise MicrosoftFehler('keine_app')
        scopes = nur_lesend(scopes_fuer(mitschriften))
        with self.lock:
            self._aufraeumen()
            if sum(1 for v in self.offen.values() if v['status'] == 'waiting') >= OFFEN_HOECHSTENS:
                raise ValueError('Es laufen schon mehrere Anmeldungen. Bitte eine abschließen oder abbrechen.')
        mandant = self.mandant(adresse)
        status, inhalt = self.request('POST', f'{login_basis()}/{mandant}/oauth2/v2.0/devicecode',
                                      data={'client_id': kennung, 'scope': scopes})
        if status != 200 or not inhalt.get('device_code') or not inhalt.get('user_code'):
            raise MicrosoftFehler(grund_aus(inhalt) if status >= 400 else 'unbekannt')
        jetzt = self.clock()
        dauer = int(inhalt.get('expires_in') or CODE_DAUER)
        sitzung = secrets.token_urlsafe(24)
        eintrag = {
            'adresse': adresse.strip(), 'mandant': mandant, 'client_id': kennung, 'mitschriften': mitschriften,
            'device_code': inhalt['device_code'], 'user_code': str(inhalt['user_code']),
            'verification_uri': str(inhalt.get('verification_uri') or DEVICELOGIN),
            'ablauf': jetzt + max(60, min(dauer, 3600)), 'intervall': max(INTERVALL, int(inhalt.get('interval') or 0)),
            'naechste': jetzt, 'status': 'waiting', 'fragt': False,
        }
        eintrag['naechste'] = jetzt + eintrag['intervall']
        with self.lock:
            self.offen[sitzung] = eintrag
        return {'sitzung': sitzung, **self.ansicht(eintrag)}

    def ansicht(self, eintrag: dict[str, Any]) -> dict[str, Any]:
        """Was die Oberfläche von einer Anmeldung sieht: nie Gerätecode oder Token."""
        sicht = {'status': eintrag['status'], 'user_code': eintrag['user_code'],
                 'verification_uri': eintrag['verification_uri'],
                 'restsekunden': max(0, int(eintrag['ablauf'] - self.clock())), 'mitschriften': eintrag['mitschriften']}
        for schluessel in ('grund', 'satz', 'email', 'name', 'ohne_mitschriften'):
            if eintrag.get(schluessel) is not None:
                sicht[schluessel] = eintrag[schluessel]
        return sicht

    def _scheitern(self, eintrag: dict[str, Any], grund: str) -> None:
        if eintrag['mitschriften'] and grund == 'admin':
            grund = 'admin_mitschriften'
        eintrag.update(status='expired' if grund == 'abgelaufen' else 'cancelled' if grund == 'abgebrochen' else 'failed',
                       grund=grund, satz=GRUENDE.get(grund, GRUENDE['unbekannt']))
        eintrag.pop('device_code', None)

    def nachfragen(self, sitzung: str) -> dict[str, Any] | None:
        """Fragt bei Microsoft nach, ob die Anmeldung fertig ist; höchstens so oft, wie Microsoft es erlaubt."""
        with self.lock:
            self._aufraeumen()
            eintrag = self.offen.get(sitzung)
            if eintrag is None:
                return None
            if eintrag['status'] != 'waiting' or eintrag['fragt'] or self.clock() < eintrag['naechste']:
                return self.ansicht(eintrag)
            if self.clock() >= eintrag['ablauf']:
                self._scheitern(eintrag, 'abgelaufen')
                return self.ansicht(eintrag)
            eintrag['fragt'] = True
            device_code, kennung, mandant = eintrag['device_code'], eintrag['client_id'], eintrag['mandant']
        try:
            status, inhalt = self.request('POST', f'{login_basis()}/{mandant}/oauth2/v2.0/token', data={
                'grant_type': 'urn:ietf:params:oauth:grant-type:device_code', 'client_id': kennung,
                'device_code': device_code})
            ergebnis = self._auswerten(eintrag, status, inhalt)
        except MicrosoftFehler as exc:
            # Kein Netz ist kein Ende: Der Code gilt weiter, die nächste Nachfrage versucht es wieder.
            ergebnis = None
            with self.lock:
                eintrag['netz'] = exc.satz if exc.grund == 'nicht_erreichbar' else None
                if exc.grund != 'nicht_erreichbar':
                    self._scheitern(eintrag, exc.grund)
        finally:
            with self.lock:
                eintrag['fragt'] = False
                eintrag['naechste'] = self.clock() + eintrag['intervall']
        with self.lock:
            sicht = self.ansicht(eintrag)
            if eintrag.get('netz') and eintrag['status'] == 'waiting':
                sicht['hinweis'] = eintrag['netz']
            return sicht if ergebnis is None else {**sicht, **ergebnis}

    def _auswerten(self, eintrag: dict[str, Any], status: int, inhalt: dict[str, Any]) -> dict[str, Any] | None:
        if status == 200 and inhalt.get('access_token'):
            gewaehrt = erteilt(inhalt.get('scope', ''))
            if not PFLICHT <= gewaehrt or not inhalt.get('refresh_token'):
                with self.lock:
                    self._scheitern(eintrag, 'unvollstaendig')
                return None
            code, ich = self.request('GET', f'{graph_basis()}/me', params={'$select': 'mail,userPrincipalName,displayName'},
                                     headers={'Authorization': 'Bearer ' + inhalt['access_token']})
            adresse = str(ich.get('mail') or ich.get('userPrincipalName') or '').strip()
            if code != 200 or not re.fullmatch(r'[^\s@\x00-\x1f]+@[^\s@\x00-\x1f]+', adresse):
                with self.lock:
                    self._scheitern(eintrag, 'unbekannt')
                return None
            with self.lock:
                eintrag.update(status='ready', email=adresse, name=str(ich.get('displayName') or '')[:120],
                               ohne_mitschriften=bool(eintrag['mitschriften'] and MITSCHRIFT_SCOPE not in gewaehrt),
                               grant={'client_id': eintrag['client_id'], 'mandant': eintrag['mandant'],
                                      'refresh_token': inhalt['refresh_token'], 'scope': ' '.join(sorted(gewaehrt))})
                eintrag.pop('device_code', None)
            return None
        fehler = str(inhalt.get('error') or '')
        with self.lock:
            if fehler == 'authorization_pending':
                return None
            if fehler == 'slow_down':
                # RFC 8628, 3.5: Das Intervall wächst um fünf Sekunden, für diese und alle weiteren Nachfragen.
                eintrag['intervall'] += 5
                return None
            self._scheitern(eintrag, grund_aus(inhalt))
        return None

    def abbrechen(self, sitzung: str) -> None:
        with self.lock:
            eintrag = self.offen.get(sitzung)
            if eintrag is not None and eintrag['status'] in ('waiting', 'ready'):
                self._scheitern(eintrag, 'abgebrochen')
                eintrag.pop('grant', None)

    def uebernehmen(self, sitzung: str) -> dict[str, Any]:
        """Gibt den Zugang einer fertigen Anmeldung zum Speichern heraus. Nur einmal; der Aufrufer hält `lock`."""
        eintrag = self.offen.get(sitzung)
        if eintrag is None or eintrag['status'] != 'ready' or 'grant' not in eintrag:
            raise ValueError('Diese Anmeldung ist nicht zur Übernahme bereit.')
        return eintrag

    # Zugriffstoken -----------------------------------------------------------------------------------------------

    def zugang(self, adresse: str) -> dict[str, Any] | None:
        """Der gespeicherte Zugang eines Kontos ohne das Geheimnis: erteilte Scopes und Mandant."""
        roh = self.keychain.get(konto_schluessel(adresse)) if self.keychain.available else None
        if not roh:
            return None
        try:
            grant = json.loads(roh)
        except ValueError:
            return None
        return {'scopes': sorted(erteilt(grant.get('scope', ''))), 'mandant': grant.get('mandant', '')}

    def access_token(self, adresse: str) -> str:
        """Ein Zugriffstoken für das Konto; wird bis kurz vor Ablauf wiederverwendet, sonst einmal erneuert."""
        schluessel = konto_schluessel(adresse)
        with self.lock:
            sperre = self.refresh_locks.setdefault(schluessel, threading.Lock())
        with sperre:
            with self.lock:
                roh = self.keychain.get(schluessel) if self.keychain.available else None
                if not roh:
                    self.tokens.pop(schluessel, None)
                    raise MicrosoftFehler('abgemeldet')
                gemerkt = self.tokens.get(schluessel)
                # Gilt nur für genau diesen Zugang: neu angemeldet oder Refresh-Token getauscht = anderer Inhalt.
                if gemerkt and gemerkt['raw'] == roh and self.clock() < gemerkt['until']:
                    return gemerkt['token']
            try:
                grant = json.loads(roh)
                scopes = nur_lesend(sorted(erteilt(grant['scope']) & ERLAUBT))
                status, inhalt = self.request('POST', f"{login_basis()}/{grant['mandant']}/oauth2/v2.0/token", data={
                    'grant_type': 'refresh_token', 'client_id': grant['client_id'],
                    'refresh_token': grant['refresh_token'], 'scope': scopes})
            except (KeyError, ValueError, TypeError):
                raise MicrosoftFehler('abgemeldet') from None
            if status != 200 or not inhalt.get('access_token'):
                grund = grund_aus(inhalt)
                raise MicrosoftFehler('abgemeldet' if grund in ('unbekannt', 'admin', 'abgelaufen') else grund)
            with self.lock:
                if inhalt.get('refresh_token'):
                    # Microsoft gibt beim Erneuern einen neuen Refresh-Token aus; der alte läuft später ab.
                    grant['refresh_token'] = inhalt['refresh_token']
                    roh = json.dumps(grant)
                    self.keychain.set(schluessel, roh)
                self._merken(schluessel, roh, inhalt)
            return inhalt['access_token']

    def _merken(self, schluessel: str, roh: str, token: dict[str, Any]) -> None:
        dauer = token.get('expires_in')
        if isinstance(dauer, str) and dauer.isdigit():
            dauer = int(dauer)
        if isinstance(dauer, (int, float)) and dauer > TOKEN_MARGIN:
            self.tokens[schluessel] = {'raw': roh, 'token': token['access_token'],
                                       'until': self.clock() + dauer - TOKEN_MARGIN}
        else:
            self.tokens.pop(schluessel, None)

    def vergessen(self, adresse: str) -> None:
        """Entfernt den Zugang eines Kontos aus Schlüsselspeicher und Arbeitsspeicher."""
        schluessel = konto_schluessel(adresse)
        with self.lock:
            self.tokens.pop(schluessel, None)
            if self.keychain.available:
                self.keychain.delete(schluessel)


__all__ = ['CLIENT_ENV', 'DEVICELOGIN', 'ERLAUBT', 'GRAPH_ENV', 'GRUENDE', 'GRUND_SCOPES', 'LOGIN_ENV',
           'MITSCHRIFT_SCOPE', 'MicrosoftAnmeldung', 'MicrosoftFehler', 'erteilt', 'graph_basis',
           'grund_aus', 'konto_schluessel', 'login_basis', 'nur_lesend', 'scopes_fuer']
