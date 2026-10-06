"""Restore a pre-update snapshot while the normal service is stopped.

Run with the *new* image, before changing the configured image back. The
restore leaves the historical inspection boundary in place deliberately.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

from .backup import restore_all
from .restore_boundary import pending


_NAME = re.compile(r'vor-update-(\d{8}T\d{6}Z)\Z')


def restore_update(snapshot_name: str, *, data_dir: Path = Path('/data')) -> None:
    """Restore one locally named snapshot; caller must have stopped the service."""
    match = _NAME.fullmatch(snapshot_name)
    if match is None:
        raise ValueError('Ungültiger Name der Update-Sicherung.')
    try:
        datetime.strptime(match.group(1), '%Y%m%dT%H%M%SZ')
    except ValueError as exc:
        raise ValueError('Ungültiger Name der Update-Sicherung.') from exc

    data_dir = Path(data_dir)
    snapshots = data_dir / 'sicherungen'
    snapshot = snapshots / snapshot_name
    if snapshots.is_symlink() or snapshot.is_symlink() or not snapshot.is_dir():
        raise ValueError('Update-Sicherung fehlt oder ist kein lokaler Ordner.')
    if any(child.is_symlink() for child in snapshot.iterdir()):
        raise ValueError('Update-Sicherung enthält einen Verweis nach außen.')

    restore_all(snapshot, data_dir)
    if not pending(data_dir):
        raise RuntimeError('Prüfmodus nach Wiederherstellung fehlt.')


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print('Genau einen Namen einer Update-Sicherung angeben.', file=sys.stderr)
        return 2
    try:
        restore_update(args[0])
    except Exception:
        # Restore exceptions can contain private filenames and paths.
        print('Wiederherstellung fehlgeschlagen. Sicherung und neueres Bild behalten; Bestand prüfen.', file=sys.stderr)
        return 1
    print('Sicherung wiederhergestellt; Prüfmodus aktiv.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
