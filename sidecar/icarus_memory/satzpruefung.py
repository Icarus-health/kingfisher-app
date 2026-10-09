"""Satzprüfung (Etappe D3, wiederverwendbar für E3): ein Satz besteht nur, wenn seine Belege ihn tragen.

Ein Modell formuliert Sätze und nennt je Satz die Nummern seiner Belege. Dieses
Modul prüft **ohne Modell**, ob die Belege den Satz decken. Es verbessert
nichts, es ergänzt nichts und es rät nicht: Jeder Satz besteht oder wird mit
Grund verworfen. Im Zweifel wird verworfen. Ein fehlender Satz kostet den
Nutzer nichts, ein falscher schon.

Ein Satz besteht nur, wenn

1. jede genannte Belegnummer existiert und gültig ist (und mindestens eine
   genannt wird),
2. alle **harten Tokens** des Satzes in den zitierten Belegen stehen:

   * Daten in allen deutschen Formen („12.10.“, „12. Oktober“, „2026-10-12“,
     „12.10.26“, Bereiche), normalisiert auf das Kalenderdatum. Relative Angaben
     der Quelle („bis Freitag“, „in zwei Wochen“) werden mit dem Zeitpunkt der
     **Quelle** aufgelöst (`fristen.py`), nicht mit heute. Ein Datum ohne Jahr im
     Satz genügt mit dem Tag und Monat eines Belegdatums; nennt der Satz ein
     Jahr, muss es das Belegdatum tragen oder aufgelöst ergeben.
   * Uhrzeiten („11 Uhr“ = „11:00“ = „11.00 Uhr“, Bereiche),
   * Zahlen und Beträge (Tausenderpunkte, Dezimalkomma, Währung bei Beträgen;
     „zwei“ = „2“),
   * E-Mail-Adressen, Links und Kennungen (Aktenzeichen, Rechnungsnummern),
   * Wochentage (im Beleg oder als Wochentag eines belegten Datums im Satz),
     Monatsnamen und „Anfang/Mitte/Ende <Monat>“,
   * Eigennamen und Orte: jedes großgeschriebene Wort, das kein Funktionswort
     und kein allgemeines Gattungswort ist, samt Namensfolgen („Klinikum
     Stuttgart“ als Folge), in Beugung und Umlautschreibung tolerant,
   * Zusagen des Status („bezahlt“, „bestätigt“, „erledigt“ …): dieselbe
     Wortgruppe muss im Beleg stehen,
   * relative Zeitangaben („heute“, „morgen“, „nächste Woche“) sind ohne festen
     Bezugstag nicht prüfbar und werden verworfen (`relative_zeit_erlaubt`),

3. keine **Verneinungsumkehr** offensichtlich ist: Verneint der Beleg im selben
   Satzteil etwas, das der Satz aufgreift („nicht“, „kein“, „abgesagt“,
   „entfällt“ …), muss der Satz selbst verneinen; verneint der Satz, muss auch
   ein Beleg verneinen.

Grenzen (bewusst): Die Prüfung erkennt keine falsche Zuordnung von Zahlen zu
Sachverhalten („12 Personen“ statt „12 Euro“ bei beiden im Beleg) und keine
sinnverdrehende Umstellung ohne Verneinungswort. Sie ist ein Sieb gegen
Erfundenes, keine Wahrheitsprüfung; deshalb steht neben jedem Satz sein Beleg.
Explizite Uhrzeitgrenzen werden nur für erkannte Formen wie „erst nach 10 Uhr“,
„ab 10 Uhr“, „nicht vor 10 Uhr“, „bis 10 Uhr“ sowie erkannte gepaarte
Uhrzeitbereiche verglichen; das ist keine
allgemeine Bedeutungs- oder Satzklammerprüfung. Wenn mehrere Ereignisse dieselbe
Uhrzeit mit verschiedenen Grenzen verbinden, kann der Vergleich eine Aussage
vorsichtshalber zurückweisen. Was der Beleg selbst behauptet, prüft sie nicht.
Erkannte explizite Grenzen an einzelnen Kalenderdaten werden ebenfalls auf vertauschte
Relationen geprüft. Bei ausdrücklich genannter Gültigkeit bleiben die Grenzen
des über Inhaltswörter zugeordneten Satzteils erhalten. Das ist keine vollständige
Prüfung von Ereigniszuordnung, Zeiträumen, Aktualität oder ausgelassenen Bedingungen.
Bei Belegen mit erkannten Erlaubnissen oder Pflichten („darf“, „erlaubt“, „muss“,
„soll“ usw.) müssen Antwortsätze vollständig wörtlich in einem zitierten
Quellkörper stehen. Anführungszeichen im Quellkörper führen konservativ zum
Zitatmodus. Leerraum, Groß-/Kleinschreibung und ein abschließender Punkt dürfen
variieren; Fragezeichen und Zitierrahmen bleiben erhalten. Das beweist weder die
Verbindlichkeit einer Quelle noch Bedingungen in einem Folgesatz. Das ist ein
begrenzter Zusatzschutz, keine allgemeine Grammatikprüfung. Nur bei
einer unverändert wiedergegebenen Regel darf der eigenständige Status „Freigabe
liegt noch nicht vor“ derselben Quelle daneben stehen, ohne ihr zu widersprechen.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping, Sequence

from .fristen import MONATE, bezugstag, fristen_in, ohne_jahr

MAX_SATZ_ZEICHEN = 600


# -- Eingabe und Ergebnis ------------------------------------------------------


@dataclass(frozen=True)
class Beleg:
    """Eine belegte Textstelle.

    `text` ist die Stelle wörtlich, `kopf` die Kennzeichnung der Quelle (Titel, Datum),
    die ebenfalls belegt ist. `zeit` ist der Zeitpunkt der Quelle: Auf ihn beziehen
    sich relative Datumsangaben im Text. `gueltig` ist falsch, wenn die Quelle
    entzogen oder überholt ist.
    """

    nummer: str
    text: str
    zeit: datetime | date | None = None
    kopf: str = ''
    gueltig: bool = True


@dataclass(frozen=True)
class Satz:
    """Ein Satz mit den Nummern seiner Belege."""

    text: str
    belege: tuple[str, ...]


@dataclass(frozen=True)
class Urteil:
    """Ergebnis für einen Satz: bestanden oder verworfen, mit allen Gründen."""

    satz: Satz
    bestanden: bool
    gruende: tuple[str, ...] = ()

    @property
    def grund(self) -> str:
        return self.gruende[0] if self.gruende else ''


# -- Normalisieren -----------------------------------------------------------


def falten(text: str) -> str:
    """Klein, ohne Umlaute und Endungen der Umlautschreibung: „Müller“ = „Mueller“ = „muller“."""
    text = str(text or '').casefold().replace('ß', 'ss')
    text = text.replace('ä', 'a').replace('ö', 'o').replace('ü', 'u')
    for paar in ('ae', 'oe', 'ue'):
        text = text.replace(paar, paar[0])
    return text


def _maske(text: str, treffer: re.Match) -> str:
    return text[:treffer.start()] + ' ' * (treffer.end() - treffer.start()) + text[treffer.end():]


# -- Daten -------------------------------------------------------------------

_MONAT = '(' + '|'.join(sorted(MONATE, key=len, reverse=True)) + r')\b\.?'
_ISO = re.compile(r'(?<![\d-])(\d{4})-(\d{2})-(\d{2})(?![\d])')
_PUNKT_BEREICH = re.compile(r'(?<![\d.,/-])(\d{1,2})\.\s*(?:[-–/]|bis)\s*(\d{1,2})\.\s?(\d{1,2})\.(?:\s?(\d{4}|\d{2})(?!\d))?(?![\d])')
_PUNKT = re.compile(r'(?<![\d.,/-])(\d{1,2})\.\s?(\d{1,2})\.(?:\s?(\d{4}|\d{2})(?!\d))?(?![\d])')
_NAME_BEREICH = re.compile(r'(?<![\d.])(\d{1,2})\.?\s*(?:[-–/]|bis)\s*(\d{1,2})\.?\s*' + _MONAT + r'(?:\s+(\d{4})(?!\d))?', re.I)
_NAME = re.compile(r'(?<![\d.])(\d{1,2})\.?\s*' + _MONAT + r'(?:\s+(\d{4})(?!\d))?', re.I)


@dataclass(frozen=True)
class Datum:
    tag: int
    monat: int
    jahr: int | None = None

    def voll(self) -> date | None:
        try:
            return date(self.jahr, self.monat, self.tag) if self.jahr else None
        except ValueError:
            return None

    def gueltig(self) -> bool:
        if self.jahr:
            return self.voll() is not None
        return 1 <= self.monat <= 12 and 1 <= self.tag <= calendar.monthrange(2024, self.monat)[1]


def _jahr(wert: str | None) -> int | None:
    if not wert:
        return None
    zahl = int(wert)
    return 2000 + zahl if len(wert) == 2 else zahl


def _datumstellen(text: str) -> tuple[list[tuple[re.Match, tuple[Datum, ...]]], str]:
    """Existing date parser with positions retained for calendar-bound checks."""
    gefunden: list[tuple[re.Match, tuple[Datum, ...]]] = []
    rest = text

    def nehmen(treffer: re.Match, *daten: Datum) -> bool:
        nonlocal rest
        if not all(d.gueltig() for d in daten):
            return False
        gefunden.append((treffer, daten))
        rest = _maske(rest, treffer)
        return True

    for t in list(_ISO.finditer(rest)):
        nehmen(t, Datum(int(t[3]), int(t[2]), int(t[1])))
    for t in list(_PUNKT_BEREICH.finditer(rest)):
        jahr = _jahr(t[4])
        nehmen(t, Datum(int(t[1]), int(t[3]), jahr), Datum(int(t[2]), int(t[3]), jahr))
    for t in list(_PUNKT.finditer(rest)):
        nehmen(t, Datum(int(t[1]), int(t[2]), _jahr(t[3])))
    for t in list(_NAME_BEREICH.finditer(rest)):
        monat, jahr = MONATE[t[3].lower()], _jahr(t[4])
        nehmen(t, Datum(int(t[1]), monat, jahr), Datum(int(t[2]), monat, jahr))
    for t in list(_NAME.finditer(rest)):
        nehmen(t, Datum(int(t[1]), MONATE[t[2].lower()], _jahr(t[3])))
    return gefunden, rest


def daten_in(text: str) -> tuple[list[Datum], str]:
    """Alle Datumsangaben eines Textes (ohne Auflösung relativer Angaben) und der Text ohne sie."""
    stellen, rest = _datumstellen(text)
    return [datum for _, daten in stellen for datum in daten], rest


_DATUM_GRENZE = re.compile(
    r'(?<!\w)(?P<zusatz>(?:(?:erst|nur|frühestens|spätestens|nicht)\s+)*)'
    r'(?P<operator>ab|bis|vor|nach|seit|am)\s+(?:(?:dem|zum)\s+)?$', re.I)
_GELTUNG = re.compile(r'\b(?:gilt|gelten|gültig\w*|gueltig\w*)\b', re.I)
_GELTUNG_QUELLE = re.compile(r'\b(?:gilt|gelten|galt|galten|gültig\w*|gueltig\w*)\b', re.I)


def _datumsgrenzen(text: str) -> list[tuple[Datum, str]]:
    grenzen = []
    for stelle, daten in _datumstellen(text)[0]:
        if len(daten) != 1:
            continue  # Compact date ranges need a separate paired-range contract.
        davor = _DATUM_GRENZE.search(text[:stelle.start()])
        if davor is None:
            continue
        operator = davor['operator'].casefold()
        modifier = ':'.join(falten(davor['zusatz']).split())
        relation = {('erst', 'nach'): 'nach', ('nur', 'nach'): 'nach',
                    ('fruhestens', 'ab'): 'ab', ('spatestens', 'bis'): 'bis',
                    ('nur', 'bis'): 'bis', ('erst', 'ab'): 'ab'}.get(
                        (modifier, operator), f'{modifier}:{operator}' if modifier else operator)
        grenzen.append((daten[0], relation))
    return grenzen


def _gleicher_tag(a: Datum, b: Datum) -> bool:
    return (a.tag, a.monat) == (b.tag, b.monat) and (a.jahr is None or b.jahr is None or a.jahr == b.jahr)


def _pruefe_datumsgrenzen(text: str, belege: Sequence[Beleg]) -> list[str]:
    """Preserve recognized explicit calendar relations, never from source headers.

    This is not event attribution or general temporal entailment. Only clauses
    explicitly asserting validity must also retain their matching dated bounds.
    Unrelated clauses and imperative summaries remain independent.
    """
    grenzen = _datumsgrenzen(text)
    beleg_grenzen = [grenze for beleg in belege for grenze in _datumsgrenzen(beleg.text)]
    gruende = []
    for datum, relation in grenzen:
        passend = [r for d, r in beleg_grenzen if _gleicher_tag(datum, d)]
        if passend and relation not in passend:
            gruende.append(f'Datumsgrenze an {datum.tag:02d}.{datum.monat:02d}. stimmt nicht mit dem Beleg überein')
    for klausel in _klauseln(text):
        if not _GELTUNG.search(klausel):
            continue
        _, ohne_datum = _datumstellen(klausel)
        anker = _inhaltswoerter(_GELTUNG.sub('', ohne_datum))
        eigene_grenzen = _datumsgrenzen(klausel)
        kandidaten = []
        for beleg in belege:
            for quelle in _klauseln(beleg.text):
                if not _GELTUNG_QUELLE.search(quelle):
                    continue
                _, quelle_ohne_datum = _datumstellen(quelle)
                gemeinsam = anker.intersection(_inhaltswoerter(_GELTUNG_QUELLE.sub('', quelle_ohne_datum)))
                if gemeinsam:
                    kandidaten.append((len(gemeinsam), _datumsgrenzen(quelle)))
        # Separate applicability clauses are alternatives, not a conjunction of
        # every bound sharing one noun. Prefer the strongest substantive overlap.
        bester = max((rang for rang, _ in kandidaten), default=0)
        passende = [bedingungen for rang, bedingungen in kandidaten if rang == bester]
        if passende and not any(all(any(_gleicher_tag(datum, d) and r == relation
                                        for d, r in eigene_grenzen)
                                    for datum, relation in bedingungen) for bedingungen in passende):
            gruende.append('Datumsgrenze einer Gültigkeitsaussage wurde weggelassen oder verändert')
    return gruende


# -- Uhrzeiten, Adressen, Kennungen, Zahlen ------------------------------------

# Both patterns keep four groups: start hour/minute, end hour/minute.
# A bare end hour requires Uhr/h; colon minutes are independently recognizable.
_BEREICH_ANFANG = r'(\d{1,2})(?:[.:]([0-5]\d))?\s*(?:(?:Uhr|h)\s*)?'
_ZEIT_BEREICHE = tuple(re.compile(prefix + _BEREICH_ANFANG + separator + ende, re.I)
    for prefix, separator in ((r'\bzwischen\s+', r'und\s*'), (r'(?<![\d.:])', r'(?:[-–]|bis)\s*'))
    for ende in (r'(\d{1,2})(?:[.:]([0-5]\d))?\s*(?:Uhr|h)\b',
                 r'(\d{1,2}):([0-5]\d)(?!\d)(?:\s*(?:Uhr|h)\b)?'))
_BEREICH_ZUSATZ = re.compile(r'\b((?:(?:erst|nur|nicht|frühestens|spätestens)\s+){1,2})(?:(?:von|zwischen)\s+)?$', re.I)
_ZEIT_DOPPELPUNKT = re.compile(r'(?<![\d:.])([01]?\d|2[0-3]):([0-5]\d)(?!\d)(?:\s*(?:Uhr|h)\b)?', re.I)
_ZEIT_PUNKT = re.compile(r'(?<![\d.])([01]?\d|2[0-3])\.([0-5]\d)\s*(?:Uhr|h)\b', re.I)
_ZEIT_UHR = re.compile(r'(?<![\d.:])([01]?\d|2[0-3])\s*(?:Uhr|h)\b(?:\s*([0-5]\d)(?!\d))?', re.I)
_ZEITBEDINGUNG = re.compile(
    r'\b(?P<zusatz>(?:(?:erst|nur|nicht|frühestens|spätestens)\s+){0,2})'
    r'(?P<operator>nach|vor|ab|bis|um)\s*'
    r'(?P<stunde>[01]?\d|2[0-3])'
    r'(?:(?::(?P<doppel>[0-5]\d)(?:\s*(?:Uhr|h)\b)?|'
    r'\.(?P<punkt>[0-5]\d)\s*(?:Uhr|h)\b|'
    r'\s*(?:Uhr|h)\b(?:\s*(?P<uhr>[0-5]\d))?))', re.I)
_MAIL = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
_LINK = re.compile(r'(?:https?://|www\.)[^\s<>"\')]+', re.I)
_KENNUNG = re.compile(r'\b(?=[\w./-]*\d)(?=[\w./-]*[A-Za-z])[\w./-]+\b|\b\d+(?:[-/]\d+)+\b')
_ZAHL = re.compile(r'(?<![\w.,])(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)(?!\w)'
                   r'(?:\s*(€|EUR\b|Euro\b|\$|USD\b|Dollar\b|%|Prozent\b))?', re.I)
_ZAHLWORT = {'zwei': 2, 'drei': 3, 'vier': 4, 'funf': 5, 'sechs': 6, 'sieben': 7, 'acht': 8, 'neun': 9, 'zehn': 10,
             'elf': 11, 'zwolf': 12, 'zwanzig': 20, 'dreissig': 30, 'hundert': 100, 'tausend': 1000}
_WAEHRUNG = {'€': 'eur', 'eur': 'eur', 'euro': 'eur', '$': 'usd', 'usd': 'usd', 'dollar': 'usd', '%': '%', 'prozent': '%'}


def zeiten_in(text: str) -> tuple[set[tuple[int, int]], str]:
    """Uhrzeiten als (Stunde, Minute) und der Text ohne sie."""
    zeiten: set[tuple[int, int]] = set()
    rest = text
    for muster in _ZEIT_BEREICHE:
        for t in list(muster.finditer(rest)):
            if int(t[1]) <= 23 and int(t[3]) <= 24:
                zeiten |= {(int(t[1]), int(t[2] or 0)), (int(t[3]) % 24, int(t[4] or 0))}
                rest = _maske(rest, t)
    for muster in (_ZEIT_DOPPELPUNKT, _ZEIT_PUNKT):
        for t in list(muster.finditer(rest)):
            zeiten.add((int(t[1]), int(t[2])))
            rest = _maske(rest, t)
    for t in list(_ZEIT_UHR.finditer(rest)):
        zeiten.add((int(t[1]), int(t[2] or 0)))
        rest = _maske(rest, t)
    return zeiten, rest


def _zeitbedingungen_in(text: str) -> set[tuple[tuple[int, int], str]]:
    """Erkannte Uhrzeitgrenzen samt Relation; ungebundene Uhrzeiten gelten als genaue Uhrzeit.

    Modifier werden nur in den expliziten, üblichen Formen normalisiert. Unbekannte Kombinationen bleiben an ihre
    wörtliche Form gebunden, damit sie nicht durch eine anders formulierte Grenze gestützt werden.
    """
    ergebnis: set[tuple[tuple[int, int], str]] = set()
    bedingt: set[tuple[int, int]] = set()
    rest = text
    # Keep the two endpoints paired: a time window is neither two exact slots nor
    # interchangeable endpoints from several windows. Mask before operator parsing.
    for muster in _ZEIT_BEREICHE:
        for treffer in list(muster.finditer(rest)):
            if int(treffer[1]) > 23 or int(treffer[3]) > 24:
                continue
            anfang = (int(treffer[1]), int(treffer[2] or 0))
            ende = (int(treffer[3]) % 24, int(treffer[4] or 0))
            zusatz = _BEREICH_ZUSATZ.search(rest[:treffer.start()])
            modifier = ':'.join(falten(zusatz[1]).split()) if zusatz else ''
            relation = f'bereich:{anfang}:{ende}:{modifier}'
            ergebnis.update(((anfang, relation), (ende, relation)))
            bedingt.update((anfang, ende))
            rest = _maske(rest, treffer)
    for treffer in _ZEITBEDINGUNG.finditer(rest):
        stunde = int(treffer['stunde'])
        minute = int(treffer['doppel'] or treffer['punkt'] or treffer['uhr'] or 0)
        uhrzeit = (stunde, minute)
        bedingt.add(uhrzeit)
        operator = falten(treffer['operator'])
        zusatz = falten(treffer['zusatz']).split()
        relation = {'nach': 'nach', 'vor': 'vor', 'ab': 'ab', 'bis': 'bis', 'um': 'um'}[operator]
        if zusatz:
            modifier = ':'.join(zusatz)
            relation = {
                ('erst', 'nach'): 'nach',
                ('nur', 'nach'): 'nach',
                ('fruhestens', 'ab'): 'ab',
                ('spatestens', 'bis'): 'bis',
            }.get((modifier, operator), f'wortlaut:{modifier}:{operator}')
        ergebnis.add((uhrzeit, relation))
    # A bare clock value still denotes an exact time (e.g. „Vortrag 11 Uhr“), but only from source text.
    for uhrzeit in zeiten_in(text)[0] - bedingt:
        ergebnis.add((uhrzeit, 'um'))
    return ergebnis


def _dezimal(roh: str) -> Decimal | None:
    try:
        if re.fullmatch(r'\d{1,3}(?:\.\d{3})+(?:,\d+)?', roh):
            return Decimal(roh.replace('.', '').replace(',', '.'))
        return Decimal(roh.replace(',', '.'))
    except InvalidOperation:
        return None


def zahlen_in(text: str) -> list[tuple[Decimal, str]]:
    """Zahlen mit Währung oder Prozent („eur“, „usd“, „%“, sonst leer); Zahlwörter „zwei“ … zählen mit."""
    ergebnis: list[tuple[Decimal, str]] = []
    for t in _ZAHL.finditer(text):
        wert = _dezimal(t[1])
        if wert is not None:
            ergebnis.append((wert.normalize() if wert else Decimal(0), _WAEHRUNG.get((t[2] or '').lower(), '')))
    for wort in re.findall(r'[A-Za-zÄÖÜäöüß]+', text):
        zahl = _ZAHLWORT.get(falten(wort))
        if zahl is not None:
            ergebnis.append((Decimal(zahl), ''))
    return ergebnis


def _ohne(text: str, *muster: re.Pattern) -> tuple[str, list[str]]:
    """Text ohne die Treffer der Muster und die Treffer selbst (klein, ohne Randzeichen)."""
    treffer_liste: list[str] = []
    for m in muster:
        for t in list(m.finditer(text)):
            treffer_liste.append(t.group(0).strip().rstrip('.,;:').casefold())
            text = _maske(text, t)
    return text, treffer_liste


# -- Wörter, Namen -------------------------------------------------------------

_WORT = re.compile(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß'’]*")
_TAGE = {'montag': 0, 'dienstag': 1, 'mittwoch': 2, 'donnerstag': 3, 'freitag': 4, 'samstag': 5, 'sonnabend': 5, 'sonntag': 6}
_MONATSNAMEN = {falten(name): nummer for name, nummer in MONATE.items() if len(name) >= 3 and name not in
                ('jan', 'feb', 'mär', 'apr', 'jun', 'jul', 'aug', 'sep', 'sept', 'okt', 'nov', 'dez', 'mar')}
_MONATSPHRASE = re.compile(r'\b(anfang|mitte|ende)\s+(' + '|'.join(sorted(_MONATSNAMEN, key=len, reverse=True)) + r')\b')

#: Funktionswörter: Artikel, Pronomen, Präpositionen, Konjunktionen, Hilfsverben, häufige Satzanfänge.
_FUNKTION = frozenset(falten(w) for w in '''
der die das den dem des ein eine einer einem einen eines er sie es wir ihr ich du man sich wer was wie wo wann warum wenn
weil dass ob und oder aber sondern doch denn auch noch nur schon sehr mehr weniger bereits bisher jetzt nun dann danach
davor dazu dafuer damit dabei darauf daran darin darum deshalb daher deswegen zudem ausserdem ebenfalls ebenso allerdings
jedoch leider bitte laut nach vor bei mit von vom zu zum zur zur auf aus an am im in ins um ueber unter fuer gegen ohne ausserhalb innerhalb
durch bis seit ab als so hier dort da ist sind war waren wird werden wurde wurden hat haben hatte hatten kann koennen
soll sollen muss muessen will wollen darf duerfen bleibt bleiben gibt geben liegt liegen steht stehen findet finden
folgt gilt gelten laeuft neu neue neuer neues neuen alt alte alter altes offen aktuell aktuelle aktueller vermutlich
wohl wahrscheinlich moeglicherweise angeblich beide alle alles jede jeder jedes jeden kein keine keiner keinen einige
viele wenige diese dieser dieses diesen jene jener zuletzt zuerst erst erste ersten erster letzte letzten letzter
naechste naechsten naechster kommende kommenden kommender ihre ihren ihrer ihrem ihres seine seinen seiner seinem
unsere unseren unserer unserem meine meinen meiner meinem andere anderer anderen anderem anderes
'''.split())

#: Allgemeine Gattungswörter, die in Zusammenfassungen vorkommen, ohne ein Name zu sein.
_GATTUNG = frozenset(falten(w) for w in '''
termin termine frist fristen programm vortrag vortraege anfrage angebot angebote rechnung rechnungen mail mails nachricht
nachrichten einladung einladungen absage absagen zusage zusagen bitte bitten aufgabe aufgaben stand sache sachen projekt
projekte person personen ort orte datum uhr uhrzeit woche wochen tag tage monat monate jahr jahre unterlagen unterlage
dokument dokumente anhang anhaenge antwort antworten rueckmeldung rueckmeldungen bestaetigung bestaetigungen quelle
quellen akte akten lage thema themen frage fragen entscheidung entscheidungen aenderung aenderungen verschiebung
verlauf beleg belege beleg euro prozent kosten preis preise betrag betraege summe zahlung zahlungen anmeldung anmeldungen
teilnahme teilnehmer teilnehmerin teilnehmerinnen veranstaltung veranstaltungen besprechung besprechungen treffen
gespraech gespraeche telefonat sitzung meeting workshop seminar tagung konferenz fachtag ergebnis ergebnisse ergebnisse
entwurf entwuerfe vertrag vertraege antrag antraege abgabe abgaben lieferung lieferungen bestellung bestellungen
zeitplan planung ablauf einreichung einreichfrist anmeldeschluss beginn ende start schluss mitte anfang
frau herr firma behoerde amt
kunde kunden kundin partner partnerin team kollege kollegin
zusammenfassung hinweis hinweise information informationen inhalt inhalte text texte datei dateien liste
ueberblick sachstand status bericht berichte protokoll ergaenzung ergaenzungen korrektur korrekturen
raum raeume adresse adressen anschrift zugang zugangsdaten link links seite seiten
druckdaten plakat
zeitraum zeitraums zeitraumes zeitraeume namensvetter namensvetters namensvettern gleichnamige gleichnamiger gleichnamigen
'''.split())

_STATUS = (
    ('erledigt', ('erledigt', 'abgeschlossen', 'fertig', 'fertiggestellt', 'erfuellt', 'geschafft')),
    ('bezahlt', ('bezahlt', 'ueberwiesen', 'beglichen', 'gezahlt')),
    ('bestätigt', ('bestaetigt', 'bestaetigung', 'zugesagt', 'zusage', 'zugestimmt', 'einverstanden')),
    ('genehmigt', ('genehmigt', 'bewilligt', 'freigegeben', 'angenommen')),
    ('geliefert', ('geliefert', 'zugestellt', 'versandt', 'verschickt', 'versendet', 'gesendet', 'geschickt')),
    ('unterschrieben', ('unterschrieben', 'unterzeichnet')),
    ('eingereicht', ('eingereicht', 'abgegeben', 'uebermittelt', 'eingegangen', 'erhalten', 'angekommen')),
    ('offen', ('offen', 'ausstehend', 'unerledigt', 'unbezahlt')),
)
_STATUS_STAEMME = tuple((gruppe, tuple(falten(w) for w in woerter)) for gruppe, woerter in _STATUS)
#: Beugungsendungen, mit denen ein Statuswort noch dasselbe Wort ist („erledigte“, „ausstehenden“); „Fertigung“ gehört nicht dazu.
_ENDUNGEN = ('', 'e', 'en', 'em', 'er', 'es', 'n', 's')
#: „noch nicht“, „noch kein“: der Gegenstatus zu jeder Erledigt-Aussage, auch ohne das Wort „offen“.
_NOCH_NICHT = re.compile(r'\bnoch\s+(?:nicht|kein\w*)\b')

_VERNEINUNG_WOERTER = ('nicht', 'kein*', 'nie', 'niemals', 'ohne', 'weder', 'abgesagt', 'absage', 'absagen', 'storniert',
                       'stornierung', 'entfaellt', 'entfallen', 'faellt aus', 'faellt weg', 'ausgefallen',
                       'zurueckgezogen', 'gestrichen', 'abgelehnt', 'ablehn*', 'unmoeglich', 'verweigert',
                       'widerrufen', 'zurueckgenommen', 'nirgends', 'niemand')


def _regex(woerter: Iterable[str]) -> re.Pattern:
    teile = []
    for wort in woerter:
        teile.append(re.escape(falten(wort.rstrip('*'))) + (r'\w*' if wort.endswith('*') else ''))
    return re.compile(r'\b(?:' + '|'.join(teile) + r')\b')


_VERNEINUNG = _regex(_VERNEINUNG_WOERTER)
_RELATIV = re.compile(
    r'\b(heute|morgen|gestern|vorgestern|ubermorgen|(?:diese|nachste|kommende|letzte|vorige|vergangene)[nrms]?\s+(?:woche|monat|jahr)'
    r'|in\s+(?:\d{1,3}|zwei|drei|vier|funf|sechs|sieben|acht|neun|zehn|einer|einem|ein|eine)\s+(?:tag|woche|monat)(?:en|e|n)?)\b')
_MONATSWORT = '|'.join(sorted(MONATE, key=len, reverse=True))
#: Satzteile: Satzzeichen, Komma, „aber“ … ; der Punkt nach einer Zahl gehört zum Datum („28. Oktober“, „12.10.“).
_KLAUSEL = re.compile(
    r'[;:!?\n]|(?<!\d)\.|(?<=\d)\.(?=\s+(?!(?:' + _MONATSWORT + r')\b)[A-ZÄÖÜ])|,\s|\s(?:aber|sondern|jedoch|während)\s', re.I)


def _woerter(text: str) -> list[str]:
    """Alle Wörter geändert zu gefalteten Teilen (Bindestrich trennt), ohne Einbuchstabiges."""
    teile: list[str] = []
    for wort in _WORT.findall(text):
        teile.extend(t for t in (falten(t) for t in re.split(r"['’]", wort)) if len(t) >= 2)
    return teile


def _gleiches_wort(a: str, b: str) -> bool:
    """Gleiches Wort bis auf Beugung und Ableitung (Vorsilbe gleich, Rest höchstens vier Zeichen)."""
    if a == b:
        return True
    kurz, lang = (a, b) if len(a) <= len(b) else (b, a)
    return len(kurz) >= 4 and lang.startswith(kurz) and len(lang) - len(kurz) <= 4


@dataclass
class _Token:
    text: str
    start: int
    ende: int


def _namensfolgen(satz: str) -> list[list[tuple[str, str]]]:
    """Folgen aus großgeschriebenen Wörtern (gefaltet, Original), die weder Funktions- noch Gattungswörter noch Tag oder Monat sind."""
    tokens = [_Token(m.group(0), m.start(), m.end()) for m in _WORT.finditer(satz)]
    folgen: list[list[tuple[str, str]]] = []
    aktuell: list[tuple[str, str]] = []
    letzte: _Token | None = None
    for token in tokens:
        for teil in re.split(r"['’]", token.text)[:1]:
            gefaltet = falten(teil)
            name = (teil[:1].isupper() and len(gefaltet) >= 2 and gefaltet not in _FUNKTION and gefaltet not in _GATTUNG
                    and gefaltet not in _TAGE and gefaltet not in _MONATSNAMEN and gefaltet not in _ZAHLWORT
                    and not any(gefaltet == s for _, staemme in _STATUS_STAEMME for s in staemme))
            zusammen = letzte is not None and re.fullmatch(r'[\s\-–/&]*', satz[letzte.ende:token.start]) is not None
            if name:
                if aktuell and not zusammen:
                    folgen.append(aktuell)
                    aktuell = []
                aktuell.append((gefaltet, teil))
            elif aktuell:
                folgen.append(aktuell)
                aktuell = []
        letzte = token
    if aktuell:
        folgen.append(aktuell)
    # Kleingeschriebene Teile nach Bindestrich („Bio-fachtag“) sind selten; großgeschriebene sind erfasst.
    return folgen


def _folge_belegt(folge: list[tuple[str, str]], woerter: list[str]) -> bool:
    n = len(folge)
    return any(all(_gleiches_wort(f, woerter[i + j]) for j, (f, _) in enumerate(folge)) for i in range(len(woerter) - n + 1))


# -- Belegte Menge ---------------------------------------------------------------


@dataclass
class _Pool:
    """Was die zitierten Belege zusammen tragen."""

    text: str = ''
    woerter: list[str] = field(default_factory=list)
    daten_voll: set[date] = field(default_factory=set)
    daten_kurz: set[tuple[int, int]] = field(default_factory=set)
    zeiten: set[tuple[int, int]] = field(default_factory=set)
    zeitbedingungen: set[tuple[tuple[int, int], str]] = field(default_factory=set)
    zahlen: dict[Decimal, set[str]] = field(default_factory=dict)
    jahre: set[int] = field(default_factory=set)
    kennungen: set[str] = field(default_factory=set)
    monate: set[int] = field(default_factory=set)
    verneinend: bool = False


def _pool(belege: Sequence[Beleg], zusatz: Iterable[str]) -> _Pool:
    pool = _Pool()
    for beleg in belege:
        gesamt = f'{beleg.kopf}\n{beleg.text}'.strip()
        pool.text += '\n' + gesamt
        daten, rest = daten_in(gesamt)
        bezug = bezugstag(beleg.zeit) if beleg.zeit else None
        for d in daten:
            pool.monate.add(d.monat)
            if d.jahr:
                pool.jahre.add(d.jahr)
                if d.voll():
                    pool.daten_voll.add(d.voll())
                    pool.daten_kurz.add((d.monat, d.tag))
            else:
                pool.daten_kurz.add((d.monat, d.tag))
                aufgeloest = ohne_jahr(d.monat, d.tag, bezug) if bezug else None
                if aufgeloest:
                    pool.daten_voll.add(aufgeloest)
        if beleg.zeit:
            # Relative Angaben („bis Freitag“, „in zwei Wochen“) mit dem Zeitpunkt der Quelle.
            for f in fristen_in(beleg.text, beleg.zeit).fristen:
                pool.daten_voll.add(f.datum)
                pool.daten_kurz.add((f.datum.month, f.datum.day))
                pool.monate.add(f.datum.month)
        zeiten, rest = zeiten_in(rest)
        pool.zeiten |= zeiten
        pool.zeitbedingungen |= _zeitbedingungen_in(beleg.text)
        rest, tokens = _ohne(rest, _MAIL, _LINK, _KENNUNG)
        pool.kennungen.update(tokens)
        for wert, waehrung in zahlen_in(rest):
            pool.zahlen.setdefault(wert, set()).add(waehrung)
        pool.verneinend = pool.verneinend or bool(_VERNEINUNG.search(falten(gesamt)))
    pool.woerter = _woerter(pool.text)
    for extra in zusatz:
        pool.woerter.extend(_woerter(str(extra)))
    pool.text = falten(pool.text)
    return pool


# -- Prüfung eines Satzes ---------------------------------------------------------


def _pruefe_daten(daten: list[Datum], pool: _Pool) -> tuple[list[str], list[date]]:
    gruende: list[str] = []
    belegt: list[date] = []
    for d in daten:
        if d.jahr:
            ok = d.voll() in pool.daten_voll
            if ok:
                belegt.append(d.voll())
            elif (d.monat, d.tag) in pool.daten_kurz:
                gruende.append(f'Jahr {d.jahr} von {d.tag:02d}.{d.monat:02d}. steht nicht im Beleg')
            else:
                gruende.append(f'Datum {d.tag:02d}.{d.monat:02d}.{d.jahr} steht nicht im Beleg')
        else:
            passend = sorted(x for x in pool.daten_voll if (x.month, x.day) == (d.monat, d.tag))
            if passend or (d.monat, d.tag) in pool.daten_kurz:
                belegt.extend(passend)
            else:
                gruende.append(f'Datum {d.tag:02d}.{d.monat:02d}. steht nicht im Beleg')
    return gruende, belegt


def _klauseln(text: str) -> list[str]:
    return [k for k in _KLAUSEL.split(text) if k and k.strip()]


def _inhaltswoerter(text: str) -> set[str]:
    return {w[:5] for w in _woerter(text) if len(w) >= 4 and w not in _FUNKTION and not _VERNEINUNG.fullmatch(w)}


# Intentionally literal: this is not a parser for arbitrary permission or
# condition paraphrases. Keep commas/conjunctions and the complete word order.
_ERLAUBNIS = re.compile(r'\b(?:darf|dürfen|duerfen)\b')
_REGEL_BEDINGUNG = re.compile(r'\b(?:(?:erst|nur)\s+nach|wenn|sofern|sobald|falls)\b')
_ZULAESSIGKEIT_WENN = re.compile(
    r'\b(?:ist|sind)\s+(?:nur\s+)?(?:zulässig|zulaessig|gestattet|erlaubt)\s*,?\s+wenn\b', re.I)
_PASSIV = re.compile(r'\b([a-zäöüß]+)\s+werden\b')
_FEHLT = re.compile(r'(?:(?:die|der|das|eine|ein)\s+)?([a-zäöüß]+)\s+(?:liegt|liegen)\s+(?:noch\s+)?nicht\s+vor')
_ZEITRAHMEN = re.compile(
    r'\b(?P<relation>vor|nach|während|waehrend|bevor|nachdem)\s+'
    r'(?:(?:der|dem|den|die|das|des|einer|einem|eines)\s+)?'
    r'(?:(?P<adjektiv>[a-zäöüß]+(?:e|en|em|er|es))\s+)?'
    r'(?!(?:darf|dürfen|duerfen|ist|sind|war|waren|wird|werden|wurde|wurden|hat|haben|'
    r'kann|können|muss|müssen|soll|sollen|nicht|nie|kein|keine|keiner|keinem|keinen)\b)'
    r'(?P<ereignis>[a-zäöüß]+)\b', re.I)
# Narrow boundary form used only to keep an exact post-boundary clause from
# inheriting a prohibition that explicitly ends at that boundary.
_BIS_GRENZE = re.compile(
    r'\bbis\s+(?:(?:zu(?:r|m)?|der|dem|den|die|das|des|einer|einem|eines)\s+)?'
    r'(?:(?P<adjektiv>[a-zäöüß]+(?:e|en|em|er|es))\s+)?'
    r'(?P<ereignis>[a-zäöüß]+)\b', re.I)
_GRENZEN_PRAEDIKAT = re.compile(
    r'^(?:[.!?;]\s*|(?:nicht|kein\w*|nie|niemals|ohne|weder|darf|dürfen|duerfen|ist|sind|'
    r'war|waren|wird|werden|wurde|wurden|bleibt|bleiben|kann|können|muss|müssen|soll|sollen|'
    r'hat|haben|liegt|liegen|steht|stehen|erfolgt|erfolgte|wenn|sofern|sobald|falls|und|oder)\b)', re.I)
_NORMATIVE_AUSSAGE = re.compile(
    r'\b(?:darf|dürfen|duerfen|erlaubt\w*|zulässig\w*|zulaessig\w*|gestattet\w*|verboten\w*)\b', re.I)
# A matching prohibition can describe the same object but cannot support an allowance (or vice versa).
_ANWENDUNGS_NEGATION = re.compile(
    r'\b(?:nicht|kein(?:e|en|em|er|es)?|nie|niemals|ohne|weder|verboten\w*|untersagt\w*)\b', re.I)
_ANWENDUNGS_STOP = frozenset(falten(w)[:5] for w in '''
auftrag aufträge auftraegen vorgang vorgänge vorgaengen ticket tickets projekt projekte fall faelle
rechnung rechnungen darf dürfen duerfen erlaubt erlauben zulässig zulaessig gestattet verboten verbot
ausschliesslich ausschließlich
'''.split())
_RELATION_GLEICH = {'während': 'während', 'waehrend': 'während'}
_ANWENDUNGS_KLAUSEL = re.compile(
    r'[;:!?\n]|(?<!\d)\.|(?<=\d)\.(?=\s+(?!(?:' + _MONATSWORT + r')\b)[A-ZÄÖÜ])|,\s|'
    r'\s(?:aber|sondern|jedoch)\s', re.I)
_ANWENDUNGS_KOORDINATION = re.compile(r'\s+(?:und|oder)\s+', re.I)
_ENDLICH = re.compile(r'\b(?:ist|sind|war|waren|wird|werden|wurde|wurden|hat|haben|kann|können|'
                      r'muss|müssen|darf|dürfen|soll|sollen|liegt|liegen|steht|stehen|bleibt|bleiben)\b', re.I)


def _regeltext(text: str) -> str:
    # casefold/falten would identify “Maße” with “Masse”; lower preserves ß/umlauts.
    return ' '.join(text.lower().strip().strip('.!?').split())


# This deliberately bounded source-unit contract is not a grammar/authority parser.
# Preserve colons, semicolons, internal line wrapping and punctuation clusters.
_REGELSIGNAL = re.compile(_NORMATIVE_AUSSAGE.pattern + r'|\b(?:muss|müssen|muessen|soll|sollen)\b', re.I)
_ABKUERZUNG = re.compile(r'\b(?:z\s*\.\s*B\.|u\s*\.\s*a\.|d\s*\.\s*h\.|'
                         r'Dr\.|Prof\.|Nr\.|bzw\.|ca\.|ggf\.|usw\.|etc\.)', re.I)
_ZITATZEICHEN = re.compile(r'["\'„“”‚‘’«»‹›`]+')


def originaltext(text: str) -> str:
    """Only spacing/case and a final period may vary; questions/quotes never do."""
    return ' '.join(text.strip().removesuffix('.').lower().split())


def originalabschnitte(text: str) -> tuple[str, ...]:
    """Complete bounded source units, keeping abbreviation/number punctuation intact.

    Unknown grammar and inter-sentence document status are outside this contract.
    A number's trailing period stays attached (ordinal/date ambiguity); merging
    adjacent sentences conservatively is preferable to issuing a false fragment.
    """
    return tuple(teil for _, _, teil in originalabschnitt_stellen(text))


def originalabschnitt_stellen(text: str) -> tuple[tuple[int, int, str], ...]:
    """Original units with offsets, so paragraph and sentence boundaries can share spans."""
    geschuetzt = {i for match in _ABKUERZUNG.finditer(text)
                  for i in range(match.start(), match.end()) if text[i] == '.'}
    teile, start = [], 0
    for match in re.finditer(r'[.!?]+', text):
        if all(text[i] == '.' and (i in geschuetzt or (i > 0 and text[i - 1].isdigit()))
               for i in range(match.start(), match.end())):
            continue
        ende = match.end()
        # A closing quote belongs to its sentence, never to the next one.
        while ende < len(text) and text[ende] in '"\'“”‘’»›`':
            ende += 1
        raw = text[start:ende]
        if teil := raw.strip():
            trim_start = start + len(raw) - len(raw.lstrip())
            teile.append((trim_start, trim_start + len(teil), teil))
        start = ende
    raw = text[start:]
    if teil := raw.strip():
        trim_start = start + len(raw) - len(raw.lstrip())
        teile.append((trim_start, trim_start + len(teil), teil))
    return tuple(teile)


def originalregelabsatz_kontexte(text: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Mehrsätzige Originalabsätze mit mindestens einer erkannten Regel.

    Für solche Absätze ist die Satzgrenze kein ausreichender Kontextbeleg:
    Ein Nachsatz kann eine Einschränkung oder den Dokumentstatus enthalten.
    Die vorhandenen Absatzgrenzen behalten ihre Quellsemantik; es werden keine
    Stichwörter für bestimmte Holdouts benötigt.
    """
    from .working_memory_analysis import _blocks

    return tuple((absatz, originalabschnitte(absatz))
                 for _, _, absatz in originalregelabsatz_einheiten(text))


