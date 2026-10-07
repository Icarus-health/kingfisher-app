"""Local EventKit worker mailbox and expiring, read-only calendar projection."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

from .calendar_memory import MAC_QUELLE, MAX_TERMINE_JE_ABSCHNITT, VERGANGENHEIT_TAGE, ZUKUNFT_TAGE, quelle_fuer_mac
from .connectors.calendar import CalendarError, Event
from .datumstext import iso_lesen_streng


def now():
    return datetime.now(timezone.utc)


# Python 3.10 liest Zulu-Zeit erst nach expliziter UTC-Normalisierung; `iso_lesen_streng` tut das.
_timestamp = iso_lesen_streng


class CalendarInfo(BaseModel):
    id: str = Field(min_length=1, max_length=1024)
    name: str = Field(max_length=1024)
    source: str = Field(default='', max_length=1024)


class Selection(BaseModel):
    ids: list[str] = Field(max_length=100)


class SnapshotEvent(BaseModel):
    uid: str = Field(min_length=1, max_length=8192)
    summary: str = Field(max_length=4096)
    start: datetime
    end: datetime
    all_day: bool = False
    location: str = Field(default='', max_length=4096)
    attendees: list[Annotated[str, Field(max_length=4096)]] = Field(default_factory=list, max_length=1000)
    source_id: str = Field(max_length=1024)
    source_label: str = Field(default='', max_length=1024)


class MemoryEvent(SnapshotEvent):
    """Ein Termin fürs Gedächtnis: wie fürs Anzeigen, dazu die Notiz."""
    notes: str = Field(default='', max_length=20000)


class MemoryUpdate(BaseModel):
    """Ein vollständig gelesener Abschnitt des Gedächtnisfensters (`calendar_memory.abschnitte`)."""
    generation: int
    range_from: datetime
    range_to: datetime
    events: list[MemoryEvent] = Field(max_length=MAX_TERMINE_JE_ABSCHNITT)


class WorkerUpdate(BaseModel):
    range_from: datetime | None = None
    range_to: datetime | None = None
    generation: int
    status: Literal['granted', 'not_determined', 'denied', 'restricted', 'write_only', 'unknown', 'error']
    calendars: list[CalendarInfo] = Field(default_factory=list, max_length=100)
    events: list[SnapshotEvent] | None = Field(default=None, max_length=10000)
    error: str = Field(default='', max_length=1000)


class MacCalendar:
    can_create = False

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO state VALUES (1, ?)', (json.dumps({
                'generation': 0, 'enabled': False, 'authorize': False, 'selected': [],
                'calendars': [], 'events': [], 'status': 'offline', 'seen_at': None,
                'synced_at': None, 'error': '',
            }),))
        path.chmod(0o600)

    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA secure_delete=ON")
        return db

    def read(self):
        with self.connection() as db:
            return json.loads(db.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])

    def cache_revision(self):
        """Jede Auswahl und jeder Adapter-Stand entwertet alte Suchergebnisse."""
        return self.read().get('cache_revision', 0)

    def change(self, action):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            state = json.loads(db.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
            action(state)
            state['cache_revision'] = state.get('cache_revision', 0) + 1
            db.execute('UPDATE state SET payload=? WHERE id=1', (json.dumps(state),))
        return self.public(state)

    def public(self, state=None):
        state = dict(state or self.read())
        state['event_count'] = len(state.pop('events'))
        # Wie weit der Arbeiter fürs Gedächtnis lesen soll; die Zahlen stehen nur in `calendar_memory`.
        state['memory_window'] = {'days_back': VERGANGENHEIT_TAGE, 'days_ahead': ZUKUNFT_TAGE}
        state['online'] = bool(state['seen_at'] and now() - _timestamp(state['seen_at']) < timedelta(seconds=30))
        return state

    def enable(self):
        def action(s):
            s.update(enabled=True, authorize=True, generation=s['generation'] + 1, error='')
        return self.change(action)

    def select(self, ids):
        def action(s):
            if not s['enabled'] or s['status'] != 'granted':
                raise HTTPException(409, 'Bitte zuerst den Mac-Kalender freigeben.')
            if not set(ids) <= {c['id'] for c in s['calendars']}:
                raise HTTPException(400, 'Ein ausgewählter Kalender ist nicht mehr verfügbar.')
            s.update(selected=list(dict.fromkeys(ids)), events=[], synced_at=None,
                     generation=s['generation'] + 1, error='')
        return self.change(action)

    def disconnect(self):
        def action(s):
            s.update(enabled=False, authorize=False, selected=[], calendars=[], events=[],
                     synced_at=None, error='', generation=s['generation'] + 1)
        return self.change(action)

    def update(self, body):
        def action(s):
            if body.generation != s['generation']:
                raise HTTPException(409, 'Veraltete Synchronisation verworfen.')
            s.update(seen_at=now().isoformat(), status=body.status, error=body.error)
            if not s['enabled']:
                return
            s['authorize'] = False
            s['calendars'] = [c.model_dump() for c in body.calendars]
            if body.status != 'granted' or body.error:
                s.update(events=[], synced_at=None)
                return
            if not set(s['selected']) <= {c.id for c in body.calendars}:
                s.update(events=[], synced_at=None, error='Ein ausgewählter Kalender fehlt. Bitte neu auswählen.')
                return
            if body.events is not None:
                for event in body.events:
                    if (event.source_id not in s['selected'] or event.start.tzinfo is None
                            or event.end.tzinfo is None or event.end < event.start):
                        raise HTTPException(400, 'Ungültige Termindaten.')
                s.update(events=[e.model_dump(mode='json') for e in body.events], synced_at=now().isoformat(),
                         range_from=body.range_from.isoformat() if body.range_from else None,
                         range_to=body.range_to.isoformat() if body.range_to else None)
        return self.change(action)

    def memory_events(self, body):
        """Prüft einen Gedächtnisabschnitt gegen Freigabe und Auswahl; gibt die Termine zurück.

        Gleiche Regeln wie `update`: Nur ein freigegebener, ausgewählter Kalender darf
        Termine liefern, und eine veraltete Generation wird verworfen.
        """
        state = self.read()
        if body.generation != state['generation']:
            raise HTTPException(409, 'Veraltete Synchronisation verworfen.')
        if not state['enabled'] or state['status'] != 'granted' or not state['selected']:
            raise HTTPException(409, 'Bitte zuerst den Mac-Kalender freigeben.')
        if body.range_to <= body.range_from or body.range_from.tzinfo is None or body.range_to.tzinfo is None:
            raise HTTPException(400, 'Ungültiger Zeitraum.')
        result = []
        for event in body.events:
            if (event.source_id not in state['selected'] or event.start.tzinfo is None
                    or event.end.tzinfo is None or event.end < event.start):
                raise HTTPException(400, 'Ungültige Termindaten.')
            result.append(Event(uid=event.uid, summary=event.summary, start=event.start, end=event.end,
                                location=event.location, attendees=list(event.attendees), all_day=event.all_day,
                                source_id=event.source_id, source_label=event.source_label, notes=event.notes))
        return result

    def freigegeben(self, quelle):
        """Ob eine Gedächtnisquelle (`mac-calendar/<Kurzhash>`) gerade freigegeben ist."""
        state = self.read()
        if not state['enabled'] or not state['selected']:
            return False
        return quelle in {quelle_fuer_mac(kalender) for kalender in state['selected']}

    def events(self, days=7, at=None):
        state = self.read()
        if not state['enabled'] or not state['selected']:
            return []
        if not state['synced_at'] or now() - _timestamp(state['synced_at']) > timedelta(minutes=5):
            raise CalendarError('Mac-Kalender ist nicht aktuell. Bitte den Mac-Adapter starten oder erneut synchronisieren.')
        start = at or now()
        end = start + timedelta(days=days)
        range_from, range_to = state.get('range_from'), state.get('range_to')
        has_complete_range = bool(range_from and range_to)
        outside_snapshot = has_complete_range and (
            _timestamp(range_from) > start or _timestamp(range_to) < end
        )
        if ((at is not None or days > 31) and not has_complete_range) or outside_snapshot:
            raise CalendarError('Kalendertermine für den angefragten Zeitraum werden noch synchronisiert. Bitte gleich erneut aktualisieren.')
        return [Event(**{**e, 'start': _timestamp(e['start']), 'end': _timestamp(e['end'])})
                for e in state['events'] if _timestamp(e['end']) > start and _timestamp(e['start']) < end]


def install_routes(app, guard, calendar, refresh, memory=None):
    """`memory`: `KalenderGedaechtnis` (oder None); ohne es bleibt der Adapter bei der Live-Anzeige."""
    prefix = '/api/v1/mac-calendar'

    def entziehen():
        # Abgewählt oder getrennt: Was nicht mehr freigegeben ist, verlässt das Gedächtnis.
        if memory is not None:
            memory.entziehen_ohne_freigabe(lambda quelle: not quelle.startswith(MAC_QUELLE) or calendar.freigegeben(quelle))

    @app.get(prefix, dependencies=guard)
    def state():
        return calendar.public()

    @app.post(prefix + '/connect', dependencies=guard)
    def connect():
        result = calendar.enable()
        refresh()
        return result

    @app.put(prefix + '/selection', dependencies=guard)
    def selection(body: Selection):
        result = calendar.select(body.ids)
        entziehen()
        return result

    @app.delete(prefix, dependencies=guard)
    def disconnect():
        result = calendar.disconnect()
        entziehen()
        refresh()
        return result

    @app.post(prefix + '/worker', dependencies=guard)
    def update(body: WorkerUpdate):
        return calendar.update(body)

    @app.post(prefix + '/memory', dependencies=guard)
    def memory_update(body: MemoryUpdate):
        """Ein Abschnitt fürs Gedächtnis. Ohne Gedächtnis (Test, Wiederherstellung) wird nichts abgelegt."""
        events = calendar.memory_events(body)
        if memory is None:
            return {'stored': False}
        from .calendar_memory import Abgleich
        summe = Abgleich()
        for kalender in dict.fromkeys(event.source_id for event in events):
            quelle = quelle_fuer_mac(kalender)
            eigene = [event for event in events if event.source_id == kalender]
            summe += memory.abgleichen(quelle, eigene[0].source_label or 'Mac-Kalender', eigene,
                                       body.range_from, body.range_to,
                                       erlaubt=lambda quelle=quelle: calendar.freigegeben(quelle))
        return {'stored': True, **summe.to_dict()}
