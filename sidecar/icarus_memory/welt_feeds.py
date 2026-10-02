"""Nachrichtenfeeds (RSS und Atom) lesen: begrenzt, ohne Entitäten, alles Fremde ist Daten.

Ein Feed ist fremder Text im Netz. Deshalb gilt hier dasselbe wie bei `world_sources.py` (öffentliche https-Adresse,
Prüfung gegen interne Ziele, Größenlimit, wenige Weiterleitungen, jeweils neu geprüft) und zusätzlich für XML:

* **Keine Entitäten, keine Dokumenttypen.** Ein Feed mit `<!DOCTYPE` oder `<!ENTITY` wird abgelehnt, bevor ein
  Parser ihn sieht (Schutz vor „Billion Laughs“ und externen Entitäten). Auch Kodierungen mit Nullbytes (UTF-16),
  die diese Prüfung umgingen, werden abgelehnt.
* **Größenlimits**: höchstens 256 KiB Antwort, 40 Einträge, Titel und Zusammenfassung gekürzt.
* **Nur Text.** HTML in Zusammenfassungen wird zu Text; Skripte und Formatierung fallen weg. Links werden nur
  übernommen, wenn sie `https` sind.

Das Ergebnis sind `Eintrag`e: Daten, nie eine Anweisung. Was mit ihnen geschieht, entscheidet `welt_meldungen.py`.
Dieses Modul hat kein Modell, keinen Zugriff auf das Gedächtnis und keine Zugangsdaten.
"""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlparse

import httpx

from .security import SecurityError
from .world_sources import MAX_REDIRECTS, REDIRECT_STATUSES, TIMEOUT_SECONDS, _validate_url

MAX_FEED_BYTES = 256 * 1024
MAX_EINTRAEGE = 40
MAX_TITEL = 200
MAX_TEXT = 600

_GEFAEHRLICH = re.compile(rb'<!\s*(?:DOCTYPE|ENTITY)', re.I)
_STEUERZEICHEN = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


class FeedFehler(ValueError):
    """Der Feed ist unbrauchbar oder unsicher. Die Meldung ist für den Nutzer gedacht und enthält keinen Feedinhalt."""


@dataclass(frozen=True)
class Eintrag:
    kennung: str
    titel: str
    text: str
    link: str
    """Nur `https`; sonst leer."""
    datum: datetime | None


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.teile: list[str] = []
        self._still = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self._still += 1
        elif tag in ('p', 'br', 'div', 'li'):
            self.teile.append(' ')

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self._still:
            self._still -= 1

    def handle_data(self, data):
        if not self._still:
            self.teile.append(data)


def _sauber(text: str | None, grenze: int) -> str:
    """Reiner Text in einer Zeile: HTML weg, Steuerzeichen weg, gekürzt."""
    roh = text or ''
    if '<' in roh:
        parser = _Text()
        try:
            parser.feed(roh)
            parser.close()
            roh = ''.join(parser.teile)
        except (RecursionError, ValueError):
            roh = re.sub(r'<[^>]*>', ' ', roh)
    roh = _STEUERZEICHEN.sub(' ', roh)
    ein_zeile = ' '.join(roh.split())
    return ein_zeile if len(ein_zeile) <= grenze else ein_zeile[:grenze].rsplit(' ', 1)[0].rstrip(',;:.') + ' …'


def _name(tag: str) -> str:
    return tag.rsplit('}', 1)[-1].casefold()


def _kind(element: ET.Element, *namen: str) -> ET.Element | None:
    for kind in element:
        if _name(kind.tag) in namen:
            return kind
    return None


def _text(element: ET.Element, *namen: str) -> str:
    kind = _kind(element, *namen)
    return ''.join(kind.itertext()) if kind is not None else ''


def _https(link: str) -> str:
    link = (link or '').strip()
    adresse = urlparse(link)
    if adresse.scheme != 'https' or not adresse.hostname or adresse.username or adresse.password or len(link) > 2000:
        return ''
    return urldefrag(link)[0]


def _datum(text: str) -> datetime | None:
    text = (text or '').strip()
    if not text:
        return None
    try:
        wert = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        try:
            wert = datetime.fromisoformat(text.replace('Z', '+00:00'))
        except ValueError:
            return None
    return wert if wert.tzinfo else wert.replace(tzinfo=timezone.utc)


def _atom_link(element: ET.Element) -> str:
    for kind in element:
        if _name(kind.tag) == 'link' and kind.get('rel', 'alternate') == 'alternate' and kind.get('href'):
            return kind.get('href', '')
    return ''


