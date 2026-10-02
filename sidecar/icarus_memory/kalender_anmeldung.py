"""Kalender wie Mail: Die Adresse genügt, Kingfisher findet den Kalender selbst (Fremdprobe, Befund 7).

Früher verlangte „Kalender hinzufügen“ für ein WEB.DE-Konto eine „HTTPS-Abonnement-Adresse“ oder eine CalDAV-Adresse.
Das weiß außerhalb der IT niemand. Jetzt reicht die Mailadresse: Der Anbieter wird an ihr erkannt (`providers_mail`),
die Adresse seines Kalenderdienstes steht im Katalog, und Kingfisher sucht dort selbst nach den Kalendern
(RFC 6764 und RFC 4791: `current-user-principal`, `calendar-home-set`, die Kalender darunter). Gefragt wird nur
nach dem Passwort bzw. App-Passwort, und bevor etwas gespeichert wird, meldet sich Kingfisher einmal an, mit fester
Zeitgrenze, wie beim Postfach (Befund 3). Scheitert das, kommt der Grund in einem Satz, und es wird nichts angelegt.

Kennt der Katalog die Adresse nicht (eigene Domain), sucht Kingfisher den Kalender selbst (Fremdprobe 2, Befund 5):
zuerst per DNS (`_caldavs._tcp.<domain>`, RFC 6764, mit dem Pfad aus dem TXT-Eintrag), dann unter
`/.well-known/caldav` auf dem Mailserver der Domain (dem Server, bei dem das Postfach liegt). Bevor dort ein Passwort
hingeht, fragt Kingfisher ohne Passwort, ob unter dieser Adresse überhaupt ein Kalenderdienst antwortet. Erst wenn
beides nichts findet, sagt Kingfisher ehrlich, dass es die Adresse des Kalenders braucht, und bietet ein Feld an. Bei Google und Microsoft gibt es keinen Kalenderzugang mit
Passwort; dann steht der Satz aus dem Katalog da (`caldav_note`), bei Google mit dem Weg über die geheime
iCal-Adresse (`kalender_abo.py`, Befund 2).

Die Gründe (`Anmeldefehler.grund`), jeweils ein Satz für den Nutzer:

* `nicht_erreichbar`: keine Antwort in der Zeitgrenze, Name nicht auflösbar, Verbindung abgelehnt.
* `passwort`: der Dienst lehnt die Anmeldung ab (401/403); bei Anbietern mit App-Passwort sagt der Satz das.
* `unsicher`: keine verschlüsselte Verbindung (Zertifikat).
* `kein_kalender`: angemeldet, aber unter der Adresse ist kein Kalender mit Terminen zu finden.
* `adresse_fehlt`: der Anbieter ist unbekannt, und es wurde keine Adresse angegeben.
* `kein_zugang`: der Anbieter bietet keinen Kalenderzugang mit Passwort an (Google, Microsoft).

Was den Rechner verlässt: nur Adresse und Passwort, nur an den Kalenderdienst des eigenen Anbieters, und erst auf
den Klick „Kalender verbinden“.
"""
from __future__ import annotations

import ssl
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from .mail_anmeldung import Anmeldefehler
from .zeitgrenze import mit_zeitgrenze

#: So lange wartet „Kalender verbinden“ höchstens auf Anmeldung und Suche (Sekunden, Wanduhr).
ZEITGRENZE = 10.0
#: Netzzeitgrenze je Anfrage; die Wanduhr oben fängt auch eine hängende Namensauflösung.
NETZ_ZEITGRENZE = 8.0
#: Mehr Kalender legt ein Klick nicht an (ein Konto mit Dutzenden geteilter Kalender wäre sonst unübersichtlich).
HOECHSTENS = 20

_DAV, _CALDAV = 'DAV:', 'urn:ietf:params:xml:ns:caldav'
_PRINCIPAL = ('<?xml version="1.0" encoding="utf-8"?><d:propfind xmlns:d="DAV:"><d:prop>'
              '<d:current-user-principal/><d:resourcetype/></d:prop></d:propfind>')
