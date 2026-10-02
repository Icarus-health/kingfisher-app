"""Mehrkonto- und Mehrkalender-Grundlage ohne echte persönliche Zugänge."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.audit import AuditLog
from icarus_memory.connectors.calendar import Event
from icarus_memory.connectors.collections import (
    CalendarCollection,
    MailCollection,
    NamedCalendar,
    NamedMail,
)
from icarus_memory.connectors.mail import MailError, Message
from icarus_memory.connectors.mail import MailConnector
from icarus_memory.episodes import EpisodeStore
from icarus_memory.server import create_app
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    app = create_app(
        SelfModelStore(MemoryBackend(), subject_id="test"),
        audit=AuditLog(tmp_path / "audit.sqlite3"),
        tasks=TaskStore(tmp_path / "tasks.sqlite3"),
        workspace=WorkspaceStore(tmp_path / "workspace.sqlite3"),
        episodes=EpisodeStore(tmp_path / "episodes.sqlite3"),
    )
    return TestClient(app)


def test_drei_mailkonten_sind_getrennt_vorbereitbar(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    for label, address in (
        ("Google privat", "privat@example.com"),
        ("Google Arbeit", "arbeit@example.com"),
        ("All-INKL", "post@example.org"),
    ):
        response = client.post("/api/v1/integrations/mail", json={
            "label": label,
            "imap_host": "imap.example.test",
            "user": address,
        })
        assert response.status_code == 201

    accounts = client.get("/api/v1/integrations").json()["mail_accounts"]
    assert [account["label"] for account in accounts] == [
        "Google privat", "Google Arbeit", "All-INKL",
    ]
    assert all(account["secret_present"] is False for account in accounts)
    assert all("password" not in account for account in accounts)


def test_mail_passwort_bleibt_im_schluesselspeicher_und_kommt_nicht_zurueck(
    tmp_path, monkeypatch
) -> None:
    # Mit Passwort wird vorher angemeldet (test_mail_anmeldung.py); hier gelingt die Anmeldung ohne Netz.
    monkeypatch.setattr(MailConnector, "pruefe_anmeldung", lambda self, timeout=8.0: None)
    response = _client(tmp_path, monkeypatch).post("/api/v1/integrations/mail", json={
        "label": "Privat",
        "imap_host": "imap.example.test",
        "user": "privat@example.com",
        "password": "nur-fuer-den-test",
    })
    assert response.status_code == 201
    account = response.json()["mail_accounts"][0]
    assert account["secret_present"] is True
    assert "password" not in account
    assert "nur-fuer-den-test" not in str(response.json())


def test_mailanbieter_hilfe_enthält_keine_gespeicherten_zugänge(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.get("/api/v1/integrations/mail-providers")
    assert response.status_code == 200
    providers = response.json()["providers"]
    gmail = next(item for item in providers if item["id"] == "gmail")
    assert gmail["imap_host"] == "imap.gmail.com"
    assert gmail["app_password"] is True
    assert "password" not in gmail


def test_https_ical_abo_ist_ohne_passwort_lesbar_konfigurierbar(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.post("/api/v1/integrations/calendar", json={
        "label": "Feiertage",
        "kind": "ical",
        "url": "https://calendar.example.test/holidays.ics",
    })
    assert response.status_code == 201
    source = response.json()["calendar_sources"][0]
    assert source["kind"] == "ical"
    assert source["secret_present"] is False


def test_eine_einzelne_lokale_quelle_laesst_sich_wieder_entziehen(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    created = client.post("/api/v1/integrations/calendar", json={
        "label": "Feiertage",
        "kind": "ical",
        "url": "https://calendar.example.test/holidays.ics",
    }).json()
    source_id = created["calendar_sources"][0]["id"]

    removed = client.delete(f"/api/v1/integrations/calendar/{source_id}")
    assert removed.status_code == 200
    assert removed.json()["calendar_sources"] == []


def test_ical_abo_akzeptiert_keine_unsichere_http_adresse(tmp_path, monkeypatch) -> None:
    response = _client(tmp_path, monkeypatch).post("/api/v1/integrations/calendar", json={
        "label": "Unsicher",
        "kind": "ical",
        "url": "http://calendar.example.test/feed.ics",
    })
    assert response.status_code == 400


class _Mail:
    def __init__(self, uid: str, when: datetime) -> None:
        self.uid, self.when = uid, when

    def inbox(self, **_: object) -> list[Message]:
        return [Message(self.uid, "Betreff", "Absender", self.when, "Vorschau", True)]

    def message(self, uid: str) -> Message:
        return Message(uid, "Betreff", "Absender", self.when, "Vorschau", True)


class _Calendar:
    def __init__(self, uid: str) -> None:
        self.uid = uid

    def events(self, **_: object) -> list[Event]:
        return [Event(self.uid, "Termin", datetime(2026, 9, 4, 10, tzinfo=timezone.utc), None)]


def test_mehrkonten_geben_stabile_qualifizierte_ids_aus() -> None:
    now = datetime(2026, 9, 4, 10, tzinfo=timezone.utc)
    mails = MailCollection([
        NamedMail("mail-a", "A", _Mail("7", now)),
        NamedMail("mail-b", "B", _Mail("7", now)),
    ])
    assert {message.uid for message in mails.inbox()} == {"mail-a:7", "mail-b:7"}
    assert mails.can_send is False
    try:
        mails.send("a", "b", "c")
    except MailError as exc:
        assert "ausdrücklich" in str(exc)
    else:
        raise AssertionError("Mehrkonto-Versand darf keinen stillen Absender wählen.")

    calendars = CalendarCollection([
        NamedCalendar("cal-a", "A", _Calendar("7")),
        NamedCalendar("cal-b", "B", _Calendar("7")),
    ])
    assert {event.uid for event in calendars.events()} == {"cal-a:7", "cal-b:7"}
    assert calendars.can_create is False


def test_mail_date_without_local_zone_does_not_break_combined_inbox() -> None:
    # RFC mail dates with -0000 denote UTC without a known original local zone.
    dates = [MailConnector._parse_date(value) for value in (
        'Wed, 09 Sep 2026 10:00:00 -0000',
        'Wed, 09 Sep 2026 11:00:00 +0200',
        'Wed, 09 Sep 2026 10:30:00',
    )]
    mails = MailCollection([
        NamedMail(str(index), str(index), _Mail('7', date))
        for index, date in enumerate(dates)
    ])
    assert [message.account_id for message in mails.inbox()] == ['2', '0', '1']
    assert dates[0].utcoffset().total_seconds() == 0
    assert dates[1].utcoffset().total_seconds() == 7200
    assert MailConnector._parse_date('not a date') is None
