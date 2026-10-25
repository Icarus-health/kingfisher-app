"""Zwischenspeicher für teure Lesungen, gültig nur, solange sich ihre Grundlage nicht geändert hat (V7, Tempo).

Ein Eintrag gilt für einen Schlüssel, der den Stand seiner Grundlage enthält: meist `marke(verbindung)`, also
`PRAGMA data_version` (ändert sich, wenn eine andere Verbindung schreibt) und `total_changes` (zählt jede Zeile, die
diese Verbindung geändert hat). Beides ist billig und eher zu vorsichtig als zu nachsichtig: Jeder Schreibvorgang an
derselben Datei macht den Eintrag ungültig, auch einer an einer Tabelle, die die Lesung gar nicht braucht. Ein
veralteter Eintrag ist ausgeschlossen, ein überflüssiges Neuberechnen nicht.

Werte gehen als Kopie hinaus: Wer die Antwort weiterbearbeitet (Namen ergänzen, Felder anhängen), verändert den
gespeicherten Eintrag nicht.
"""
from __future__ import annotations

import copy
import sqlite3
import threading
from collections import OrderedDict
from typing import Any, Callable, Hashable


def marke(verbindung: sqlite3.Connection, sperre: Any = None) -> tuple[int, int, int]:
    """Stand einer SQLite-Verbindung: (Kennung der Verbindung, data_version, total_changes)."""
    if sperre is None:
        return (id(verbindung), verbindung.execute('PRAGMA data_version').fetchone()[0], verbindung.total_changes)
    with sperre:
        return (id(verbindung), verbindung.execute('PRAGMA data_version').fetchone()[0], verbindung.total_changes)


def marke_von(speicher: Any) -> tuple | None:
    """Stand eines Speichers mit SQLite-Verbindung (`_conn`, auch hinter `_backend` und `_store`, etwa
    `SelfModelStore` → `CogneeBackend` → `SqliteBackend`); None ohne eine solche.

    Ein Speicher ohne Datei kann seine Schreibvorgänge selbst zählen (`aenderungsmarke()`, etwa `MemoryBackend`).
    None heißt: nicht zwischenspeichern.
    """
    traeger = speicher
    for _ in range(4):
        if traeger is None:
            return None
        verbindung = getattr(traeger, '_conn', None)
        if isinstance(verbindung, sqlite3.Connection):
            return marke(verbindung, getattr(traeger, '_lock', None))
        eigene_marke = getattr(traeger, 'aenderungsmarke', None)
        if callable(eigene_marke):  # ein Speicher ohne Datei, der seine Schreibvorgänge selbst zählt
            return (id(traeger), eigene_marke())
        traeger = getattr(traeger, '_backend', None) or getattr(traeger, '_store', None)
    return None


class Zwischenspeicher:
    """Wenige Einträge, die zuletzt benutzten bleiben. Sicher für mehrere Fäden."""

    def __init__(self, groesse: int = 16) -> None:
        self._groesse = groesse
        self._eintraege: OrderedDict[Hashable, Any] = OrderedDict()
        self._sperre = threading.Lock()
        self.treffer = 0
        self.berechnet = 0

    def holen(self, schluessel: Hashable | None, berechnen: Callable[[], Any]) -> Any:
        """Der gespeicherte Wert zum Schlüssel (als Kopie), sonst `berechnen()`; ohne Schlüssel nie gespeichert."""
        if schluessel is None:
            self.berechnet += 1
            return berechnen()
        with self._sperre:
            if schluessel in self._eintraege:
                self._eintraege.move_to_end(schluessel)
                self.treffer += 1
                return copy.deepcopy(self._eintraege[schluessel])
        wert = berechnen()
        with self._sperre:
            self.berechnet += 1
            self._eintraege[schluessel] = copy.deepcopy(wert)
            self._eintraege.move_to_end(schluessel)
            while len(self._eintraege) > self._groesse:
                self._eintraege.popitem(last=False)
        return wert

    def merken(self, schluessel: Hashable, wert: Any) -> None:
        """Legt einen Wert ab, der schon berechnet ist (etwa unter dem Stand nach der Berechnung)."""
        with self._sperre:
            self._eintraege[schluessel] = copy.deepcopy(wert)
            self._eintraege.move_to_end(schluessel)
            while len(self._eintraege) > self._groesse:
                self._eintraege.popitem(last=False)

    def nachsehen(self, schluessel: Hashable) -> Any | None:
        """Der gespeicherte Wert (als Kopie) oder None."""
        with self._sperre:
            if schluessel not in self._eintraege:
                return None
            self._eintraege.move_to_end(schluessel)
            self.treffer += 1
            return copy.deepcopy(self._eintraege[schluessel])

    def leeren(self) -> None:
        with self._sperre:
            self._eintraege.clear()