def originalregelabsatz_einheiten(text: str) -> tuple[tuple[int, int, str], ...]:
    """Atomic visible spans for multi-sentence paragraphs containing a recognized rule.

    Paragraphs are the source structure; global sentence units identify an
    unpunctuated heading attached to a following paragraph. The selector and
    the final completeness check consume these same spans.
    """
    from .working_memory_analysis import _blocks

    blocks = list(_blocks(text))
    units = originalabschnitt_stellen(text)
    atomic = []
    for index, (start, end) in enumerate(blocks):
        paragraph = text[start:end].strip()
        local_units = originalabschnitte(paragraph)
        if len(local_units) <= 1 or not any(
                _REGELSIGNAL.search(unit) or _ERLAUBNIS.search(unit) for unit in local_units):
            continue
        lower, upper = start, end
        # A preceding paragraph without sentence-ending punctuation may be a
        # heading attached to the first rule by the global source-unit splitter.
        cursor = index - 1
        while cursor >= 0:
            prior_start, prior_end = blocks[cursor]
            crosses = any(unit_start <= prior_end and unit_end >= start
                          and unit_start < start and unit_end > prior_end
                          for unit_start, unit_end, _ in units)
            if not crosses:
                break
            lower = prior_start
            start = prior_start
            cursor -= 1
        raw = text[lower:upper]
        span_start = lower + len(raw) - len(raw.lstrip())
        span_end = upper - (len(raw) - len(raw.rstrip()))
        atomic.append((span_start, span_end, text[span_start:span_end]))
    # A source unit crossing two adjacent qualifying paragraphs is one span.
    merged = []
    for start, end, value in atomic:
        if merged and start <= merged[-1][1]:
            old_start, old_end, _ = merged[-1]
            merged[-1] = (old_start, max(old_end, end), text[old_start:max(old_end, end)])
        else:
            merged.append((start, end, value))
    return tuple(merged)


