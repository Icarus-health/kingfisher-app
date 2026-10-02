"""Den Mailserver einer eigenen Domain selbst finden (Fremdprobe 2, Befund 2).

Eine Adresse wie `lena.probe@example.org` (Hoster, Verein, Kanzlei, Praxis) steht in keinem Katalog. Früher hieß es dann
„Servereinstellungen“, „IMAP-Server“, „IMAP-Port“ und „Die Angaben stehen auf der Hilfeseite deines Mailanbieters“:
nachschlagen, abtippen. Dabei hat die Domain diese Angaben oft schon selbst veröffentlicht, genau dafür, dass
Mailprogramme sie finden. Kingfisher sieht dort nach, in dieser Reihenfolge, jeweils mit Zeitgrenze:

1. **DNS-SRV** (RFC 6186): `_imaps._tcp.<domain>` nennt den Postfachserver samt Port, `_submission._tcp.<domain>` den
   Versandserver. Ein Ziel `.` heißt ausdrücklich „gibt es hier nicht“.
2. **Autoconfig** im Thunderbird-Format: `https://autoconfig.<domain>/mail/config-v1.1.xml`, dann
   `https://<domain>/.well-known/autoconfig/mail/config-v1.1.xml`. Nur HTTPS mit gültigem Zertifikat, keine
   Weiterleitung, höchstens 64 KB, kein DOCTYPE.
3. **Mailserver (MX) gegen den Katalog**: Die Domain liegt bei einem bekannten Hoster (IONOS, STRATO, mailbox.org …,
   `providers_mail.MailProvider.mx`), oder bei einem Hoster, dessen MX zugleich der Postfachserver ist
   (`providers_mail.HOSTER_AM_MX`).

Genommen wird nur IMAP mit TLS (Port 993); Versand nur mit STARTTLS, sonst bleibt der Versand leer (Lesen geht dann
trotzdem). Ob die Angaben stimmen, zeigt die Anmeldung beim Verbinden (`mail_anmeldung.pruefe`); gespeichert wird erst
danach.

**Was den Rechner verlässt.** Nur die Domain, nie die ganze Adresse: als DNS-Anfrage an den Namensdienst des Rechners
(`dns_abfrage.py`) und als HTTPS-Abruf beim Server der Domain selbst (`autoconfig.<domain>`, `<domain>`). Keine zentrale
Datenbank im Netz, kein Dritter. Ein Fund gilt zehn Minuten (`MERKEN`); ein Nichtfund wird nicht gemerkt.

`transport` (Tests und Browserproben: ein `httpx`-Transport, der die Abrufe an eine Attrappe auf 127.0.0.1 lenkt)
ersetzt den Weg ins Netz; die Route nimmt ihn aus `app.state.autoconfig_transport`.
"""
from __future__ import annotations

import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Callable

import httpx

from .providers_mail import HOSTER_AM_MX, PROVIDERS, MailProvider

#: Zeitgrenze je HTTPS-Abruf (Sekunden).
ZEITGRENZE_HTTP = 3.0
#: So lange darf die ganze Suche höchstens dauern (Sekunden, Wanduhr; DNS hat je Frage 2 s).
ZEITGRENZE_GESAMT = 9.0
#: Größer ist keine Autoconfig-Datei.
HOECHSTENS_BYTES = 64 * 1024
#: So lange gilt ein Fund (Sekunden).
MERKEN = 600.0
IMAP_TLS_PORT = 993

Abfrage = Callable[[str, str], list[str]]

#: Der Weg ins Netz, wenn der Aufrufer keinen nennt; `None` ist das echte Netz. Tests setzen eine Attrappe.
TRANSPORT: httpx.BaseTransport | None = None

_gemerkt: dict[str, tuple[float, 'Fund']] = {}
_sperre = threading.Lock()