def lesen(rohdaten: bytes) -> list[Eintrag]:
    """Die Einträge eines RSS-, RDF- oder Atom-Feeds. Wirft `FeedFehler` bei allem, was nicht sicher lesbar ist."""
    if len(rohdaten) > MAX_FEED_BYTES:
        raise FeedFehler('Der Feed ist zu groß.')
    if b'\x00' in rohdaten[:4096] or rohdaten[:2] in (b'\xff\xfe', b'\xfe\xff'):
        raise FeedFehler('Der Feed ist nicht als Text lesbar.')
    if _GEFAEHRLICH.search(rohdaten):
        raise FeedFehler('Der Feed enthält Definitionen, die aus Sicherheitsgründen nicht gelesen werden.')
    try:
        wurzel = ET.fromstring(rohdaten)
    except (ET.ParseError, ValueError, RecursionError):
        raise FeedFehler('Das ist kein lesbarer Feed.') from None
    art = _name(wurzel.tag)
    if art == 'rss':
        kanal = _kind(wurzel, 'channel')
        elemente = [e for e in (kanal if kanal is not None else []) if _name(e.tag) == 'item']
    elif art == 'rdf':
        elemente = [e for e in wurzel if _name(e.tag) == 'item']
    elif art == 'feed':
        elemente = [e for e in wurzel if _name(e.tag) == 'entry']
    else:
        raise FeedFehler('Das ist kein RSS- oder Atom-Feed.')
    eintraege: list[Eintrag] = []
    for element in elemente[:MAX_EINTRAEGE]:
        titel = _sauber(_text(element, 'title'), MAX_TITEL)
        if not titel:
            continue
        link = _https(_atom_link(element) if art == 'feed' else _text(element, 'link'))
        text = _sauber(_text(element, 'description', 'summary', 'content', 'encoded'), MAX_TEXT)
        datum = _datum(_text(element, 'pubdate', 'published', 'updated', 'date'))
        kennung = _sauber(_text(element, 'guid', 'id'), 300) or link
        if not kennung:
            kennung = hashlib.sha256(titel.encode()).hexdigest()[:16]
        eintraege.append(Eintrag(kennung, titel, text, link, datum))
    return eintraege


def abrufen(url: str, *, client: httpx.Client | None = None) -> bytes:
    """Die Rohbytes eines Feeds. Gleiche Schutzregeln wie `world_sources.fetch_public_text`, aber ohne Textumwandlung."""
    eigener = client is None
    aktiv = client or httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False)
    koerper = bytearray()
    aktuell = url
    try:
        for versuche in range(MAX_REDIRECTS + 1):
            try:
                aktuell = _validate_url(aktuell)
            except (SecurityError, ValueError):
                raise FeedFehler('Diese Adresse ist nicht erlaubt: Sie muss öffentlich sein und mit https beginnen.') from None
            try:
                with aktiv.stream('GET', aktuell, follow_redirects=False, timeout=TIMEOUT_SECONDS,
                                  headers={'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml'}
                                  ) as antwort:
                    if antwort.status_code in REDIRECT_STATUSES:
                        ziel = antwort.headers.get('location')
                        if not ziel or versuche >= MAX_REDIRECTS:
                            raise FeedFehler('Zu viele oder fehlerhafte Weiterleitungen.')
                        aktuell = urldefrag(urljoin(aktuell, ziel))[0]
                        continue
                    antwort.raise_for_status()
                    try:
                        angekuendigt = int(antwort.headers.get('content-length') or 0)
                    except ValueError:
                        angekuendigt = 0
                    if angekuendigt > MAX_FEED_BYTES:
                        raise FeedFehler('Der Feed ist zu groß.')
                    for stueck in antwort.iter_bytes():
                        koerper.extend(stueck)
                        if len(koerper) > MAX_FEED_BYTES:
                            raise FeedFehler('Der Feed ist zu groß.')
            except httpx.HTTPError:
                raise FeedFehler('Der Feed konnte nicht abgerufen werden.') from None
            break
        else:  # pragma: no cover - die Schleife läuft mindestens einmal
            raise FeedFehler('Zu viele Weiterleitungen.')
    finally:
        if eigener:
            aktiv.close()
    return bytes(koerper)


__all__ = ['Eintrag', 'FeedFehler', 'MAX_FEED_BYTES', 'abrufen', 'lesen']
