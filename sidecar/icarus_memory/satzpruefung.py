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
Was der Beleg selbst behauptet, prüft sie nicht.
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


def daten_in(text: str) -> tuple[list[Datum], str]:
    """Alle Datumsangaben eines Textes (ohne Auflösung relativer Angaben) und der Text ohne sie."""
    gefunden: list[Datum] = []
    rest = text

    def nehmen(treffer: re.Match, *daten: Datum) -> bool:
        nonlocal rest
        if not all(d.gueltig() for d in daten):
            return False
        gefunden.extend(daten)
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


# -- Uhrzeiten, Adressen, Kennungen, Zahlen ------------------------------------

_ZEIT_BEREICH = re.compile(r'(?<![\d.:])(\d{1,2})(?::([0-5]\d))?\s*(?:[-–]|bis)\s*(\d{1,2})(?::([0-5]\d))?\s*Uhr\b', re.I)
_ZEIT_DOPPELPUNKT = re.compile(r'(?<![\d:.])([01]?\d|2[0-3]):([0-5]\d)(?!\d)(?:\s*(?:Uhr|h)\b)?', re.I)
_ZEIT_PUNKT = re.compile(r'(?<![\d.])([01]?\d|2[0-3])\.([0-5]\d)\s*(?:Uhr|h)\b', re.I)
_ZEIT_UHR = re.compile(r'(?<![\d.:])([01]?\d|2[0-3])\s*(?:Uhr|h)\b(?:\s*([0-5]\d)(?!\d))?', re.I)
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
    for t in list(_ZEIT_BEREICH.finditer(rest)):
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
            for f in fristen_in(gesamt, beleg.zeit).fristen:
                pool.daten_voll.add(f.datum)
                pool.daten_kurz.add((f.datum.month, f.datum.day))
                pool.monate.add(f.datum.month)
        zeiten, rest = zeiten_in(rest)
        pool.zeiten |= zeiten
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
    zeiten, rest = zeiten_in(rest)
    for stunde, minute in sorted(zeiten):
        if (stunde, minute) not in pool.zeiten:
            gruende.append(f'Uhrzeit {stunde}:{minute:02d} steht nicht im Beleg')
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


__all__ = ['Beleg', 'Datum', 'Satz', 'Urteil', 'belegte_daten', 'daten_in', 'falten', 'pruefen', 'satz_pruefen', 'zahlen_in', 'zeiten_in']
