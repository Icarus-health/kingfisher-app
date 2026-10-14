"""Reversible presentation metadata; never edits originals, identities or claims."""
import base64
import json
import math
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .migrations import Migration, run_migrations, validate_legacy_or_empty, verify_schema


TABLES = {'view_records': {'kind', 'id', 'document', 'revision'},
          'view_events': {'sequence', 'kind', 'record_id', 'previous', 'revision', 'recorded_at'}}
KEYS = {'view_records': {'kind', 'id'}, 'view_events': {'sequence'}}
KINDS = {'folder', 'source_folder', 'organisation_group', 'place', 'avatar', 'preferences', 'project_hint'}


def verify(conn):
    verify_schema(conn, expected_tables=TABLES, expected_primary_keys=KEYS)


def install(conn):
    validate_legacy_or_empty(conn, store='workspace_views', path=conn.execute('PRAGMA database_list').fetchone()[2], expected_tables=TABLES, expected_primary_keys=KEYS)
    conn.execute('CREATE TABLE view_records (kind TEXT NOT NULL,id TEXT NOT NULL,document TEXT,revision INTEGER NOT NULL,PRIMARY KEY(kind,id))')
    conn.execute('CREATE TABLE view_events (sequence INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,record_id TEXT NOT NULL,previous TEXT,revision INTEGER NOT NULL,recorded_at TEXT NOT NULL)')


_MIGRATIONS = (Migration(1, 'reversible_presentation_metadata', install, verify),)


class ViewChanged(ValueError):
    pass


