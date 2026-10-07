"""Working interpretations are bounded references to current original episodes."""
from datetime import datetime, timedelta, timezone
import hashlib
from types import SimpleNamespace

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.working_memory_store import MAX_SNAPSHOT_BYTES, MAX_SOURCE_CHARS, WorkingMemoryStore, source_fingerprint


AT = datetime(2026, 9, 23, tzinfo=timezone.utc)


def source(episodes, body, *, title="Mail", key="", kind=EpisodeKind.MESSAGE):
    episode, _ = episodes.record(kind, title, body,
        Provenance(SourceType.CHAT, source_ref="chat:local"),
        source_key=key, at=AT)
    if key:
        episodes.advance_source_head(key, episodes.source_head(key), episode.id)
    return episode


def test_source_request_and_conditional_commitment_are_searchable_without_confirmation(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    memory = WorkingMemoryStore(episodes)
    body = "Bitte sende die Rechnung. Wenn der Entwurf freigegeben ist, liefere ich Montag."
    episode = source(episodes, body)
    snapshot = memory.pending()[0]
    assert snapshot.episode.id == episode.id
    assert memory.commit(snapshot, [
        {"start": 0, "end": 25, "kind": "request"},
        {"start": 26, "end": len(body), "kind": "conditional"}], model="local-v1")
    found = memory.search("Rechnungen")
    assert found["refs"] and found["refs"][0]["episode_id"] == episode.id
    assert memory.resolve(found["refs"][0]).episode.body == body
    conditional = memory.search("Entwurf")["refs"][0]
    assert "Wenn" in body[conditional["start"]:conditional["end"]]
    assert memory.pending() == []
    assert episodes.get(episode.id).produced == []


def test_empty_completion_and_restart_keep_source_out_of_pending(tmp_path):
    path = tmp_path / "episodes.sqlite3"
    episodes = EpisodeStore(path)
    memory = WorkingMemoryStore(episodes)
    episode = source(episodes, "Nur eine beiläufige Nachricht")
    assert memory.commit(memory.pending()[0], [], model="local-v1")
    assert memory.pending() == []
    episodes.close()
    reopened = EpisodeStore(path)
    assert WorkingMemoryStore(reopened).pending() == []
    assert reopened.get(episode.id).body == "Nur eine beiläufige Nachricht"


def test_analysis_version_is_explicit_and_current(tmp_path):
    import icarus_memory.working_memory_store as module

    assert module.ANALYSIS_VERSION == 1


def test_outdated_interpretation_stays_readable_but_counts_as_pending(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    memory = WorkingMemoryStore(episodes)
    episode = source(episodes, "Bitte prüfe den Orion Vertrag")
    snapshot = memory.pending()[0]
    assert memory.commit(snapshot, [{"start": 0, "end": len(episode.body), "kind": "request"}], model="local-v1")
    ref = memory.search("Orion")["refs"][0]
    with episodes.transaction():
        episodes._conn.execute(
            "UPDATE working_memory_sources SET analysis_version=0 WHERE episode_id=?",
            (episode.id,))

    assert memory.source_state(episode.id) == "pending"
    assert memory.pending() == [snapshot]
    assert memory.resolve(ref).episode.body == episode.body
    assert memory.coverage()["pending"] == 1
    assert memory.progress()["done"] == 0
    assert memory.progress()["remaining"] == 1


def test_outdated_interpretation_is_open_in_classification_state(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    memory = WorkingMemoryStore(episodes)
    episode = source(episodes, "Orion has one useful detail")
    snapshot = memory.pending()[0]
    assert memory.commit(snapshot, [{"start": 0, "end": len(episode.body), "kind": "fact"}], model="local-v1")
    with episodes.transaction():
        episodes._conn.execute(
            "UPDATE working_memory_sources SET analysis_version=0 WHERE episode_id=?", (episode.id,))

    assert memory.classification_state([episode.id]) == {
        "eingeordnet": 0, "offen": 1, "ausgeschlossen": 0}


def test_ignore_reopen_and_dismiss_never_revive_old_refs(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    memory = WorkingMemoryStore(episodes)
    episode = source(episodes, "Sende Orion Rechnung")
    first = memory.pending()[0]
    assert memory.commit(first, [{"start": 0, "end": len(episode.body), "kind": "request"}], model="a")
    ref = memory.search("Orion")["refs"][0]
    episodes.ignore(episode.id)
    assert memory.resolve(ref) is None
    assert memory.search("Orion")["refs"] == []
    episodes.reopen(episode.id)
    assert memory.resolve(ref) is None
    assert memory.pending()
    assert memory.dismiss(episode.id)
    assert memory.pending() == []
    assert memory.search("Orion")["refs"] == []
    assert not memory.dismiss(episode.id)


def test_changed_metadata_or_source_head_rejects_commit(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    memory = WorkingMemoryStore(episodes)
    first = source(episodes, "Orion erster Stand", key="mail:1")
    stale = memory.pending()[0]
    second = source(episodes, "Orion zweiter Stand", key="mail:1")
    assert not memory.commit(stale, [{"start": 0, "end": 5, "kind": "fact"}], model="a")
    assert first.id != second.id
    snapshot = next(s for s in memory.pending() if s.episode.id == second.id)
    # Metadata visible in the source document must be part of the fingerprint.
    changed = episodes.get(second.id)
    changed.provenance.source_ref = "chat:changed"
    episodes._put(changed)
    assert not memory.commit(snapshot, [{"start": 0, "end": 5, "kind": "fact"}], model="a")


def test_oldest_matching_source_is_found_beyond_128_newer_episodes(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    memory = WorkingMemoryStore(episodes)
    old = source(episodes, "Der Quasarvertrag bleibt bis Dezember bedingt")
    assert memory.commit(memory.pending()[0], [{"start": 0, "end": len(old.body), "kind": "conditional"}], model="a")
    for n in range(140):
        source(episodes, f"Neue Nachricht Nummer {n}")
    assert memory.search("Quasarvertrag")["refs"][0]["episode_id"] == old.id


def test_oversize_and_failed_source_do_not_starve_eligible_source(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    memory = WorkingMemoryStore(episodes)
    source(episodes, "x" * (MAX_SOURCE_CHARS + 1))
    failed = source(episodes, "Modellfehler zu Orion")
    eligible = source(episodes, "Bitte prüfen Sie den Plan")
    failed_snapshot = next(s for s in memory.pending() if s.episode.id == failed.id)
    assert memory.fail(failed_snapshot)
    assert [s.episode.id for s in memory.pending(limit=1)] == [eligible.id]


def test_refs_only_persisted_and_condition_span_keeps_qualification(tmp_path):
    path = tmp_path / "episodes.sqlite3"
    episodes = EpisodeStore(path)
    memory = WorkingMemoryStore(episodes)
    text = "Wenn der Kunde unterschreibt, sende ich die Rechnung."
    episode = source(episodes, text)
    assert memory.commit(memory.pending()[0], [{"start": 0, "end": len(text), "kind": "conditional"}], model="model-1")
    ref = memory.search("Rechnung")["refs"][0]
    assert set(ref) == {"episode_id", "fingerprint", "start", "end", "kind"}
    assert text[ref["start"]:ref["end"]].startswith("Wenn")
    episodes.close()
    reopened = EpisodeStore(path)
    assert WorkingMemoryStore(reopened).resolve(ref).episode.id == episode.id


def test_title_terms_find_body_reference_and_complete_is_not_reclassified(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    memory = WorkingMemoryStore(episodes)
    episode = source(episodes, "Anna liefert Freitag, falls der Vertrag gilt.", title="Angebot Mainz")
    snapshot = memory.pending()[0]
    item = {"start": 0, "end": len(episode.body), "kind": "conditional"}
    assert memory.is_current(snapshot)
    assert memory.commit(snapshot, [item], model="first")
    assert memory.search("Mainz")["refs"][0]["episode_id"] == episode.id
    assert not memory.commit(snapshot, [{**item, "kind": "fact"}], model="second")
    assert memory.search("Mainz")["refs"][0]["kind"] == "conditional"


def test_pending_scan_cursor_reaches_all_sources_beyond_one_page(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    memory = WorkingMemoryStore(episodes)
    expected = {source(episodes, f"Quelle {n}").id for n in range(505)}
    seen = set()
    for _ in range(51):
        seen.update(snapshot.episode.id for snapshot in memory.pending(limit=10))
    assert seen == expected


def test_oversize_source_is_deferred_without_parsing_its_document(tmp_path, monkeypatch):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    memory = WorkingMemoryStore(episodes)
    huge = source(episodes, "A" * (MAX_SNAPSHOT_BYTES + 1000))
    original = memory._snapshot
    def guarded(episode_id):
        assert episode_id != huge.id
        return original(episode_id)
    monkeypatch.setattr(memory, "_snapshot", guarded)
    assert memory.pending() == []
    assert memory.coverage()["deferred"] == 1


def test_search_caps_stale_candidates_and_reports_truncation(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    memory = WorkingMemoryStore(episodes)
    episode = source(episodes, "Quasarkonto")
    snapshot = memory.pending()[0]
    assert memory.commit(snapshot, [{"start": 0, "end": len(episode.body), "kind": "fact"}], model="a")
    # Tampered source makes all old indexed references invalid; query still has
    # a fixed work budget and reports incomplete coverage.
    with episodes.transaction():
        from icarus_memory.working_memory_store import hex_key
        token = hex_key(hashlib.sha256(b"quasarkonto").hexdigest())
        for n in range(501):
            item_id = f"stale-{n:04d}"
            episodes._conn.execute("INSERT INTO working_memory_items VALUES(?,?,?,?,?,?,?)",
                                   (item_id, episode.id, source_fingerprint(snapshot), 0, 99999, "fact", n))
            episodes._conn.execute("INSERT INTO working_memory_terms VALUES(?,?)", (token, n))
    result = memory.search("Quasarkonto")
    assert result["truncated"]


def test_failure_retries_after_cooldown_and_index_contains_no_source_words(tmp_path, monkeypatch):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    memory = WorkingMemoryStore(episodes)
    episode = source(episodes, "GeheimerQuasar bittet um eine Rückmeldung.")
    snapshot = memory.pending()[0]
    assert memory.fail(snapshot)
    assert memory.pending() == []
    import icarus_memory.working_memory_store as module
    original = module.time.time
    monkeypatch.setattr(module.time, "time", lambda: original() + 301)
    assert [s.episode.id for s in memory.pending()] == [episode.id]
    assert memory.commit(snapshot, [{"start": 0, "end": len(episode.body), "kind": "request"}], model="a")
    with episodes._lock:
        for table in ("working_memory_sources", "working_memory_items", "working_memory_terms"):
            rows = episodes._conn.execute(f"SELECT * FROM {table}").fetchall()
            assert "GeheimerQuasar" not in repr([tuple(row) for row in rows])


def test_revision_is_durable_and_changes_only_on_successful_commit_or_dismiss(tmp_path):
    path = tmp_path / "episodes.sqlite3"
    episodes = EpisodeStore(path)
    memory = WorkingMemoryStore(episodes)
    episode = source(episodes, "Orion Vertragsentwurf")
    snapshot = memory.pending()[0]
    assert memory.revision() == 0
    item = {"start": 0, "end": len(episode.body), "kind": "fact"}
    assert memory.commit(snapshot, [item], model="a")
    assert memory.revision() == 1
    assert not memory.commit(snapshot, [item], model="b")
    assert memory.revision() == 1
    episodes.close()
    reopened = EpisodeStore(path)
    memory = WorkingMemoryStore(reopened)
    assert memory.revision() == 1
    assert memory.dismiss(episode.id)
    assert memory.revision() == 2
    assert not memory.dismiss(episode.id)
    assert memory.revision() == 2


def test_equally_matching_sources_rank_by_occurred_then_recorded_time(tmp_path, monkeypatch):
    import icarus_memory.episodes as episode_module
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    memory = WorkingMemoryStore(episodes)
    identifiers = iter(["000000000000", "ffffffffffff", "888888888888"])
    monkeypatch.setattr(episode_module.uuid, "uuid4", lambda: SimpleNamespace(hex=next(identifiers)))
    provenance = Provenance(SourceType.CHAT, source_ref="chat:local")
    older, _ = episodes.record(EpisodeKind.MESSAGE, "Alter Stand", "Quasarkonto alter Stand",
                               provenance, at=AT, occurred_at=AT - timedelta(days=2))
    newer, _ = episodes.record(EpisodeKind.MESSAGE, "Neuer Stand", "Quasarkonto neuer Stand",
                               provenance, at=AT - timedelta(days=1), occurred_at=AT)
    undated, _ = episodes.record(EpisodeKind.MESSAGE, "Ohne Ereigniszeit", "Quasarkonto undatiert",
                                 provenance, at=AT + timedelta(days=1))
    for episode in (older, newer, undated):
        snapshot = episodes.support_snapshot(episode.id)
        assert memory.commit(snapshot, [{"start": 0, "end": len(episode.body), "kind": "status"}], model="a")
    assert [r["episode_id"] for r in memory.search("Quasarkonto")["refs"]] == [newer.id, older.id, undated.id]


def test_participant_terms_find_sender_when_body_uses_pronoun(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    memory = WorkingMemoryStore(episodes)
    episode, _ = episodes.record(EpisodeKind.MESSAGE, "Entwurf", "Ich liefere ihn Freitag.",
                                 Provenance(SourceType.CHAT, source_ref="chat:local"),
                                 participants=["Anna <anna@example.com>"], at=AT)
    assert memory.commit(episodes.support_snapshot(episode.id),
                         [{"start": 0, "end": len(episode.body), "kind": "commitment"}], model="a")
    assert memory.search("Was hat Anna zugesagt?")["refs"][0]["episode_id"] == episode.id


def test_deterministic_classifier_gap_is_deferred_until_source_changes(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    memory = WorkingMemoryStore(episodes)
    episode = source(episodes, "Zu viele Abschnitte für die Klassifikation", key="mail:gap")
    snapshot = memory.pending()[0]
    assert memory.defer(snapshot)
    assert memory.coverage()["deferred"] == 1
    assert memory.pending() == []
    assert memory.revision() == 0
    assert not memory.defer(snapshot)
    newer = source(episodes, "Kürzere neue Fassung", key="mail:gap")
    assert newer.id != episode.id
    assert [s.episode.id for s in memory.pending()] == [newer.id]
    assert memory.commit(episodes.support_snapshot(newer.id), [], model="a")
    assert not memory.defer(episodes.support_snapshot(newer.id))
    assert memory.revision() == 1


def test_candidate_signature_ignores_unrelated_sources_but_detects_thirteenth_match(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    memory = WorkingMemoryStore(episodes)
    provenance = Provenance(SourceType.CHAT, source_ref="chat:local")
    for n in range(12):
        body = f"Orion Bericht Nummer {n}"
        episode, _ = episodes.record(EpisodeKind.MESSAGE, "Bericht", body,
                                     provenance, at=AT)
        assert memory.commit(episodes.support_snapshot(episode.id),
                             [{"start": 0, "end": len(body), "kind": "status"}], model="a")
    first_twelve = memory.search("Orion")["refs"]
    signature = memory.candidate_signature("Orion")
    unrelated = source(episodes, "Borealis Nachricht")
    assert memory.commit(episodes.support_snapshot(unrelated.id),
                         [{"start": 0, "end": len(unrelated.body), "kind": "fact"}], model="a")
    assert memory.candidate_signature("Orion") == signature
    body = "Orion Bericht aus der alten Ablage"
    thirteenth, _ = episodes.record(EpisodeKind.MESSAGE, "Alte Ablage", body,
                                    provenance, at=AT - timedelta(days=30))
    assert memory.commit(episodes.support_snapshot(thirteenth.id),
                         [{"start": 0, "end": len(body), "kind": "historical"}], model="a")
    assert memory.search("Orion")["refs"] == first_twelve
    assert memory.candidate_signature("Orion") != signature


def test_candidate_signature_changes_on_dismissal_and_source_reclassification(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    memory = WorkingMemoryStore(episodes)
    first = source(episodes, "Orion alter Entwurf", key="mail:orion")
    assert memory.commit(episodes.support_snapshot(first.id),
                         [{"start": 0, "end": len(first.body), "kind": "status"}], model="a")
    before = memory.candidate_signature("Orion")
    second = source(episodes, "Orion neuer Entwurf", key="mail:orion")
    assert memory.commit(episodes.support_snapshot(second.id),
                         [{"start": 0, "end": len(second.body), "kind": "change"}], model="a")
    after_change = memory.candidate_signature("Orion")
    assert after_change != before
    assert memory.dismiss(second.id)
    assert memory.candidate_signature("Orion") != after_change
