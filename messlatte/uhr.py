"""Eingefrorene Uhr: „heute“ ist der Stichtag der Welt.

Das Produkt liest die Uhrzeit an vielen Stellen (`datetime.now(...)` in
`model.py`, `server.py`, `time_scope.py`, `bedeutungen.py`, `mac_calendar.py`,
`calendar_context.py`). Ohne eingefrorene Uhr ergäbe „Was war letzte Woche?“
oder der Terminkalender ±30 Tage je nach Tag der Messung etwas anderes, und
eine Welt mit Stichtag 29. September würde in einem Jahr nur noch aus
Vergangenheit bestehen.

Umgesetzt wird das ohne Produktänderung: In jedem geladenen Modul des Pakets
`icarus_memory`, das die Klasse `datetime` unter diesem Namen führt, wird sie für
die Dauer des Blocks durch eine Unterklasse ersetzt, deren `now()` den Stichtag
liefert. Danach wird alles zurückgesetzt. **Grenze:** `time.time()` und
`time.monotonic()` (Wiederholungsfristen, Zeitbudgets) laufen weiter echt.
"""
from __future__ import annotations

import importlib
import pkgutil
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

_ECHT = datetime


class _Meta(type(_ECHT)):
    """`isinstance(echtes_datum, datetime)` muss auch für die Ersatzklasse gelten."""

    def __instancecheck__(cls, instanz):
        return isinstance(instanz, _ECHT)

    def __subclasscheck__(cls, unterklasse):
        return issubclass(unterklasse, _ECHT)


def eingefrorene_klasse(stichtag: datetime):
    """Eine `datetime`-Unterklasse, deren `now()` immer der Stichtag ist."""
    if stichtag.tzinfo is None:
        raise ValueError('Der Stichtag braucht eine Zeitzone.')

    class Eingefroren(_ECHT, metaclass=_Meta):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                # Wie die Systemuhr: Ortszeit ohne Zone.
                return stichtag.astimezone().replace(tzinfo=None)
            return stichtag.astimezone(tz)

        @classmethod
        def utcnow(cls):
            return stichtag.astimezone(timezone.utc).replace(tzinfo=None)

    return Eingefroren


def ist_eingefroren(paket: str = 'icarus_memory') -> bool:
    """Läuft in diesem Prozess schon eine eingefrorene Uhr? Dann darf keine zweite Instanz starten."""
    return any(name.startswith(paket) and getattr(modul, 'datetime', _ECHT) is not _ECHT
               for name, modul in list(sys.modules.items()) if modul is not None)


def _module_laden(paket: str) -> None:
    """Alle Module des Pakets vorab importieren.

    Das Produkt importiert manche Module erst beim ersten Gebrauch (etwa
    `time_scope` in `working_memory_answers.prepare`). Ein Modul, das erst nach
    dem Einfrieren geladen wird, bekäme die echte Uhr und fiele aus der Reihe.
    """
    wurzel = importlib.import_module(paket)
    for info in pkgutil.walk_packages(wurzel.__path__, paket + '.'):
        try:
            importlib.import_module(info.name)
        except ImportError:  # optionale Abhängigkeit fehlt: das Modul gehört dann nicht zur Messung
            continue


@contextmanager
def eingefrorene_zeit(stichtag: datetime, paket: str = 'icarus_memory') -> Iterator[None]:
    """Setzt die Uhr des Produkts auf `stichtag` und stellt sie danach wieder her."""
    ersatz = eingefrorene_klasse(stichtag)
    _module_laden(paket)
    ersetzt: list[tuple[object, str]] = []
    try:
        for name, modul in list(sys.modules.items()):
            if modul is None or not (name == paket or name.startswith(paket + '.')):
                continue
            if getattr(modul, 'datetime', None) is _ECHT:
                modul.datetime = ersatz  # type: ignore[attr-defined]
                ersetzt.append((modul, 'datetime'))
        yield
    finally:
        for modul, attribut in ersetzt:
            setattr(modul, attribut, _ECHT)