class WorkspaceViews:
    def __init__(self, path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        try:
            run_migrations(self._conn, store='workspace_views', path=self._path, migrations=_MIGRATIONS)
        except Exception:
            self._conn.close()
            raise

    def close(self):
        self._conn.close()

    def get(self, kind, identifier):
        with self._lock:
            row = self._conn.execute('SELECT * FROM view_records WHERE kind=? AND id=?', (kind, identifier)).fetchone()
        return {'id': identifier, 'kind': kind, 'revision': row['revision'] if row else 0,
                'data': json.loads(row['document']) if row and row['document'] is not None else None}

    def items(self, kind):
        with self._lock:
            rows = self._conn.execute('SELECT id FROM view_records WHERE kind=? AND document IS NOT NULL ORDER BY id LIMIT 2000', (kind,)).fetchall()
            return [self.get(kind, row['id']) for row in rows]

    def _validate(self, kind, identifier, data):
        if kind not in KINDS or not isinstance(identifier, str) or not 1 <= len(identifier) <= 1000:
            raise ValueError('Unbekannter Ablagebereich oder ungültige Kennung.')
        if data is None:
            return
        if not isinstance(data, dict) or len(json.dumps(data)) > 1_500_000:
            raise ValueError('Die Ablageangabe ist ungültig oder zu groß.')
        if kind == 'folder':
            if set(data) != {'name', 'parent_id'} or not isinstance(data['name'], str) or not 1 <= len(data['name'].strip()) <= 200:
                raise ValueError('Ordnername fehlt oder ist zu lang.')
            parent = data['parent_id']
            visited = {identifier}
            while parent is not None:
                if not isinstance(parent, str) or parent in visited:
                    raise ValueError('Ordner dürfen keine Kreisverknüpfung enthalten.')
                visited.add(parent)
                record = self.get('folder', parent)['data']
                if record is None:
                    raise ValueError('Der übergeordnete Ordner fehlt.')
                parent = record['parent_id']
        elif kind == 'source_folder':
            if set(data) != {'folder_id'} or (data['folder_id'] is not None and (not isinstance(data['folder_id'], str) or self.get('folder', data['folder_id'])['data'] is None)):
                raise ValueError('Der ausgewählte Ordner fehlt.')
        elif kind == 'organisation_group':
            if (set(data) != {'name', 'members'} or not isinstance(data['name'], str) or not 1 <= len(data['name'].strip()) <= 200
                    or not isinstance(data['members'], list) or not 1 <= len(data['members']) <= 200
                    or any(not isinstance(x, str) or not 1 <= len(x) <= 1000 for x in data['members'])
                    or len(set(data['members'])) != len(data['members'])):
                raise ValueError('Bitte einen Gruppennamen und unterschiedliche Organisationen wählen.')
        elif kind == 'place':
            if set(data) != {'lat', 'lng'} or any(type(data[k]) not in (int, float) or not math.isfinite(data[k]) for k in ('lat', 'lng')) or not -90 <= data['lat'] <= 90 or not -180 <= data['lng'] <= 180:
                raise ValueError('Bitte eine gültige Position ausdrücklich festlegen.')
        elif kind == 'preferences':
            if identifier != 'online' or set(data) != {'logos', 'maps'} or any(type(v) is not bool for v in data.values()):
                raise ValueError('Online-Bilder und Karte brauchen ausdrückliche Schalter.')
        elif kind == 'avatar':
            if set(data) != {'data_url'} or not isinstance(data['data_url'], str):
                raise ValueError('Ungültiges Bild.')
            header, sep, encoded = data['data_url'].partition(',')
            magic = {'data:image/png;base64': b'\x89PNG\r\n\x1a\n', 'data:image/jpeg;base64': b'\xff\xd8\xff', 'data:image/webp;base64': b'RIFF'}
            if not sep or header not in magic:
                raise ValueError('Bitte PNG, JPEG oder WebP verwenden.')
            try:
                raw = base64.b64decode(encoded, validate=True)
            except ValueError:
                raise ValueError('Das Bild ist kein gültiges Base64.') from None
            if not 12 <= len(raw) <= 1_000_000 or not raw.startswith(magic[header]) or (header.endswith('webp;base64') and raw[8:12] != b'WEBP'):
                raise ValueError('Das Bild ist ungültig oder größer als 1 MB.')
        elif kind == 'project_hint':
            if len(json.dumps(data)) > 16000:
                raise ValueError('Projektvorschlag überschreitet den Rahmen.')

    def put(self, kind, identifier, data, revision):
        with self._lock, self._conn:
            self._conn.execute('BEGIN IMMEDIATE')
            current = self.get(kind, identifier)
            if type(revision) is not int or revision != current['revision']:
                raise ViewChanged('Die Zuordnung wurde verändert. Bitte neu laden.')
            self._validate(kind, identifier, data)
            return self._write(kind, identifier, data, current)

    def _write(self, kind, identifier, data, current):
        next_revision = current['revision'] + 1
        encode = lambda value: json.dumps(value, ensure_ascii=False, allow_nan=False) if value is not None else None
        self._conn.execute('INSERT INTO view_events(kind,record_id,previous,revision,recorded_at) VALUES(?,?,?,?,?)',
                           (kind, identifier, encode(current['data']), next_revision, datetime.now(timezone.utc).isoformat()))
        self._conn.execute('INSERT INTO view_records(kind,id,document,revision) VALUES(?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET document=excluded.document,revision=excluded.revision',
                           (kind, identifier, encode(data), next_revision))
        return {'id': identifier, 'kind': kind, 'revision': next_revision, 'data': data}

    def undo(self, kind, identifier, revision):
        with self._lock, self._conn:
            self._conn.execute('BEGIN IMMEDIATE')
            current = self.get(kind, identifier)
            if revision != current['revision']:
                raise ViewChanged('Die Zuordnung wurde verändert. Bitte neu laden.')
            event = self._conn.execute('SELECT previous FROM view_events WHERE kind=? AND record_id=? AND revision=?', (kind, identifier, revision)).fetchone()
            if event is None:
                raise ValueError('Keine frühere Zuordnung vorhanden.')
            previous = json.loads(event['previous']) if event['previous'] is not None else None
            self._validate(kind, identifier, previous)
            if kind == 'folder' and previous is None:
                if any(x['data']['parent_id'] == identifier for x in self.items('folder')) or any(x['data']['folder_id'] == identifier for x in self.items('source_folder')):
                    raise ViewChanged('Dieser Ordner enthält noch Unterordner oder Dokumentzuordnungen.')
            return self._write(kind, identifier, previous, current)


def register(app, guard, data_dir):
    from fastapi import HTTPException
    from pydantic import BaseModel, ConfigDict, StrictInt

    app.state.workspace_views = WorkspaceViews(data_dir() / 'workspace-views.sqlite3')

    class Input(BaseModel):
        model_config = ConfigDict(extra='forbid')
        revision: StrictInt
        data: dict

    class Undo(BaseModel):
        model_config = ConfigDict(extra='forbid')
        revision: StrictInt

    @app.get('/api/v1/workspace-view', dependencies=guard)
    def overview():
        store = app.state.workspace_views
        online = store.get('preferences', 'online')
        return {key: store.items(kind) for key, kind in (('folders', 'folder'), ('source_folders', 'source_folder'),
                ('organisation_groups', 'organisation_group'), ('places', 'place'))} | {
                'avatars': [{**record, 'data': {'available': True}} for record in store.items('avatar')],
                'online': online['data'] or {'logos': False, 'maps': False}, 'online_revision': online['revision']}

    @app.get('/api/v1/workspace-view/{kind}/{identifier:path}', dependencies=guard)
    def record(kind: str, identifier: str):
        if kind not in KINDS or kind == 'project_hint':
            raise HTTPException(422, 'Unbekannter Ablagebereich.')
        return app.state.workspace_views.get(kind, identifier)

    @app.put('/api/v1/workspace-view/{kind}/{identifier:path}', dependencies=guard)
    def save(kind: str, identifier: str, body: Input):
        if kind == 'project_hint':
            raise HTTPException(422, 'Projektvorschläge kommen aus der begrenzten lokalen Prüfung.')
        try:
            return app.state.workspace_views.put(kind, identifier, body.data, body.revision)
        except ViewChanged as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post('/api/v1/workspace-view/{kind}/{identifier:path}/undo', dependencies=guard)
    def undo(kind: str, identifier: str, body: Undo):
        if kind == 'project_hint':
            raise HTTPException(422, 'Dieser Vorschlag kann hier nicht geändert werden.')
        try:
            return app.state.workspace_views.undo(kind, identifier, body.revision)
        except ViewChanged as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
