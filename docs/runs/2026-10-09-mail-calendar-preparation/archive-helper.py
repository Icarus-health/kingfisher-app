#!/usr/bin/env python3
"""Plan/apply removal of one host-verified duplicate snapshot leaf."""
import argparse
import hashlib
import json
import os
import stat
from pathlib import Path

TARGET = 'vor-update-20261009T022544Z'

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()

def digest_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def checked_root(path):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise ValueError('unsafe snapshot parent')
    return path.resolve(strict=True)

def tree(root):
    """Manifest one fixed leaf; reject symlinks and non-regular entries."""
    root = checked_root(root)
    top = root / TARGET
    try:
        top_stat = top.lstat()
    except FileNotFoundError:
        raise ValueError('snapshot missing') from None
    if not stat.S_ISDIR(top_stat.st_mode) or stat.S_ISLNK(top_stat.st_mode):
        raise ValueError('snapshot is not a real directory')
    rows = [['dir', '.']]
    for base, dirs, files in os.walk(top, topdown=True, followlinks=False):
        base = Path(base)
        for name in list(dirs):
            path = base / name
            mode = path.lstat().st_mode
            if not stat.S_ISDIR(mode) or stat.S_ISLNK(mode):
                raise ValueError('symlink or special directory')
            rows.append(['dir', path.relative_to(top).as_posix()])
        for name in files:
            path = base / name
            mode = path.lstat().st_mode
            if not stat.S_ISREG(mode) or stat.S_ISLNK(mode):
                raise ValueError('symlink or special file')
            rows.append(['file', path.relative_to(top).as_posix(), path.stat().st_size, digest_file(path)])
    rows.sort(key=lambda row: row[1])
    return {'root': str(root), 'target': TARGET, 'entries': rows}

def scan(root):
    return {'version': 1, 'snapshot': tree(root)}

def make_plan(host_root, live_scan):
    host = tree(host_root)
    if not isinstance(live_scan, dict):
        raise ValueError('invalid live scan')
    live = live_scan.get('snapshot')
    if live_scan.get('version') != 1 or not isinstance(live, dict):
        raise ValueError('invalid live scan')
    if live.get('target') != TARGET or live.get('entries') != host['entries']:
        raise ValueError('host/live snapshot differs')
    return {'version': 1, 'target': TARGET, 'host_root': host['root'],
            'live_root': live.get('root'), 'entries': host['entries']}


def _remove_contents(directory_fd, prefix, expected):
    direct = {}
    for row in expected:
        if row[1] == '.':
            continue
        parent, sep, name = row[1].rpartition('/')
        parent = parent if sep else '.'
        if parent == prefix:
            direct[name] = row
    names = os.listdir(directory_fd)
    if set(names) != set(direct):
        raise ValueError('snapshot changed during removal')
    flags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    nofollow = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    for name in sorted(names):
        row = direct[name]
        observed = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if row[0] == 'dir':
            if not stat.S_ISDIR(observed.st_mode) or stat.S_ISLNK(observed.st_mode):
                raise ValueError('symlink or special directory raced')
            child_fd = os.open(name, flags, dir_fd=directory_fd)
            try:
                opened = os.fstat(child_fd)
                if (opened.st_dev, opened.st_ino) != (observed.st_dev, observed.st_ino):
                    raise ValueError('directory raced')
                _remove_contents(child_fd, row[1], expected)
            finally:
                os.close(child_fd)
            current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (observed.st_dev, observed.st_ino):
                raise ValueError('directory raced')
            os.rmdir(name, dir_fd=directory_fd)
        elif row[0] == 'file':
            if not stat.S_ISREG(observed.st_mode) or stat.S_ISLNK(observed.st_mode):
                raise ValueError('symlink or special file raced')
            file_fd = os.open(name, nofollow, dir_fd=directory_fd)
            try:
                opened = os.fstat(file_fd)
                if (opened.st_dev, opened.st_ino) != (observed.st_dev, observed.st_ino):
                    raise ValueError('file raced')
                h = hashlib.sha256(); size = 0
                with os.fdopen(os.dup(file_fd), 'rb') as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        h.update(block); size += len(block)
                after_read = os.fstat(file_fd)
                if ((after_read.st_dev, after_read.st_ino) != (observed.st_dev, observed.st_ino)
                        or size != row[2] or h.hexdigest() != row[3]):
                    raise ValueError('file content changed during removal')
            finally:
                os.close(file_fd)
            current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (observed.st_dev, observed.st_ino):
                raise ValueError('file path raced')
            os.unlink(name, dir_fd=directory_fd)
        else:
            raise ValueError('invalid manifest entry')