def originalregeln(text: str) -> tuple[str, ...]:
    """Recognized permission/obligation units; literal binding, not truth proof."""
    return tuple(originaltext(t) for t in originalabschnitte(text) if _REGELSIGNAL.search(t))


def originalbindung(satz: str, quellen: Sequence[str], *, sichtbar: Sequence[str] | None = None) -> bool:
    """If a cited source is normative, every clause needs an unquoted full original.

    Quote context cannot safely be inferred from an inner sentence, so a source
    with quotation delimiters cannot establish an affirmative rule here. The
    caller keeps the full source in the quote fallback instead.
    """
    if not originalregeln(satz) and not any(originalregeln(t) for t in quellen):
        return True
    if sichtbar is not None and len(sichtbar) != len(quellen):
        return False
    original = {originaltext(t) for n, quelle in enumerate(quellen) if not _ZITATZEICHEN.search(quelle)
                for t in originalabschnitte(quelle) if sichtbar is None or t in sichtbar[n]}
    return all(originaltext(t) in original for t in originalabschnitte(satz))


def bedingte_regeln(text: str) -> tuple[str, ...]:
    """Recognized passive permission rules, complete and normalized only for spacing/case.

    A comma belongs to the rule; splitting at it would lose a trailing condition.
    Headers do not establish permissions. Other grammar remains outside this guard.
    """
    return tuple(t for teil in _abschnitte(text, False) if (t := _regeltext(teil))
                 and _ERLAUBNIS.search(t) and _REGEL_BEDINGUNG.search(t) and _PASSIV.search(t))


