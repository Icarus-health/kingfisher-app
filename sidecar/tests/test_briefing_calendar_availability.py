"""Calendar failures are incomplete coverage; the morning fallback spans a week."""
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory.connectors.calendar import CalendarError, Event
from icarus_memory.connectors.collections import CalendarCollection, NamedCalendar
from tests.test_context_identity import core  # noqa: F401
from tests.test_source_answers_http import _api
from tests.test_conversation_retraction import _close_app
from tests.test_terminvorbereitung import ANNA, ICH, _mail


class Reader:
    def __init__(self, *events):
        self.items = list(events)

    def events(self, **kwargs):
        return self.items


class Offline:
    def events(self, **kwargs):
        raise RuntimeError('synthetic private connector diagnostic')


@pytest.fixture
def api(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    model_calls = []
    def forbidden(*args, **kwargs):
        model_calls.append(True)
        raise AssertionError('Briefing must not call a model')
    monkeypatch.setattr(provider, 'complete', forbidden)
    app.state.settings.mail.user = 'lea@hartmann-beratung.example'
    try:
        yield app, client
        assert model_calls == []
    finally:
        client.close()
        _close_app(app)


@pytest.mark.parametrize('days, visible', [(3, True), (8, False)])
def test_morning_route_reads_the_documented_next_week_without_unbounded_events(api, days, visible):
    app, client = api
    starts = datetime.now(timezone.utc) + timedelta(days=days)
    event = Event('synthetic-next', 'Synthetischer nächster Termin', starts, starts + timedelta(hours=1))
    app.state.calendar = CalendarCollection([NamedCalendar('synthetic', 'Künstlicher Kalender', Reader(event))])
    response = client.get('/api/v1/morning-briefing', params={'post': 'false'})
    assert response.status_code == 200
    assert response.json()['later_today'] == []
    next_event = response.json()['naechster_termin']
    if visible:
        assert next_event is not None and next_event['title'] == event.summary
    else:
        assert next_event is None


def test_partial_calendar_failure_is_not_a_successfully_empty_day(api):
    app, client = api
    app.state.calendar = CalendarCollection([
        NamedCalendar('offline', 'Nicht erreichbar', Offline()),
        NamedCalendar('empty', 'Erreichbar und leer', Reader()),
    ])
    response = client.get('/api/v1/tag/briefing', params={'nachladen': 'true'})
    assert response.status_code == 200
    result = response.json()
    assert result['termine'] == [] and 'termine' in result['fehler']
    assert result['tageslage']['einleitung'] != 'Heute liegt nichts an, das ich vorbereiten müsste.'
    assert 'private connector diagnostic' not in response.text


def test_partial_failure_keeps_healthy_events_and_local_deadlines(api):
    app, client = api
    starts = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=12, minute=0)
    event = Event('healthy', 'Erreichbarer Termin', starts, starts + timedelta(hours=1))
    source = _mail(app, 'Lokale Frist', [(f'Bitte schick mir die Druckdaten bis zum {starts:%d.%m.%Y}.', 'request')], [ANNA, ICH])
    app.state.calendar = CalendarCollection([
        NamedCalendar('offline', 'Nicht erreichbar', Offline()),
        NamedCalendar('healthy', 'Erreichbar', Reader(event)),
    ])
    response = client.get('/api/v1/tag/briefing', params={'nachladen': 'true'})
    assert response.status_code == 200
    result = response.json()
    assert 'termine' in result['fehler']
    assert any(item['titel'] == event.summary for item in result['termine'])
    assert any(item['episode_id'] == source.id for item in result['fristen'])


def test_error_metadata_belongs_to_the_current_read_not_shared_last_errors(api):
    app, client = api
    class RequestScopedCalendar(Reader):
        last_errors = {}
        def display_events(self, **kwargs):
            # Another read could reset the compatibility field before this
            # response is composed; its returned metadata remains authoritative.
            self.last_errors = {}
            return [], {'offline': 'synthetic failure'}, 'synthetic-context'
    app.state.calendar = RequestScopedCalendar()
    response = client.get('/api/v1/tag/briefing', params={'nachladen': 'true'})
    assert response.status_code == 200
    assert 'termine' in response.json()['fehler']


def test_successfully_empty_calendar_still_has_a_quiet_empty_state(api):
    app, client = api
    app.state.calendar = CalendarCollection([NamedCalendar('empty', 'Leer', Reader())])
    response = client.get('/api/v1/tag/briefing', params={'nachladen': 'true'})
    assert response.status_code == 200
    assert response.json()['fehler'] == {}
    assert response.json()['tageslage']['einleitung'] == 'Heute liegt nichts an, das ich vorbereiten müsste.'


def test_notification_calendar_reader_keeps_full_failure_semantics(api):
    from icarus_memory.tag_routes import termine
    app, _ = api
    app.state.calendar = CalendarCollection([NamedCalendar('offline', 'Offline', Offline())])
    with pytest.raises(CalendarError):
        termine(app, datetime.now(timezone.utc))
