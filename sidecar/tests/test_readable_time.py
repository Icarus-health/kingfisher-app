"""Zeitangaben in Antworten sind lesbar und stehen in der Zeitzone des Nutzers."""
from datetime import datetime, timedelta, timezone

from icarus_memory.model import readable_time
from tests.test_context_identity import core
from tests.test_conversation_retraction import _close_app
from tests.test_source_answers_http import _api, _ask, _conversation
from tests.test_working_memory_flow import classifier, run_working


def test_utc_source_is_shown_in_berlin_time(monkeypatch):
    monkeypatch.delenv('KINGFISHER_TIMEZONE', raising=False)
    # Sommerzeit: UTC+2. Der Container läuft in UTC, der Nutzer nicht.
    assert readable_time(datetime(2026, 9, 23, 13, 38, 1, tzinfo=timezone.utc)) == '23.09.2026, 15:38 Uhr'
    # Winterzeit: UTC+1.
    assert readable_time('2026-12-01T08:05:00+00:00') == '01.12.2026, 09:05 Uhr'
    # Eine Mail aus einer anderen Zone wird ebenfalls umgerechnet.
    assert readable_time(datetime(2026, 9, 23, 9, 0, tzinfo=timezone(timedelta(hours=-4)))) == '23.09.2026, 15:00 Uhr'


def test_unknown_time_and_configured_zone(monkeypatch):
    assert readable_time(None) == 'unbekannt'
    monkeypatch.setenv('KINGFISHER_TIMEZONE', 'Europe/Lisbon')
    assert readable_time('2026-09-23T13:38:00+00:00') == '23.09.2026, 14:38 Uhr'


def test_missing_zone_database_shows_offset_instead_of_a_wrong_time(monkeypatch):
    monkeypatch.setenv('KINGFISHER_TIMEZONE', 'Nirgendwo/Unbekannt')
    assert readable_time('2026-09-23T13:38:00+00:00') == '23.09.2026, 13:38 Uhr (UTC+00:00)'
    assert readable_time('2026-09-23T15:38:00+02:00') == '23.09.2026, 15:38 Uhr (UTC+02:00)'


def test_conversation_source_time_is_readable_in_answers(core, tmp_path, monkeypatch):
    monkeypatch.delenv('KINGFISHER_TIMEZONE', raising=False)
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    try:
        conversation = _conversation(client)
        client.post(f'/api/v1/conversations/{conversation}/messages',
                    json={'message': 'Für den Gusstest bitte erst nach 11 Uhr anrufen.', 'answer_mode': 'chat'})
        run_working(app)
        answer = _ask(client, _conversation(client), 'Wann kann man mich wegen des Gusstests anrufen?')
        line = next(line for line in answer['content'].splitlines() if line.startswith('Quellenzeit:'))
        assert line.endswith(' Uhr') and 'T' not in line.removeprefix('Quellenzeit: ')
        datetime.strptime(line.removeprefix('Quellenzeit: '), '%d.%m.%Y, %H:%M Uhr')
    finally:
        client.close()
        _close_app(app)


def test_mail_draft_wording(monkeypatch):
    monkeypatch.delenv('KINGFISHER_TIMEZONE', raising=False)
    assert readable_time('2026-09-20T14:00:00+00:00', joiner=' um ') == '20.09.2026 um 16:00 Uhr'


def test_model_clock_tool_reports_user_time_not_container_utc(monkeypatch):
    # Der Container läuft in UTC; „Wie spät ist es?“ muss die Zeit des Nutzers nennen.
    from icarus_memory import tools
    monkeypatch.delenv('KINGFISHER_TIMEZONE', raising=False)

    class Fixed(datetime):
        @classmethod
        def now(cls, tz=None):
            moment = datetime(2026, 9, 23, 13, 38, tzinfo=timezone.utc)
            return moment.astimezone(tz) if tz else moment.replace(tzinfo=None)
    monkeypatch.setattr(tools, 'datetime', Fixed)
    assert '23.09.2026, 15:38' in tools._now()
