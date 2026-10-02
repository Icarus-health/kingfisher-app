"""Ob sich ein Postfach anmelden lässt, und wenn nicht: warum, in einem Satz.

Früher meldete „Postfach verbinden“ sofort „Dein Postfach ist verbunden“, auch wenn der Server nicht
erreichbar und das Passwort erfunden war (Fremdprobe, Befund 3). Jetzt wird beim Verbinden einmal angemeldet,
mit fester Zeitgrenze, und erst eine gelungene Anmeldung macht aus den Angaben ein Konto.

Dieselbe Prüfung beantwortet die Frage der Fertig-Seite, ob ein verbundenes Postfach gerade antwortet
(`GET /api/v1/mail/erreichbar`, Befund 5), und übersetzt die Fehler beim Einlesen (Befund 4).

Die Gründe, jeweils ein Satz für den Nutzer:

* `nicht_erreichbar`: keine Antwort in der Zeitgrenze, Name nicht auflösbar, Verbindung abgelehnt.
* `imap_aus`: der Anbieter sagt ausdrücklich, dass IMAP ausgeschaltet ist.
* `app_passwort`: der Anbieter verlangt ein App-Passwort (Google, Apple, Microsoft …); bei Google „App-Passwort nötig“
  mit dem Weg dorthin, erkannt am Server oder an Googles typischer Ablehnung (Fremdprobe, Befund 2).
* `passwort`: die Anmeldung wurde abgelehnt. Bei Anbietern, bei denen IMAP erst eingeschaltet werden muss (WEB.DE,
  GMX), sagt der Server dann dasselbe wie bei einem falschen Passwort; der Satz nennt deshalb beides.
* `unsicher`: die Verbindung ließ sich nicht verschlüsselt aufbauen (Zertifikat).
"""
from __future__ import annotations

import imaplib
import ssl
from typing import Any

from .zeitgrenze import mit_zeitgrenze

#: So lange wartet „Postfach verbinden“ höchstens auf die Anmeldung (Sekunden, Wanduhr).
ZEITGRENZE = 10.0
#: Netzzeitgrenze je Schritt der Verbindung; die Wanduhr oben fängt auch eine hängende Namensauflösung.
NETZ_ZEITGRENZE = 8.0

_IMAP_AUS = ('imap is disabled', 'imap access is disabled', 'imap not enabled', 'imap is not enabled',
             'imap access not enabled', 'imap deaktiviert', 'imap nicht aktiviert', 'imap ist deaktiviert',
             'imap ist nicht aktiviert', 'imap nicht freigeschaltet', 'enable imap')
_APP_PASSWORT = ('application-specific password', 'app password', 'app-passwort', 'web browser', 'webloginrequired',
                 'basicauthblocked', 'basic authentication is disabled')
#: So lehnt Gmail eine Anmeldung ab (Fremdprobe, Befund 2): mit dem normalen Passwort „Invalid credentials (Failure)“
#: oder „Application-specific password required“ mit einem Verweis auf support.google.com.
_GOOGLE = ('invalid credentials (failure)', 'support.google.com')
GOOGLE_HOST = 'imap.gmail.com'
GOOGLE_SATZ = ('App-Passwort nötig: Google lehnt das normale Passwort ab; erzeuge auf der Google-Seite '
               '„App-Passwörter“ ein App-Passwort (dafür muss die Bestätigung in zwei Schritten eingeschaltet sein) '
               'und trage es hier ein.')


class Anmeldefehler(Exception):
    """Die Anmeldung gelang nicht. `satz` ist für den Nutzer, `grund` für die Oberfläche und Tests."""

    def __init__(self, grund: str, satz: str) -> None:
        super().__init__(satz)
        self.grund = grund
        self.satz = satz

    def __str__(self) -> str:
        return self.satz

    @property
    def status(self) -> int:
        """HTTP-Status: abgelehnt ist eine Frage der Angaben (422), keine Antwort eine des Netzes (503)."""
        return 503 if self.grund in ('nicht_erreichbar', 'unsicher') else 422


