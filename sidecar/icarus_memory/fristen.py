"""Fristen aus Text: Datumsangaben deterministisch auflösen, ohne Modell.

Ein Abschnitt sagt „bis Freitag“, „bis zum 12.10.“, „Ende Oktober“ oder „in zwei
Wochen“. Gemeint ist ein Kalendertag, aber nur relativ zu dem Zeitpunkt, an dem
die Quelle entstand. Dieses Modul löst solche Angaben auf und nur solche, die
sich **eindeutig** auflösen lassen. Alles andere („nächste Woche“, „Mitte
Oktober“, ein Datum ohne Jahr, das ebenso gut vergangen wie künftig sein kann)
bleibt Text und bekommt kein Datum: Eine falsche Frist ist schlimmer als keine.

Regeln:

* **Bezug ist die Quelle, nicht heute.** „Bis Freitag“ in einer Mail vom März
  meint den Freitag danach, nicht den kommenden.
* **Ein Datum ohne Jahr** gilt im Jahr des Bezugs, wenn es nicht vor dem Bezug
  liegt. Liegt es davor, gilt es im Folgejahr nur, wenn das Jahr des Bezugs
  eindeutig vorbei wäre (mehr als 120 Tage zurück) und das Folgejahr nah ist
  (höchstens 120 Tage voraus). Sonst ist es uneindeutig.
* **Wochentag:** „bis Freitag“ ist der nächste Freitag nach dem Bezugstag. Am
  selben Wochentag ist es uneindeutig. „Nächsten Freitag“ ist uneindeutig (dieser
  oder der der Folgewoche).
* **Jede Auflösung nennt ihre Textstelle** (Zeichenpositionen im untersuchten
  Text); der Ausdruck steht wörtlich da. Nichts wird ergänzt.

Zahlwörter liest `time_scope.zahl`, dieselbe Stelle wie bei Zeiträumen in Fragen.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from .datumstext import MONAT_NUMMER
from .model import user_timezone
from .time_scope import NUMBERS, zahl

#: Ab so viele Tage vor dem Bezug gilt ein Datum ohne Jahr nicht mehr als „gerade eben“.
_JAHRESGRENZE = 120

# Namen aus `datumstext.MONAT_NUMMER`, dazu die Kürzel, die in Fristsätzen vorkommen.
_MONATE = {**MONAT_NUMMER, 'jan': 1, 'feb': 2, 'mär': 3, 'apr': 4, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9,
           'sept': 9, 'okt': 10, 'nov': 11, 'dez': 12}
_WOCHENTAGE = {'montag': 0, 'dienstag': 1, 'mittwoch': 2, 'donnerstag': 3, 'freitag': 4, 'samstag': 5,
               'sonnabend': 5, 'sonntag': 6}

_MONAT = r'(' + '|'.join(sorted(_MONATE, key=len, reverse=True)) + r')\b\.?'
_TAG = '(' + '|'.join(_WOCHENTAGE) + ')'
_ZAHL = r'(\d{1,3}|' + '|'.join(list(NUMBERS) + ['einer', 'einem', 'eine', 'ein']) + r')'

_ZIFFERN = re.compile(r'(?<![\d.,])(\d{1,2})\.\s?(\d{1,2})\.(?:\s?(\d{4}|\d{2})(?!\d))?(?![\d]|\.\d)')
_MONATSNAME = re.compile(r'(?<![\d.])(\d{1,2})\.?\s*' + _MONAT + r'(?:\s+(\d{4})(?!\d))?', re.I)
_MONATSENDE = re.compile(r'\bEnde\s+' + _MONAT + r'(?:\s+(\d{4})(?!\d))?', re.I)
_ENDE_MONAT = re.compile(r'\b(?:Ende\s+(?:des|dieses)\s+Monats|zum\s+Monatsende|Monatsende)\b', re.I)
_JAHRESENDE = re.compile(r'\b(?:Ende\s+(?:des|dieses)\s+Jahres|zum\s+Jahresende|Jahresende)\b', re.I)
_WOCHENTAG = re.compile(r'\b(bis|am|zum|vor|spätestens|kommenden|diesen)\s+' + _TAG + r'\b', re.I)
_RELATIV = re.compile(r'\bin\s+' + _ZAHL + r'\s+(Tag(?:en|e)?|Woche[n]?|Monat(?:en|e)?)\b', re.I)
_TAGE_NAH = re.compile(r'\b(?:bis|spätestens|vor|für)\s+(heute|morgen|übermorgen)\b', re.I)
# Angaben, die eine Frist nennen, aber kein Datum ergeben. Sie bleiben Text.
_UNEINDEUTIG = re.compile(
    r'\b(?:nächste[nmrs]?\s+(?:Woche|Monat|Jahr|' + '|'.join(_WOCHENTAGE) + r')'
    r'|(?:Anfang|Mitte)\s+(?:' + '|'.join(_MONATE) + r'|nächsten?\s+Monats?|der\s+Woche)\b'
    r'|Ende\s+(?:der|nächster)\s+Woche|KW\s?\d{1,2}|in\s+' + _ZAHL + r'\s+bis\s+' + _ZAHL + r'\s+(?:Tagen|Wochen|Monaten)'
    r'|bald|zeitnah|kurzfristig)\b', re.I)


@dataclass(frozen=True)
class Frist:
    """Ein aufgelöstes Datum mit seiner Textstelle."""

    datum: date
    ausdruck: str
    start: int
    ende: int
    art: str
    """`datum`, `monatsende`, `wochentag` oder `relativ`."""

    def to_dict(self) -> dict:
        return {'datum': self.datum.isoformat(), 'ausdruck': self.ausdruck, 'start': self.start,
                'ende': self.ende, 'art': self.art}


@dataclass
class Fristensuche:
    fristen: list[Frist] = field(default_factory=list)
    ohne_datum: list[str] = field(default_factory=list)
    """Zeitangaben, die sich nicht eindeutig auflösen ließen, wörtlich."""


def bezugstag(bezug: datetime | date) -> date:
    """Der Kalendertag des Bezugs in der Zeitzone des Nutzers."""
    if isinstance(bezug, datetime):
        zone = user_timezone() or timezone.utc
        moment = bezug if bezug.tzinfo else bezug.replace(tzinfo=timezone.utc)
        return moment.astimezone(zone).date()
    return bezug


def _tag(jahr: int, monat: int, tag: int) -> date | None:
    try:
        return date(jahr, monat, tag)
    except ValueError:
        return None


def _ohne_jahr(monat: int, tag: int, bezug: date) -> date | None:
    """Datum ohne Jahr nach der Regel im Modulkopf; None, wenn uneindeutig."""
    dieses = _tag(bezug.year, monat, tag)
    if dieses is not None and dieses >= bezug:
        return dieses
    naechstes = _tag(bezug.year + 1, monat, tag)
    if (dieses is not None and naechstes is not None and (bezug - dieses).days > _JAHRESGRENZE
            and (naechstes - bezug).days <= _JAHRESGRENZE):
        return naechstes
    return None


def ohne_jahr(monat: int, tag: int, bezug: date) -> date | None:
    """Öffentlich: Datum ohne Jahr nach der Regel im Modulkopf (für die Satzprüfung); None, wenn uneindeutig."""
    return _ohne_jahr(monat, tag, bezug)


def _monatsletzter(jahr: int, monat: int) -> date:
    return date(jahr, monat, calendar.monthrange(jahr, monat)[1])


def _plus_monate(tag: date, monate: int) -> date:
    gesamt = tag.year * 12 + tag.month - 1 + monate
    jahr, monat = divmod(gesamt, 12)
    monat += 1
    return date(jahr, monat, min(tag.day, calendar.monthrange(jahr, monat)[1]))


def _jahr(wert: str | None, *, zweistellig: bool = False) -> int | None:
    if not wert:
        return None
    zahl_ = int(wert)
    return 2000 + zahl_ if zweistellig and zahl_ < 100 else zahl_


def fristen_in(text: str, bezug: datetime | date) -> Fristensuche:
    """Alle eindeutig auflösbaren Datumsangaben im Text, in Reihenfolge des Textes.

    `bezug` ist der Zeitpunkt der Quelle. Gleiche Textstellen werden nicht
    doppelt gezählt (ein „12. Oktober“ ist nicht zugleich „12.10.“).
    """
    heute = bezugstag(bezug)
    ergebnis = Fristensuche()
    belegt: list[tuple[int, int]] = []

    def frei(start: int, ende: int) -> bool:
        return not any(start < b_ende and b_start < ende for b_start, b_ende in belegt)

    def nehmen(datum: date | None, treffer: re.Match, art: str) -> None:
        if not frei(treffer.start(), treffer.end()):
            return
        belegt.append((treffer.start(), treffer.end()))
        ausdruck = treffer.group(0).strip()
        if datum is None:
            ergebnis.ohne_datum.append(ausdruck)
        else:
            ergebnis.fristen.append(Frist(datum, ausdruck, treffer.start(), treffer.end(), art))

    for treffer in _ZIFFERN.finditer(text):
        tag, monat, jahr = int(treffer[1]), int(treffer[2]), treffer[3]
        if not (1 <= monat <= 12 and 1 <= tag <= 31):
            continue
        if jahr:
            nehmen(_tag(_jahr(jahr, zweistellig=len(jahr) == 2), monat, tag), treffer, 'datum')
        else:
            nehmen(_ohne_jahr(monat, tag, heute), treffer, 'datum')
    for treffer in _MONATSNAME.finditer(text):
        tag, monat = int(treffer[1]), _MONATE[treffer[2].lower()]
        if not 1 <= tag <= 31:
            continue
        jahr = _jahr(treffer[3])
        nehmen(_tag(jahr, monat, tag) if jahr else _ohne_jahr(monat, tag, heute), treffer, 'datum')
    for treffer in _MONATSENDE.finditer(text):
        monat, jahr = _MONATE[treffer[1].lower()], _jahr(treffer[2])
        if jahr is None:
            letzter = _monatsletzter(heute.year, monat)
            if letzter < heute:
                # Wie ein Datum ohne Jahr: nur eindeutig, wenn das Folgejahr die einzige Lesart ist.
                folgend = _monatsletzter(heute.year + 1, monat)
                letzter = folgend if (heute - letzter).days > _JAHRESGRENZE and \
                    (folgend - heute).days <= _JAHRESGRENZE else None
        else:
            letzter = _monatsletzter(jahr, monat)
        nehmen(letzter, treffer, 'monatsende')
    for treffer in _ENDE_MONAT.finditer(text):
        nehmen(_monatsletzter(heute.year, heute.month), treffer, 'monatsende')
    for treffer in _JAHRESENDE.finditer(text):
        nehmen(date(heute.year, 12, 31), treffer, 'monatsende')
    for treffer in _WOCHENTAG.finditer(text):
        ziel = _WOCHENTAGE[treffer[2].lower()]
        abstand = (ziel - heute.weekday()) % 7
        # Am selben Wochentag ist unklar, ob heute oder in einer Woche gemeint ist.
        nehmen(heute + timedelta(days=abstand) if abstand else None, treffer, 'wochentag')
    for treffer in _RELATIV.finditer(text):
        anzahl = zahl(treffer[1])
        if not anzahl or anzahl > 366:
            continue
        einheit = treffer[2].lower()
        if einheit.startswith('tag'):
            datum = heute + timedelta(days=anzahl)
        elif einheit.startswith('woche'):
            datum = heute + timedelta(weeks=anzahl)
        else:
            datum = _plus_monate(heute, anzahl)
        nehmen(datum, treffer, 'relativ')
    for treffer in _TAGE_NAH.finditer(text):
        nehmen(heute + timedelta(days={'heute': 0, 'morgen': 1, 'übermorgen': 2}[treffer[1].lower()]),
               treffer, 'relativ')
    for treffer in _UNEINDEUTIG.finditer(text):
        nehmen(None, treffer, 'uneindeutig')
    ergebnis.fristen.sort(key=lambda frist: frist.start)
    return ergebnis


#: Monatsnamen und -kürzel (klein) mit Nummer; dieselbe Tabelle für die Satzprüfung.
MONATE = _MONATE

__all__ = ['Frist', 'Fristensuche', 'MONATE', 'bezugstag', 'fristen_in', 'ohne_jahr']
