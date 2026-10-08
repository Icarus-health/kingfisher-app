"""Source-first memory areas are a bounded read-only projection."""
import sqlite3
import threading

from fastapi import FastAPI
from fastapi.testclient import TestClient

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.backup import restore_all, snapshot_all
from icarus_memory.mail_intake_routes import register
from icarus_memory.memory_categories import Categories


def _app(tmp_path):
    app = FastAPI()
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    app.state.episodes = episodes
    app.state.conversation_lock = threading.RLock()
    register(app, [], lambda: tmp_path, lambda _app: None)
    return app, episodes


def _source(episodes, title="Projekt", body="Originaltext.", *, source_key=""):
    return episodes.record(EpisodeKind.MESSAGE, title, body,
        Provenance(SourceType.EMAIL, source_ref=f"synthetic:{title}:{body[:10]}"),
        source_key=source_key)[0]


def _stored_topics(categories, episode, category_ids, *, end=1):
    snapshot = categories.memory._snapshot(episode.id)
    version = categories.taxonomy()["version"]
    topics = [(identifier, 0, end) for identifier in category_ids]
    assert categories._write(snapshot, version, topics, [], "synthetic")


def _downgrade_to_v18(path, *, custom_health=False, fill_taxonomy=False):
    connection = sqlite3.connect(path)
    connection.execute("DELETE FROM memory_category_taxonomy WHERE category_id='health'")
    if custom_health:
        connection.execute("INSERT INTO memory_category_taxonomy VALUES('health',1,'Eigene Gesundheit','Eigene Beschreibung')")
    if fill_taxonomy:
        present = {row[0] for row in connection.execute(
            "SELECT DISTINCT category_id FROM memory_category_taxonomy")}
        for index in range(64 - len(present)):
            connection.execute("INSERT INTO memory_category_taxonomy VALUES(?,1,?,?)",
                (f"custom_{index:02d}", f"Eigene {index}", "Synthetische Kategorie"))
    connection.execute("UPDATE memory_category_scan SET taxonomy_version=1,corpus_version=1 WHERE id=1")
    connection.execute("PRAGMA user_version=18")
    connection.commit()
    connection.close()


