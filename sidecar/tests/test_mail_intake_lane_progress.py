"""Progress must compare one mailbox lane, not add live filters to history.

The reader replaces only IMAP. Intake, original storage, retry and the public
mailbox sentence all run normally against a temporary database.
"""
from datetime import datetime, timezone

import pytest

from icarus_memory.connectors.mail import Message
from icarus_memory.episodes import EpisodeStore
from icarus_memory.mail_filter import Decision
from icarus_memory.mail_intake import Intake
from icarus_memory.mail_stand import konto_stand


class Mailbox:
    def __init__(self, count):
        self.count = count
        self.failed = set()

    def inventory_page(self, folder, after_uid=0, before_uid=None, limit=200,
                       uidvalidity=None):
        assert folder == "INBOX"
        assert uidvalidity in (None, "7")
        upper = self.count if before_uid is None else min(before_uid, self.count)
        end = min(upper, after_uid + limit)
        return {"folder": folder, "uidvalidity": "7", "upper_uid": upper,
                "uids": list(range(after_uid + 1, end + 1)),
                "next_uid": end, "done": end >= upper}

    def message_in_folder(self, folder, uid):
        assert folder == "INBOX"
        if uid in self.failed:
            raise OSError("synthetic private server response")
        return Message(uid, f"Synthetic {uid}", "QA <qa@example.test>",
                       datetime(2026, 10, 8, tzinfo=timezone.utc), "", False,
                       body=f"Synthetic original {uid}")


@pytest.fixture
def intake(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    store = Intake(episodes)
    store.start("qa", ["INBOX"])
    yield store
    episodes.close()


def live_newsletters_with_open_history(intake):
    reader = Mailbox(10)
    intake.step("qa", reader, batch=2)
    # Six original history mails are stored; four history mails remain unread.
    # Four later incoming newsletters have been screened, never stored.
    def screen(message):
        return Decision(int(message.uid.split(".")[1]) <= 10, "newsletter")
    for _ in range(4):
        reader.count += 1
        intake.step("qa", reader, batch=2, screen=screen)
    return reader


def test_live_filters_do_not_fill_unread_history_progress(intake):
    live_newsletters_with_open_history(intake)
    folder = intake.status("qa")["folders"][0]
    assert (folder["total"], folder["captured"], folder["pending"]) == (10, 6, 4)
    assert sum(intake.episodes.counts().values()) == 6
    assert folder["filtered"] == 0
    assert folder["filtered_by"] == {}
    assert folder["live_filtered"] == 4
    assert folder["live_filtered_by"] == {"newsletter": 4}


def test_mailbox_sentence_does_not_report_current_with_unread_history(intake):
    live_newsletters_with_open_history(intake)
    state = intake.status("qa")
    assert state["folders"][0]["pending"] == 4
    sentence = konto_stand("QA", intake=state)
    assert sentence["zustand"] == "liest"


def test_live_filter_does_not_overflow_finished_history_denominator(intake):
    reader = Mailbox(1)
    intake.step("qa", reader, batch=2)
    reader.count = 2
    intake.step("qa", reader, batch=2,
                screen=lambda message: Decision(False, "newsletter"))
    folder = intake.status("qa")["folders"][0]
    assert (folder["total"], folder["captured"], folder["pending"]) == (1, 1, 0)
    assert folder["filtered"] == 0
    assert folder["filtered_by"] == {}
    assert folder["live_filtered"] == 1
    assert folder["live_filtered_by"] == {"newsletter": 1}
    assert sum(intake.episodes.counts().values()) == 1


def test_history_filters_still_count_towards_history_completion(intake):
    reader = Mailbox(1)
    intake.step("qa", reader, batch=2,
                screen=lambda message: Decision(False, "newsletter"))
    state = intake.status("qa")
    folder = state["folders"][0]
    assert (folder["total"], folder["captured"], folder["filtered"]) == (1, 0, 1)
    assert folder["filtered_by"] == {"newsletter": 1}
    assert sum(intake.episodes.counts().values()) == 0
    assert konto_stand("QA", intake=state)["zustand"] == "aktuell"


def test_retry_of_failed_live_mail_stays_unfinished_until_captured(intake):
    reader = Mailbox(1)
    intake.step("qa", reader, batch=2)
    reader.count = 2
    reader.failed = {"7.2"}
    intake.step("qa", reader, batch=2)
    failed = intake.status("qa")
    assert failed["folders"][0]["live_pending"] == 1
    assert sum(failed["folders"][0]["failed_by"].values()) == 1
    assert "synthetic private" not in str(failed)
    assert konto_stand("QA", intake=failed)["zustand"] == "gescheitert"

    intake.retry("qa")
    retrying = intake.status("qa")
    assert retrying["folders"][0]["live_pending"] == 1
    assert retrying["folders"][0]["failed_by"] == {}
    assert konto_stand("QA", intake=retrying)["zustand"] == "liest"

    reader.failed.clear()
    intake.step("qa", reader, batch=2)
    captured = intake.status("qa")
    assert captured["folders"][0]["live_pending"] == 0
    assert sum(intake.episodes.counts().values()) == 2
    assert konto_stand("QA", intake=captured)["zustand"] == "aktuell"


def test_retry_of_filtered_live_mail_does_not_claim_history_is_pending(intake):
    reader = Mailbox(1)
    intake.step("qa", reader, batch=2)
    reader.count = 2
    intake.step("qa", reader, batch=2,
                screen=lambda message: Decision(False, "newsletter"))
    intake.retry("qa")
    retrying = intake.status("qa")
    folder = retrying["folders"][0]
    assert (folder["total"], folder["captured"], folder["pending"],
            folder["live_pending"]) == (1, 1, 0, 1)
    assert konto_stand("QA", intake=retrying)["zustand"] == "liest"

    intake.step("qa", reader, batch=2, screen=lambda message: Decision(True))
    done = intake.status("qa")
    assert done["folders"][0]["live_pending"] == 0
    assert done["folders"][0]["filtered"] == 0
    assert done["folders"][0]["live_filtered"] == 0
    assert sum(intake.episodes.counts().values()) == 2
