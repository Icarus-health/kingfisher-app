"""Persistent historical inspection and a shared runtime/restore exclusion boundary.

The marker is outside the snapshot file allowlist. Every restore creates a fresh
marker; saved configuration and snapshot contents cannot activate it. There is
intentionally no blanket activation endpoint for unknown historical permissions.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
import asyncio
import json
import os
import threading
import time
import uuid

MARKER = 'restore-state.json'
CAPABILITY = 1
_active = ContextVar('kingfisher_runtime_boundaries', default=frozenset())


class RestorePending(RuntimeError):
    pass


def pending(directory):
    path = Path(directory) / MARKER
    # Even a malformed or dangling marker is a restriction, never a release.
    return path.exists() or path.is_symlink()


def mark_pending(directory, reason):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    state = {'version': 1, 'mode': 'inspection', 'restore_id': uuid.uuid4().hex,
             'reason': reason, 'operational': False}
    temporary = directory / ('.restore-state-' + uuid.uuid4().hex)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(state, stream)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, directory / MARKER)
        fd = os.open(directory, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)
    return state


class RuntimeBoundary:
    def __init__(self, directory):
        self.directory = Path(directory)
        self._lock = threading.Lock()
        self._readers = 0
        self._exclusive = False

    def check(self):
        if pending(self.directory):
            raise RestorePending('Wiederhergestellter Bestand ist nur zur historischen Einsicht geöffnet.')

    def try_enter(self, *, exclusive=False):
        with self._lock:
            if self._exclusive or (exclusive and self._readers):
                return False
            if exclusive: self._exclusive = True
            else: self._readers += 1
            return True

    def leave(self, *, exclusive=False):
        with self._lock:
            if exclusive: self._exclusive = False
            else: self._readers -= 1

    @contextmanager
    def operation(self):
        self.check()
        if id(self) in _active.get():
            yield
            self.check()
            return
        while not self.try_enter():
            self.check()
            time.sleep(.01)
        token = _active.set(_active.get() | {id(self)})
        try:
            self.check()
            yield
            self.check()
        finally:
            _active.reset(token)
            self.leave()


def guarded(function):
    @wraps(function)
    def call(self, *args, **kwargs):
        boundary = getattr(self, '_runtime_boundary', None)
        if boundary is None:
            return function(self, *args, **kwargs)
        with boundary.operation():
            return function(self, *args, **kwargs)
    return call


class RecoveryBoundaryMiddleware:
    def __init__(self, app, boundary, inspection):
        self.app, self.boundary, self.inspection = app, boundary, inspection

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        if pending(self.boundary.directory):
            return await self.inspection(scope, receive, send)
        exclusive = scope['path'] == '/backups/restore' and scope['method'] == 'POST'
        # Do not occupy a worker thread while waiting for requests/jobs to drain.
        while not self.boundary.try_enter(exclusive=exclusive):
            if pending(self.boundary.directory):
                return await self.inspection(scope, receive, send)
            await asyncio.sleep(.01)
        token = _active.set(_active.get() | {id(self.boundary)})
        try:
            if pending(self.boundary.directory):
                return await self.inspection(scope, receive, send)
            await self.app(scope, receive, send)
        finally:
            _active.reset(token)
            self.boundary.leave(exclusive=exclusive)
