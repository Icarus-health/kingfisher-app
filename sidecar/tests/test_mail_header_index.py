"""Exact-thread retrieval must remain useful in a large synthetic mail archive."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import json

from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.mail_timeline import thread_tags
from icarus_memory.model import Provenance, SourceType
from icarus_memory.task_source_review import review_tasks


def record(store, mid, refs=(), *, captured=None):
    captured = captured or datetime.now(timezone.utc)
    return store.record(
        EpisodeKind.MESSAGE, "Synthetic", "Synthetic " + mid,
        Provenance(SourceType.EMAIL, source_ref="synthetic:" + mid),
        at=captured, occurred_at=captured,
        tags=thread_tags(SimpleNamespace(account_id="synthetic", message_id=mid,
                                        references=refs, in_reply_to="")),
    )[0]


def test_exact_followup_is_found_among_fifty_thousand_unrelated_mails(tmp_path):
    store = EpisodeStore(tmp_path / "episodes.sqlite3")
    now = datetime.now(timezone.utc)
    source = record(store, "<source@scale>", captured=now - timedelta(hours=2))
    reply = record(store, "<reply@scale>", ("<source@scale>",), captured=now)
    assert source.id != reply.id
    doc = source.to_dict()
    rows = []
    for i in range(50000):
        other = {**doc, "id": f"unrelated-{i}", "digest": f"unrelated-digest-{i}",
                 "tags": [f"mail:message:unrelated-{i}"]}
        rows.append((other["id"], other["digest"], other["kind"], other["state"],
                     other["recorded_at"], other["occurred_at"], other["title"],
                     other["body"], json.dumps(other)))
    with store._conn:
        store._conn.executemany(
            "INSERT INTO episodes(id,digest,kind,state,recorded_at,occurred_at,title,body,document) "
            "VALUES (?,?,?,?,?,?,?,?,?)", rows)
    task = SimpleNamespace(id="confirmed-task", status="open", created_at=now - timedelta(hours=1),
                           provenance=Provenance(SourceType.USER_STATED, source_ref="episode:" + source.id))
    result = review_tasks(store, [task])
    assert result.by_task[task.id]["followup_episode_id"] == reply.id
    assert result.coverage_limited is False
    store._conn.close()


def test_v21_backfill_preserves_original_rows_and_deduplication(tmp_path):
    import sqlite3
    from icarus_memory.episodes import _MIGRATIONS
    from icarus_memory.migrations import run_migrations
    fixture = EpisodeStore(tmp_path / "fixture.sqlite3")
    source = record(fixture, "<old@local>")
    row = dict(fixture._conn.execute("SELECT * FROM episodes WHERE id=?", (source.id,)).fetchone())
    fixture.close()
    path = tmp_path / "v21.sqlite3"
    conn = sqlite3.connect(path)
    run_migrations(conn, store="episodes", path=path, migrations=_MIGRATIONS[:21])
    fields = list(row)
    conn.execute(f"INSERT INTO episodes({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})", tuple(row.values()))
    conn.commit()
    before = conn.execute("SELECT * FROM episodes").fetchall()
    conn.close()
    store = EpisodeStore(path)
    assert store._conn.execute("PRAGMA user_version").fetchone()[0] == 25
    assert [tuple(row) for row in store._conn.execute("SELECT * FROM episodes")] == before
    assert [tuple(row) for row in store._conn.execute("SELECT value,episode_id FROM episode_mail_headers")] == [(source.tags[0], source.id)]
    assert record(store, "<old@local>").id == source.id
    store.close()


def test_header_changes_and_rollback_keep_projection_atomic(tmp_path):
    store = EpisodeStore(tmp_path / "episodes.sqlite3")
    source = record(store, "<one@local>")
    document = source.to_dict()
    def headers():
        return [row[0] for row in store._conn.execute("SELECT value FROM episode_mail_headers WHERE episode_id=? ORDER BY value", (source.id,))]
    before = headers()
    try:
        with store.transaction():
            store._conn.execute("UPDATE episodes SET document=? WHERE id=?", (json.dumps({**document, "tags": ["mail:reply:temporary"]}), source.id))
            assert headers() == ["mail:reply:temporary"]
            raise RuntimeError("synthetic rollback")
    except RuntimeError:
        pass
    assert headers() == before
    with store.transaction():
        store._conn.execute("UPDATE episodes SET document=? WHERE id=?", (json.dumps({**document, "tags": ["mail:reply:changed", "mail:reply:changed", 123]}), source.id))
    assert headers() == ["mail:reply:changed"]
    assert store.get(source.id).body == source.body
    with store.transaction():
        store._conn.execute("DELETE FROM episodes WHERE id=?", (source.id,))
    assert headers() == []
    store.close()


def test_nonmail_and_document_sources_are_not_header_candidates(tmp_path):
    store = EpisodeStore(tmp_path / "episodes.sqlite3")
    for kind, origin in ((EpisodeKind.MESSAGE, SourceType.CHAT), (EpisodeKind.DOCUMENT, SourceType.EMAIL)):
        store.record(kind, "Synthetic", f"Synthetic {kind.value} {origin.value}", Provenance(origin), tags=["mail:message:test", "mail:reply:test"])
    assert store._conn.execute("SELECT count(*) FROM episode_mail_headers").fetchone()[0] == 0
    store.close()


def test_missing_header_trigger_is_rejected_without_rewriting_original(tmp_path):
    import sqlite3
    import pytest
    from icarus_memory.migrations import MigrationError
    path = tmp_path / "episodes.sqlite3"
    store = EpisodeStore(path)
    source = record(store, "<one@local>")
    with store._conn:
        store._conn.execute("DROP TRIGGER trg_mail_headers_update")
    before = store._conn.execute("SELECT document FROM episodes WHERE id=?", (source.id,)).fetchone()[0]
    store.close()
    with pytest.raises(MigrationError):
        EpisodeStore(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT document FROM episodes WHERE id=?", (source.id,)).fetchone()[0] == before
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 25


def test_interrupted_v22_backfill_rolls_back_before_successful_retry(tmp_path, monkeypatch):
    import sqlite3
    import pytest
    from icarus_memory import mail_header_index
    from icarus_memory.episodes import _MIGRATIONS
    from icarus_memory.migrations import MigrationError, run_migrations
    path = tmp_path / "v21.sqlite3"
    fixture = EpisodeStore(tmp_path / "fixture.sqlite3")
    source = record(fixture, "<rollback@local>")
    row = dict(fixture._conn.execute("SELECT * FROM episodes WHERE id=?", (source.id,)).fetchone())
    fixture.close()
    conn = sqlite3.connect(path)
    run_migrations(conn, store="episodes", path=path, migrations=_MIGRATIONS[:21])
    conn.execute(f"INSERT INTO episodes({','.join(row)}) VALUES ({','.join('?' for _ in row)})", tuple(row.values()))
    conn.commit(); before = conn.execute("SELECT * FROM episodes").fetchall(); conn.close()
    actual_migrate = mail_header_index.migrate
    def interrupted(connection):
        actual_migrate(connection)
        raise RuntimeError("synthetic interruption after backfill")
    with monkeypatch.context() as patch:
        patch.setattr(mail_header_index, "migrate", interrupted)
        with pytest.raises(MigrationError):
            EpisodeStore(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 21
        assert conn.execute("SELECT name FROM sqlite_schema WHERE name='episode_mail_headers'").fetchall() == []
        assert conn.execute("SELECT * FROM episodes").fetchall() == before
    retried = EpisodeStore(path)
    assert retried._conn.execute("PRAGMA user_version").fetchone()[0] == 25
    assert retried._conn.execute("SELECT episode_id FROM episode_mail_headers").fetchone()[0] == source.id
    assert [tuple(row) for row in retried._conn.execute("SELECT * FROM episodes")] == before
    retried.close()
