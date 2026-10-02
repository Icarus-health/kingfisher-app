"""Die eine Anbieter-Erkennung: Wo liegt die Post zu einer Adresse? Google, Microsoft oder ein bekannter Anbieter.

`providers_mail.guess` kennt nur die Endungen der großen Anbieter (`gmail.com`, `web.de` …). Eine Adresse wie
`lena.probe@praxis-probe.example` kann trotzdem bei Google liegen (Google Workspace) und `lena.probe@hochschule.example`
bei Microsoft 365; dann fragte die Einrichtung „Welcher Anbieter?“, und das weiß ein Nicht-Techniker oft nicht. Das
Programm kann es selbst herausfinden, denn wo die Post einer Domain liegt, steht öffentlich in ihrem DNS-Eintrag.

Eine Funktion (`erkennen`) liefert alles, was die Oberfläche zum Verzweigen braucht:

* `anbieter`: der Katalogeintrag für den Weg mit Adresse und Passwort (bei Google Gmail, bei Microsoft Outlook);
* `dienst`: `google`, `microsoft` oder leer, `art`: `organisation` (Workspace, Microsoft 365 einer Hochschule oder
  Firma) oder `privat` (gmail.com, outlook.com …);
* `woran`: `domain` (an der Endung), `mx` (Mailserver), `autodiscover` (CNAME) oder `txt` (`MS=ms…`); für eine eigene
  Domain, deren Server Kingfisher selbst gefunden hat (`server_finden.py`), `srv`, `autoconfig` oder `mx` mit dem
  Anbieter `gefunden` (Fremdprobe 2, Befund 2).

Die Zeichen, in dieser Reihenfolge, und jedes reicht: die Endung (ohne jede Anfrage); der Mailserver (MX) auf Google
(`….google.com`, `….googlemail.com`) oder Exchange Online (`….mail.protection.outlook.com`); `autodiscover.<domain>`
zeigt auf `autodiscover.outlook.com`; die Domain trägt den Bestätigungseintrag eines Microsoft-365-Mandanten (TXT
`MS=ms…`). Hochschulen mit eigenem Filter vor der Post zeigen oft nur das dritte oder vierte.

**Was den Rechner verlässt.** Nur die Domain, nur an den Namensdienst des Rechners (`dns_abfrage.py`, Zeitgrenze 2 s,
Antworten zehn Minuten gemerkt), nie die ganze Adresse und nie an Google oder Microsoft. Dasselbe geschieht ohnehin
beim ersten Verbinden mit dem Postfach. Für eine eigene Domain fragt `server_finden.py` außerdem den Server der Domain
selbst nach ihrer Autoconfig-Datei, mit der Domain im Namen, ohne Adresse. Antwortet nichts, bleibt es bei der Auswahl.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from .providers_mail import BY_ID, MailProvider, guess

#: Domains der privaten Konten (kein Mandant, keine Organisation).
GOOGLE_PRIVAT = frozenset({'gmail.com', 'googlemail.com'})
MICROSOFT_PRIVAT = frozenset({'outlook.com', 'outlook.de', 'hotmail.com', 'hotmail.de', 'live.com', 'live.de',
                              'msn.com'})
#: Endungen des Mailservers (MX) -> Dienst.
MX_GOOGLE = ('google.com', 'googlemail.com')
MX_MICROSOFT = ('mail.protection.outlook.com',)
AUTODISCOVER_MICROSOFT = frozenset({'autodiscover.outlook.com', 'autodiscover-s.outlook.com'})
#: Der Katalogeintrag für den Passwortweg je Dienst.
KATALOG = {'google': 'gmail', 'microsoft': 'outlook'}

Abfrage = Callable[[str, str], list[str]]


@dataclass(frozen=True)
class Erkennung:
    anbieter: MailProvider | None = None
    woran: str = ''
    dienst: str = ''
    art: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {'provider': self.anbieter.to_dict() if self.anbieter else None, 'erkannt_an': self.woran,
                'dienst': self.dienst, 'art': self.art}


def domain_von(adresse: str) -> str:
    """Die Domain einer Adresse, klein und geprüft; leer, wenn es keine ist."""
    teil = (adresse or '').strip().rpartition('@')[2].strip().lower().rstrip('.')
    return teil if '@' in (adresse or '') and re.fullmatch(r'[a-z0-9-]+(\.[a-z0-9-]+)+', teil) else ''


def _endet(host: str, endungen: tuple[str, ...]) -> bool:
    host = host.lower().rstrip('.')
    return any(host == endung or host.endswith('.' + endung) for endung in endungen)


def _dienst(dienst: str, art: str, woran: str) -> Erkennung:
    return Erkennung(BY_ID[KATALOG[dienst]], woran, dienst, art)


def erkennen(adresse: str, dns: Abfrage | None = None, transport: Any = None) -> Erkennung:
    """Der Anbieter zu einer Adresse; leer (`Erkennung()`), wenn er nicht zu erkennen ist. Fragt nur nach der Domain.

    `transport` geht an `server_finden.finde` (Tests und Browserproben: Autoconfig-Attrappe statt Netz)."""
    domain = domain_von(adresse)
    if not domain:
        return Erkennung()
    if domain in GOOGLE_PRIVAT:
        return _dienst('google', 'privat', 'domain')
    if domain in MICROSOFT_PRIVAT:
        return _dienst('microsoft', 'privat', 'domain')
    bekannt = guess(f'x@{domain}')
    if bekannt is not None:
        return Erkennung(bekannt, 'domain')
    if dns is None:
        from .dns_abfrage import abfragen as dns
    mailserver: list[str] = []
    try:
        mailserver = dns(domain, 'MX')
        if any(_endet(host, MX_MICROSOFT) for host in mailserver):
            return _dienst('microsoft', 'organisation', 'mx')
        if any(_endet(host, MX_GOOGLE) for host in mailserver):
            return _dienst('google', 'organisation', 'mx')
        if any(ziel.lower().rstrip('.') in AUTODISCOVER_MICROSOFT for ziel in dns(f'autodiscover.{domain}', 'CNAME')):
            return _dienst('microsoft', 'organisation', 'autodiscover')
        if any(re.fullmatch(r'MS=ms\d+', text.strip()) for text in dns(domain, 'TXT')):
            return _dienst('microsoft', 'organisation', 'txt')
    except Exception:  # noqa: BLE001 - ohne Antwort ist es eben nicht erkannt; die Auswahl bleibt
        pass
    # Eine eigene Domain, die keinem großen Dienst gehört: den Server selbst finden (SRV, Autoconfig, MX-Katalog).
    from .server_finden import finde
    fund = finde(domain, dns=dns, transport=transport, mx=mailserver)
    if fund is not None:
        return Erkennung(fund.als_anbieter(), fund.woran)
    return Erkennung()


def vergessen() -> None:
    """Für Tests und Browserproben: gemerkte DNS-Antworten verwerfen."""
    from .dns_abfrage import vergessen as dns_vergessen
    from .server_finden import vergessen as server_vergessen
    dns_vergessen()
    server_vergessen()


__all__ = ['Erkennung', 'GOOGLE_PRIVAT', 'MICROSOFT_PRIVAT', 'domain_von', 'erkennen', 'vergessen']
