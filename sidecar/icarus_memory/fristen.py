"""Fristen aus Text: Datumsangaben deterministisch auflösen, ohne Modell.

Ein Abschnitt sagt „bis Freitag“, „bis zum 12.10.“, „Ende Oktober“ oder „in zwei
Wochen“. Ein Kalendertag wird nur relativ zu dem Zeitpunkt aufgelöst, an dem
die Quelle entstand, und nur aus Angaben, die
sich **eindeutig** auflösen lassen. Alles andere („nächste Woche“, „Mitte
Oktober“, „Ende Oktober“, „Monatsende“, „Jahresende“ oder ein Datum ohne Jahr,
das ebenso gut vergangen wie künftig sein kann)
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

# A resolved date is not yet a deadline. The relation must be local to that
# expression, never inherited from the kind of a whole paragraph. In
# particular, "Tagung am 16. April ... Anmeldung bis 7. April" has two dates
# but only one explicit cutoff. These small grammatical links deliberately
# leave unbound dates undecided; event knowledge stays in the source.
_SATZTEIL = re.compile(r'(?<=[a-zäöüß)\]])[.!?](?:\s|$)|[,;\n]', re.I)
_FRIST_VOR = re.compile(
    r'\b(?:bis(?:\s+spätestens)?|spätestens(?:\s+bis)?|vor)\s+'
    r'(?:(?:zum|zur|am|den|dem|kommenden|diesen)\s+)?$', re.I)
_FRIST_IM_AUSDRUCK = re.compile(r'^(?:bis|spätestens|vor)\b', re.I)
# Match a cutoff headword, not any word containing one: an
# Abschlussveranstaltung or an Abgabeformular is not itself a due date.
_FRISTNAME = re.compile(
    r'\b(?:\w*(?:frist(?:en|ende)?|deadline(?:s)?|abgabe(?:n|termin(?:e)?)?|fälligkeit(?:en)?)|'
    r'(?:anmelde|redaktions|einsende|bewerbungs|annahme|abgabe|einreich(?:ungs)?|teilnahme|melde)schluss|fällig)\b', re.I)
_FRIST_LINK = re.compile(
    r'(?:\s|[:=–-]|\b(?:ist|sind|der|die|das|den|dem|am|zum|auf|bis|nun|jetzt|'
    r'neue?|wurde|wird|endet|erfolgt|gilt|verschoben|verlängert|festgelegt|verschiebt|sich)\b)*', re.I)
_ZEITRAUM_ANFANG = re.compile(r'\b(?:von|vom|ab|zwischen)\s*$', re.I)
_ZEITRAUM_LINK = re.compile(r'\s*(?:bis(?:\s+zum)?|und|[–-])\s*', re.I)
_ZEITRAUM_KURZ = re.compile(r'\b(?:von|vom|ab)\s+\d{1,2}\.\s*$', re.I)
_DAUER_VOR = re.compile(
    r'\b(?:dauer(?:t|n)|andauer(?:t|n)|läuft|laufen)\s*'
    r'(?:(?:noch|weiter|voraussichtlich|planmäßig|regulär)\s+)?$', re.I)
_ZUSTAND = r'(?:bin|bist|ist|sind|seid|bleibe|bleibst|bleibt|bleiben)'
_ABWESEND = r'(?:im\s+Urlaub|abwesend|krank|nicht\s+erreichbar)'
_ZUSTAND_VOR = re.compile(r'\b' + _ZUSTAND + r'\s+(?:noch\s+)?$', re.I)
_ABWESEND_VOR = re.compile(r'\b' + _ZUSTAND + r'\s+(?:noch\s+)?' + _ABWESEND + r'\s*$', re.I)
_ABWESEND_NACH = re.compile(r'^\s*' + _ABWESEND + r'\b', re.I)
# A bare invitation schedules attendance, not an action cutoff. Without an
# explicit cutoff word, recognise only direct reply/delivery requests here.
_ANTWORT_ABGABE_VOR = re.compile(
    r'\bbitte\s+(?:antworte[n]?|melde[n]?|sende[n]?|schicke[n]?|reiche[n]?|einreiche[n]?)\s+'
    r'(?:Sie\s+)?(?:sich\s+)?$', re.I)
# "bis" also ends events and absences. It needs positive action evidence,
# rather than an expanding list of event verbs to veto. Unrecognised wording
# stays in the original and broad date API instead of becoming a deadline.
_FRISTHANDLUNG = re.compile(
    r'\b(?:antworte[n]?|beantworte[n]?|antwort|rückmeldung|anmeldung|melde[n]?|sende[n]?|'
    r'sendet|schick(?:e|en|t)?|einreiche[n]?|reiche[n]?|kündig(?:e|en|t)|'
    r'bestätig(?:e|en|t)|überweis(?:e|en|t)|zahl(?:e|en|t)|zahlung|liefer(?:e|n|t))\b', re.I)
_ZUSTELLUNG_VOR = re.compile(
    r'\b(?:\w*erklärung|unterlagen|dokumente?|muster|rechnung|daten|bericht)\s+komm(?:t|en)\s*$', re.I)
_FERTIG_NACH = re.compile(r'^\s*(?:fertig|einzureichen|abzugeben|erledigt)\b', re.I)
_FRIST_FORTSETZUNG = re.compile(r'\s*,\s*spätestens\s*(?:(?:am|zum)\s+)?', re.I)


@dataclass(frozen=True)
class Frist:
    """Ein aufgelöstes Datum mit seiner Textstelle."""

    datum: date
    ausdruck: str
    start: int
    ende: int
    art: str
    """`datum`, `wochentag` oder `relativ`."""

    def to_dict(self) -> dict:
        return {'datum': self.datum.isoformat(), 'ausdruck': self.ausdruck, 'start': self.start,
                'ende': self.ende, 'art': self.art}


@dataclass
class Fristensuche:
    fristen: list[Frist] = field(default_factory=list)
    ohne_datum: list[str] = field(default_factory=list)
    """Zeitangaben, die sich nicht eindeutig auflösen ließen, wörtlich."""
    ohne_datum_stellen: list[tuple[int, int]] = field(default_factory=list)
    """Passende Originalposition je Eintrag in `ohne_datum`, auch bei gleichem Wortlaut."""


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


def ungenaues_ende(text: str) -> bool:
    """Nennt der Text ein Monats-/Jahresende ohne ausdrücklich genannten Tag?"""
    return any(muster.search(text) for muster in (_MONATSENDE, _ENDE_MONAT, _JAHRESENDE))


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


def fristen_in(text: str, bezug: datetime | date | None) -> Fristensuche:
    """Alle eindeutig auflösbaren Datumsangaben im Text, in Reihenfolge des Textes.

    `bezug` ist der Zeitpunkt der Quelle. Ohne ihn bleiben relative Angaben und Daten ohne Jahr offen;
    ausgeschriebene absolute Daten mit Jahr gelten weiterhin. Gleiche Textstellen werden nicht doppelt gezählt
    (ein „12. Oktober“ ist nicht zugleich „12.10.“).
    """
    heute = bezugstag(bezug) if bezug is not None else None
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
            ergebnis.ohne_datum_stellen.append((treffer.start(), treffer.end()))
        else:
            ergebnis.fristen.append(Frist(datum, ausdruck, treffer.start(), treffer.end(), art))

    for treffer in _ZIFFERN.finditer(text):
        tag, monat, jahr = int(treffer[1]), int(treffer[2]), treffer[3]
        if not (1 <= monat <= 12 and 1 <= tag <= 31):
            continue
        if jahr:
            nehmen(_tag(_jahr(jahr, zweistellig=len(jahr) == 2), monat, tag), treffer, 'datum')
        else:
            nehmen(_ohne_jahr(monat, tag, heute) if heute else None, treffer, 'datum')
    for treffer in _MONATSNAME.finditer(text):
        tag, monat = int(treffer[1]), _MONATE[treffer[2].lower()]
        if not 1 <= tag <= 31:
            continue
        jahr = _jahr(treffer[3])
        nehmen(_tag(jahr, monat, tag) if jahr else (_ohne_jahr(monat, tag, heute) if heute else None),
               treffer, 'datum')
    # An end-of-month/year expression does not state a particular day. Keep
    # the original even when the year or source date is known.
    for muster in (_MONATSENDE, _ENDE_MONAT, _JAHRESENDE):
        for treffer in muster.finditer(text):
            nehmen(None, treffer, 'uneindeutig')
    for treffer in _WOCHENTAG.finditer(text):
        ziel = _WOCHENTAGE[treffer[2].lower()]
        abstand = (ziel - heute.weekday()) % 7 if heute else 0
        # Am selben Wochentag ist unklar, ob heute oder in einer Woche gemeint ist.
        nehmen(heute + timedelta(days=abstand) if heute and abstand else None, treffer, 'wochentag')
    for treffer in _RELATIV.finditer(text):
        anzahl = zahl(treffer[1])
        if not anzahl or anzahl > 366:
            continue
        if heute is None:
            nehmen(None, treffer, 'relativ')
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
        nehmen(heute + timedelta(days={'heute': 0, 'morgen': 1, 'übermorgen': 2}[treffer[1].lower()]) if heute else None,
               treffer, 'relativ')
    for treffer in _UNEINDEUTIG.finditer(text):
        nehmen(None, treffer, 'uneindeutig')
    ergebnis.fristen.sort(key=lambda frist: frist.start)
    return ergebnis


def fristangaben_in(text: str, bezug: datetime | date | None) -> Fristensuche:
    """Dates explicitly bound to a cutoff, for deadline consumers such as Akten.

    ``fristen_in`` remains the broad date API for source checking, matching and
    retrieval. Here, cutoff words must bind a local deadline action, or a deadline
    noun must be joined by a grammatical link in the same clause. A direct
    reply/delivery request ("Bitte melden Sie sich nächste Woche") also binds its time. Another date
    always bounds the link, so event dates cannot borrow a neighbouring cutoff.
    Event/absence durations and source date ranges are not due dates. The same
    relation check applies to unresolved expressions, whose exact original
    positions remain available even when the wording occurs more than once.

    This deliberately supports a bounded set of reply, registration, delivery,
    payment and cancellation wording. Other or syntactically complex wording
    may remain source evidence without a derived deadline; it is not a general
    German semantic parser and does not establish attendance or responsibility.
    """
    suche = fristen_in(text, bezug)
    grenzen = list(_SATZTEIL.finditer(text))
    angaben = sorted(
        [(f.start, f.ende, f.ausdruck) for f in suche.fristen]
        + [(start, ende, ausdruck) for ausdruck, (start, ende)
           in zip(suche.ohne_datum, suche.ohne_datum_stellen)])
    gebunden: set[tuple[int, int]] = set()

    def fristbezug(nummer: int, angabe: tuple[int, int, str]) -> bool:
        start, ende, ausdruck = angabe
        links = max((m.end() for m in grenzen if m.end() <= start), default=0)
        rechts = next((m.start() for m in grenzen if m.start() >= ende), len(text))
        vorher = angaben[nummer - 1] if nummer else None
        nachher = angaben[nummer + 1] if nummer + 1 < len(angaben) else None
        # "vom 7. April bis zum 16. April" describes a range, even inside a
        # paragraph classified as a request. Its endpoint supplies no deadline.
        if vorher and _ZEITRAUM_LINK.fullmatch(text[vorher[1]:start]):
            if _ZEITRAUM_ANFANG.search(text[links:vorher[0]]):
                return False
        if vorher:
            links = max(links, vorher[1])
        if nachher:
            rechts = min(rechts, nachher[0])
        vor, nach = text[links:start], text[ende:rechts]
        cutoff = _FRIST_VOR.search(vor)
        if cutoff or _FRIST_IM_AUSDRUCK.match(ausdruck):
            # A directly linked duration predicate owns its endpoint, even in
            # a request paragraph. A deadline noun ("Einreichfrist läuft bis")
            # still names a cutoff. Other dates/clauses cannot donate context.
            davor = vor[:cutoff.start()] if cutoff else vor
            if _ZEITRAUM_KURZ.search(davor):
                return False
            dauer = _DAUER_VOR.search(davor)
            if dauer:
                subjekt = davor[:dauer.start()]
                if not any(_FRIST_LINK.fullmatch(subjekt[m.end():]) for m in _FRISTNAME.finditer(subjekt)):
                    return False
                return True
            if (_ABWESEND_VOR.search(davor)
                    or (_ZUSTAND_VOR.search(davor) and _ABWESEND_NACH.match(nach))):
                return False
            if (_FRISTHANDLUNG.search(davor) or _ZUSTELLUNG_VOR.search(davor)
                    or _FERTIG_NACH.match(nach) or _FRISTHANDLUNG.match(nach.lstrip())):
                return True
            if (vorher and vorher[:2] in gebunden
                    and _FRIST_FORTSETZUNG.fullmatch(text[vorher[1]:start])):
                return True
        if _ANTWORT_ABGABE_VOR.search(vor):
            return True
        return (any(_FRIST_LINK.fullmatch(vor[m.end():]) for m in _FRISTNAME.finditer(vor))
                or any(_FRIST_LINK.fullmatch(nach[:m.start()])
                       and not (nachher and rechts == nachher[0]
                                and _FRIST_LINK.fullmatch(nach[m.end():]))
                       for m in _FRISTNAME.finditer(nach)))

    for nummer, angabe in enumerate(angaben):
        if fristbezug(nummer, angabe):
            gebunden.add(angabe[:2])
    offen = [(ausdruck, stelle) for ausdruck, stelle in zip(suche.ohne_datum, suche.ohne_datum_stellen)
             if stelle in gebunden]
    return Fristensuche([frist for frist in suche.fristen if (frist.start, frist.ende) in gebunden],
                        [ausdruck for ausdruck, _ in offen], [stelle for _, stelle in offen])


#: Monatsnamen und -kürzel (klein) mit Nummer; dieselbe Tabelle für die Satzprüfung.
MONATE = _MONATE

__all__ = ['Frist', 'Fristensuche', 'MONATE', 'bezugstag', 'fristen_in', 'fristangaben_in', 'ohne_jahr',
           'ungenaues_ende']
