"""Safe, source-current diagnostics for failed category suggestions."""
from __future__ import annotations

import json
import sqlite3

import pytest

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.providers import ProviderError, Reply


class Provider:
    is_local = True
    entity_anchor_mode = "block_quote"
    name = "local-category-fixture"
    model = "fixture-v1"

    def __init__(self, result=None, error=None):
        self.result = result or {"categories": [], "entities": []}
        self.error = error
        self.calls = 0

    def complete_json(self, messages, *, max_tokens, schema):
        self.calls += 1
        if self.error:
            raise self.error
        return Reply(text=json.dumps(self.result))


def make(tmp_path, body="Anna prüft die Projektunterlagen.", *, source_key=""):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    item, created = episodes.record(EpisodeKind.MESSAGE, "Quelle", body,
        Provenance(SourceType.CHAT, source_ref="category-diagnostic-test"), source_key=source_key)
    assert created
    if source_key:
        episodes.advance_source_head(source_key, None, item.id)
    from icarus_memory.memory_categories import Categories
    return episodes, Categories(episodes), item


def test_validation_failure_persists_only_closed_reason_code(tmp_path):
    episodes, categories, item = make(tmp_path)
    provider = Provider({"categories": [{"category_id": "made-up", "block_id": "B1"}], "entities": []})

    result = categories.run(provider)

    assert result.ok is False
    stored = episodes._conn.execute(
        "SELECT status,failure_code FROM memory_category_sources WHERE episode_id=?", (item.id,)).fetchone()
    assert tuple(stored) == ("failed", "validation_category_evidence")
    projected = categories.list_for(item.id)
    assert projected["failure_code"] == "validation_category_evidence"
    assert "made-up" not in str(projected)
    assert "Unbelegte Kategorie" not in str(projected)
    with pytest.raises(sqlite3.IntegrityError):
        with episodes.transaction():
            episodes._conn.execute(
                "UPDATE memory_category_sources SET failure_code='provider said secret' WHERE episode_id=?",
                (item.id,))


def test_source_category_http_projection_includes_safe_reason(tmp_path, monkeypatch):
    import threading
    from types import SimpleNamespace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from icarus_memory.mail_intake_routes import register

    episodes, categories, item = make(tmp_path)
    categories.run(Provider(error=ProviderError("private HTTP provider detail")))
    app = FastAPI()
    app.state.episodes = episodes
    app.state.settings = SimpleNamespace(mail_accounts=[], schedule=SimpleNamespace(mail_accounts=[], enabled=False))
    app.state.mail = SimpleNamespace(reader_for=lambda _account: None)
    app.state.conversation_lock = threading.RLock()
    monkeypatch.setattr("icarus_memory.mail_intake_routes.config.save", lambda *args: None)
    register(app, [], lambda: tmp_path, lambda _app: None)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/episodes/{item.id}/categories")

    assert response.status_code == 200
    assert response.json()["failure_code"] == "provider_error"
    assert "private" not in response.text


@pytest.mark.parametrize(("error", "expected"), [
    (ProviderError("private provider detail"), "provider_error"),
    (RuntimeError("private traceback detail"), "internal_error"),
])
def test_provider_and_internal_failures_are_sanitized(tmp_path, error, expected):
    episodes, categories, item = make(tmp_path)

    categories.run(Provider(error=error))

    row = episodes._conn.execute(
        "SELECT failure_code FROM memory_category_sources WHERE episode_id=?", (item.id,)).fetchone()
    assert row[0] == expected
    assert expected in str(categories.list_for(item.id))
    assert "private" not in str(categories.list_for(item.id))


def test_success_clears_failure_code_and_source_edit_hides_stale_code(tmp_path):
    episodes, categories, item = make(tmp_path, source_key="diagnostic-source")
    invalid = Provider({"categories": [{"category_id": "made-up", "block_id": "B1"}], "entities": []})
    categories.run(invalid)
    assert categories.list_for(item.id)["failure_code"] == "validation_category_evidence"

    with episodes.transaction():
        episodes._conn.execute("UPDATE memory_category_sources SET retry_after=0 WHERE episode_id=?", (item.id,))
    assert categories.run(Provider()).ok
    row = episodes._conn.execute(
        "SELECT status,failure_code FROM memory_category_sources WHERE episode_id=?", (item.id,)).fetchone()
    assert tuple(row) == ("complete", None)

    invalid = Provider({"categories": [{"category_id": "made-up", "block_id": "B1"}], "entities": []})
    categories.request_recheck([item.id])
    categories.run(invalid)
    assert categories.list_for(item.id)["failure_code"] == "validation_category_evidence"
    replacement, created = episodes.record(EpisodeKind.MESSAGE, "Quelle", "Eine neue Fassung.",
        Provenance(SourceType.CHAT, source_ref="category-diagnostic-test"), source_key="diagnostic-source")
    assert created
    episodes.advance_source_head("diagnostic-source", item.id, replacement.id)
    projection = categories.list_for(item.id)
    assert projection["status"] == "excluded"
    assert projection.get("failure_code") is None
    assert categories.list_for(replacement.id).get("failure_code") is None