_HOME = ('<?xml version="1.0" encoding="utf-8"?><d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
         '<d:prop><c:calendar-home-set/></d:prop></d:propfind>')
_KALENDER = ('<?xml version="1.0" encoding="utf-8"?><d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
             '<d:prop><d:resourcetype/><d:displayname/><c:supported-calendar-component-set/></d:prop></d:propfind>')


@dataclass(frozen=True)
class Kalender:
    url: str
    name: str


def _q(ns: str, name: str) -> str:
    return f'{{{ns}}}{name}'


class _Sitzung:
    """Eine Anmeldung bei einem Kalenderdienst: PROPFIND mit Benutzer und Passwort, Fehler als Satz."""

    def __init__(self, benutzer: str, passwort: str, wer: str, app_passwort: bool,
                 transport: httpx.BaseTransport | None = None) -> None:
        self.wer, self.app_passwort = wer, app_passwort
        self.client = httpx.Client(auth=(benutzer, passwort), timeout=NETZ_ZEITGRENZE, follow_redirects=True,
                                   transport=transport)

    def propfind(self, url: str, koerper: str, tiefe: str) -> list[ET.Element]:
        antwort = self.client.request('PROPFIND', url, content=koerper.encode('utf-8'),
                                      headers={'Depth': tiefe, 'Content-Type': 'application/xml; charset=utf-8'})
        if antwort.status_code in (401, 403):
            if self.app_passwort:
                raise Anmeldefehler('passwort', f'{self.wer} hat die Anmeldung abgelehnt: Für den Kalender braucht '
                                                'es ein App-Passwort; erzeuge eines beim Anbieter und trage es hier ein.')
            raise Anmeldefehler('passwort', f'{self.wer} hat die Anmeldung abgelehnt: Adresse oder Passwort stimmen nicht.')
        if antwort.status_code in (404, 405, 501):
            return []
        if antwort.status_code != 207:
            raise Anmeldefehler('nicht_erreichbar', f'{self.wer} antwortet gerade nicht richtig. Bitte versuche es '
                                                    'gleich noch einmal.')
        try:
            wurzel = ET.fromstring(antwort.content)
        except ET.ParseError:
            return []
        basis = str(antwort.url)
        for href in wurzel.iter(_q(_DAV, 'href')):  # jede Adresse relativ zur Antwortadresse auflösen
            if href.text:
                href.text = urljoin(basis, href.text.strip())
        return wurzel.findall(_q(_DAV, 'response'))

    def schliessen(self) -> None:
        self.client.close()


def _href_in(eintraege: list[ET.Element], eigenschaft: str, ns: str = _DAV) -> str | None:
    for eintrag in eintraege:
        fund = eintrag.find(f'.//{_q(ns, eigenschaft)}/{_q(_DAV, "href")}')
        if fund is not None and fund.text:
            return fund.text.strip()
    return None


def _ist_kalender(eintrag: ET.Element) -> bool:
    return eintrag.find(f'.//{_q(_DAV, "resourcetype")}/{_q(_CALDAV, "calendar")}') is not None


def _mit_terminen(eintrag: ET.Element) -> bool:
    """Ein Kalender ohne Angabe nimmt alles; einer mit Angabe nur, wenn Termine (VEVENT) dabei sind."""
    komponenten = eintrag.findall(f'.//{_q(_CALDAV, "supported-calendar-component-set")}/{_q(_CALDAV, "comp")}')
    return not komponenten or any((k.get('name') or '').upper() == 'VEVENT' for k in komponenten)


def _absolut(basis: str, href: str) -> str:
    return urljoin(basis, href)