@dataclass(frozen=True)
class Fund:
    imap_host: str
    imap_port: int
    smtp_host: str
    smtp_port: int
    woran: str  # srv | autoconfig | mx
    label: str
    benutzer: str = 'adresse'

    def als_anbieter(self) -> MailProvider:
        """Wie ein Katalogeintrag, damit die Oberfläche denselben Weg nimmt: „Erkannt: …“, dann nur das Passwort."""
        return MailProvider(id='gefunden', label=self.label, imap_host=self.imap_host, smtp_host=self.smtp_host,
                            imap_port=self.imap_port, smtp_port=self.smtp_port, benutzer=self.benutzer)


def _host(text: str) -> str:
    """Ein Hostname, klein und ohne Punkt am Ende; leer, wenn er keiner ist."""
    host = (text or '').strip().lower().rstrip('.')
    erlaubt = set('abcdefghijklmnopqrstuvwxyz0123456789-.')
    return host if host and len(host) <= 253 and set(host) <= erlaubt and '..' not in host else ''


def _srv_eintraege(dns: Abfrage, name: str) -> list[tuple[int, int, int, str]] | None:
    """SRV-Einträge, nach Vorrang (klein zuerst) und Gewicht (groß zuerst). `None`: ausdrücklich „gibt es nicht“."""
    eintraege = []
    for zeile in dns(name, 'SRV'):
        teile = zeile.split()
        if len(teile) != 4 or not all(t.isdigit() for t in teile[:3]):
            continue
        vorrang, gewicht, port, ziel = int(teile[0]), int(teile[1]), int(teile[2]), teile[3]
        if ziel in ('.', ''):
            return None
        if _host(ziel) and 0 < port < 65536:
            eintraege.append((vorrang, -gewicht, port, _host(ziel)))
    return [(v, -g, p, z) for v, g, p, z in sorted(eintraege)]


def aus_srv(domain: str, dns: Abfrage) -> Fund | None:
    """RFC 6186: `_imaps._tcp` für das Postfach (nur TLS), `_submission._tcp` für den Versand."""
    imap = _srv_eintraege(dns, f'_imaps._tcp.{domain}')
    if not imap:
        return None
    _, _, imap_port, imap_host = imap[0]
    smtp = _srv_eintraege(dns, f'_submission._tcp.{domain}') or []
    smtp_host, smtp_port = (smtp[0][3], smtp[0][2]) if smtp else ('', 587)
    return Fund(imap_host, imap_port, smtp_host, smtp_port, 'srv', imap_host)


def autoconfig_adressen(domain: str) -> list[str]:
    """Die zwei Orte, an denen eine Domain ihre Einstellungen veröffentlicht (Thunderbird-Format). Ohne Mailadresse."""
    return [f'https://autoconfig.{domain}/mail/config-v1.1.xml',
            f'https://{domain}/.well-known/autoconfig/mail/config-v1.1.xml']


def lies_autoconfig(text: str, domain: str) -> Fund | None:
    """Liest eine `clientConfig` (Version 1.1): IMAP mit TLS, Versand mit STARTTLS. Kein DOCTYPE (keine Entitäten)."""
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        return None
    try:
        wurzel = ET.fromstring(text)
    except ET.ParseError:
        return None

    def feld(server: ET.Element, name: str) -> str:
        return (server.findtext(name) or '').strip()

    def setzen(wert: str) -> str:
        return wert.replace('%EMAILDOMAIN%', domain)

    imap = None
    for server in wurzel.iter('incomingServer'):
        if (server.get('type') or '').lower() != 'imap' or feld(server, 'socketType').upper() != 'SSL':
            continue
        host, port = _host(setzen(feld(server, 'hostname'))), feld(server, 'port')
        if host and port.isdigit() and 0 < int(port) < 65536:
            imap = (host, int(port), feld(server, 'username'))
            break
    if imap is None:
        return None
    smtp_host, smtp_port = '', 587
    for server in wurzel.iter('outgoingServer'):
        if (server.get('type') or '').lower() != 'smtp' or feld(server, 'socketType').upper() != 'STARTTLS':
            continue
        host, port = _host(setzen(feld(server, 'hostname'))), feld(server, 'port')
        if host and port.isdigit() and 0 < int(port) < 65536:
            smtp_host, smtp_port = host, int(port)
            break
    benutzer = 'lokalteil' if imap[2].upper() == '%EMAILLOCALPART%' else 'adresse'
    return Fund(imap[0], imap[1], smtp_host, smtp_port, 'autoconfig', imap[0], benutzer)


