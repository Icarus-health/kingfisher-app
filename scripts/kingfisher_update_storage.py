"""Read-only storage probe and fail-closed capacity policy for Kingfisher updates.

The source string is shipped into the native app bundle and runs with the
currently running container's Python. Keep that probe self-contained and
stdlib-only: it must not depend on this host-side module being installed.
"""
from __future__ import annotations

from typing import Any

PROBE_SOURCE = r'''import json
import os
import stat
import sys

MAX_U64 = (1 << 64) - 1
SCHEMA = {
    "root_available_bytes",
    "root_available_inodes",
    "data_available_bytes",
    "data_available_inodes",
    "backup_bytes",
    "backup_files",
}


class ProbeError(Exception):
    pass


def _u64(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > MAX_U64:
        raise ProbeError("measurement unavailable")
    return value


def _available(statistics):
    try:
        total_inodes = _u64(statistics.f_files)
        if total_inodes == 0:
            raise ProbeError("measurement unavailable")
        fragment_size = _u64(statistics.f_frsize)
        blocks_available = _u64(statistics.f_bavail)
        inodes_available = _u64(statistics.f_favail)
        available_bytes = blocks_available * fragment_size
        if available_bytes > MAX_U64:
            raise ProbeError("measurement unavailable")
        return available_bytes, inodes_available
    except (AttributeError, OSError, TypeError, ValueError, OverflowError) as exc:
        raise ProbeError("measurement unavailable") from exc


def collect_status(data_dir=None, statvfs=None):
    """Measure filesystem capacity and regular top-level backup inputs only."""
    statvfs = statvfs or os.statvfs
    data_dir = data_dir or os.environ.get("ICARUS_DATA_DIR") or "/data"
    try:
        root_bytes, root_inodes = _available(statvfs("/"))
        data_bytes, data_inodes = _available(statvfs(data_dir))
        root_stat = os.lstat(data_dir)
        if not stat.S_ISDIR(root_stat.st_mode):
            raise ProbeError("measurement unavailable")
        if not root_stat.st_mode & 0o555:
            raise ProbeError("measurement unavailable")

        backup_bytes = 0
        backup_files = 0
        with os.scandir(data_dir) as entries:
            for entry in entries:
                try:
                    entry_stat = entry.stat(follow_symlinks=False)
                except OSError as exc:
                    raise ProbeError("measurement unavailable") from exc
                mode = entry_stat.st_mode
                if stat.S_ISLNK(mode):
                    raise ProbeError("measurement unavailable")
                if stat.S_ISDIR(mode):
                    continue
                if not stat.S_ISREG(mode) or not mode & 0o444:
                    raise ProbeError("measurement unavailable")
                size = _u64(entry_stat.st_size)
                backup_bytes += size
                backup_files += 1
                if backup_bytes > MAX_U64 or backup_files > MAX_U64:
                    raise ProbeError("measurement unavailable")
    except ProbeError:
        raise
    except (OSError, TypeError, ValueError, OverflowError) as exc:
        raise ProbeError("measurement unavailable") from exc

    status = {
        "root_available_bytes": root_bytes,
        "root_available_inodes": root_inodes,
        "data_available_bytes": data_bytes,
        "data_available_inodes": data_inodes,
        "backup_bytes": backup_bytes,
        "backup_files": backup_files,
    }
    if set(status) != SCHEMA:
        raise ProbeError("measurement unavailable")
    return status


if __name__ == "__main__":
    try:
        print(json.dumps(collect_status(), separators=(",", ":")))
    except Exception:
        sys.stderr.write("storage probe unavailable\n")
        raise SystemExit(2)
'''

MAX_U64 = (1 << 64) - 1
SCHEMA = frozenset({
    'root_available_bytes',
    'root_available_inodes',
    'data_available_bytes',
    'data_available_inodes',
    'backup_bytes',
    'backup_files',
})
ROOT_RESERVE_BYTES = 512 * 1024 * 1024
DATA_RESERVE_BYTES = 512 * 1024 * 1024
ROOT_RESERVE_INODES = 64
DATA_RESERVE_INODES = 64


def evaluate_status(status: Any, before_backup: bool) -> str | None:
    """Return low_space, low_inodes, or unavailable; None means both reserves fit."""
    if not isinstance(before_backup, bool) or not isinstance(status, dict) or set(status) != SCHEMA:
        return 'unavailable'
    values: dict[str, int] = {}
    for name in SCHEMA:
        value = status.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_U64:
            return 'unavailable'
        values[name] = value

    copies = 3 if before_backup else 2
    projected_bytes = DATA_RESERVE_BYTES + copies * values['backup_bytes']
    projected_inodes = DATA_RESERVE_INODES + copies * values['backup_files']
    if projected_bytes > MAX_U64 or projected_inodes > MAX_U64:
        return 'unavailable'
    if (values['root_available_bytes'] < ROOT_RESERVE_BYTES
            or values['data_available_bytes'] < projected_bytes):
        return 'low_space'
    if (values['root_available_inodes'] < ROOT_RESERVE_INODES
            or values['data_available_inodes'] < projected_inodes):
        return 'low_inodes'
    return None


if __name__ == '__main__':
    exec(PROBE_SOURCE, {'__name__': '__main__'})