def test_fresh_store_adds_health_taxonomy_without_bumping_corpus_version(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    categories = Categories(episodes)
    taxonomy = categories.taxonomy()

    assert any(item["id"] == "health" for item in taxonomy["items"])
    assert tuple(episodes._conn.execute(
        "SELECT corpus_version,taxonomy_version FROM memory_category_scan WHERE id=1").fetchone()) == (1, 2)
    episodes.close()


def test_v18_upgrade_adds_health_but_preserves_custom_health_and_corpus_version(tmp_path):
    path = tmp_path / "episodes.sqlite3"
    episodes = EpisodeStore(path)
    episodes.close()
    _downgrade_to_v18(path)

    upgraded = EpisodeStore(path)
    categories = Categories(upgraded)
    taxonomy = categories.taxonomy()
    assert next(item for item in taxonomy["items"] if item["id"] == "health")["label"] == "Gesundheit"
    assert tuple(upgraded._conn.execute(
        "SELECT corpus_version,taxonomy_version FROM memory_category_scan WHERE id=1").fetchone()) == (1, 2)
    upgraded.close()

    custom_path = tmp_path / "custom.sqlite3"
    custom = EpisodeStore(custom_path)
    custom.close()
    _downgrade_to_v18(custom_path, custom_health=True)
    custom = EpisodeStore(custom_path)
    taxonomy = Categories(custom).taxonomy()
    assert next(item for item in taxonomy["items"] if item["id"] == "health")["label"] == "Eigene Gesundheit"
    assert tuple(custom._conn.execute(
        "SELECT corpus_version,taxonomy_version FROM memory_category_scan WHERE id=1").fetchone()) == (1, 1)
    custom.close()


def test_v18_upgrade_at_category_limit_reports_health_unavailable(tmp_path):
    path = tmp_path / "episodes.sqlite3"
    episodes = EpisodeStore(path)
    episodes.close()
    _downgrade_to_v18(path, fill_taxonomy=True)

    upgraded = EpisodeStore(path)
    taxonomy = Categories(upgraded).taxonomy()
    assert len(taxonomy["items"]) == 64
    assert all(item["id"] != "health" for item in taxonomy["items"])
    from icarus_memory.memory_areas import MemoryAreas
    areas = MemoryAreas(upgraded).page()["areas"]
    assert next(item for item in areas if item["id"] == "health")["available"] is False
    assert next(item for item in areas if item["id"] == "work")["available"] is True
    assert tuple(upgraded._conn.execute(
        "SELECT corpus_version,taxonomy_version FROM memory_category_scan WHERE id=1").fetchone()) == (1, 1)
    upgraded.close()


def test_restored_v18_snapshot_migrates_to_supported_schema_19(tmp_path):
    live = tmp_path / "live"
    path = live / "episodes.sqlite3"
    episodes = EpisodeStore(path)
    episodes.close()
    _downgrade_to_v18(path)
    snapshot = snapshot_all(live, tmp_path / "backups")
    restored = tmp_path / "restored"
    restore_all(snapshot, restored)

    from icarus_memory.update_backup import _targets
    assert max(item.version for item in _targets()["episodes.sqlite3"]) == 19
    recovered = EpisodeStore(restored / "episodes.sqlite3")
    assert any(item["id"] == "health" for item in Categories(recovered).taxonomy()["items"])
    recovered.close()


def test_memory_areas_is_paginated_source_first_and_read_only(tmp_path, monkeypatch):
    app, episodes = _app(tmp_path)
    categories = Categories(episodes)
    categories.add_category("custom_topic", "Eigene Kategorie")
    taxonomy_ids = [item["id"] for item in categories.taxonomy()["items"]]
    first = _source(episodes, "Titel " + "x" * 300, "Beleg " + "y" * 300)
    second = _source(episodes, "Manuelle Quelle", "Manueller Ursprung.")
    third = _source(episodes, "Noch offen", "Noch nicht ausgewertet.")
    ignored = _source(episodes, "Ausgeschlossen", "Darf nicht erscheinen.")
    episodes.ignore(ignored.id)
    _stored_topics(categories, first, taxonomy_ids, end=len(first.body))
    categories.correct(second.id, ["personal"])
    before = episodes._conn.total_changes
    def no_analysis(*_args, **_kwargs):
        raise AssertionError("GET darf keine Kategorien berechnen")
    monkeypatch.setattr(Categories, "run", no_analysis)

    with TestClient(app) as client:
        page1 = client.get("/api/v1/memory/areas?limit=2")
        assert page1.status_code == 200
        result1 = page1.json()
        assert [item["id"] for item in result1["areas"]] == ["work", "personal", "health", "finance"]
        assert result1["scanned_count"] == 2
        assert result1["counts_scope"] == "page"
        assert result1["truncated"] is True
        assert result1["next_cursor"] is not None
        assert [source["episode_id"] for source in result1["sources"]] == [third.id, second.id]
        assert result1["sources"][0]["categories"] == []
        assert result1["sources"][1]["status"] == "pending"
        assert result1["sources"][1]["categories"][0]["origin"] == "user"
        assert result1["sources"][1]["categories"][0]["evidence"] == []

        result2 = client.get(f"/api/v1/memory/areas?limit=2&cursor={result1['next_cursor']}").json()
        assert [source["episode_id"] for source in result2["sources"]] == [first.id]
        source = result2["sources"][0]
        assert len(source["title"]) == 240
        assert source["categories"]
        assert {category["id"] for category in source["categories"]} == set(taxonomy_ids)
        assert all(len(category["evidence"]) <= 1 for category in source["categories"])
        assert all(len(item["quote"]) <= 240 and item["quote_truncated"]
                   for category in source["categories"] for item in category["evidence"])
        assert result2["next_cursor"] is None and result2["truncated"] is False
        assert client.get("/api/v1/memory/areas?limit=101").status_code == 422

    assert episodes._conn.total_changes == before
    episodes.close()


def test_memory_areas_filters_superseded_original_versions(tmp_path):
    app, episodes = _app(tmp_path)
    old = _source(episodes, "Alte Fassung", "Alt.", source_key="mail:1")
    latest = episodes.record(EpisodeKind.MESSAGE, "Neue Fassung", "Neu.",
        Provenance(SourceType.EMAIL, source_ref="synthetic:latest"), source_key="mail:1")[0]
    episodes.advance_source_head("mail:1", None, old.id)
    episodes.advance_source_head("mail:1", old.id, latest.id)

    with TestClient(app) as client:
        response = client.get("/api/v1/memory/areas").json()
    assert [source["episode_id"] for source in response["sources"]] == [latest.id]
    assert response["sources"][0]["episode_id"] != old.id
    episodes.close()


def test_upgrade_keeps_old_current_hints_and_explicit_corrections_without_reanalysis(tmp_path):
    path = tmp_path / 'episodes.sqlite3'
    episodes = EpisodeStore(path)
    categories = Categories(episodes)
    automatic = _source(episodes, 'Arbeit', 'Ein früherer Projektstand.')
    manual = _source(episodes, 'Privat', 'Eine private Quelle.')
    _stored_topics(categories, automatic, ['work'])
    categories.correct(manual.id, ['personal'])
    originals = [episodes.get(item.id).to_dict() for item in (automatic, manual)]
    episodes.close()
    _downgrade_to_v18(path)
    with sqlite3.connect(path) as db:
        db.execute('UPDATE memory_category_sources SET taxonomy_version=1')
        db.execute('UPDATE memory_category_corrections SET taxonomy_version=1')
    upgraded = EpisodeStore(path)
    categories = Categories(upgraded)
    assert [upgraded.get(item.id).to_dict() for item in (automatic, manual)] == originals
    assert categories.list_for(automatic.id)['status'] == 'complete'
    assert categories.list_for(automatic.id)['categories'][0]['id'] == 'work'
    corrected = categories.list_for(manual.id)
    assert corrected['correction']['stale'] is False
    assert corrected['categories'][0]['origin'] == 'user'
    assert corrected['categories'][0]['id'] == 'personal'
    upgraded.close()


def test_areas_hide_stale_categories_after_original_changes_and_explicit_withdrawal(tmp_path):
    app, episodes = _app(tmp_path)
    categories = Categories(episodes)
    item = _source(episodes, 'Änderung', 'Ein früherer Arbeitsbeleg.')
    _stored_topics(categories, item, ['work'])
    categories.correct(item.id, ['personal'])
    with TestClient(app) as client:
        assert client.get('/api/v1/memory/areas').json()['sources'][0]['categories']
        changed = episodes.get(item.id)
        changed.body = 'Eine neue Originalfassung mit anderem Inhalt.'
        episodes._put(changed)
        response = client.get('/api/v1/memory/areas').json()
        assert response['sources'][0]['categories'] == []
        episodes.ignore(item.id)
        assert client.get('/api/v1/memory/areas').json()['sources'] == []
    episodes.close()
