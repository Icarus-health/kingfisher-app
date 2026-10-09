#!/usr/bin/env python3
"""Synthetic API smoke for mail-task source-version binding."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import warnings


def build_case(data_dir: Path):
    # Set the isolated directory before importing/constructing the application.
    os.environ["ICARUS_DATA_DIR"] = str(data_dir)

    warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient` is deprecated.*")
    from fastapi.testclient import TestClient
    from icarus_memory import MemoryBackend, SelfModelStore
    from icarus_memory.agent import Agent
    from icarus_memory.connectors.collections import MailCollection, NamedMail
    from icarus_memory.connectors.mail import Message
    from icarus_memory.policy import Policy
    from icarus_memory.server import _mail_sink, create_app
    from icarus_memory.tools import build_registry

    class Mailbox:
        def __init__(self):
            self.item = Message(
                uid="1",
                subject="Synthetic source check",
                sender="sender@example.invalid",
                date=datetime(2026, 10, 9, 8, 0, tzinfo=timezone.utc),
                preview="Synthetic preview.",
                unread=True,
                body="Synthetic original request.",
                message_id="<smoke@example.invalid>",
                reply_to="sender@example.invalid",
            )

        def inbox(self, **_kwargs):
            return [self.item]

        def message(self, uid):
            if uid != "1":
                raise RuntimeError("synthetic UID missing")
            return self.item

        def send(self, *_args, **_kwargs):
            raise AssertionError("smoke must never send mail")

    store = SelfModelStore(MemoryBackend(), subject_id="synthetic-smoke")
    app = create_app(store)
    mailbox = Mailbox()
    app.state.mail = MailCollection([
        NamedMail("work", "Synthetic", mailbox, True, "owner@example.invalid")
    ])
    app.state.agent = Agent(
        store=app.state.store,
        policy=Policy(),
        audit=app.state.audit,
        tools=build_registry(app.state.store, mail=app.state.mail, outward_sink=_mail_sink(app)),
    )
    return app, mailbox, TestClient(app)


def assert_counts(app, tasks: int, episodes: int):
    assert len(app.state.tasks.all_tasks()) == tasks
    assert len(app.state.episodes.all_episodes()) == episodes


def main():
    results = []
    with tempfile.TemporaryDirectory(prefix="kingfisher-mail-task-smoke-") as raw_dir:
        root = Path(raw_dir)
        for case, change in (
            ("body", lambda item: replace(item, body="Synthetic request withdrawn.")),
            ("date", lambda item: replace(item, date=datetime(2015, 1, 1, tzinfo=timezone.utc))),
            ("truncated", lambda item: replace(item, truncated=True)),
        ):
            case_dir = root / case
            case_dir.mkdir()
            app, mailbox, client = build_case(case_dir)
            opened = client.get("/api/v1/messages/work:1")
            assert opened.status_code == 200
            digest = opened.json()["source_digest"]
            mailbox.item = change(mailbox.item)
            response = client.post("/api/v1/messages/work:1/task", json={
                "title": "Synthetic manually entered task",
                "due": "2026-10-12T12:00:00+02:00",
                "source_digest": digest,
            })
            assert response.status_code == 409, f"{case} returned {response.status_code}"
            assert_counts(app, tasks=0, episodes=0)
            results.append({"case": case, "http_status": response.status_code,
                            "tasks": 0, "episodes": 0})

        fresh_dir = root / "fresh"
        fresh_dir.mkdir()
        app, mailbox, client = build_case(fresh_dir)
        opened = client.get("/api/v1/messages/work:1")
        assert opened.status_code == 200
        original_body = mailbox.item.body
        response = client.post("/api/v1/messages/work:1/task", json={
            "title": "Synthetic manually entered task",
            "source_digest": opened.json()["source_digest"],
        })
        assert response.status_code == 201, f"fresh request returned {response.status_code}"
        task = response.json()
        source_ref = task["provenance"]["source_ref"]
        assert source_ref.startswith("episode:")
        episode = app.state.episodes.get(source_ref.removeprefix("episode:"))
        assert episode is not None and episode.body == original_body
        assert_counts(app, tasks=1, episodes=1)
        results.append({"case": "fresh", "http_status": response.status_code,
                        "tasks": 1, "episodes": 1, "source_verified": True})

    print(json.dumps({"result": "pass", "cases": results}, sort_keys=True))


if __name__ == "__main__":
    main()