def _suchen(sitzung: _Sitzung, start: str) -> list[Kalender]:
    # 1. Wer bin ich? Am Startpunkt, sonst am bekannten Ort des Hosts (RFC 6764).
    teile = urlsplit(start)
    wohlbekannt = f'{teile.scheme}://{teile.netloc}/.well-known/caldav'
    principal, direkt = None, []
    for ort in dict.fromkeys((start, wohlbekannt)):
        eintraege = sitzung.propfind(ort, _PRINCIPAL, '0')
        direkt = [e for e in eintraege if _ist_kalender(e)]
        if direkt:  # die Adresse zeigt schon auf einen Kalender
            href = direkt[0].find(_q(_DAV, 'href'))
            return [Kalender(url=_absolut(ort, href.text if href is not None and href.text else ort), name='Kalender')]
        principal = _href_in(eintraege, 'current-user-principal')
        if principal:
            break
    if not principal:
        return []
    # 2. Wo liegen meine Kalender?
    heim = _href_in(sitzung.propfind(principal, _HOME, '0'), 'calendar-home-set', _CALDAV) or principal
    # 3. Welche Kalender mit Terminen gibt es dort?
    gefunden: list[Kalender] = []
    for eintrag in sitzung.propfind(heim, _KALENDER, '1'):
        href = eintrag.find(_q(_DAV, 'href'))
        if href is None or not href.text or not _ist_kalender(eintrag) or not _mit_terminen(eintrag):
            continue
        name = (eintrag.findtext(f'.//{_q(_DAV, "displayname")}') or '').strip()
        url = href.text.strip()
        gefunden.append(Kalender(url=url, name=name or url.rstrip('/').rsplit('/', 1)[-1] or 'Kalender'))
    return gefunden[:HOECHSTENS]


def finde_kalender(start: str, benutzer: str, passwort: str, *, wer: str, app_passwort: bool = False,
                   sekunden: float | None = None, transport: httpx.BaseTransport | None = None) -> list[Kalender]:
    """Meldet sich an und sucht die Kalender, höchstens `sekunden` lang. Wirft `Anmeldefehler`."""
    if not start.startswith('https://'):
        raise Anmeldefehler('adresse_fehlt', 'Die Adresse des Kalenders muss mit https:// beginnen.')
    sekunden = ZEITGRENZE if sekunden is None else sekunden
    sitzung = _Sitzung(benutzer, passwort, wer, app_passwort, transport)
    try:
        kalender = mit_zeitgrenze(lambda: _suchen(sitzung, start), sekunden)
    except Anmeldefehler:
        raise
    except (ssl.SSLError, httpx.ConnectError) as exc:
        if isinstance(exc, ssl.SSLError) or 'CERTIFICATE' in str(exc).upper() or 'SSL' in str(exc).upper():
            raise Anmeldefehler('unsicher', f'Die Verbindung zu {wer} ließ sich nicht sicher aufbauen; '
                                            'bitte später noch einmal versuchen.') from None
        raise Anmeldefehler('nicht_erreichbar', f'{wer} antwortet gerade nicht. Prüfe die Internetverbindung und '
                                                'versuche es gleich noch einmal.') from None
    except Exception:  # noqa: BLE001 - Zeitgrenze, Namensauflösung, Abbruch: keine Antwort
        raise Anmeldefehler('nicht_erreichbar', f'{wer} antwortet gerade nicht. Prüfe die Internetverbindung und '
                                                'versuche es gleich noch einmal.') from None
    finally:
        sitzung.schliessen()
    if not kalender:
        raise Anmeldefehler('kein_kalender', f'Die Anmeldung bei {wer} hat geklappt, aber unter dieser Adresse habe ich '
                                             'keinen Kalender mit Terminen gefunden. Prüfe die Adresse des Kalenders.')
    return kalender


ADRESSE_FEHLT = ('Für diesen Anbieter brauche ich die Adresse deines Kalenders. Bei deinem Mailserver habe ich keinen '
                 'gefunden; dein Anbieter nennt sie in seiner Anleitung für Kalender-Programme (oft „CalDAV“). Du kannst '
                 'den Kalender auch überspringen; das schadet nichts.')