def bedingte_regeln_fuer_antwort(text: str) -> tuple[str, ...]:
    """Existing passive rules plus a literal bounded `zulässig/erlaubt, wenn` clause."""
    regeln = list(bedingte_regeln(text))
    for regel in _bedingte_zulaessigkeitsregeln(text):
        if regel not in regeln:
            regeln.append(regel)
    return tuple(regeln)


def _bedingte_zulaessigkeitsregeln(text: str) -> tuple[str, ...]:
    return tuple(regel for teil in _abschnitte(text, False)
                 if (regel := _regeltext(teil)) and _NORMATIVE_AUSSAGE.search(regel)
                 and _ZULAESSIGKEIT_WENN.search(regel))


def _anwendbarkeitsklauseln(text: str) -> list[str]:
    """Split standalone conjuncts but preserve temporal 'während' as a scope marker."""
    klauseln = []
    for teil in _ANWENDUNGS_KLAUSEL.split(text):
        if not teil.strip():
            continue
        start = 0
        for koordination in _ANWENDUNGS_KOORDINATION.finditer(teil):
            links, rechts = teil[start:koordination.start()], teil[koordination.end():]
            finites_rechts = _ENDLICH.search(rechts)
            if not _ENDLICH.search(links) or finites_rechts is None:
                continue
            subjekt = rechts[:finites_rechts.start()]
            umgekehrter_zeitrahmen = bool(_ZEITRAHMEN.search(subjekt))
            subjekt = _ZEITRAHMEN.sub(' ', subjekt)
            nach_predikat = rechts[finites_rechts.end():]
            neues_subjekt_nach_predikat = (umgekehrter_zeitrahmen
                                            and len(_inhaltswoerter(nach_predikat)) >= 2)
            if not _inhaltswoerter(subjekt) and not neues_subjekt_nach_predikat:
                continue
            klauseln.append(links.strip())
            start = koordination.end()
        if teil[start:].strip():
            klauseln.append(teil[start:].strip())
    return klauseln


