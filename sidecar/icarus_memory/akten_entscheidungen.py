"""Entscheidungen des Nutzers in einer Akte: „Erledigt“, „Gilt nicht mehr“, „Gilt weiter“, „Findet doch statt“.

Die Akte vermutet nur (`akten.py`): Ein Punkt ist „vermutlich offen“, ein Termin „vermutlich abgesagt“. Ein
guter Stabschef fragt dann einmal und merkt sich die Antwort. Diese Ablage hält genau diese Antworten fest.

Was eine Entscheidung ist und was nicht:

* Sie ist eine **Einordnung durch den Nutzer**, keine Tatsache über die Welt und kein Fakt im Bestand. Sie
  ändert keine Quelle, keine Einordnung (Ebene 1) und keinen Bezug. Die Akte liest sie nur bei der Anzeige
  (offen oder erledigt, abgesagt oder nicht); der Zwischenspeicher der Akte bleibt unberührt.
* Sie gilt für **eine Textstelle** (Quelle, Anfang, Ende, Inhalt der Quelle) oder **einen Termin** (Quelle) und
  damit in jeder Akte, in der diese vorkommt: Was bei der Person erledigt ist, ist es auch bei ihrer Firma.
* Ändert sich der Text der Quelle (neue Fassung), gilt die Entscheidung nicht mehr; die Akte vermutet dann wieder
  neu. Nachgetragene Kontakte, Kopfzeilen oder Anhänge ändern den Text nicht und lassen sie stehen. Ein geänderter
  Termin ist eine neue Quelle (`calendar_memory.py`) und fragt deshalb neu.
* Gespeichert werden **nur Verweise** (Kennung der Quelle, Fingerabdruck, Stellen) und der Zeitpunkt. Kein Text,
  keine Sache, keine Adresse.
* Jede Entscheidung lässt sich mit einem Klick zurücknehmen (`zuruecknehmen`); danach gilt wieder die Vermutung.
"""
from __future__ import annotations

import re
import sqlite3
import time
from typing import Any, Iterable

#: Was ein Mensch zu einer Textstelle sagen kann.
FUER_ABSCHNITT = ('erledigt', 'gilt_nicht', 'offen')
#: Was ein Mensch zu einem vermutlich abgesagten Termin sagen kann: erledigt (abgesagt, im Kalender bereinigt) oder
#: „findet doch statt“ (`offen`).
FUER_TERMIN = ('erledigt', 'offen')
ENTSCHEIDUNGEN = ('erledigt', 'gilt_nicht', 'offen')

TABLES = {'akten_entscheidungen': {'ziel', 'entscheidung', 'entschieden_am'}}
PRIMARY_KEYS = {'akten_entscheidungen': {'ziel'}}

# Der Inhaltsdigest steht zuletzt: Er darf Doppelpunkte tragen („sha256:…“).
_ZIEL = re.compile(r'^(?:a:[^:\s]{1,200}:\d{1,9}:\d{1,9}:\S{1,200}|t:[^:\s]{1,200})$')


def migrate(connection: sqlite3.Connection) -> None:
    """Migration 23 der Episoden: die Entscheidungen des Nutzers in Akten (nur Verweise)."""
    connection.execute("""CREATE TABLE akten_entscheidungen (
        ziel TEXT PRIMARY KEY,
        entscheidung TEXT NOT NULL CHECK(entscheidung IN ('erledigt','gilt_nicht','offen')),
        entschieden_am REAL NOT NULL)""")


def ziel_abschnitt(ref: dict[str, Any], digest: str = '') -> str:
    """Die Kennung einer Textstelle: Quelle, Anfang, Ende und Inhalt der Quelle (Digest des Textes).

    Nicht der Fingerabdruck der Einordnung: Der ändert sich mit jedem Nachtrag an der Quelle (Kontakte,
    Kopfzeilen), der Text nicht. Ohne Digest gilt ersatzweise der Fingerabdruck.
    """
    return f"a:{ref['episode_id']}:{int(ref['start'])}:{int(ref['end'])}:{digest or ref['fingerprint']}"


def ziel_termin(episode_id: str) -> str:
    """Die Kennung eines Termins: die Quelle (ein geänderter Termin ist eine neue Quelle und fragt neu)."""
    return f't:{episode_id}'


def ist_termin(ziel: str) -> bool:
    return ziel.startswith('t:')


def gueltiges_ziel(ziel: str) -> bool:
    return isinstance(ziel, str) and bool(_ZIEL.match(ziel))


class Entscheidungen:
    """Liest und schreibt die Entscheidungen. Schreibt nur auf ausdrücklichen Wunsch (`setzen`, `zuruecknehmen`)."""

    def __init__(self, episodes: Any) -> None:
        self.episodes = episodes

    def zu(self, ziele: Iterable[str]) -> dict[str, dict[str, Any]]:
        """Die Entscheidungen zu den genannten Zielen: Ziel -> {entscheidung, entschieden_am}."""
        liste = sorted({z for z in ziele if z})
        ergebnis: dict[str, dict[str, Any]] = {}
        with self.episodes._lock:
            for anfang in range(0, len(liste), 400):
                teil = liste[anfang:anfang + 400]
                for zeile in self.episodes._conn.execute(
                        'SELECT ziel, entscheidung, entschieden_am FROM akten_entscheidungen WHERE ziel IN ('
                        + ','.join('?' for _ in teil) + ')', teil):
                    ergebnis[zeile['ziel']] = {'entscheidung': zeile['entscheidung'],
                                               'entschieden_am': zeile['entschieden_am']}
        return ergebnis

    def setzen(self, ziel: str, entscheidung: str) -> dict[str, Any]:
        """Hält die Entscheidung fest; `vorher` ist die bisherige (oder None), damit „Rückgängig“ sie zurückholt."""
        if not gueltiges_ziel(ziel):
            raise ValueError('Unbekanntes Ziel.')
        erlaubt = FUER_TERMIN if ist_termin(ziel) else FUER_ABSCHNITT
        if entscheidung not in erlaubt:
            raise ValueError('Diese Entscheidung passt hier nicht.')
        jetzt = time.time()
        with self.episodes.transaction():
            alt = self.episodes._conn.execute(
                'SELECT entscheidung FROM akten_entscheidungen WHERE ziel = ?', (ziel,)).fetchone()
            self.episodes._conn.execute(
                'INSERT INTO akten_entscheidungen VALUES (?,?,?) ON CONFLICT(ziel) DO UPDATE SET '
                'entscheidung=excluded.entscheidung, entschieden_am=excluded.entschieden_am',
                (ziel, entscheidung, jetzt))
        return {'ziel': ziel, 'entscheidung': entscheidung, 'entschieden_am': jetzt,
                'vorher': alt['entscheidung'] if alt else None}

    def zuruecknehmen(self, ziel: str) -> bool:
        with self.episodes.transaction():
            return self.episodes._conn.execute(
                'DELETE FROM akten_entscheidungen WHERE ziel = ?', (ziel,)).rowcount > 0


__all__ = ['ENTSCHEIDUNGEN', 'Entscheidungen', 'FUER_ABSCHNITT', 'FUER_TERMIN', 'gueltiges_ziel', 'ist_termin',
           'ziel_abschnitt', 'ziel_termin']