def aus_autoconfig(domain: str, transport: httpx.BaseTransport | None = None) -> Fund | None:
    transport = transport if transport is not None else TRANSPORT
    for adresse in autoconfig_adressen(domain):
        try:
            with httpx.Client(timeout=ZEITGRENZE_HTTP, follow_redirects=False, trust_env=False,
                              transport=transport) as client:
                with client.stream('GET', adresse, headers={'Accept': 'application/xml, text/xml'}) as antwort:
                    if antwort.status_code != 200:
                        continue
                    teile, groesse = [], 0
                    for stueck in antwort.iter_bytes():
                        groesse += len(stueck)
                        if groesse > HOECHSTENS_BYTES:
                            break
                        teile.append(stueck)
                    if groesse > HOECHSTENS_BYTES:
                        continue
        except (httpx.HTTPError, OSError, ValueError):
            continue
        fund = lies_autoconfig(b''.join(teile).decode('utf-8', errors='replace'), domain)
        if fund is not None:
            return fund
    return None


def _endet(host: str, endung: str) -> bool:
    return host == endung or host.endswith('.' + endung)


def aus_mx(domain: str, dns: Abfrage, mx: list[str] | None = None) -> Fund | None:
    """Der Mailserver der Domain liegt bei einem Hoster aus dem Katalog. `mx`: schon gefragt (nicht zweimal fragen)."""
    mailserver = [_host(h) for h in (dns(domain, 'MX') if mx is None else mx)]
    for host in (h for h in mailserver if h):
        for anbieter in PROVIDERS:
            if any(_endet(host, endung) for endung in anbieter.mx):
                return Fund(anbieter.imap_host, anbieter.imap_port, anbieter.smtp_host, anbieter.smtp_port, 'mx',
                            anbieter.label)
        for name, endungen in HOSTER_AM_MX.items():
            if any(_endet(host, endung) for endung in endungen):
                return Fund(host, IMAP_TLS_PORT, host, 587, 'mx', f'{name} ({host})')
    return None


def finde(domain: str, *, dns: Abfrage | None = None, transport: httpx.BaseTransport | None = None,
          sekunden: float | None = None, mx: list[str] | None = None) -> Fund | None:
    """Der Mailserver zu einer Domain: SRV, dann Autoconfig, dann MX gegen den Katalog. `None`, wenn nichts antwortet."""
    domain = _host(domain)
    if not domain or '.' not in domain:
        return None
    with _sperre:
        gemerkt = _gemerkt.get(domain)
    if gemerkt and time.monotonic() - gemerkt[0] < MERKEN:
        return gemerkt[1]
    if dns is None:
        from .dns_abfrage import abfragen as dns
    frist = time.monotonic() + (ZEITGRENZE_GESAMT if sekunden is None else sekunden)
    fund = None
    for schritt in (lambda: aus_srv(domain, dns), lambda: aus_autoconfig(domain, transport),
                    lambda: aus_mx(domain, dns, mx)):
        rest = frist - time.monotonic()
        if rest <= 0:
            break
        try:
            from .zeitgrenze import mit_zeitgrenze
            fund = mit_zeitgrenze(schritt, rest)
        except Exception:  # noqa: BLE001 - Zeitgrenze oder Fehler: dieser Weg hat nichts gefunden
            fund = None
        if fund is not None:
            break
    if fund is not None:
        with _sperre:
            _gemerkt[domain] = (time.monotonic(), fund)
    return fund


def vergessen() -> None:
    """Für Tests und Browserproben: gemerkte Funde verwerfen."""
    with _sperre:
        _gemerkt.clear()


__all__ = ['Fund', 'MERKEN', 'TRANSPORT', 'ZEITGRENZE_GESAMT', 'ZEITGRENZE_HTTP', 'aus_autoconfig', 'aus_mx', 'aus_srv',
           'autoconfig_adressen', 'finde', 'lies_autoconfig', 'vergessen']