def _anwendbarkeitsregeln(
        text: str) -> list[tuple[set[tuple[str, str, str]], set[str], set[str], bool]]:
    """Explizit zeitlich begrenzte Erlaubnisse, je Klausel an ihrer Handlung verankert.

    Die Anker lassen Vorgangskennung und Erlaubniswort absichtlich weg. Zwei
    verbleibende Inhaltswörter sind nötig, damit eine Bedingung zu einem
    anderen Gegenstand nicht wegen derselben Kennung oder desselben Modalverbs
    an die Aussage geliehen wird.
    """
    regeln = []
    for klausel in _anwendbarkeitsklauseln(text):
        if not _NORMATIVE_AUSSAGE.search(klausel):
            continue
        zeitrahmen = list(_ZEITRAHMEN.finditer(klausel))
        if not zeitrahmen:
            continue
        rest = klausel
        for rahmen in reversed(zeitrahmen):
            rest = rest[:rahmen.start()] + ' ' * (rahmen.end() - rahmen.start()) + rest[rahmen.end():]
        rest, kennungen = _ohne(rest, _KENNUNG)
        anker = _inhaltswoerter(rest) - _ANWENDUNGS_STOP
        if len(anker) < 2:
            continue
        scopes = {
            (_RELATION_GLEICH.get(rahmen['relation'].casefold(), rahmen['relation'].casefold()),
             falten(rahmen['adjektiv'] or ''), falten(rahmen['ereignis']))
            for rahmen in zeitrahmen
        }
        negativ = bool(_ANWENDUNGS_NEGATION.search(klausel))
        regeln.append((scopes, anker, {kennung.casefold() for kennung in kennungen}, negativ))
    return regeln


