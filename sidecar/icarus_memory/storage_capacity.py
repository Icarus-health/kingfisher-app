"""Read-only headroom gate for automatic intake, not a disk quota or cleanup."""
from __future__ import annotations

import os
from pathlib import Path

# Leave room for SQLite journals, connection/config files and recovery. A
# bounded source can still grow beyond this reserve; it is not a write quota.
MIN_BYTES = 512 * 1024**2
MIN_INODES = 1024
MESSAGES = {
    'storage_low': 'Die Verarbeitung wartet auf freien Speicher. Bereits gespeicherte Inhalte bleiben erhalten. Nach dem Freimachen von Speicher geht es automatisch weiter, sofern du nicht selbst pausiert hast.',
    'storage_unknown': 'Die freie Speicherreserve lässt sich gerade nicht prüfen. Die Verarbeitung wartet und versucht es erneut. Bereits gespeicherte Inhalte bleiben erhalten.',
}


def reason(data_dir: str | Path) -> str | None:
    """Check root and actual data filesystem freshly; never inspect source text."""
    try:
        for path in ('/', data_dir):
            s = os.statvfs(path)
            values = (s.f_frsize, s.f_bavail, s.f_files, s.f_favail)
            if any(isinstance(n, bool) or not isinstance(n, int) or n < 0 for n in values):
                return 'storage_unknown'
            if s.f_frsize == 0 or s.f_files == 0:
                return 'storage_unknown'
            if s.f_frsize * s.f_bavail < MIN_BYTES or s.f_favail < MIN_INODES:
                return 'storage_low'
    except (OSError, AttributeError, TypeError, ValueError, OverflowError):
        return 'storage_unknown'
    return None
