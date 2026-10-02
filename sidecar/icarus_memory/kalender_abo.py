"""Ein Kalender über seine geheime iCal-Adresse, vor allem Google ohne eigenes Cloud-Projekt (Fremdprobe, Befund 2).

„Mit Google anmelden“ braucht ein Google-Cloud-Projekt mit OAuth-Client; das legt kein Nicht-Techniker an. Google gibt
jedem Kalender aber eine „Geheime Adresse im iCal-Format“ (Einstellungen des Kalenders → Kalender integrieren). Wer sie
einfügt, verbindet den Kalender nur lesend, ohne Passwort und ohne Projekt.

Was hier geschieht, und nur das:

* `einordnen`: Ist das eine Google-Adresse, und die richtige? Die geheime Adresse hat die Form
  `https://calendar.google.com/calendar/ical/<kalender>/private-<schlüssel>/basic.ics`. Die öffentliche Adresse
  (`…/public/basic.ics`) geht nur bei öffentlichen Kalendern; eine Einbettungs- oder Einstellungsseite ist gar kein
  Kalender. `webcal://` wird `https://`.
* `pruefe`: Die Adresse wird einmal abgerufen, mit Wanduhr (10 s), ohne Weiterleitung, höchstens 5 MB, und muss ein
  gültiges iCalendar sein (`BEGIN:VCALENDAR`). Sonst ein Satz mit Grund. Hinaus geht nichts außer diesem Abruf.

Die Adresse ist ein Schlüssel zum ganzen Kalender: Sie liegt im Schlüsselbund wie ein Passwort (`server.py`), in den
Einstellungen steht nur `https://calendar.google.com/` ohne den geheimen Teil. Die zwei Sätze der Karte, wo man die
Adresse findet, stehen in der Oberfläche (`googleWeg.ts`, `WO_FINDEN`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlsplit

import httpx

from .connectors.calendar import parse_events
from .mail_anmeldung import Anmeldefehler
from .zeitgrenze import mit_zeitgrenze

#: So lange wartet „Kalender verbinden“ höchstens auf den Abruf (Sekunden, Wanduhr).
ZEITGRENZE = 10.0
GROESSE = 5_000_000
GOOGLE = 'calendar.google.com'
#: Was in den Einstellungen statt der geheimen Adresse steht.
GOOGLE_ANZEIGE = 'https://calendar.google.com/'
_PFAD_GEHEIM = re.compile(r'^/calendar/ical/[^/]+/private-[0-9a-f]{16,}/basic\.ics$')
_PFAD_OEFFENTLICH = re.compile(r'^/calendar/ical/[^/]+/public/basic\.ics$')

@dataclass(frozen=True)
class Einordnung:
    art: str
    """`google_geheim`, `google_oeffentlich`, `google_falsch`, `abo` oder `ungueltig`."""
    url: str
    satz: str = ''

    @property
    def google(self) -> bool:
        return self.art.startswith('google')


@dataclass(frozen=True)
class Abo:
    name: str
    termine: int


def einordnen(roh: str) -> Einordnung:
    """Welche Art Adresse das ist; `url` ist die bereinigte Fassung (`webcal://` → `https://`)."""
    url = (roh or '').strip()
    if url.lower().startswith('webcal://'):
        url = 'https://' + url[len('webcal://'):]
    teile = urlsplit(url)
    if teile.scheme != 'https' or not teile.hostname:
        return Einordnung('ungueltig', url, 'Das ist keine Kalenderadresse; sie beginnt mit https://.')
    if teile.hostname.lower() != GOOGLE:
        return Einordnung('abo', url)
    pfad = unquote(teile.path)
    if _PFAD_GEHEIM.match(pfad):
        return Einordnung('google_geheim', url)
    if _PFAD_OEFFENTLICH.match(pfad):
        return Einordnung('google_oeffentlich', url)
    return Einordnung('google_falsch', url, 'Das ist eine Seite von Google Kalender, aber nicht die Adresse des '
                                            'Kalenders: Kopiere in den Einstellungen des Kalenders die „Geheime '
                                            'Adresse im iCal-Format“.')


def _wer(einordnung: Einordnung) -> str:
    return 'Google' if einordnung.google else (urlsplit(einordnung.url).hostname or 'Der Kalenderdienst')


def _abrufen(url: str, transport: Any = None) -> tuple[int, str]:
    """(Status, Text) eines einzigen Abrufs, ohne Weiterleitung und höchstens `GROESSE` Bytes."""
    optionen: dict[str, Any] = {'timeout': ZEITGRENZE - 1, 'follow_redirects': False}
    if transport is not None:
        optionen['transport'] = transport
    with httpx.Client(**optionen) as client:
        with client.stream('GET', url, headers={'Accept': 'text/calendar'}) as antwort:
            if antwort.status_code != 200:
                return antwort.status_code, ''
            teile, groesse = [], 0
            for stueck in antwort.iter_bytes():
                groesse += len(stueck)
                if groesse > GROESSE:
                    raise Anmeldefehler('zu_gross', 'Dieser Kalender ist größer als 5 MB; so viel liest Kingfisher '
                                                    'über eine Adresse nicht.')
                teile.append(stueck)
            return 200, b''.join(teile).decode(antwort.encoding or 'utf-8', errors='replace')


def pruefe(roh: str, *, transport: Any = None, sekunden: float = ZEITGRENZE) -> tuple[Einordnung, Abo]:
    """Ruft die Adresse einmal ab und prüft, ob dort ein Kalender liegt. Wirft `Anmeldefehler` mit einem Satz."""
    einordnung = einordnen(roh)
    if einordnung.art in ('ungueltig', 'google_falsch'):
        raise Anmeldefehler(einordnung.art, einordnung.satz)
    wer = _wer(einordnung)
    try:
        status, text = mit_zeitgrenze(lambda: _abrufen(einordnung.url, transport), sekunden)
    except Anmeldefehler:
        raise
    except Exception as exc:  # noqa: BLE001 - jeder Netzfehler wird zu einem Satz
        if isinstance(exc, httpx.ConnectError) and 'CERTIFICATE' in str(exc).upper():
            raise Anmeldefehler('unsicher', f'Die Verbindung zu {wer} ließ sich nicht sicher aufbauen; '
                                            'bitte später noch einmal versuchen.') from None
        raise Anmeldefehler('nicht_erreichbar', f'{wer} antwortet gerade nicht; prüfe die Internetverbindung und '
                                                'versuche es gleich noch einmal.') from None
    if status in (401, 403, 404, 410):
        satz = ('Google kennt diese Adresse nicht (mehr): Kopiere die „Geheime Adresse im iCal-Format“ noch einmal aus '
                'den Einstellungen deines Kalenders.' if einordnung.art == 'google_geheim' else
                'Google gibt diesen Kalender über die öffentliche Adresse nicht heraus: Nimm die „Geheime Adresse im '
                'iCal-Format“ aus den Einstellungen deines Kalenders.' if einordnung.art == 'google_oeffentlich' else
                f'{wer} kennt diese Adresse nicht oder gibt den Kalender nicht heraus.')
        raise Anmeldefehler('abgelehnt', satz)
    if status != 200:
        raise Anmeldefehler('kein_kalender', f'{wer} liefert unter dieser Adresse keinen Kalender (Antwort {status}).')
    if not re.search(r'^BEGIN:VCALENDAR\s*$', text[:2000].lstrip('﻿'), re.MULTILINE) or 'END:VCALENDAR' not in text:
        raise Anmeldefehler('kein_kalender', 'Unter dieser Adresse liegt kein Kalender; bitte kopiere die Adresse '
                                             'noch einmal vollständig.')
    name = re.search(r'^X-WR-CALNAME:(.*)$', text, re.MULTILINE)
    anzeige = ' '.join((name.group(1) if name else '').split())[:80]
    return einordnung, Abo(name=anzeige, termine=len(parse_events(text)))


__all__ = ['Abo', 'Einordnung', 'GOOGLE_ANZEIGE', 'ZEITGRENZE', 'einordnen', 'pruefe']