def _anwendbarkeitsanker(
        text: str) -> tuple[set[tuple[str, str, str]], set[str], set[str], bool] | None:
    if not _NORMATIVE_AUSSAGE.search(text):
        return None
    zeitrahmen = list(_ZEITRAHMEN.finditer(text))
    rest = text
    for rahmen in reversed(zeitrahmen):
        rest = rest[:rahmen.start()] + ' ' * (rahmen.end() - rahmen.start()) + rest[rahmen.end():]
    rest, kennungen = _ohne(rest, _KENNUNG)
    anker = _inhaltswoerter(rest) - _ANWENDUNGS_STOP
    return (
        {(_RELATION_GLEICH.get(rahmen['relation'].casefold(), rahmen['relation'].casefold()),
          falten(rahmen['adjektiv'] or ''), falten(rahmen['ereignis'])) for rahmen in zeitrahmen},
        anker,
        {kennung.casefold() for kennung in kennungen},
        bool(_ANWENDUNGS_NEGATION.search(text)),
    )


def _gemeinsame_anker(links: set[str], rechts: set[str]) -> int:
    verwendet = set()
    for linkswort in sorted(links):
        rechtswort = next((wort for wort in sorted(rechts - verwendet)
                           if _gleiches_wort(linkswort, wort)), None)
        if rechtswort is not None:
            verwendet.add(rechtswort)
    return len(verwendet)


def _anwendbarkeit_verloren(satz: str, belege: Sequence[Beleg]) -> str | None:
    """Reject a paraphrased permission only when it restates that clause's action without its scope."""
    kandidaten = [anker for klausel in _anwendbarkeitsklauseln(satz)
                  if (anker := _anwendbarkeitsanker(klausel)) is not None]
    # Each matching clause in the cited evidence is an alternative supported
    # context, including clauses found in different cited sources. Other
    # validators remain responsible for contradictory claims across sources.
    regeln = [regel for beleg in belege for regel in _anwendbarkeitsregeln(beleg.text)]
    for kandidat_scopes, kandidat_anker, kandidat_kennungen, kandidat_negativ in kandidaten:
        related = [(regel_scopes, regel_negativ)
                   for regel_scopes, regel_anker, regel_kennungen, regel_negativ in regeln
                   if not (regel_kennungen and kandidat_kennungen
                           and regel_kennungen.isdisjoint(kandidat_kennungen))
                   and _gemeinsame_anker(regel_anker, kandidat_anker) >= 2]
        # A prohibition is never an alternative source for an allowance. Keep
        # it related, though, so opposite polarity cannot make the guard fail open.
        passende = [regel_scopes for regel_scopes, regel_negativ in related
                    if regel_negativ == kandidat_negativ]
        # Separate same-polarity source clauses are alternative contexts; a
        # conjunction of scopes inside one clause remains cumulative.
        if related and (not passende or not any(scopes <= kandidat_scopes for scopes in passende)):
            return 'Zeitliche Anwendbarkeit der Erlaubnis fehlt oder weicht vom Beleg ab'
    return None


