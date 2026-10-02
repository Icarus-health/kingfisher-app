"""Relative Zeitangaben in einem Antwortsatz („morgen“, „nächste Woche“) gegen den Stichtag auflösen.

Die Satzprüfung (`satzpruefung.py`) verwirft jede relative Angabe, weil sie ohne festen
Tag nicht prüfbar ist. In einer Antwort auf „Was steht morgen an?“ ist sie aber natürlich.
Dieses Modul macht sie prüfbar: Es löst eine geschlossene Liste von Ausdrücken gegen den
**Stichtag** (das „jetzt“ der Antwort) in einen Tag oder einen Zeitraum auf. Alles, was
nicht in der Liste steht („demnächst“, „kürzlich“, „bald“), bleibt unaufgelöst, und die
Satzprüfung verwirft es weiter.

Ein Satz mit relativer Angabe besteht nur, wenn der aufgelöste Tag belegt ist:

* Ein einzelner Tag („morgen“ = 30.09.2026) wird hinter den Ausdruck geschrieben
  („morgen (30.09.2026)“) und läuft als gewöhnliches Datum durch die Prüfung: Er muss im
  Beleg stehen, entweder ausgeschrieben oder aus dem Zeitpunkt der Quelle aufgelöst.
* Ein Zeitraum („nächste Woche“ = 05.–11.10.2026) besteht, wenn der zitierte Beleg
  mindestens ein Datum in diesem Zeitraum trägt.

Die Ergänzung in Klammern hat einen zweiten Zweck: Eine gespeicherte Antwort wird
später wieder gelesen, und „morgen“ meint dann einen anderen Tag. Mit dem Datum dabei
bleibt der Satz wahr.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

_AE, _UE = '(?:ä|ae)', '(?:ü|ue)'
_ZAHL = r'(\d{1,3}|zwei|drei|vier|f(?:ü|ue)nf|sechs|sieben|acht|neun|zehn|einer|einem|ein|eine)'
_ZAHLWORT = {'ein': 1, 'eine': 1, 'einer': 1, 'einem': 1, 'zwei': 2, 'drei': 3, 'vier': 4, 'fünf': 5, 'fuenf': 5,
             'sechs': 6, 'sieben': 7, 'acht': 8, 'neun': 9, 'zehn': 10}
_TAG = {'heute': 0, 'morgen': 1, 'gestern': -1, 'vorgestern': -2}

_MUSTER = re.compile(
    r'(?<![\wäöüß-])(?:'
    r'(?P<uebermorgen>' + _UE + r'bermorgen)|(?P<tag>heute|morgen|gestern|vorgestern)|'
    r'(?P<bezug>diese|dieser|diesen|dieses|n' + _AE + r'chste|kommende|letzte|vorige|vergangene)(?P<endung>[nrms]?)'
    r'\s+(?P<einheit>woche|monat|jahr)|'
    r'in\s+' + _ZAHL + r'\s+(?P<frist>tag|woche|monat)(?:en|e|n)?)(?![\wäöüß])',
    re.I)


@dataclass(frozen=True)
class Aufloesung:
    """Ein aufgelöster Ausdruck: wo er im Satz steht und welchen Tag oder Zeitraum er meint."""

    ausdruck: str
    start: int
    ende: int
    von: date
    bis: date

    @property
    def einzeln(self) -> bool:
        return self.von == self.bis

    def datum_text(self) -> str:
        """Der Tag als „30.09.2026“, ein Zeitraum als „05.10.–11.10.2026“ (oder mit zwei Jahren)."""
        if self.einzeln:
            return self.von.strftime('%d.%m.%Y')
        if self.von.year == self.bis.year:
            return f'{self.von.strftime("%d.%m.")}–{self.bis.strftime("%d.%m.%Y")}'
        return f'{self.von.strftime("%d.%m.%Y")}–{self.bis.strftime("%d.%m.%Y")}'


def _monat_plus(tag: date, monate: int) -> date:
    index = tag.month - 1 + monate
    jahr, monat = tag.year + index // 12, index % 12 + 1
    return date(jahr, monat, min(tag.day, calendar.monthrange(jahr, monat)[1]))


def _zahl(text: str) -> int:
    text = text.casefold()
    return int(text) if text.isdigit() else _ZAHLWORT.get(text, _ZAHLWORT.get(text.replace('ü', 'ue'), 0))


def _bezug_wert(wort: str) -> int:
    """diese = 0, nächste/kommende = +1, letzte/vorige/vergangene = −1."""
    wort = wort.casefold()
    if 'chste' in wort or wort.startswith('kommende'):
        return 1
    return -1 if wort.startswith(('letzte', 'vorige', 'vergangene')) else 0


def aufloesen(text: str, jetzt: datetime | date) -> list[Aufloesung]:
    """Alle relativen Ausdrücke des Textes, aufgelöst gegen `jetzt` (Tag genügt); Unbekanntes taucht nicht auf.

    Wer wissen will, ob ein Satz relative Angaben trägt, die nicht in der Liste stehen, fragt
    die Satzprüfung (sie verwirft sie); diese Funktion löst nur, was eindeutig ist.
    """
    heute = jetzt.date() if isinstance(jetzt, datetime) else jetzt
    ergebnis: list[Aufloesung] = []
    for treffer in _MUSTER.finditer(text or ''):
        von = bis = None
        if treffer['uebermorgen']:
            von = bis = heute + timedelta(days=2)
        elif treffer['tag']:
            von = bis = heute + timedelta(days=_TAG[treffer['tag'].casefold()])
        elif treffer['bezug']:
            schritt = _bezug_wert(treffer['bezug'])
            einheit = treffer['einheit'].casefold()
            if einheit == 'woche':
                montag = heute - timedelta(days=heute.weekday()) + timedelta(weeks=schritt)
                von, bis = montag, montag + timedelta(days=6)
            elif einheit == 'monat':
                erster = _monat_plus(heute.replace(day=1), schritt)
                von, bis = erster, erster.replace(day=calendar.monthrange(erster.year, erster.month)[1])
            else:
                jahr = heute.year + schritt
                von, bis = date(jahr, 1, 1), date(jahr, 12, 31)
        elif treffer['frist']:
            anzahl = _zahl(treffer.group(0).split()[1])
            if anzahl:
                einheit = treffer['frist'].casefold()
                von = bis = (heute + timedelta(days=anzahl) if einheit == 'tag'
                             else heute + timedelta(weeks=anzahl) if einheit == 'woche'
                             else _monat_plus(heute, anzahl))
        if von is not None and bis is not None:
            ergebnis.append(Aufloesung(treffer.group(0), treffer.start(), treffer.end(), von, bis))
    return ergebnis


def mit_datum(text: str, aufgeloest: list[Aufloesung], *, klein: bool = False) -> str:
    """Schreibt hinter jeden aufgelösten Ausdruck den Tag oder Zeitraum in Klammern („morgen (30.09.2026)“).

    `klein` schreibt die Ausdrücke klein: Für die Satzprüfung, die einen Satzanfang „Morgen“ sonst für einen Namen hält.
    """
    for a in sorted(aufgeloest, key=lambda a: -a.start):
        ausdruck = text[a.start:a.ende].lower() if klein else text[a.start:a.ende]
        text = text[:a.start] + ausdruck + f' ({a.datum_text()})' + text[a.ende:]
    return text


__all__ = ['Aufloesung', 'aufloesen', 'mit_datum']
