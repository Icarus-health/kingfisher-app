"""Bounded read-only evidence for recovery; never grants activation authority.

All row identifiers and values remain internal. A comparison filename does not
prove lineage or recency, and equality cannot prove the absence of later edits.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import struct
import time

from .backup import BACKUP_DATA_FILES, SQLITE_DATA_FILES
from .restore_boundary import MARKER

MAX_SECONDS = 15
MAX_ROWS = 200_000
MAX_BYTES = 512 * 1024 * 1024
MAX_GROUPS = 8
MAX_ENTRIES = 10_000
SIDECARS = ('-wal', '-shm', '-journal')


class LimitExceeded(Exception):
    pass


class Budget:
    def __init__(self):
        self.deadline = time.monotonic() + MAX_SECONDS
        self.rows = self.bytes = 0

    def check(self, *, rows=0, size=0):
        self.rows += rows
        self.bytes += size
        if time.monotonic() > self.deadline or self.rows > MAX_ROWS or self.bytes > MAX_BYTES:
            raise LimitExceeded


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True).encode()).hexdigest()


def _state(path):
    try:
        s = path.lstat()
        return (s.st_mode, s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    except FileNotFoundError:
        return None
    except OSError:
        return ('unreadable',)


def _file_hash(path, budget):
    digest = hashlib.sha256()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise OSError('not regular')
        while chunk := stream.read(64 * 1024):
            budget.check(size=len(chunk))
            digest.update(chunk)
    return digest.hexdigest()


def _row_hash(row):
    digest = hashlib.sha256()
    for value in row:
        if value is None:
            tag, raw = b'n', b''
        elif isinstance(value, int):
            tag, raw = b'i', str(value).encode('ascii')
        elif isinstance(value, float):
            tag, raw = b'f', struct.pack('!d', value)
        elif isinstance(value, bytes):
            tag, raw = b'b', value
        else:
            tag, raw = b't', value.encode('utf-8', errors='surrogatepass')
        digest.update(tag + len(raw).to_bytes(8, 'big') + raw)
    return digest.hexdigest()


def _quoted(name):
    return '"' + name.replace('"', '""') + '"'


def _tables(conn, budget):
    # Views/virtual tables may invoke application-specific code. Their schemas
    # remain fingerprinted; only ordinary stored tables are read here.
    schema = conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name").fetchall()
    tables = []
    for kind, name, _, sql in schema:
        if kind != 'table' or name.startswith('sqlite_'):
            continue
        budget.check()
        if len(tables) >= 128:
            raise LimitExceeded
        item = {'table': name if re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_]{0,100}', name) else '[unknown]',
                'schema_sha256': _digest(sql), 'row_count': None}
        tables.append(item)
        if not sql or re.match(r'\s*CREATE\s+VIRTUAL\s+TABLE', sql, re.I):
            item['status'] = 'virtual_table'
            continue
        columns = conn.execute('PRAGMA table_info(' + _quoted(name) + ')').fetchall()
        # table_info omits generated columns. Use this exact column list for
        # SELECT as well, so physical cids never index a different projection.
        keys = [index for index, c in enumerate(columns) if c[5]]
        item['row_count'] = conn.execute('SELECT COUNT(*) FROM ' + _quoted(name)).fetchone()[0]
        if not keys:
            item['status'] = 'no_usable_key'
            continue
        rows = {}
        invalid_key = False
        projection = ','.join(_quoted(c[1]) for c in columns)
        for row in conn.execute('SELECT ' + projection + ' FROM ' + _quoted(name)):
            budget.check(rows=1)
            key = tuple(row[i] for i in keys)
            digest = _row_hash(key)
            if None in key or digest in rows:
                invalid_key = True
            rows[digest] = _row_hash(row)
        if invalid_key:
            item['status'] = 'no_usable_key'
        else:
            item.update(status='verified', content_sha256=_digest(sorted(rows.items())), _rows=rows)
    return _digest(schema), tables


def _inspect(root, name, physical, targets, budget):
    path = root / physical
    result = {'name': name, 'status': 'missing', 'tables': []}
    before = _state(path)
    if before is None:
        return result
    if before == ('unreadable',):
        result['status'] = 'unreadable'
        return result
    if stat.S_ISLNK(before[0]):
        result['status'] = 'symlink'
        return result
    if not stat.S_ISREG(before[0]):
        result['status'] = 'non_regular'
        return result
    # Leftover sidecars at the original filename may belong to the pre-restore
    # database. Never infer which state they belong to from the timestamp.
    sidecars = {root / (base + suffix) for base in (name, physical) for suffix in SIDECARS}
    if name in SQLITE_DATA_FILES and any(_state(p) is not None for p in sidecars):
        result['status'] = 'sidecar_present'
        return result
    try:
        budget.check()
        result.update(bytes=before[3], sha256=_file_hash(path, budget))
        if name in SQLITE_DATA_FILES:
            conn = sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)
            try:
                conn.set_progress_handler(lambda: int(time.monotonic() > budget.deadline), 1000)
                conn.execute('PRAGMA query_only=ON')
                conn.execute('PRAGMA trusted_schema=OFF')
                version = conn.execute('PRAGMA user_version').fetchone()[0]
                result['user_version'] = version
                if not 0 <= version <= targets.get(name, 0):
                    result['status'] = 'unsupported_schema'
                    return result
                if conn.execute('PRAGMA integrity_check').fetchone() != ('ok',):
                    result['status'] = 'corrupt'
                    return result
                result['schema_sha256'], result['tables'] = _tables(conn, budget)
            finally:
                conn.close()
        after_hash = _file_hash(path, budget)
        if (_state(path) != before or after_hash != result['sha256'] or
                (name in SQLITE_DATA_FILES and any(_state(p) is not None for p in sidecars))):
            result.update(status='changed_during_read', tables=[])
        else:
            result['status'] = 'verified'
    except LimitExceeded:
        result.update(status='limit_exceeded', tables=[])
    except (OSError, sqlite3.Error, UnicodeError, ValueError) as exc:
        code = getattr(exc, 'sqlite_errorcode', None)
        result.update(status=('limit_exceeded' if time.monotonic() > budget.deadline else
                              'corrupt' if code in (11, 26) else
                              'unreadable'), tables=[])
    return result


def _inventory(root):
    groups = {}
    entries = {}
    incomplete = False
    patterns = [(name, re.compile(re.escape(Path(name).stem) + r'\.vor-wiederherstellung-(\d{8}T\d{6}Z)' +
                                 re.escape(Path(name).suffix) + r'(?:-wal|-shm|-journal)?$'))
                for name in BACKUP_DATA_FILES]
    with os.scandir(root) as directory:
        for index, entry in enumerate(directory):
            if index >= MAX_ENTRIES:
                incomplete = True
                break
            name = entry.name
            if name == MARKER or name in BACKUP_DATA_FILES or any(name == n + s for n in SQLITE_DATA_FILES for s in SIDECARS):
                entries[name] = _state(root / name)
            else:
                for original, pattern in patterns:
                    match = pattern.fullmatch(name)
                    if match:
                        entries[name] = _state(root / name)
                        group = match[1]
                        groups.setdefault(group, {})[original] = (
                            f'{Path(original).stem}.vor-wiederherstellung-{group}{Path(original).suffix}')
                        break
                else:
                    if '.vor-wiederherstellung-' in name:
                        incomplete = True
    return entries, groups, incomplete


def _compare(restored, other):
    result = []
    for name in SQLITE_DATA_FILES:
        left, right = restored[name], other[name]
        l_tables = {t['table']: t for t in left['tables']}
        r_tables = {t['table']: t for t in right['tables']}
        for table in sorted(l_tables.keys() | r_tables.keys()):
            a, b = l_tables.get(table), r_tables.get(table)
            item = {'store': name, 'table': table, 'same_rows': None, 'changed_rows': None,
                    'only_in_restored': None, 'only_in_comparison': None, 'status': 'unresolved'}
            result.append(item)
            if left['status'] != 'verified' or right['status'] != 'verified' or not a or not b:
                item['reason'] = 'missing_or_unreadable_table'
            elif a['schema_sha256'] != b['schema_sha256']:
                item['reason'] = 'different_schema'
            elif a['status'] != 'verified' or b['status'] != 'verified':
                item['reason'] = 'no_usable_key'
            else:
                ar, br = a['_rows'], b['_rows']
                common = ar.keys() & br.keys()
                same = sum(ar[key] == br[key] for key in common)
                item.update(status='compared', same_rows=same, changed_rows=len(common) - same,
                            only_in_restored=len(ar.keys() - br.keys()),
                            only_in_comparison=len(br.keys() - ar.keys()))
    return result


def _public(files):
    return [{**item, 'tables': [{k: v for k, v in t.items() if k != '_rows'} for t in item['tables']]}
            for item in files.values()]


def preflight(directory: Path) -> dict:
    root = Path(directory).absolute()
    report = {'version': 1, 'mode': 'inspection', 'operational': False, 'activation_allowed': False,
              'comparison_complete': False, 'restore_id': None, 'restored': {'files': []},
              'comparison_groups': [], 'unresolved': ['current_authority_unverified']}
    if root.is_symlink() or not root.is_dir():
        report['unresolved'].append('invalid_directory')
        report['report_fingerprint'] = _digest(report)
        return report
    budget = Budget()
    try:
        before, groups, incomplete = _inventory(root)
    except OSError:
        report['unresolved'].append('unreadable_directory')
        report['report_fingerprint'] = _digest(report)
        return report
    marker = root / MARKER
    try:
        if marker.is_symlink() or not marker.is_file() or marker.stat().st_size > 8192:
            raise ValueError
        state = json.loads(marker.read_text())
        if (state.get('version') != 1 or state.get('mode') != 'inspection' or
                state.get('operational') is not False or
                not re.fullmatch(r'[a-f0-9]{32}', state.get('restore_id', ''))):
            raise ValueError
        report['restore_id'] = state['restore_id']
    except (OSError, ValueError, AttributeError, TypeError):
        report['unresolved'].append('invalid_restore_marker')
    from .update_backup import _targets
    targets = {name: max(m.version for m in migrations) for name, migrations in _targets().items()}
    restored = {name: _inspect(root, name, name, targets, budget) for name in BACKUP_DATA_FILES}
    report['restored']['files'] = _public(restored)
    if not groups:
        report['unresolved'].append('no_comparison_state')
    for number, (group, physical) in enumerate(sorted(groups.items())):
        item = {'group': group, 'relationship': 'unverified', 'files': [], 'tables': [], 'unresolved': []}
        report['comparison_groups'].append(item)
        if number >= MAX_GROUPS:
            item['unresolved'].append('group_limit_exceeded')
            continue
        compared = {name: _inspect(root, name, physical.get(name,
            f'{Path(name).stem}.vor-wiederherstellung-{group}{Path(name).suffix}'), targets, budget)
                    for name in BACKUP_DATA_FILES}
        item['files'] = _public(compared)
        item['tables'] = _compare(restored, compared)
        item['unresolved'].append('lineage_and_recency_unverified')
    try:
        after, _, after_incomplete = _inventory(root)
    except OSError:
        after, after_incomplete = None, True
        report['unresolved'].append('unreadable_directory')
    if incomplete or after_incomplete:
        report['unresolved'].append('inventory_incomplete')
    if before != after:
        report['unresolved'].append('changed_during_read')
        # No equality result survives a change to any participating file/group.
        for group in report['comparison_groups']:
            group['tables'] = []
            group['unresolved'].append('changed_during_read')
    report['inventory_fingerprint'] = _digest(after)
    report['report_fingerprint'] = _digest(report)
    return report
