"""Fresh, authenticated host power reports; never infer the Mac from Docker.

Only the requirement to hear from the host is persisted. An old AC reading
must never authorize work after a restart, failed probe or missing helper.
"""
from __future__ import annotations

import json
from pathlib import Path
import threading
import time
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict

from .atomic import write_text_atomic
from .device_profile import load_device_profile

MAX_AGE = 90.0


def mac_expected(path: Path) -> bool:
    return load_device_profile(path).get('platform') == 'macos'


class HostPower:
    def __init__(self, path: Path, *, expected=None, clock=time.monotonic):
        self.path = Path(path) / 'host-power-required.json'
        self.expected = expected or (lambda: mac_expected(Path(path)))
        self.clock = clock
        self.lock = threading.RLock()
        # Even an unreadable marker requires a fresh host measurement.
        self.required = self.path.exists()
        self.source = 'unknown'
        self.received_at = None

    def report(self, source):
        if not isinstance(source, str) or source not in ('ac', 'battery', 'unknown'):
            raise ValueError('Ungültiger Energiestatus.')
        with self.lock:
            if not self.path.exists():
                self.path.parent.mkdir(parents=True, exist_ok=True)
                write_text_atomic(self.path, json.dumps({'required': True}))
            self.required = True
            self.source, self.received_at = source, self.clock()
        return self.public()

    def reason(self):
        with self.lock:
            if not self.required:
                try:
                    self.required = bool(self.expected())
                except Exception:
                    # If host metadata cannot be checked, automatic model work
                    # is safer to postpone than to treat the host as plugged in.
                    return 'energie_unbekannt'
            if not self.required:
                return None
            age = None if self.received_at is None else self.clock() - self.received_at
            if age is None or not 0 <= age <= MAX_AGE or self.source == 'unknown':
                return 'energie_unbekannt'
            return 'akku' if self.source == 'battery' else None

    def public(self):
        with self.lock:
            reason = self.reason()
            return {'required': self.required, 'source': self.source if self.received_at is not None and 0 <= self.clock() - self.received_at <= MAX_AGE else 'unknown',
                    'blocked': reason is not None, 'reason': reason}


class PowerReport(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source: Literal['ac', 'battery', 'unknown']


def install_routes(app, guard, data_dir):
    power = HostPower(data_dir())
    app.state.host_power = power

    @app.post('/api/v1/device/power', dependencies=guard)
    def report(body: PowerReport):
        try:
            result = power.report(body.source)
        except OSError:
            raise HTTPException(503, 'Energiestatus konnte nicht sicher gespeichert werden.') from None
        if not result['blocked']:
            wake = getattr(getattr(app.state, 'scheduler', None), 'wecken', None)
            if callable(wake): wake()
        return result

    return power
