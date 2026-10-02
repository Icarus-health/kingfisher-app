"""Atomares Schreiben kleiner Zustandsdateien.

Eine Datei, die direkt überschrieben wird, ist bei einem Absturz mitten im
Schreiben halb leer. Bei Einstellungen oder dem Chiffrat der Zugangsdaten hieße
das: Konten und Zeitplan weg. Deshalb wird erst in eine Temporärdatei im selben
Verzeichnis geschrieben und diese mit `os.replace` an den Zielort gesetzt — der
Leser sieht immer die alte oder die neue Fassung, nie etwas dazwischen.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path


def write_text_atomic(path: str | Path, text: str, *, mode: int = 0o600) -> Path:
    """Schreibt `text` atomar nach `path`, mit Rechten `mode` (Vorgabe 0600).

    Die Temporärdatei entsteht schon mit 0600 (`mkstemp`), der Inhalt steht also
    zu keinem Zeitpunkt unter Standardrechten auf der Platte. Bei jedem Fehler
    wird sie entfernt und die Zieldatei bleibt unversehrt.
    """
    target = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise
    # Verzeichniseintrag dauerhaft machen; wo das nicht geht (z. B. Windows),
    # ist die Datei selbst trotzdem ganz.
    with contextlib.suppress(OSError):
        dir_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    return target


def ordner_tauschen(neu: str | Path, ziel: str | Path) -> Path:
    """Setzt den fertigen Ordner `neu` an die Stelle von `ziel`; der Leser sieht die alte oder die neue Fassung.

    Ein Verzeichnis lässt sich nicht in einem Schritt ersetzen. Deshalb: das alte beiseiteschieben, das neue
    an den Zielort setzen, das alte löschen. Bricht etwas zwischen den beiden Umbenennungen ab, stellt der
    nächste Aufruf die alte Fassung wieder her (`.<Name>.alt` liegt dann noch da, `ziel` fehlt). Das Ziel wird
    hier nie gelöscht, bevor die neue Fassung an ihrem Platz steht.
    """
    import shutil
    neu, ziel = Path(neu), Path(ziel)
    alt = ziel.with_name(f".{ziel.name}.alt")
    if alt.exists():
        if ziel.exists():
            shutil.rmtree(alt, ignore_errors=True)
        else:
            os.replace(alt, ziel)
    if ziel.exists():
        os.replace(ziel, alt)
    try:
        os.replace(neu, ziel)
    except BaseException:
        if alt.exists() and not ziel.exists():
            os.replace(alt, ziel)
        raise
    shutil.rmtree(alt, ignore_errors=True)
    with contextlib.suppress(OSError):
        dir_fd = os.open(ziel.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    return ziel
