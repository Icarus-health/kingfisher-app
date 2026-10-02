"""Vertragstests für stabile explizite Entitätskennungen."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from icarus_memory.entities import EntityError, EntityRegistry, install_schema


def _connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=10, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    install_schema(connection)
    connection.commit()
    return connection


def test_restart_same_explicit_id_is_readable_and_not_repurposed(tmp_path: Path) -> None:
    path = tmp_path / "knowledge.sqlite3"
    first = _connection(path)
    registry = EntityRegistry(first)
    created = registry.create("person", "Ada Lovelace", explicit_id="person:legacy-ada")
    first.close()

    second = _connection(path)
    restarted = EntityRegistry(second)
    assert restarted.get("person:legacy-ada") == created
    with pytest.raises(EntityError):
        restarted.create("person", "Someone else", explicit_id="person:legacy-ada")
    second.close()


def test_same_name_creates_distinct_candidates_and_search_returns_all(tmp_path: Path) -> None:
    connection = _connection(tmp_path / "knowledge.sqlite3")
    registry = EntityRegistry(connection)

    first = registry.create("person", "Alex Kim")
    second = registry.create("person", "Alex Kim")

    assert first["id"] != second["id"]
    assert {item["id"] for item in registry.search("Alex Kim")} == {
        first["id"],
        second["id"],
    }
    connection.close()


def test_rename_keeps_identity_and_changes_exact_search(tmp_path: Path) -> None:
    connection = _connection(tmp_path / "knowledge.sqlite3")
    registry = EntityRegistry(connection)
    created = registry.create("project", "Atlas")

    renamed = registry.rename(created["id"], "Atlas Relaunch")

    assert renamed["id"] == created["id"]
    assert renamed["created_at"] == created["created_at"]
    assert registry.search("Atlas") == []
    assert registry.search("Atlas Relaunch") == [renamed]
    connection.close()


def test_source_binding_isolated_by_account_and_conflicts_are_rejected(tmp_path: Path) -> None:
    connection = _connection(tmp_path / "knowledge.sqlite3")
    registry = EntityRegistry(connection)
    first = registry.create("person", "Mailbox one")
    second = registry.create("person", "Mailbox two")

    registry.link_source(first["id"], "mail", "work", "42")
    registry.link_source(second["id"], "mail", "private", "42")
    assert registry.resolve_source("mail", "work", "42")["id"] == first["id"]
    assert registry.resolve_source("mail", "private", "42")["id"] == second["id"]
    with pytest.raises(EntityError):
        registry.link_source(second["id"], "mail", "work", "42")
    connection.close()


def test_unlink_source_does_not_delete_entity(tmp_path: Path) -> None:
    connection = _connection(tmp_path / "knowledge.sqlite3")
    registry = EntityRegistry(connection)
    entity = registry.create("document", "Briefing")
    registry.link_source(entity["id"], "drive", "account", "doc-1")

    assert registry.unlink_source("drive", "account", "doc-1") is True
    assert registry.resolve_source("drive", "account", "doc-1") is None
    assert registry.get(entity["id"]) == entity
    assert registry.unlink_source("drive", "account", "doc-1") is False
    connection.close()


def test_two_connections_race_cannot_overwrite_binding(tmp_path: Path) -> None:
    path = tmp_path / "knowledge.sqlite3"
    setup = _connection(path)
    first = EntityRegistry(setup).create("person", "First")
    second = EntityRegistry(setup).create("person", "Second")
    setup.close()

    left = _connection(path)
    right = _connection(path)
    registries = (EntityRegistry(left), EntityRegistry(right))

    def bind(index: int):
        try:
            return registries[index].link_source(
                (first if index == 0 else second)["id"], "chat", "account", "native-1"
            )
        except EntityError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(bind, (0, 1)))

    assert sum(result is not None for result in results) == 1
    resolved = EntityRegistry(left).resolve_source("chat", "account", "native-1")
    assert resolved is not None
    assert resolved["id"] in {first["id"], second["id"]}
    left.close()
    right.close()


def test_schema_install_does_not_change_user_version_or_commit(tmp_path: Path) -> None:
    connection = sqlite3.connect(tmp_path / "knowledge.sqlite3")
    connection.execute("BEGIN")
    install_schema(connection)
    assert connection.in_transaction is True
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
    connection.rollback()
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE name = 'entity_registry'"
    ).fetchone() is None
    connection.close()


def test_invalid_explicit_id_kind_and_external_transaction_fail_cleanly(tmp_path: Path) -> None:
    connection = _connection(tmp_path / "knowledge.sqlite3")
    registry = EntityRegistry(connection)
    with pytest.raises(EntityError):
        registry.create("person", "Ada", explicit_id="project:ada")
    connection.execute("BEGIN")
    with pytest.raises(EntityError, match="external transaction"):
        registry.create("person", "Ada")
    connection.rollback()
    connection.close()
