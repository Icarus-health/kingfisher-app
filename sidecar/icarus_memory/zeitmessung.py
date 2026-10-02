"""Zeitmessung einer Antwort: wie lange brauchten Frage, Suche, Modelle und Satzprüfung?

Ohne Zahl bleibt das Raten: Auf dem Zielgerät weiß niemand, ob der zweite Modellaufruf
2 Sekunden oder 20 kostet. Die Messung ist bewusst klein:

* Ein `Zeiten`-Sammler gehört zu **einer** Antwort und wird an den Aufrufen entlang
  weitergereicht (Parameter `zeiten`, vorgabemäßig `None` = nicht messen). Es gibt keinen
  Zustand, den Anfragen oder Threads teilen.
* Die Zahlen landen in `answer['zeiten']` und damit im gespeicherten Gesprächsverlauf.
* Gemessen wird nur, was wirklich lief: ein Abschnitt ohne Aufruf fehlt im Ergebnis
  (statt „0,0“), damit ein Median nicht von Nullen gedrückt wird.

Abschnitte (Sekunden, auf Millisekunden gerundet):

    frage            Frage verstehen (Rolle `frage`, `frage.py`)
    suche            Kandidaten, Akten, Kontext (`working_memory_answers.prepare` bis zum ersten Modellaufruf)
    antwort_modell   erster Modellaufruf: Quellen auswählen (Rolle `antwort`)
    saetze_modell    zweiter Modellaufruf: Sätze formulieren (`satzantwort.formulieren`)
    satzpruefung     jeder Satz gegen seine Belege
    pruefung_modell  zweites Tor: das Prüfmodell urteilt je Satz (`satzpruefung_modell.py`)
    gesamt           alles zusammen, einschließlich dessen, was in keinem Abschnitt steht
"""
from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable, Mapping
from contextlib import nullcontext
from statistics import median
from typing import Any

ABSCHNITTE = ('frage', 'suche', 'antwort_modell', 'saetze_modell', 'satzpruefung', 'pruefung_modell')
GESAMT = 'gesamt'
NAMEN = (*ABSCHNITTE, GESAMT)

ZIEL_MEDIAN_S = 8.0
"""Das Ziel: Eine Antwort soll im Median höchstens so lange dauern (Messlatte, Protokoll)."""

LETZTE_ANTWORTEN = 50
"""So viele jüngste Antworten geht das Protokoll ein."""


class Abschnitt:
    """Eine laufende Teilmessung; `ende()` ist wiederholbar, `with` geht auch."""

    __slots__ = ('_zeiten', '_name', '_start', '_fertig')

    def __init__(self, zeiten: Zeiten, name: str) -> None:
        self._zeiten, self._name, self._start, self._fertig = zeiten, name, zeiten._uhr(), False

    def ende(self) -> None:
        if not self._fertig:
            self._fertig = True
            self._zeiten._addiere(self._name, self._zeiten._uhr() - self._start)

    def __enter__(self) -> Abschnitt:
        return self

    def __exit__(self, *_ausnahme: Any) -> None:
        self.ende()


class Zeiten:
    """Der Sammler einer Antwort. Die Uhr ist austauschbar (Tests)."""

    def __init__(self, uhr: Callable[[], float] = time.perf_counter) -> None:
        self._uhr = uhr
        self._start = uhr()
        self._vorlauf = 0.0
        self._summen: dict[str, float] = {}
        self._schloss = threading.Lock()

    def _addiere(self, name: str, sekunden: float) -> None:
        with self._schloss:
            self._summen[name] = self._summen.get(name, 0.0) + max(0.0, sekunden)

    def abschnitt(self, name: str) -> Abschnitt:
        if name not in ABSCHNITTE:
            raise ValueError(f'unbekannter Abschnitt: {name}')
        return Abschnitt(self, name)

    def vorlauf(self, name: str, sekunden: float) -> None:
        """Zeit, die schon vor diesem Sammler verging (die Frage wurde im Server verstanden)."""
        if name not in ABSCHNITTE:
            raise ValueError(f'unbekannter Abschnitt: {name}')
        if sekunden > 0:
            self._addiere(name, sekunden)
            with self._schloss:
                self._vorlauf += sekunden

    def als_dict(self) -> dict[str, float]:
        """Die Abschnitte, die liefen, und `gesamt`; für `answer['zeiten']`."""
        with self._schloss:
            daten = {name: round(self._summen[name], 3) for name in ABSCHNITTE if name in self._summen}
            daten[GESAMT] = round(self._vorlauf + max(0.0, self._uhr() - self._start), 3)
        return daten


def messen(zeiten: Zeiten | None, name: str):
    """Kontextmanager um einen Abschnitt; ohne Sammler tut er nichts (dünn an den Aufrufstellen)."""
    return nullcontext() if zeiten is None else zeiten.abschnitt(name)


def beginne(zeiten: Zeiten | None, name: str) -> Abschnitt | None:
    """Teilmessung, die sich nicht in einen `with`-Block fassen lässt; `None` ohne Sammler."""
    return None if zeiten is None else zeiten.abschnitt(name)


def gueltig(roh: Any) -> dict[str, float] | None:
    """Die gespeicherten Zeiten, wenn es Zahlen sind (nicht negativ, unter einem Tag); sonst None.

    Fremde Namen fallen weg. `gesamt` muss da sein.
    """
    if not isinstance(roh, Mapping) or GESAMT not in roh:
        return None
    daten: dict[str, float] = {}
    for name in NAMEN:
        if name not in roh:
            continue
        wert = roh[name]
        if isinstance(wert, bool) or not isinstance(wert, (int, float)) or not 0 <= wert < 86400:
            return None
        daten[name] = float(wert)
    return daten


def _perzentil(werte: list[float], anteil: float) -> float:
    """Der Wert, unter dem `anteil` der Messungen liegen (nächster Rang, ohne Mittelung)."""
    geordnet = sorted(werte)
    rang = max(1, math.ceil(len(geordnet) * anteil - 1e-9))
    return geordnet[rang - 1]


def kennzahlen(liste: list[Mapping[str, float]]) -> dict[str, dict[str, float | int]]:
    """Median und 90-%-Wert je Abschnitt aus mehreren Antworten; nur Abschnitte mit Messungen."""
    ergebnis: dict[str, dict[str, float | int]] = {}
    for name in NAMEN:
        werte = [float(z[name]) for z in liste if name in z]
        if werte:
            ergebnis[name] = {'median': round(median(werte), 3), 'p90': round(_perzentil(werte, 0.9), 3),
                              'anzahl': len(werte)}
    return ergebnis


__all__ = ['ABSCHNITTE', 'Abschnitt', 'GESAMT', 'LETZTE_ANTWORTEN', 'NAMEN', 'ZIEL_MEDIAN_S', 'Zeiten',
           'beginne', 'gueltig', 'kennzahlen', 'messen']
