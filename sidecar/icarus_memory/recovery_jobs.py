"""Lokaler Sicherungsauftrag: nur Status auf Disk, Passwort ausschließlich im RAM."""
from contextlib import contextmanager
import json
from pathlib import Path
import secrets
import sqlite3
import threading
import time
import uuid

from fastapi import Header, HTTPException, Response
from pydantic import BaseModel, Field, SecretStr


class RecoveryJobs:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.passwords = {}
        self.seen = None
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS recovery_status (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO recovery_status VALUES (1, ?)', (json.dumps({'job':None}),))
        path.chmod(0o600)
        with self.transaction() as state:
            if state['job'] and state['job']['status'] == 'queued':
                state['job'].update(status='failed', message='Auftrag durch Neustart unterbrochen. Bitte erneut starten.')

    @contextmanager
    def transaction(self):
        with self.lock, sqlite3.connect(self.path, timeout=10) as db:
            db.execute('BEGIN IMMEDIATE')
            state = json.loads(db.execute('SELECT payload FROM recovery_status WHERE id=1').fetchone()[0])
            yield state
            db.execute('UPDATE recovery_status SET payload=? WHERE id=1', (json.dumps(state),))

    def online(self):
        return self.seen is not None and time.monotonic() - self.seen < 15

    def status(self):
        with self.transaction() as state:
            return {'online':self.online(), **state}

    def enqueue(self, password):
        if not 16 <= len(password) <= 256:
            raise ValueError('Bitte ein Sicherungspasswort mit 16 bis 256 Zeichen wählen.')
        with self.transaction() as state:
            if not self.online():
                raise ValueError('Der lokale Sicherungshelfer ist nicht erreichbar.')
            if state['job'] and state['job']['status'] in ('queued', 'running'):
                raise ValueError('Eine Sicherung läuft bereits.')
            ident = uuid.uuid4().hex
            self.passwords[ident] = password
            state['job'] = {'id':ident, 'status':'queued', 'message':'Sicherung wird vorbereitet.', 'path':None}
            return dict(state['job'])

    def claim(self):
        with self.transaction() as state:
            self.seen = time.monotonic()
            job = state['job']
            if job and job['status'] == 'queued':
                password = self.passwords.pop(job['id'], None)
                if password is not None:
                    job.update(status='running', message='Sicherung läuft. Kingfisher wird kurz neu gestartet.')
                    return {'id':job['id'], 'password':password}
                job.update(status='failed', message='Auftrag unterbrochen. Bitte erneut starten.')
            elif job and job['status'] == 'running':
                # Der einzelne Mac-Helfer fragt erst nach Abschluss erneut nach.
                # Eine neue Leerlauf-Abfrage bedeutet deshalb einen Helferneustart.
                job.update(status='failed', message='Der Sicherungshelfer wurde unterbrochen. Bitte erneut starten.')
            return None

    def finish(self, ident, success, path):
        with self.transaction() as state:
            job = state['job']
            if not job or job['id'] != ident:
                raise ValueError('Unbekannter Sicherungsauftrag.')
            if job['status'] == 'running':
                job.update(status='completed' if success else 'failed', path=path if success else None,
                    message='Sicherung erstellt und Wiederherstellung geprüft.' if success else
                            'Sicherung nicht abgeschlossen. Bitte Docker und die lokale Konfiguration prüfen.')
            self.seen = time.monotonic()


class RecoveryRequest(BaseModel):
    password: SecretStr


class RecoveryResult(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    success: bool
    path: str | None = Field(default=None, max_length=4096)


def install_routes(app, guard, jobs, expected):
    def worker_auth(x_icarus_token: str | None = Header(default=None)):
        if expected is None or x_icarus_token is None or not secrets.compare_digest(expected, x_icarus_token):
            raise HTTPException(status_code=401, detail='Lokaler Helfer nicht angemeldet.')

    from fastapi import Depends
    worker_guard = [Depends(worker_auth)]

    @app.get('/api/v1/recovery', dependencies=guard)
    def recovery_status(response: Response):
        response.headers['Cache-Control'] = 'no-store'
        return jobs.status()

    @app.post('/api/v1/recovery', dependencies=guard, status_code=202)
    def recovery_start(body: RecoveryRequest):
        try:
            return jobs.enqueue(body.password.get_secret_value())
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get('/api/v1/recovery/worker', dependencies=worker_guard)
    def recovery_claim(response: Response):
        response.headers['Cache-Control'] = 'no-store'
        return {'job':jobs.claim()}

    @app.post('/api/v1/recovery/worker', dependencies=worker_guard)
    def recovery_finish(body: RecoveryResult):
        try:
            jobs.finish(body.id, body.success, body.path)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {'ok':True}
