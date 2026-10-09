#!/usr/bin/env python3
"""One-shot OFFLINE schema-19 -> 20 check; never starts the application.

Caller must keep every service/writer stopped and the candidate unpublished
for the whole invocation. This is not a generic downgrade or post-publish
rollback tool. Only the frozen category patch is supported.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sqlite3

from icarus_memory import backup, episodes, memory_categories, restore_boundary, update_backup, update_restore

PATCH_SHA256 = '25244a13586375dc9366aaad8d68adf4cd4867174bd9a2b207afacb44ad907b8'
CODE_HASHES = {
    'episodes': '31a460f63e77dbd0266e88ef8499bff07fe374eb8b269b3b7e3ebc5896d361b3',
    'memory_categories': '6687e729977eb967df4815bfc36d47adf1872fb6a2b638a2c42f9623a97b537d',
    'backup': 'd1c6555adc94657778ca5879045a4acaf817b8c8e01ca7886d8a147090289851',
    'update_backup': '47d43c74e31eae7bc516b66f4eae6080067e42afe7ce80c618be7288574a1fd5',
    'update_restore': 'ad0c2ec64b7202ac0738a6c85b7f4ef843aea192ddea426c0bea8954ca25d113',
}
# Operational job state is deliberately outside the product snapshot allowlist.
OPERATIONAL = ('recovery-status.sqlite3',)


class CheckFailed(RuntimeError):
    """A closed diagnostic code; never wrap private SQL/results/exception text."""


def _require(condition, code):
    if not condition:
        raise CheckFailed(code)


def _sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _connect(path):
    # Layout checks reject journal/WAL sidecars first. Immutable reads neither
    # mutate the data nor create shared-memory files; quiescence is a caller duty.
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro&immutable=1', uri=True)


def _quote(name):
    return '"' + name.replace('"', '""') + '"'


def _feed(digest, values):
    typed = [('blob', value.hex()) if isinstance(value, bytes) else (type(value).__name__, value)
             for value in values]
    data = json.dumps(typed, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    digest.update(len(data).to_bytes(8, 'big')); digest.update(data)


def _layout(directory):
    _require(directory.is_absolute() and directory.is_dir() and not directory.is_symlink(), 'data_directory')
    allowed = set(backup.BACKUP_DATA_FILES) | set(OPERATIONAL)
    for name in allowed:
        path = directory / name
        _require(not path.is_symlink() and (not path.exists() or path.is_file()), 'unsafe_active_file')
        if name.endswith('.sqlite3'):
            for suffix in ('-wal', '-shm', '-journal'):
                sidecar = directory / (name + suffix)
                _require(not sidecar.exists() and not sidecar.is_symlink(), 'database_not_cleanly_closed')
    # Product restore retains displaced stores. They are historical copies,
    # not active databases and are never migrated or deleted by this script.
    stems = '|'.join(re.escape(Path(name).stem) for name in backup.SQLITE_DATA_FILES)
    displaced = re.compile(r'(?:' + stems + r')\.vor-wiederherstellung-\d{8}T\d{6}Z\.sqlite3\Z')
    _require(all(path.name in allowed or displaced.fullmatch(path.name)
                 for path in directory.glob('*.sqlite3')), 'uncovered_database')
    snapshots = directory / 'sicherungen'
    _require(not snapshots.is_symlink() and (not snapshots.exists() or snapshots.is_dir()), 'unsafe_snapshot_directory')
    return sorted(name for name in allowed if (directory / name).is_file())


def _table_inventory(connection, table, *, omit_failure=False):
    info = connection.execute(f'PRAGMA table_info({_quote(table)})').fetchall()
    columns = [row[1] for row in info if not (omit_failure and row[1] == 'failure_code')]
    keys = [row[1] for row in sorted(info, key=lambda row: row[5]) if row[5]]
    order = ','.join(map(_quote, keys)) if keys else 'rowid'
    query = f'SELECT {",".join(map(_quote, columns))} FROM {_quote(table)} ORDER BY {order}'
    digest, count = hashlib.sha256(), 0
    for row in connection.execute(query):
        _feed(digest, row); count += 1
    return {'columns': columns, 'rows': count, 'sha256': digest.hexdigest()}


def _inventory(directory, expected_version):
    names = _layout(directory)
    _require('episodes.sqlite3' in names, 'episodes_missing')
    files, versions, originals = {}, {}, {}
    targets = update_backup._targets()
    for name in names:
        path = directory / name
        if not name.endswith('.sqlite3'):
            files[name] = {'sha256': _sha(path)}
            continue
        with closing(_connect(path)) as connection:
            _require(connection.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'quick_check_failed')
            version = int(connection.execute('PRAGMA user_version').fetchone()[0])
            versions[name] = version
            if name in targets:
                _require(0 <= version <= len(targets[name]), 'unsupported_schema')
            if name == 'episodes.sqlite3':
                _require(version == expected_version, 'episode_schema')
                episodes._MIGRATIONS[version - 1].verify(connection)
                if version == 20:
                    info = connection.execute('PRAGMA table_info(memory_category_sources)').fetchall()
                    field = next(row for row in info if row[1] == 'failure_code')
                    _require(field[2:] == ('TEXT', 0, None, 0), 'failure_column_contract')
                    _require(connection.execute('SELECT COUNT(*) FROM memory_category_sources WHERE failure_code IS NOT NULL').fetchone()[0] == 0, 'non_null_old_failure_code')
                digests = {key: hashlib.sha256() for key in ('ids', 'stored_digest', 'body', 'document')}
                count = 0
                for ident, stored_digest, body, document in connection.execute('SELECT id,digest,body,document FROM episodes ORDER BY id'):
                    _require(episodes.digest_of(body) == stored_digest, 'original_digest_mismatch')
                    for key, value in zip(digests, (ident, stored_digest, body, document)):
                        _feed(digests[key], (ident, value))
                    count += 1
                originals = {'count': count, **{key + '_sha256': value.hexdigest() for key, value in digests.items()}}
            # Hash stored tables (including FTS shadow data), not virtual projections
            # that would require app-specific SQL functions merely to read.
            tables = [row[0] for row in connection.execute("SELECT name,sql FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
                      if not str(row[1]).lstrip().upper().startswith('CREATE VIRTUAL TABLE')]
            files[name] = {table: _table_inventory(connection, table, omit_failure=(name == 'episodes.sqlite3' and table == 'memory_category_sources' and version == 20)) for table in tables}
    return {'files': files, 'versions': versions, 'originals': originals}


def _same(before, after, *, migrated=False, snapshot=False):
    baseline = {'files': dict(before['files']), 'versions': dict(before['versions']), 'originals': before['originals']}
    if snapshot:
        for name in OPERATIONAL:
            baseline['files'].pop(name, None); baseline['versions'].pop(name, None)
    if migrated:
        baseline['versions']['episodes.sqlite3'] = 20
    _require(baseline == after, 'inventory_changed')


def _verified_snapshot(snapshot, before):
    _require(re.fullmatch(r'vor-update-\d{8}T\d{6}Z', snapshot.name) is not None, 'snapshot_name_not_restorable')
    _require(not snapshot.is_symlink() and not any(p.is_symlink() for p in snapshot.iterdir()), 'unsafe_snapshot')
    entries = backup.verify_snapshot_set(snapshot)
    expected = set(before['files']) & set(backup.BACKUP_DATA_FILES)
    _require({entry['name'] for entry in entries} == expected, 'snapshot_incomplete')
    _same(before, _inventory(snapshot, 19), snapshot=True)


def _postcheck(directory, before):
    after = _inventory(directory, 20)
    _same(before, after, migrated=True)
    _require(update_backup.outdated(directory) == [], 'other_pending_migrations')
    _require(not restore_boundary.pending(directory), 'unexpected_inspection_marker')
    return after


def run(data_dir, *, service_stopped=False, unpublished=False):
    """Return content-free JSON data; never publish/start any service.

    Both flags are attestations by the installer, not process detection. The
    installer must also reserve disk for a snapshot, restore staging, and the
    displaced databases. Once this call returns, it offers NO rollback API.
    """
    result = {'status': 'preflight_failed', 'publish_allowed': False, 'patch_sha256': PATCH_SHA256,
              'phase': 'preconditions', 'rollback': {'attempted': False, 'verified': False}}
    # Product migration helpers log exception context; this one-shot reports
    # only closed diagnostic codes/types. Restore the caller logging level.
    logging_before = logging.root.manager.disable
    logging.disable(max(logging.CRITICAL, logging_before))
    migration_started = False
    lock_fd = None
    directory, snapshot, before = None, None, None
    try:
        directory = Path(data_dir)
        _require(service_stopped is True and unpublished is True, 'offline_unpublished_required')
        names = _layout(directory)
        _require(not restore_boundary.pending(directory), 'inspection_already_pending')
        actual = {name: _sha(Path(globals()[name].__file__)) for name in CODE_HASHES}
        _require(actual == CODE_HASHES, 'unreviewed_product_code')
        result['product_hashes'] = actual
        _require(len(episodes._MIGRATIONS) == 20 and episodes._MIGRATIONS[-1].name == 'category_failure_diagnostics', 'migration_contract')
        lock_fd = os.open(directory / '.category-migration20-preflight.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result['phase'] = 'inventory_before'
        before = _inventory(directory, 19)
        _require(update_backup.outdated(directory) == ['episodes.sqlite3'], 'other_pending_migrations')
        result['inventory_before'] = before
        result['operational_not_in_snapshot'] = [name for name in OPERATIONAL if name in names]
        result['phase'] = 'snapshot'
        target = directory / 'sicherungen'
        at = datetime.now(timezone.utc)
        # restore_update deliberately does not accept snapshot_all's -1 suffix.
        while (target / f'{backup.UPDATE_SET_PREFIX}{at:%Y%m%dT%H%M%SZ}').exists() or (target / f'.{backup.UPDATE_SET_PREFIX}{at:%Y%m%dT%H%M%SZ}.partial').exists():
            at += timedelta(seconds=1)
        keep = sum(1 for p in target.glob(backup.UPDATE_SET_PREFIX + '*') if p.is_dir()) + 1
        snapshot = backup.snapshot_all(directory, target, keep=keep, at=at, prefix=backup.UPDATE_SET_PREFIX)
        result['snapshot_name'] = snapshot.name
        result['phase'] = 'verify_snapshot'
        _verified_snapshot(snapshot, before)
        _same(before, _inventory(directory, 19))  # detect changes during backup, before migration
        result['snapshot_verified'] = True
        result['phase'] = 'migrate'
        migration_started = True
        store = None
        try:
            store = episodes.EpisodeStore(directory / 'episodes.sqlite3')
        finally:
            if store is not None:
                store.close()
        result['phase'] = 'postcheck'
        result['inventory_after'] = _postcheck(directory, before)
        result.update(status='migrated', publish_allowed=True, phase='complete', outdated=[])
    except Exception as error:
        result['error'] = str(error) if isinstance(error, CheckFailed) else type(error).__name__
        if migration_started:
            result['rollback']['attempted'] = True
            try:
                _layout(directory)  # never unlink/checkpoint an unexplained journal/WAL
                _verified_snapshot(snapshot, before)
                update_restore.restore_update(snapshot.name, data_dir=directory)
                restored = _inventory(directory, 19)
                _same(before, restored)
                marker = json.loads((directory / restore_boundary.MARKER).read_text())
                _require(restore_boundary.pending(directory) and marker.get('mode') == 'inspection' and marker.get('operational') is False, 'inspection_marker_missing')
                result.update(status='restored_inspection', inventory_restored=restored)
                result['rollback'].update(verified=True, schema=19, inspection=True)
            except Exception as recovery_error:
                result['status'] = 'recovery_failed'
                result['rollback']['error'] = str(recovery_error) if isinstance(recovery_error, CheckFailed) else type(recovery_error).__name__
                # This is not a claim that restore succeeded. Restrict accidental
                # later starts of the remaining new/current store to inspection.
                try:
                    restore_boundary.mark_pending(directory, 'migration20_preflight_failed')
                except Exception:
                    pass
                result['rollback']['inspection'] = restore_boundary.pending(directory)
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
        logging.disable(logging_before)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--service-stopped', action='store_true')
    parser.add_argument('--unpublished', action='store_true')
    args = parser.parse_args(argv)
    result = run(args.data_dir, service_stopped=args.service_stopped, unpublished=args.unpublished)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result['status'] == 'migrated' else 1


if __name__ == '__main__':
    raise SystemExit(main())