def remove_exact(root, expected_entries):
    root = checked_root(root)
    if tree(root)['entries'] != expected_entries:
        raise ValueError('snapshot changed at removal boundary')
    flags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    parent_fd = os.open(root, flags)
    try:
        before = os.stat(TARGET, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISDIR(before.st_mode) or stat.S_ISLNK(before.st_mode):
            raise ValueError('snapshot path changed')
        leaf_fd = os.open(TARGET, flags, dir_fd=parent_fd)
        try:
            opened = os.fstat(leaf_fd)
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise ValueError('snapshot path raced')
        finally:
            os.close(leaf_fd)
        if tree(root)['entries'] != expected_entries:
            raise ValueError('snapshot raced at removal boundary')
        leaf_fd = os.open(TARGET, flags, dir_fd=parent_fd)
        try:
            opened = os.fstat(leaf_fd)
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise ValueError('snapshot path raced')
            _remove_contents(leaf_fd, '.', expected_entries)
        finally:
            os.close(leaf_fd)
        current = os.stat(TARGET, dir_fd=parent_fd, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError('snapshot path raced')
        os.rmdir(TARGET, dir_fd=parent_fd)
        try:
            os.stat(TARGET, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ValueError('snapshot removal incomplete')
    finally:
        os.close(parent_fd)

def apply(root, raw, expected_sha256):
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('plan sha mismatch')
    try:
        plan = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ValueError('invalid plan') from None
    if (plan.get('version') != 1 or plan.get('target') != TARGET
            or not isinstance(plan.get('entries'), list)):
        raise ValueError('target contract mismatch')
    root = checked_root(root)
    if str(root) != plan.get('live_root'):
        raise ValueError('live root changed')
    siblings_before = sorted(p.name for p in root.iterdir())
    if TARGET not in siblings_before or tree(root)['entries'] != plan['entries']:
        raise ValueError('live snapshot changed; nothing removed')
    # Re-read the fixed leaf immediately before removal. The host archive path
    # is never opened for writing or deletion by this helper.
    remove_exact(root, plan['entries'])
    siblings_after = sorted(p.name for p in root.iterdir())
    if siblings_after != [name for name in siblings_before if name != TARGET]:
        raise ValueError('unexpected sibling change')
    return {'status': 'one_verified_duplicate_removed', 'target': TARGET,
            'host_archive_retained': True}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    q = sub.add_parser('scan'); q.add_argument('--root', required=True)
    q = sub.add_parser('plan'); q.add_argument('--host-root', required=True); q.add_argument('--live-scan', required=True); q.add_argument('--out', required=True)
    q = sub.add_parser('apply'); q.add_argument('--root', required=True); q.add_argument('--plan', required=True); q.add_argument('--sha256', required=True)
    args = parser.parse_args()
    if args.command == 'scan':
        print(canonical(scan(args.root)).decode())
    elif args.command == 'plan':
        live = json.loads(Path(args.live_scan).read_bytes())
        raw = canonical(make_plan(args.host_root, live))
        Path(args.out).write_bytes(raw)
        print(hashlib.sha256(raw).hexdigest())
    else:
        result = apply(args.root, Path(args.plan).read_bytes(), args.sha256)
        print(json.dumps(result, sort_keys=True))

if __name__ == '__main__':
    main()
