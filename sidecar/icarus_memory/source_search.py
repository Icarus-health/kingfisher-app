"""Wörtliche Suche in den Rohtexten aller verwendbaren Quellen, über den Suchindex.

Nur Episoden-IDs verlassen diese Schicht. Der Aufrufer muss jede Quelle vor der
Verwendung als Beleg erneut lesen und prüfen.

Der Index (``source_index``, Trigramme) nennt Kandidaten für eine Zeichenfolge;
er faltet Akzente und Leerraum und findet deshalb ein Übermaß. Jeder Kandidat
wird hier am Originaltext bestätigt, mit der Semantik von früher: Die Zeichenfolge
kommt (mit ``casefold``) buchstäblich im Text vor. Damit ist das Ergebnis auch bei
großem Bestand vollständig, statt nach einem Zeitbudget leer zu enden. Das Budget
gilt nur noch der Bestätigung; wird es überschritten, gilt das Ergebnis als
unvollständig und liefert keinen Teiltreffer.
"""

from __future__ import annotations

import time
import unicodedata

from . import source_index
from .episodes import EpisodeStore


_MAX_SECONDS = 0.5
_MAX_IDS = 20
# So viele Kandidaten werden höchstens bestätigt, bis 21 Treffer feststehen; darüber gilt die Suche als unvollständig.
_MAX_KANDIDATEN = 5_000


def search(episodes: EpisodeStore, literal: str) -> dict:
    """Bis zu 20 verwendbare Quellen-IDs finden, deren Text die Zeichenfolge enthält.

    Zu große Quellen (nicht im Index) und ein überschrittenes Budget werden als
    unvollständige Abdeckung gemeldet. Bei überschrittenem Budget entfallen alle
    Teiltreffer, damit keine Antwort sie für vollständig halten kann.
    """
    if (not isinstance(literal, str) or not 3 <= len(literal) <= 120
            or any(unicodedata.category(char) == "Cc" for char in literal)):
        raise ValueError("Literal must be 3..120 characters without controls")

    result = {
        "ids": [], "truncated": False, "budget_exhausted": False,
        "oversize_skipped": False, "normalization": "literal-casefold-v1",
    }
    needle = literal.casefold()
    deadline = time.monotonic() + _MAX_SECONDS
    with episodes._lock:
        connection = episodes._conn
        result["oversize_skipped"] = source_index.abdeckung(connection)["zu_gross"] > 0
        if len(source_index.falte(literal)) < 3:
            # Nach dem Falten zu kurz für den Index: ehrlich als nicht durchsucht melden.
            result["budget_exhausted"] = True
            return result
        gefunden, geprueft = [], 0
        for episode_id in source_index.literal_kandidaten(connection, literal):
            geprueft += 1
            if geprueft > _MAX_KANDIDATEN or time.monotonic() >= deadline:
                result["budget_exhausted"] = True
                return result
            row = connection.execute("SELECT body FROM episodes WHERE id=?", (episode_id,)).fetchone()
            if row is not None and needle in row[0].casefold():
                gefunden.append(episode_id)
                if len(gefunden) > _MAX_IDS:
                    break
        # Auch ein kleiner Lauf darf das Budget nicht überschreiten, ohne es zu melden.
        if time.monotonic() >= deadline:
            result["budget_exhausted"] = True
            return result
    result["ids"] = gefunden[:_MAX_IDS]
    result["truncated"] = len(gefunden) > _MAX_IDS
    return result