def _bedingung_verloren(satz: str, belege: Sequence[Beleg]) -> str | None:
    # Zeilenumbrüche sind Layout, keine sichere Satzgrenze: Die Bedingung kann
    # in der nächsten Zeile stehen. Gilt auch beim Lesen alter Antworten.
    if not originalbindung(satz, [b.text for b in belege]):
        return 'Quelle mit Erlaubnis oder Pflicht verlangt vollständige wörtliche Satzbelege'
    return None


def _regel_mit_fehlendem_nachweis(satz: str, klausel: str, beleg: Beleg) -> bool:
    """Only an unchanged rule can coexist with its same-source standalone absence status."""
    fehlt = _FEHLT.fullmatch(_regeltext(klausel))
    if fehlt is None:
        return False
    for regel in bedingte_regeln(beleg.text):
        if _regeltext(satz) != regel:
            continue
        bedingung = _REGEL_BEDINGUNG.search(regel)
        ende = len(regel)
        if bedingung.group(0).endswith('nach'):
            ende = next((p.start() for p in _PASSIV.finditer(regel) if p.start() >= bedingung.end()), len(regel))
        if re.search(r'\b' + re.escape(fehlt[1]) + r'\b', regel[bedingung.end():ende]):
            return True
    return False


def _exakte_nachgrenzenregel(satz: str, klausel: str, beleg: Beleg) -> bool:
    """A literal conditional permission after a boundary is outside a prior `bis` prohibition."""
    if not _NORMATIVE_AUSSAGE.search(satz) or not _ZULAESSIGKEIT_WENN.search(satz):
        return False
    if _regeltext(satz) not in {_regeltext(teil) for teil in _abschnitte(beleg.text, False)}:
        return False
    nach_satz = [rahmen for rahmen in _ZEITRAHMEN.finditer(satz)
                 if rahmen['relation'].casefold() == 'nach']

    def gleiches_adjektiv(links, rechts):
        # Keep ß distinct from ss: boundary identity is intentionally literal.
        links, rechts = links.lower(), rechts.lower()
        if links == rechts:
            return True
        return any(links == rechts + endung or rechts == links + endung
                   for endung in _ENDUNGEN if endung)

    def gleiches_ereignis(links, rechts):
        if links['ereignis'].lower() != rechts['ereignis'].lower():
            return False
        adj_links, adj_rechts = links['adjektiv'], rechts['adjektiv']
        return not (adj_links and adj_rechts and not gleiches_adjektiv(adj_links, adj_rechts))

    def grenze_unqualifiziert(text, rahmen):
        """Only an unqualified event boundary is supported by this exception."""
        rest = text[rahmen.end():].lstrip()
        return not rest or bool(_GRENZEN_PRAEDIKAT.match(rest))

    # The exception is only supported for one parsed negative proposition.
    # Multiple negative propositions can otherwise lend each other a boundary.
    negative_clauses = [teil for teil in _anwendbarkeitsklauseln(klausel)
                        if _VERNEINUNG.search(falten(teil))]
    if len(negative_clauses) != 1:
        return False
    negativ_klausel = negative_clauses[0]
    grenze = _BIS_GRENZE.search(negativ_klausel)
    if grenze is None:
        return False
    # A prohibition that itself begins after the same event can still apply in
    # the post-boundary window (for example, `nach Abnahme bis Prüfende`).
    nach_klausel = [rahmen for rahmen in _ZEITRAHMEN.finditer(negativ_klausel)
                    if rahmen['relation'].casefold() == 'nach']
    if any(gleiches_ereignis(rahmen, kandidat)
           for rahmen in nach_klausel for kandidat in nach_satz):
        return False
    if not any(gleiches_ereignis(grenze, rahmen) for rahmen in nach_satz):
        return False
    # Additional genitive, prepositional, or relative qualification is not
    # parsed. Fail closed instead of treating the event noun alone as identity.
    return grenze_unqualifiziert(negativ_klausel, grenze) and any(
               grenze_unqualifiziert(satz, rahmen)
               for rahmen in nach_satz if gleiches_ereignis(grenze, rahmen))


def _exakte_nach_vor_regel(satz: str, klausel: str, beleg: Beleg) -> bool:
    """Keep a written after-event permission separate from a bounded before-event ban.

    Only complete original clauses and simple modal/passive grammar qualify.
    This does not infer that the event happened or that a condition is fulfilled.
    """
    # A sentence inside a multi-sentence quotation may contain neither quote
    # delimiter itself. This narrow exception does not parse reported speech.
    if re.search(r'''[„“»«"'`‘’‚‛‟”‹›]''', beleg.text):
        return False
    teile = re.split(r'([!?]+|(?<!\d)\.(?!\d)[.!?]*)', beleg.text)
    original = [_regeltext(teile[i]) for i in range(0, len(teile), 2)
                if teile[i].strip() and (i + 1 == len(teile) or '?' not in teile[i + 1])]
    positiv = _regeltext(satz)
    if positiv not in original:
        return False
    negativ = [t for t in original if _regeltext(klausel) in t]
    if len(negativ) != 1:
        return False

    def phase(regel: str, relation: str, verneint: bool):
        if re.search(r'[„“»«\"\u2018\u2019]', regel):
            return None
        modal, passiv = list(_ERLAUBNIS.finditer(regel)), list(_PASSIV.finditer(regel))
        rahmen = list(_ZEITRAHMEN.finditer(regel))
        if len(modal) != 1 or len(passiv) != 1 or len(rahmen) != 1:
            return None
        modal, passiv, rahmen = modal[0], passiv[0], rahmen[0]
        if rahmen['relation'].lower() != relation or modal.end() > passiv.start():
            return None
        # A second predicate cannot lend its event boundary to this action.
        hauptregel = regel[:passiv.end()]
        if len(_ENDLICH.findall(hauptregel)) != 2:
            return None
        if verneint:
            if re.search(r'[,;]|\b(?:und|oder|aber|sondern)\b', regel):
                return None
            negationen = list(_VERNEINUNG.finditer(falten(regel)))
            if len(negationen) != 1 or negationen[0].group(0) != 'nicht':
                return None
            if not re.search(r'\bnicht\s+$', regel[:passiv.start()]) or regel[passiv.end():].strip():
                return None
        elif _VERNEINUNG.search(falten(regel)):
            return None
        if rahmen.start() < modal.start():
            # Preserve one optional original header. No subject qualifier or
            # genitive/relative event extension may hide before the modal.
            prefix = regel[:rahmen.start()].strip()
            if ':' in prefix:
                header, prefix = prefix.split(':', 1)
                if not re.fullmatch(r'[a-zäöüß][a-zäöüß\s-]*', header):
                    return None
                prefix = prefix.strip()
            if prefix not in {'', 'erst', 'nur'} or regel[rahmen.end():modal.start()].strip():
                return None
        elif modal.end() <= rahmen.start() < passiv.start():
            rest = regel[rahmen.end():passiv.start()].strip()
            if rest != ('nicht' if verneint else ''):
                return None
        else:
            return None
        return (rahmen['adjektiv'] or '', rahmen['ereignis'], passiv[1])

    vorher = phase(negativ[0], 'vor', True)
    nachher = phase(positiv, 'nach', False)
    return vorher is not None and vorher == nachher


def _verneinungsumkehr(satz: str, belege: Sequence[Beleg], pool: _Pool) -> str | None:
    """Grund, falls Beleg und Satz sich in der Verneinung widersprechen; sonst None."""
    satz_verneint = bool(_VERNEINUNG.search(falten(satz)))
    if satz_verneint and not pool.verneinend:
        return 'Der Satz verneint, der Beleg nicht'
    if satz_verneint:
        return None
    satz_woerter = _inhaltswoerter(satz)
    satz_daten, _ = daten_in(satz)
    satz_kurz = {(d.monat, d.tag) for d in satz_daten}
    for beleg in belege:
        for klausel in _klauseln(f'{beleg.kopf}\n{beleg.text}'):
            treffer = _VERNEINUNG.search(falten(klausel))
            if not treffer:
                continue
            klausel_daten, _ = daten_in(klausel)
            teilt = (satz_woerter & _inhaltswoerter(klausel)) or (satz_kurz & {(d.monat, d.tag) for d in klausel_daten})
            if teilt:
                if _exakte_nach_vor_regel(satz, klausel, beleg):
                    continue
                if _exakte_nachgrenzenregel(satz, klausel, beleg):
                    continue
                if _regel_mit_fehlendem_nachweis(satz, klausel, beleg):
                    continue
                return f'Der Beleg verneint („{treffer.group(0)}“), der Satz nicht'
    return None


def _wortform(wort: str, stamm: str) -> bool:
    """Ist `wort` das Statuswort `stamm` in einer Beugungsform? „Fertigung“ ist nicht „fertig“."""
    return wort.startswith(stamm) and wort[len(stamm):] in _ENDUNGEN


def _status_woerter(text: str) -> set[str]:
    gruppen = set()
    for wort in _woerter(text):
        for gruppe, staemme in _STATUS_STAEMME:
            if any(_wortform(wort, stamm) for stamm in staemme):
                gruppen.add(gruppe)
    if _NOCH_NICHT.search(falten(text)):
        gruppen.add('offen')
    return gruppen