def test_support_generation_change_hides_failure_diagnostic(tmp_path):
    episodes, categories, item = make(tmp_path)
    categories.run(Provider({"categories": [{"category_id": "made-up", "block_id": "B1"}], "entities": []}))
    assert categories.list_for(item.id)["failure_code"] == "validation_category_evidence"

    with episodes.transaction():
        episodes._conn.execute("UPDATE episodes SET support_generation=support_generation+1 WHERE id=?", (item.id,))
    assert categories.list_for(item.id).get("failure_code") is None


def test_backup_restore_preserves_failure_code(tmp_path):
    from icarus_memory.backup import snapshot_all
    from icarus_memory.memory_categories import Categories
    episodes, categories, item = make(tmp_path)
    categories.run(Provider(error=ProviderError("private backup test detail")))

    saved = snapshot_all(tmp_path, tmp_path / "backups")
    restored = EpisodeStore(saved / "episodes.sqlite3")
    assert restored._conn.execute("PRAGMA user_version").fetchone()[0] == 20
    assert Categories(restored).list_for(item.id)["failure_code"] == "provider_error"
    restored.close()
    episodes.close()


def test_deferred_source_has_no_failure_code_or_retry(tmp_path):
    episodes, categories, item = make(tmp_path, "x" * 12_001)

    categories.run(Provider())

    row = episodes._conn.execute(
        "SELECT status,failure_code,retry_after FROM memory_category_sources WHERE episode_id=?", (item.id,)).fetchone()
    assert tuple(row) == ("deferred", None, None)
    assert categories.list_for(item.id)["status"] == "deferred"
    assert categories.list_for(item.id).get("failure_code") is None


def test_preserve_on_failure_does_not_persist_status_or_diagnostic(tmp_path):
    episodes, categories, item = make(tmp_path)

    categories.run(Provider({"categories": [{"category_id": "made-up", "block_id": "B1"}], "entities": []}))
    previous = episodes._conn.execute(
        "SELECT status,failure_code FROM memory_category_sources WHERE episode_id=?", (item.id,)).fetchone()
    categories.request_recheck([item.id])
    with pytest.raises(ProviderError):
        categories.run(Provider(error=ProviderError("private scoped error")), preserve_on_failure=True)

    row = episodes._conn.execute(
        "SELECT status,failure_code FROM memory_category_sources WHERE episode_id=?", (item.id,)).fetchone()
    assert tuple(row) == tuple(previous) == ("failed", "validation_category_evidence")
    assert categories.list_for(item.id)["failure_code"] == "validation_category_evidence"


def test_v19_upgrade_preserves_legacy_status_with_unknown_reason(tmp_path):
    from icarus_memory.memory_categories import Categories
    path = tmp_path / "episodes.sqlite3"
    episodes, categories, item = make(tmp_path)
    categories.run(Provider(error=ProviderError("private legacy failure")))
    old = episodes._conn.execute(
        "SELECT status,model,retry_after FROM memory_category_sources WHERE episode_id=?", (item.id,)).fetchone()
    episodes.close()

    connection = sqlite3.connect(path)
    connection.execute("ALTER TABLE memory_category_sources DROP COLUMN failure_code")
    connection.execute("PRAGMA user_version=19")
    connection.commit()
    connection.close()

    store = EpisodeStore(path)
    row = store._conn.execute("SELECT status,model,retry_after,failure_code FROM memory_category_sources WHERE episode_id=?", (item.id,)).fetchone()
    assert store._conn.execute("PRAGMA user_version").fetchone()[0] == 20
    assert tuple(row) == (*tuple(old), None)
    assert Categories(store).list_for(item.id)["status"] == "failed"
    assert Categories(store).list_for(item.id)["failure_code"] is None
    store.close()
