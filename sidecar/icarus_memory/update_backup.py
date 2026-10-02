"""Sicherung vor einem Update, bevor eine Datenbank umgebaut wird.

Jeder Migrationsschritt läuft in einer eigenen Transaktion und wird geprüft;
ein Absturz mitten im Umbau hinterlässt deshalb keinen halben Bestand. Was
eine Transaktion nicht abfängt, ist ein Umbau, der fehlerfrei durchläuft und
trotzdem das Falsche tut. Dagegen hilft nur eine Kopie von vorher.

Der Nutzer muss daran nicht denken: Beim Start wird nachgesehen, ob eine der
vorhandenen Dateien älter ist als der Code, und nur dann ein vollständiger
Satz gesichert. Die Kopien liegen neben den laufenden Sicherungen und lassen
sich genauso zurückspielen, rotieren aber getrennt, damit die regelmäßige
Sicherung sie nicht nach wenigen Läufen wegräumt.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Sequence

from .backup import UPDATE_SET_PREFIX, BackupError, snapshot_all
from .migrations import Migration

logger = logging.getLogger(__name__)

KEEP = 3


def _targets() -> dict[str, Sequence[Migration]]:
    from . import (audit, backends, claims, conversations, episodes, lint, logbuch, proposals, regeln, rueckmeldung, tasks,
                   transkript_zuordnung, workspace)
    return {
        "self-model.sqlite3": backends._MIGRATIONS,
        "audit.sqlite3": audit._MIGRATIONS,
        "tasks.sqlite3": tasks._MIGRATIONS,
        "workspace.sqlite3": workspace._MIGRATIONS,
        "episodes.sqlite3": episodes._MIGRATIONS,
        "proposals.sqlite3": proposals._MIGRATIONS,
        "conversations.sqlite3": conversations._MIGRATIONS,
        "knowledge.sqlite3": claims._MIGRATIONS,
        "regeln.sqlite3": regeln._MIGRATIONS,
        "gespraeche.sqlite3": transkript_zuordnung._MIGRATIONS,
        "rueckmeldungen.sqlite3": rueckmeldung._MIGRATIONS,
        "logbuch.sqlite3": logbuch._MIGRATIONS,
        "lint.sqlite3": lint._MIGRATIONS,
    }


def _version(path: Path) -> tuple[int, bool] | None:
    """Version und ob die Datei überhaupt Tabellen hat; nur lesend geöffnet."""
    try:
        connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        tables = connection.execute(
            "SELECT 1 FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' LIMIT 1"
        ).fetchone() is not None
        return version, tables
    except sqlite3.Error:
        return None
    finally:
        connection.close()


def outdated(data_dir: Path) -> list[str]:
    """Dateien, die beim Öffnen umgebaut würden. Leere und neue zählen nicht."""
    found = []
    for name, migrations in _targets().items():
        path = Path(data_dir) / name
        if not path.is_file():
            continue
        state = _version(path)
        if state is None:
            continue
        version, tables = state
        target = max(migration.version for migration in migrations)
        if tables and 0 <= version < target:
            found.append(name)
    return found


def backup_before_update(data_dir: Path) -> Path | None:
    """Sichert den ganzen Bestand, wenn ein Umbau ansteht; sonst nichts.

    Scheitert die Sicherung, startet Kingfisher trotzdem: Die Umbauschritte
    sind einzeln abgesichert, und ein Programm, das wegen einer vollen Platte
    gar nicht mehr aufgeht, hilft niemandem. Der Grund steht im Protokoll.
    """
    data_dir = Path(data_dir)
    names = outdated(data_dir)
    if not names:
        return None
    try:
        path = snapshot_all(data_dir, data_dir / "sicherungen", keep=KEEP, prefix=UPDATE_SET_PREFIX)
    except (BackupError, OSError, sqlite3.Error):
        logger.exception("Sicherung vor dem Update fehlgeschlagen: %s", ", ".join(names))
        return None
    logger.info("Sicherung vor dem Update angelegt: %s (umgebaut werden: %s)",
                path, ", ".join(names))
    return path