def _abschnitte(text: str, granular: bool) -> list[str]:
    if granular:
        return _klauseln(text)
    return [t for t in re.split(r'[!?\n]|(?<!\d)\.(?!\d)', text) if t.strip()]


def _gegenstatus(satz: str, belege: Sequence[Beleg]) -> str | None:
    """Grund, falls der Beleg zur selben Sache das Gegenteil des Status im Satz sagt (offen gegen erledigt).

    Verglichen wird dort, wo Satz und Beleg die meisten Sachwörter teilen, je Satzteil und je Satz des
    Belegs. Steht an dieser Stelle der Status des Satzes irgendwo, bleibt er unbeanstandet.
    """
    satz_status = _status_woerter(satz)
    if not satz_status:
        return None
    satz_woerter = _inhaltswoerter(satz) - {w[:5] for w in _status_woerter_liste()}
    if not satz_woerter:
        return None
    for granular in (True, False):
        einheiten = []
        for beleg in belege:
            for stelle in _abschnitte(f'{beleg.kopf}\n{beleg.text}', granular):
                gemeinsam = len(satz_woerter & _inhaltswoerter(stelle))
                if gemeinsam:
                    einheiten.append((gemeinsam, _status_woerter(stelle)))
        if not einheiten:
            continue
        beste = max(anzahl for anzahl, _ in einheiten)
        status_dort = [st for anzahl, st in einheiten if anzahl == beste]
        gefunden = set().union(*status_dort)
        for gruppe in sorted(satz_status):
            if gruppe in gefunden:
                continue
            gegen = {'offen'} if gruppe != 'offen' else {g for g, _ in _STATUS if g != 'offen'}
            if gegen & gefunden:
                gegenteil = sorted(gegen & gefunden)[0]
                return f'Der Beleg sagt „{gegenteil}“, der Satz „{gruppe}“'
    return None


def _status_woerter_liste() -> list[str]:
    return [w for _, staemme in _STATUS_STAEMME for w in staemme]


def satz_pruefen(satz: Satz, belege: Mapping[str, Beleg], *, zusatz_woerter: Iterable[str] = (),
                 relative_zeit_erlaubt: bool = False) -> Urteil:
    """Prüft einen Satz gegen die Belege (siehe Modulkopf). Ergibt bestanden oder Gründe der Verwerfung."""
    gruende: list[str] = []
    text = satz.text.strip() if isinstance(satz.text, str) else ''
    if not text:
        return Urteil(satz, False, ('Leerer Satz',))
    if len(text) > MAX_SATZ_ZEICHEN:
        return Urteil(satz, False, ('Satz zu lang',))
    if not satz.belege:
        return Urteil(satz, False, ('Kein Beleg genannt',))
    zitiert: list[Beleg] = []
    for nummer in dict.fromkeys(str(n) for n in satz.belege):
        beleg = belege.get(nummer)
        if beleg is None:
            gruende.append(f'Beleg {nummer} gibt es nicht')
        elif not beleg.gueltig:
            gruende.append(f'Beleg {nummer} gilt nicht mehr')
        else:
            zitiert.append(beleg)
    if gruende:
        return Urteil(satz, False, tuple(gruende))
    pool = _pool(zitiert, zusatz_woerter)
    gefaltet = falten(text)

    if not relative_zeit_erlaubt:
        relativ = _RELATIV.search(gefaltet)
        if relativ:
            gruende.append(f'Relative Zeitangabe („{relativ.group(0)}“) ist ohne festen Tag nicht prüfbar')

    daten, rest = daten_in(text)
    datum_gruende, belegte_daten = _pruefe_daten(daten, pool)
    gruende += datum_gruende
    gruende += _pruefe_datumsgrenzen(text, zitiert)
    zeiten, rest = zeiten_in(rest)
    for stunde, minute in sorted(zeiten):
        if (stunde, minute) not in pool.zeiten:
            gruende.append(f'Uhrzeit {stunde}:{minute:02d} steht nicht im Beleg')
    bedingungen = _zeitbedingungen_in(text)
    bedingungen_nach_zeit: dict[tuple[int, int], set[str]] = {}
    for uhrzeit, relation in bedingungen:
        bedingungen_nach_zeit.setdefault(uhrzeit, set()).add(relation)
    belegbedingungen_nach_zeit: dict[tuple[int, int], set[str]] = {}
    for uhrzeit, relation in pool.zeitbedingungen:
        belegbedingungen_nach_zeit.setdefault(uhrzeit, set()).add(relation)
    for uhrzeit in bedingungen_nach_zeit:
        if bedingungen_nach_zeit[uhrzeit] != belegbedingungen_nach_zeit.get(uhrzeit, set()):
            gruende.append(f'Zeitbedingung an {uhrzeit[0]}:{uhrzeit[1]:02d} stimmt nicht mit dem Beleg überein')
    rest, kennungen = _ohne(rest, _MAIL, _LINK, _KENNUNG)
    for kennung in kennungen:
        if kennung not in pool.kennungen:
            gruende.append(f'„{kennung}“ steht nicht im Beleg')
    for wert, waehrung in zahlen_in(rest):
        vorhanden = pool.zahlen.get(wert)
        if vorhanden is None and wert.is_finite() and wert == wert.to_integral_value() and 1900 <= wert <= 2100:
            vorhanden = {''} if int(wert) in pool.jahre else None
        if vorhanden is None:
            gruende.append(f'Zahl {wert:f}{" " + waehrung if waehrung else ""} steht nicht im Beleg')
        elif waehrung and waehrung not in vorhanden and '' not in vorhanden:
            gruende.append(f'Zahl {wert:f} steht im Beleg nicht mit {waehrung}')

    for wort in _WORT.findall(rest):
        tag = _TAGE.get(falten(wort))
        if tag is not None and not any(_gleiches_wort(falten(wort), w) for w in pool.woerter) \
                and tag not in {d.weekday() for d in belegte_daten}:
            gruende.append(f'Wochentag „{wort}“ steht nicht im Beleg')
    fuer_monat = falten(rest)
    for name, nummer in _MONATSNAMEN.items():
        if re.search(r'\b' + name + r'\b', fuer_monat) and nummer not in pool.monate \
                and not any(_gleiches_wort(name, w) for w in pool.woerter):
            gruende.append(f'Monat „{name.capitalize()}“ steht nicht im Beleg')
    for phrase in _MONATSPHRASE.finditer(fuer_monat):
        monat = _MONATSNAMEN[phrase[2]]
        letzter_tag = any(d.month == monat and d.day == calendar.monthrange(d.year, monat)[1] for d in pool.daten_voll)
        if phrase.group(0) not in pool.text and not (phrase[1] == 'ende' and letzter_tag):
            gruende.append(f'„{phrase.group(0).title()}“ steht nicht im Beleg')

    for folge in _namensfolgen(rest):
        if not _folge_belegt(folge, pool.woerter):
            fehlend = ' '.join(original for _, original in folge)
            einzeln = all(any(_gleiches_wort(f, w) for w in pool.woerter) for f, _ in folge)
            gruende.append(f'Namensfolge „{fehlend}“ steht nicht so im Beleg' if einzeln and len(folge) > 1
                           else f'„{fehlend}“ steht nicht im Beleg')

    for gruppe in sorted(_status_woerter(text) - _status_woerter(pool.text)):
        gruende.append(f'Aussage „{gruppe}“ steht nicht im Beleg')

    bedingung = _bedingung_verloren(text, zitiert)
    if bedingung:
        gruende.append(bedingung)
    anwendbarkeit = _anwendbarkeit_verloren(text, zitiert)
    if anwendbarkeit:
        gruende.append(anwendbarkeit)
    umkehr = _verneinungsumkehr(text, zitiert, pool)
    if umkehr:
        gruende.append(umkehr)
    gegen = _gegenstatus(text, zitiert)
    if gegen:
        gruende.append(gegen)
    return Urteil(satz, not gruende, tuple(dict.fromkeys(gruende)))


def belegte_daten(belege: Iterable[Beleg]) -> set[date]:
    """Alle Kalendertage, die die Belege tragen (ausgeschrieben oder aus dem Zeitpunkt der Quelle aufgelöst).

    Für Aufrufer, die relative Angaben („nächste Woche“) gegen einen Zeitraum prüfen: Sie fragen, ob ein
    Beleg irgendeinen Tag darin trägt (`satzantwort.py`).
    """
    return set(_pool(list(belege), ()).daten_voll)


def pruefen(saetze: Iterable[Satz], belege: Mapping[str, Beleg], *, zusatz_woerter: Iterable[str] = (),
            relative_zeit_erlaubt: bool = False) -> list[Urteil]:
    """Prüft alle Sätze; die Reihenfolge bleibt, nichts wird verbessert oder umgestellt."""
    zusatz = list(zusatz_woerter)
    return [satz_pruefen(s, belege, zusatz_woerter=zusatz, relative_zeit_erlaubt=relative_zeit_erlaubt) for s in saetze]


__all__ = ['Beleg', 'Datum', 'Satz', 'Urteil', 'bedingte_regeln', 'belegte_daten', 'daten_in', 'falten', 'pruefen', 'satz_pruefen', 'zahlen_in', 'zeiten_in']
