"""Der Gesprächskalender bleibt an die aktuell verbundene Quelle gebunden."""
from datetime import datetime, timedelta, timezone
from threading import Event as Signal

from fastapi import FastAPI

from icarus_memory.connectors.calendar import Event
from icarus_memory.connectors.collections import CalendarCollection, NamedCalendar
from icarus_memory.mac_calendar import MacCalendar, WorkerUpdate
from icarus_memory.agent_verdrahtung import _search_calendar


class Calendar:
    def __init__(self, uid, *, enter=None, release=None):
        self.uid, self.enter, self.release = uid, enter, release
        self.calls = 0

    def events(self, *, days, at):
        self.calls += 1
        if self.enter:
            self.enter.set()
            assert self.release.wait(5)
        return [Event(uid=self.uid, summary=self.uid, start=datetime.now(timezone.utc),
                      end=datetime.now(timezone.utc) + timedelta(hours=1))]


def test_withdrawal_and_replacement_do_not_reuse_cached_events():
    app = FastAPI()
    app.state.calendar = Calendar('first')
    read = _search_calendar(app)
    assert [event['uid'] for event in read()] == ['first']
    app.state.calendar = None
    assert read() == []
    app.state.calendar = Calendar('second')
    assert [event['uid'] for event in read()] == ['second']


def test_retired_worker_cannot_publish_after_source_changes(monkeypatch):
    from icarus_memory import agent_verdrahtung as server
    monkeypatch.setattr(server, 'TERMINE_WARTEN', 0.01)
    app = FastAPI()
    entered, release = Signal(), Signal()
    app.state.calendar = Calendar('old', enter=entered, release=release)
    read = _search_calendar(app)
    assert read() is None
    assert entered.wait(2)
    app.state.calendar = Calendar('new')
    assert [event['uid'] for event in read()] == ['new']
    release.set()
    assert [event['uid'] for event in read()] == ['new']


def test_rebuild_generation_retires_cached_events_with_same_calendar():
    app = FastAPI()
    calendar = Calendar('same')
    app.state.calendar = calendar
    app.state._calendar_search_generation = 1
    read = _search_calendar(app)
    assert read()
    app.state._calendar_search_generation = 2
    assert [event['uid'] for event in read()] == ['same']
    assert calendar.calls == 2


def _mac_ready(tmp_path, calendar_type=MacCalendar):
    mac = calendar_type(tmp_path / 'calendar.sqlite3')
    state = mac.enable()
    calendars = [{'id': 'private', 'name': 'Privat'}]
    mac.update(WorkerUpdate(generation=state['generation'], status='granted', calendars=calendars))
    state = mac.select(['private'])
    at = datetime.now(timezone.utc) + timedelta(days=1)
    mac.update(WorkerUpdate(generation=state['generation'], status='granted', calendars=calendars,
                            range_from=at.replace(month=1, day=1),
                            range_to=at.replace(month=12, day=31),
                            events=[{'uid': 'secret', 'summary': 'Private Diagnose',
                                     'start': at, 'end': at + timedelta(hours=1),
                                     'source_id': 'private'}]))
    return mac, state, calendars


def test_same_mac_calendar_selection_and_worker_denial_retire_cached_events(tmp_path):
    mac, state, calendars = _mac_ready(tmp_path)
    app = FastAPI()
    app.state.calendar = CalendarCollection([NamedCalendar('mac-calendar', 'Mac', mac)])
    read = _search_calendar(app)
    assert [row['uid'] for row in read()] == ['mac-calendar:secret']
    mac.select([])
    assert read() == []
    state = mac.select(['private'])
    mac.update(WorkerUpdate(generation=state['generation'], status='granted', calendars=calendars,
                            events=[{'uid': 'new', 'summary': 'Neuer Termin',
                                     'start': datetime.now(timezone.utc) + timedelta(days=1),
                                     'end': datetime.now(timezone.utc) + timedelta(days=1, hours=1),
                                     'source_id': 'private'}]))
    # Ohne bestätigtes Jahresfenster kann die Sammlung einen Fehler melden;
    # entscheidend ist, dass die alte Diagnose nicht wieder erscheint.
    assert all(row['uid'] != 'mac-calendar:secret' for row in (read() or []))
    mac.update(WorkerUpdate(generation=state['generation'], status='denied'))
    assert all(row['uid'] != 'mac-calendar:secret' for row in (read() or []))


def test_inflight_mac_worker_cannot_publish_after_selection_withdrawal(tmp_path, monkeypatch):
    from icarus_memory import agent_verdrahtung as server
    monkeypatch.setattr(server, 'TERMINE_WARTEN', 0.01)
    entered, release = Signal(), Signal()
    class SlowMac(MacCalendar):
        def events(self, *, days, at):
            events = super().events(days=days, at=at)
            entered.set()
            assert release.wait(5)
            return events
    mac, _, _ = _mac_ready(tmp_path, SlowMac)
    app = FastAPI()
    app.state.calendar = CalendarCollection([NamedCalendar('mac-calendar', 'Mac', mac)])
    read = _search_calendar(app)
    assert read() is None
    assert entered.wait(2)
    mac.select([])
    release.set()
    assert read() == []
