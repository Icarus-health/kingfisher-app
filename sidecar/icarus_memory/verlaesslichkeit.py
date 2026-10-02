"""Unsicherheit je Satz: wie gut trägt, was ihn trägt? Drei Stufen aus Regeln, kein Modell.

Ein Satz, der beide Tore bestanden hat, ist belegt. Belegt ist aber nicht gleich verlässlich: Eine einzige Mail von
vor zwei Jahren trägt einen Satz dünner als zwei Quellen von letzter Woche. Das soll der Nutzer sehen, ohne dass
jede Antwort laut wird. Deshalb eine stille Einstufung je Satz (`GeprueftSatz.verlaesslichkeit`):

    gut      mindestens zwei Belege oder ein Beleg jünger als 90 Tage, und das Prüfmodell sagte ja
    einfach  ein Beleg, älter als 90 Tage (oder ohne Datum), oder das Prüfmodell lief nicht
    duenn    ein Beleg ist gekennzeichnet (andere Person gleichen Namens, außerhalb des Zeitraums), oder der Satz
             ist nur über die Kopfzeile (Betreff, Absender, Datum) gestützt, nicht über den Text

`duenn` geht vor `einfach`, `einfach` vor `gut`. Überholtes zählt hier nicht als Kennzeichnung: Ein Satz mit einer
überholten Angabe besteht nur, wenn er den Wandel und die neuere Quelle nennt, und stützt sich damit auf sie.

Angezeigt wird nur bei `einfach` und `duenn`, als gedämpfter Nebensatz hinter dem Satz („nur eine Quelle, von
2024“), und nur mit einem Anlass, der den Satz selbst betrifft. Dass das Prüfmodell für die ganze Antwort nicht lief,
steht einmal unter der Antwort, nicht hinter jedem Satz. Gerechnet wird mit dem Stichtag der Antwort; beim
Anzeigen einer gespeicherten Antwort wird neu gerechnet (`satzantwort.wiederherstellen`).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

GUT, EINFACH, DUENN = 'gut', 'einfach', 'duenn'
STUFEN = (GUT, EINFACH, DUENN)
JUNG = timedelta(days=90)


@dataclass(frozen=True)
class Einstufung:
    stufe: str
    hinweis: str = ''
    """Der Nebensatz hinter dem Satz; leer, wenn es nichts zu sagen gibt, das den Satz selbst betrifft."""


def _jahr(moment: datetime | None) -> str:
    if moment is None:
        return ''
    from .model import user_timezone
    return str(moment.astimezone(user_timezone() or timezone.utc).year)


def einstufen(zitiert: Sequence[Any], jetzt: datetime, *, pruefmodell_ja: bool, nur_kopf: bool) -> Einstufung:
    """Die Stufe eines Satzes aus seinen Belegen (mit `episode_id`, `zeit`, `kennzeichen`) und den beiden Toren."""
    if any(getattr(b, 'kennzeichen', ()) for b in zitiert):
        return Einstufung(DUENN, 'gestützt auf eine gekennzeichnete Quelle')
    if nur_kopf:
        return Einstufung(DUENN, 'nur über Betreff oder Absender belegt')
    quellen = {getattr(b, 'episode_id', id(b)): getattr(b, 'zeit', None) for b in zitiert}
    jung = any(zeit is not None and jetzt - zeit < JUNG for zeit in quellen.values())
    breit = len(quellen) >= 2 or jung
    if breit and pruefmodell_ja:
        return Einstufung(GUT)
    if breit:
        return Einstufung(EINFACH)  # nur das Prüfmodell fehlt: steht einmal unter der Antwort
    zeit = next(iter(quellen.values()), None)
    return Einstufung(EINFACH, f'nur eine Quelle, von {_jahr(zeit)}' if zeit is not None else 'nur eine Quelle')


__all__ = ['DUENN', 'EINFACH', 'Einstufung', 'GUT', 'JUNG', 'STUFEN', 'einstufen']