def anbieter_name(imap_host: str, vorgabe: str = '') -> str:
    """Wie der Nutzer den Anbieter kennt („WEB.DE“), nicht der Servername.

    Ohne Katalogeintrag: `vorgabe` (der Name eines schon verbundenen Postfachs, etwa „Privat antwortet gerade nicht“),
    sonst der Server („Der Mailserver mail.example.org“). Beim Hinzufügen eines Postfachs gibt es keine Vorgabe: Der
    selbst vergebene Name hat die Anmeldung nicht abgelehnt, der Server war es (Fremdprobe 2, Befund 4).
    """
    from .providers_mail import PROVIDERS
    host = (imap_host or '').strip().lower()
    for anbieter in PROVIDERS:
        if anbieter.imap_host.lower() == host:
            return anbieter.label
    if vorgabe:
        return vorgabe
    return f'Der Mailserver {host}' if host else 'Der Mailserver'


def _imap_muss_an(imap_host: str) -> bool:
    from .providers_mail import PROVIDERS
    host = (imap_host or '').strip().lower()
    return any(p.imap_host.lower() == host and 'IMAP' in p.hint for p in PROVIDERS)


def einordnen(fehler: BaseException, imap_host: str, name: str = '') -> Anmeldefehler:
    """Macht aus einem Fehler von `imaplib`, `ssl`, `socket` oder der Zeitgrenze einen Satz mit Grund."""
    wer = anbieter_name(imap_host, name)
    if isinstance(fehler, Anmeldefehler):
        return fehler
    if isinstance(fehler, imaplib.IMAP4.error) and not isinstance(fehler, imaplib.IMAP4.abort):
        text = str(fehler).lower()
        if any(merkmal in text for merkmal in _IMAP_AUS):
            return Anmeldefehler('imap_aus', f'{wer} lässt die Anmeldung über IMAP nicht zu: Schalte IMAP in den '
                                             'Einstellungen deines Postfachs ein und versuche es dann noch einmal.')
        if (imap_host or '').strip().lower() == GOOGLE_HOST or any(merkmal in text for merkmal in _GOOGLE):
            # Bei Gmail ist eine Ablehnung praktisch immer das fehlende App-Passwort, auch wenn das Passwort stimmt.
            return Anmeldefehler('app_passwort', GOOGLE_SATZ)
        if any(merkmal in text for merkmal in _APP_PASSWORT):
            return Anmeldefehler('app_passwort', f'{wer} verlangt ein App-Passwort statt deines normalen Passworts; '
                                                 'erzeuge eines beim Anbieter und trage es hier ein.')
        if _imap_muss_an(imap_host):
            return Anmeldefehler('passwort', f'{wer} hat die Anmeldung abgelehnt: Das Passwort stimmt nicht, oder IMAP '
                                             'ist in den Einstellungen deines Postfachs noch nicht eingeschaltet.')
        return Anmeldefehler('passwort', f'{wer} hat die Anmeldung abgelehnt: Adresse oder Passwort stimmen nicht.')
    if isinstance(fehler, ssl.SSLError):
        return Anmeldefehler('unsicher', f'{wer} ließ sich nicht sicher (verschlüsselt) erreichen; '
                                         'bitte später noch einmal versuchen.')
    # Zeitgrenze, Namensauflösung, abgelehnte Verbindung, Abbruch mitten im Gespräch: keine Antwort.
    return Anmeldefehler('nicht_erreichbar', f'{wer} antwortet gerade nicht. Prüfe die Internetverbindung und '
                                             'versuche es gleich noch einmal.')


def pruefe(connector: Any, imap_host: str, *, name: str = '', sekunden: float | None = None) -> None:
    """Meldet sich einmal an (`connector.pruefe_anmeldung`), höchstens `sekunden` lang. Wirft `Anmeldefehler`."""
    sekunden = ZEITGRENZE if sekunden is None else sekunden
    try:
        mit_zeitgrenze(lambda: connector.pruefe_anmeldung(timeout=min(NETZ_ZEITGRENZE, sekunden)), sekunden)
    except Exception as exc:  # noqa: BLE001 - jeder Fehler wird zu genau einem Satz
        raise einordnen(exc, imap_host, name) from None


__all__ = ['Anmeldefehler', 'NETZ_ZEITGRENZE', 'ZEITGRENZE', 'anbieter_name', 'einordnen', 'pruefe']