def _antwortet_als_kalender(url: str, transport: httpx.BaseTransport | None) -> bool:
    """Antwortet unter `url` ein Kalenderdienst? Gefragt wird ohne Passwort: 207, 401 oder eine Weiterleitung."""
    try:
        with httpx.Client(timeout=NETZ_ZEITGRENZE / 2, follow_redirects=False, transport=transport) as client:
            antwort = client.request('PROPFIND', url, content=_PRINCIPAL.encode('utf-8'),
                                     headers={'Depth': '0', 'Content-Type': 'application/xml; charset=utf-8'})
    except (httpx.HTTPError, OSError, ValueError):
        return False
    return antwort.status_code in (207, 401, 301, 302, 307, 308)


def _host(text: str) -> str:
    host = (text or '').strip().lower().rstrip('.')
    return host if host and set(host) <= set('abcdefghijklmnopqrstuvwxyz0123456789-.') and '..' not in host else ''


def eigener_kalender(domain: str, mailserver: str = '', *, dns=None, transport: httpx.BaseTransport | None = None,
                     sekunden: float = 6.0) -> str | None:
    """Wo der Kalender einer eigenen Domain liegt: SRV `_caldavs._tcp` (mit Pfad aus TXT), sonst `/.well-known/caldav`
    auf dem Mailserver. `None`, wenn nichts antwortet. Hinaus gehen nur die Domain (an den Namensdienst) und eine
    Anfrage ohne Passwort an den Mailserver der Domain."""
    if dns is None:
        from .dns_abfrage import abfragen as dns

    def suchen() -> str | None:
        name = f'_caldavs._tcp.{domain}'
        eintraege = []
        for zeile in dns(name, 'SRV'):
            teile = zeile.split()
            if len(teile) == 4 and all(t.isdigit() for t in teile[:3]):
                if teile[3] in ('.', ''):
                    eintraege = []
                    break
                if _host(teile[3]):
                    eintraege.append((int(teile[0]), -int(teile[1]), int(teile[2]), _host(teile[3])))
        if eintraege:
            _, _, port, ziel = sorted(eintraege)[0]
            pfad = next((t.split('=', 1)[1] for t in dns(name, 'TXT') if t.startswith('path=')), '/')
            pfad = pfad if pfad.startswith('/') else '/' + pfad
            return f'https://{ziel}{"" if port == 443 else f":{port}"}{pfad}'
        host = _host(mailserver)
        if host:
            ort = f'https://{host}/.well-known/caldav'
            if _antwortet_als_kalender(ort, transport):
                return ort
        return None

    try:
        return mit_zeitgrenze(suchen, sekunden)
    except Exception:  # noqa: BLE001 - Zeitgrenze oder Fehler: nicht gefunden
        return None


def startpunkt(adresse: str, url: str | None, *, mailserver: str = '', dns=None,
               transport: httpx.BaseTransport | None = None):
    """Anbieter und Startadresse zur Mailadresse. Wirft `Anmeldefehler`, wenn es keinen Weg gibt.

    `mailserver`: der Server, bei dem das Postfach dieser Adresse liegt (für eine eigene Domain, Befund 5)."""
    from .providers_mail import guess
    anbieter = guess(adresse)
    eigene = (url or '').strip()
    if eigene:
        return anbieter, eigene
    if anbieter is not None and anbieter.caldav_note:
        raise Anmeldefehler('kein_zugang', anbieter.caldav_note)
    if anbieter is not None and anbieter.caldav_url:
        return anbieter, anbieter.caldav_url
    domain = adresse.strip().rpartition('@')[2].lower()
    gefunden = eigener_kalender(domain, mailserver, dns=dns, transport=transport) if '.' in domain else None
    if gefunden is None:
        raise Anmeldefehler('adresse_fehlt', ADRESSE_FEHLT)
    return anbieter, gefunden


__all__ = ['ADRESSE_FEHLT', 'HOECHSTENS', 'Kalender', 'eigener_kalender', 'NETZ_ZEITGRENZE', 'ZEITGRENZE', 'finde_kalender', 'startpunkt']
