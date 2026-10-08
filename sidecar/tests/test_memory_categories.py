"""Topic suggestions stay tied to current originals and explicit corrections."""
import json
import re
from types import SimpleNamespace

import pytest

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.providers import Reply


class Local:
    is_local = True
    name = "local-fixture"
    model = "bounded-fixture"

    def __init__(self, result=None, on_call=None):
        self.result, self.on_call, self.calls = result, on_call, []

    def complete_json(self, messages, *, max_tokens, schema):
        payload = json.loads(messages[-1]["content"])
        self.calls.append(payload)
        assert schema["additionalProperties"] is False
        assert 64 <= max_tokens <= 1200
        if self.on_call:
            self.on_call(payload)
        result = self.result(payload) if callable(self.result) else self.result
        if result is None:
            result = {"categories": [{"category_id": "work", "block_id": "B1"}],
                      "entities": []}
        return Reply(text=json.dumps(result))


def setup(tmp_path):
    from icarus_memory.memory_categories import Categories, migrate, verify
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    if not episodes._conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='memory_category_scan'").fetchone():
        with episodes.transaction():
            migrate(episodes._conn)
    verify(episodes._conn)
    return episodes, Categories(episodes)


def source(episodes, body="Anna Kranz arbeitet an Projekt Atlas.", **kwargs):
    item, created = episodes.record(EpisodeKind.MESSAGE, "Projekt", body,
        Provenance(SourceType.CHAT, source_ref="synthetic-source"), **kwargs)
    assert created
    return item


def test_topics_and_entities_read_only_exact_original_evidence(tmp_path):
    episodes, categories = setup(tmp_path)
    item = source(episodes)
    before = episodes.get(item.id).to_dict()
    provider = Local(result={"categories": [
        {"category_id": "work", "block_id": "B1"},
        {"category_id": "information", "block_id": "B1"}], "entities": [
        {"kind": "person", "name": "Anna Kranz", "start": 0, "end": 10, "role": "mentioned"},
        {"kind": "project", "name": "Atlas", "start": 31, "end": 36, "role": "mentioned"}]})
    assert categories.run(provider).ok
    result = categories.list_for(item.id)
    assert [entry["id"] for entry in result["categories"]] == ["work", "information"]
    assert all(entry["origin"] == "automatic" for entry in result["categories"])
    assert result["categories"][0]["evidence"][0]["quote"] == item.body
    assert result["entities"][0]["quote"] == "Anna Kranz"
    assert result["entities"][1]["quote"] == "Atlas"
    assert episodes.get(item.id).to_dict() == before
    assert categories.run(provider).ok
    assert len(provider.calls) == 1


def test_withdrawal_and_source_head_change_hide_saved_evidence(tmp_path):
    episodes, categories = setup(tmp_path)
    item = source(episodes, source_key="mail:synthetic:1")
    episodes.advance_source_head("mail:synthetic:1", None, item.id)
    categories.run(Local())
    categories.correct(item.id, ["personal"])
    replacement = source(episodes, "Anna Kranz hat das Projekt beendet.", source_key="mail:synthetic:1")
    episodes.advance_source_head("mail:synthetic:1", item.id, replacement.id)
    old = categories.list_for(item.id)
    assert old["status"] == "excluded"
    assert old["categories"] == old["entities"] == []
    assert old["correction"]["stale"]
    categories.run(Local())
    assert categories.list_for(replacement.id)["categories"]
    episodes.ignore(replacement.id)
    assert categories.list_for(replacement.id)["categories"] == []


def test_withdrawal_or_permission_change_during_call_prevents_commit(tmp_path):
    episodes, categories = setup(tmp_path)
    item = source(episodes)
    provider = Local(on_call=lambda _: episodes.ignore(item.id))
    categories.run(provider)
    assert categories.list_for(item.id)["categories"] == []
    other = source(episodes, "Eine andere Arbeitsquelle.")
    permission = {"yes": True}
    provider = Local(on_call=lambda _: permission.update(yes=False))
    categories.run(provider, permitted=lambda: permission["yes"])
    assert categories.list_for(other.id)["status"] == "pending"


def test_user_correction_survives_reclassification_and_changed_source_is_stale(tmp_path):
    episodes, categories = setup(tmp_path)
    item = source(episodes)
    categories.run(Local())
    categories.correct(item.id, ["personal", "finance"])
    categories.add_category("health", "Gesundheit", "Gesundheitsbezogene Originalaussagen", episode_ids=[item.id])
    provider = Local()
    categories.run(provider)
    result = categories.list_for(item.id)
    assert [entry["id"] for entry in result["categories"]] == ["personal", "finance"]
    assert all(entry["origin"] == "user" for entry in result["categories"])
    assert result["correction"]["stale"] is False
    # A consistent metadata edit changes the visible original fingerprint,
    # preserving the old correction without silently endorsing the new source.
    changed = episodes.get(item.id)
    changed.participants = ["A different sender"]
    episodes._put(changed)
    result = categories.list_for(item.id)
    assert result["categories"] == []
    assert result["correction"]["categories"] == ["personal", "finance"]
    assert result["correction"]["stale"] is True
    categories.run(Local())
    assert categories.list_for(item.id)["correction"]["stale"] is True


def test_new_taxonomy_targets_only_selected_existing_sources_and_survives_restart(tmp_path):
    episodes, categories = setup(tmp_path)
    first = source(episodes)
    second = source(episodes, "Zweite Arbeitsquelle.")
    categories.run(Local(), limit=2)
    original = episodes.get(first.id).to_dict()
    next_version = categories.taxonomy()["version"] + 1
    entry = categories.add_category("health", "Gesundheit", "Belegte Gesundheitsthemen", episode_ids=[first.id])
    assert entry["version"] == next_version
    provider = Local(result={"categories": [{"category_id": "health", "block_id": "B1"}], "entities": []})
    categories.run(provider)
    assert len(provider.calls) == 1
    assert categories.list_for(first.id)["categories"][0]["id"] == "health"
    assert categories.list_for(second.id)["categories"][0]["id"] == "work"
    assert episodes.get(first.id).to_dict() == original
    episodes.close()
    episodes, categories = setup(tmp_path)
    assert categories.taxonomy()["version"] == next_version
    assert categories.list_for(first.id)["categories"][0]["id"] == "health"
    assert categories.run(provider).ok
    assert len(provider.calls) == 1


@pytest.mark.parametrize("result", [
    {"categories": [{"category_id": "invented", "block_id": "B1"}], "entities": []},
    {"categories": [{"category_id": "work", "block_id": "B99"}], "entities": []},
    {"categories": [{"category_id": "work", "block_id": "B1", "claim": "made up"}], "entities": []},
    {"categories": [], "entities": [{"kind": "person", "name": "Maria", "start": 0, "end": 10, "role": "mentioned"}]},
    {"categories": [], "entities": [{"kind": "person", "name": "Anna Kranz", "start": False, "end": 10, "role": "mentioned"}]},
    {"categories": [], "entities": [{"kind": "unknown", "name": "Anna Kranz", "start": 0, "end": 10, "role": "mentioned"}]},
    {"categories": [], "entities": [], "source_text": "untrusted secret"},
])
def test_invalid_model_output_is_sanitized_and_uses_retry_cooldown(tmp_path, result):
    episodes, categories = setup(tmp_path)
    item = source(episodes)
    provider = Local(result=result)
    run = categories.run(provider)
    assert run.ok is False
    assert "untrusted secret" not in run.detail
    assert categories.list_for(item.id)["status"] == "failed"
    assert categories.list_for(item.id)["categories"] == []
    categories.run(provider)
    assert len(provider.calls) == 1


@pytest.mark.parametrize("address", ["info@example.org", "no-reply@example.org", "newsletter@example.org"])
def test_generic_or_automated_mailbox_is_never_a_person_in_body(tmp_path, address):
    episodes, categories = setup(tmp_path)
    body = f"Von: Acme Team <{address}>\nAcme Team informiert über Projekt Atlas.\nAnna Kranz antwortet."
    item = source(episodes, body, participants=[f"Acme Team <{address}>"])
    bad_name = body.index("Acme Team", body.index("\n"))
    anna = body.index("Anna Kranz")
    provider = Local(result={"categories": [{"category_id": "information", "block_id": "B1"}], "entities": [
        {"kind": "person", "name": "Acme Team", "start": bad_name, "end": bad_name + 9, "role": "mentioned"},
        {"kind": "person", "name": address, "start": body.index(address), "end": body.index(address) + len(address), "role": "sender"},
        {"kind": "person", "name": "Anna Kranz", "start": anna, "end": anna + 10, "role": "mentioned"}]})
    assert categories.run(provider).ok
    assert [entity["name"] for entity in categories.list_for(item.id)["entities"]] == ["Anna Kranz"]


def test_cloud_and_missing_permission_receive_no_original_input(tmp_path):
    episodes, categories = setup(tmp_path)
    item = source(episodes)
    provider = Local()
    provider.is_local = False
    categories.run(provider)
    provider.is_local = True
    categories.run(provider, permitted=lambda: False)
    assert provider.calls == []
    assert categories.list_for(item.id)["status"] == "pending"


@pytest.mark.parametrize("body,tags", [("x" * 12001, []), ("first", ["source:truncated"]),
                                       ("\n\n".join(f"Block {i}" for i in range(25)), [])])
def test_unbounded_or_truncated_sources_are_visible_deferred_without_model_calls(tmp_path, body, tags):
    episodes, categories = setup(tmp_path)
    item = source(episodes, body, tags=tags)
    provider = Local()
    categories.run(provider)
    categories.run(provider)
    assert provider.calls == []
    assert categories.list_for(item.id)["status"] == "deferred"


def test_scan_cursor_is_bounded_fair_and_survives_restart(tmp_path, monkeypatch):
    import icarus_memory.episodes as episode_module
    import icarus_memory.memory_categories as module
    monkeypatch.setattr(module, "SCAN_BUDGET", 4)
    identifiers = iter(f"{n:012x}" for n in range(1, 8))
    monkeypatch.setattr(episode_module.uuid, "uuid4", lambda: SimpleNamespace(hex=next(identifiers)))
    episodes, categories = setup(tmp_path)
    originals = [source(episodes, f"Quelle {i}") for i in range(6)]
    provider = Local(result={"categories": [{"category_id": "missing", "block_id": "B1"}], "entities": []})
    categories.run(provider, limit=2)
    episodes.close()
    episodes, categories = setup(tmp_path)
    categories.run(provider, limit=2)
    categories.run(provider, limit=2)
    assert len(provider.calls) == 6
    assert {categories.list_for(item.id)["status"] for item in originals} == {"failed"}


def test_taxonomy_and_correction_validation_are_bounded(tmp_path):
    episodes, categories = setup(tmp_path)
    item = source(episodes)
    with pytest.raises(ValueError):
        categories.add_category("bad id", "Schlecht")
    with pytest.raises(ValueError):
        categories.add_category("extra", "x" * 81)
    with pytest.raises(ValueError):
        categories.correct(item.id, ["unknown"])
    with pytest.raises(ValueError):
        categories.correct(item.id, ["work", "work"])
    categories.correct(item.id, [])
    categories.run(Local())
    assert categories.list_for(item.id)["categories"] == []
    assert categories.list_for(item.id)["correction"]["stale"] is False


def test_mentioned_mailbox_display_name_does_not_claim_source_sender(tmp_path):
    episodes, categories = setup(tmp_path)
    item = source(episodes, "Bitte frage:\nAnna Kranz <anna@example.org> zum Projekt.")
    start = item.body.index("Anna Kranz")
    provider = Local(result={"categories": [], "entities": [
        {"kind": "person", "name": "Anna Kranz", "start": start, "end": start + 10, "role": "sender"}]})
    assert categories.run(provider).ok is False
    assert categories.list_for(item.id)["entities"] == []


def test_actual_email_sender_and_same_named_other_source_remain_separate(tmp_path):
    episodes, categories = setup(tmp_path)
    first, _ = episodes.record(EpisodeKind.MESSAGE, "Arbeit", "Anna Kranz startet Atlas.",
        Provenance(SourceType.EMAIL, source_ref="synthetic-1"),
        participants=["Anna Kranz <anna@first.example>"])
    second, _ = episodes.record(EpisodeKind.MESSAGE, "Arbeit", "Anna Kranz beendet Atlas.",
        Provenance(SourceType.EMAIL, source_ref="synthetic-2"),
        participants=["Anna Kranz <anna@second.example>"])
    provider = Local(result={"categories": [], "entities": [
        {"kind": "person", "name": "Anna Kranz", "start": 0, "end": 10, "role": "sender"}]})
    assert categories.run(provider, limit=2).ok
    assert categories.list_for(first.id)["entities"][0]["role"] == "sender"
    assert categories.list_for(second.id)["entities"][0]["role"] == "sender"
    assert categories.list_for(first.id)["episode_id"] != categories.list_for(second.id)["episode_id"]
    assert "person_id" not in categories.list_for(first.id)["entities"][0]


def test_new_category_during_model_call_does_not_claim_latest_taxonomy_was_used(tmp_path):
    episodes, categories = setup(tmp_path)
    item = source(episodes)
    next_version = categories.taxonomy()["version"] + 1
    provider = Local(on_call=lambda _: categories.add_category("health", "Gesundheit"))
    categories.run(provider)
    assert categories.list_for(item.id)["status"] == "pending"
    assert categories.list_for(item.id)["categories"] == []
    categories.run(Local())
    assert categories.list_for(item.id)["categories"][0]["taxonomy_version"] == next_version


def test_status_counts_are_explicitly_a_bounded_sample(tmp_path, monkeypatch):
    import icarus_memory.memory_categories as module
    episodes, categories = setup(tmp_path)
    source(episodes, "Erste Quelle")
    source(episodes, "Zweite Quelle")
    monkeypatch.setattr(module, "SCAN_BUDGET", 1)
    status = categories.status()
    assert status["total"] == 2
    assert status["scanned"] == status["pending"] == 1
    assert status["limited"] is True


def test_category_progress_rows_record_current_source_generation(tmp_path):
    episodes, categories = setup(tmp_path)
    item = source(episodes)
    categories.run(Local())
    saved = episodes._conn.execute("SELECT support_generation FROM memory_category_sources WHERE episode_id=?", (item.id,)).fetchone()[0]
    current = episodes._conn.execute("SELECT support_generation FROM episodes WHERE id=?", (item.id,)).fetchone()[0]
    assert saved == current


def test_model_call_releases_permission_lock_and_commit_holds_it(tmp_path):
    from threading import RLock
    episodes, categories = setup(tmp_path)
    source(episodes)
    lock = RLock()
    provider = Local(on_call=lambda _: pytest.fail("model must run outside lock") if lock._is_owned() else None)
    calls = []
    def permitted():
        assert lock._is_owned()
        calls.append(True)
        return True
    assert categories.run(provider, permitted=permitted, permission_lock=lock).ok
    assert len(calls) >= 3


def test_whole_generic_mail_label_is_not_a_person_but_organization_can_be_sender(tmp_path):
    episodes, categories = setup(tmp_path)
    body = "Acme Team <info@example.org> informiert über Atlas."
    item, _ = episodes.record(EpisodeKind.MESSAGE, "Nachricht", body,
        Provenance(SourceType.EMAIL, source_ref="synthetic"), participants=["Acme Team <info@example.org>"])
    label = "Acme Team <info@example.org>"
    provider = Local(result={"categories": [], "entities": [
        {"kind": "person", "name": label, "start": 0, "end": len(label), "role": "mentioned"},
        {"kind": "organization", "name": "Acme Team", "start": 0, "end": 9, "role": "sender"}]})
    assert categories.run(provider).ok
    entities = categories.list_for(item.id)["entities"]
    assert len(entities) == 1
    assert entities[0]["kind"] == "organization"


def test_dismissed_interpretation_never_regenerates_topics_or_entities(tmp_path):
    from icarus_memory.working_memory_store import WorkingMemoryStore
    episodes, categories = setup(tmp_path)
    item = source(episodes)
    categories.run(Local())
    categories.correct(item.id, ["personal"])
    categories.add_category("health", "Gesundheit")
    assert WorkingMemoryStore(episodes).dismiss(item.id)
    provider = Local()
    categories.run(provider)
    assert provider.calls == []
    result = categories.list_for(item.id)
    assert result["status"] == "excluded"
    assert result["categories"] == result["entities"] == []
    assert result["correction"] is None
    assert episodes._conn.execute("SELECT categories FROM memory_category_corrections WHERE episode_id=?", (item.id,)).fetchone()[0] == '["personal"]'
    with pytest.raises(ValueError):
        categories.correct(item.id, ["work"])


@pytest.mark.parametrize("invalid", [False, True])
def test_dismissal_during_model_call_prevents_success_and_failure_writes(tmp_path, invalid):
    from icarus_memory.working_memory_store import WorkingMemoryStore
    episodes, categories = setup(tmp_path)
    item = source(episodes)
    result = {"categories": [{"category_id": "invalid", "block_id": "B1"}], "entities": []} if invalid else None
    provider = Local(result=result, on_call=lambda _: WorkingMemoryStore(episodes).dismiss(item.id))
    categories.run(provider)
    assert categories.list_for(item.id)["status"] == "excluded"
    assert episodes._conn.execute("SELECT 1 FROM memory_category_sources WHERE episode_id=?", (item.id,)).fetchone() is None


def test_explicit_new_upload_is_processed_before_backlog_without_advancing_scan(tmp_path):
    episodes, categories = setup(tmp_path)
    old = source(episodes, "Alte Arbeitsquelle im Rückstand.")
    new = source(episodes, "Neu hochgeladene Arbeitsquelle.")
    before = episodes._conn.execute("SELECT cursor FROM memory_category_scan WHERE id=1").fetchone()[0]
    provider = Local()
    assert categories.run(provider, source_ids=[new.id, new.id]).ok
    assert len(provider.calls) == 1
    assert provider.calls[0]["blocks"][0]["text"] == new.body
    assert categories.list_for(new.id)["status"] == "complete"
    assert categories.list_for(old.id)["status"] == "pending"
    assert episodes._conn.execute("SELECT cursor FROM memory_category_scan WHERE id=1").fetchone()[0] == before
    assert categories.run(provider, source_ids=[]).ok
    assert len(provider.calls) == 1


def test_explicit_upload_selection_is_bounded_and_skips_unavailable_sources(tmp_path):
    episodes, categories = setup(tmp_path)
    item = source(episodes)
    episodes.ignore(item.id)
    provider = Local()
    assert categories.run(provider, source_ids=[item.id, "does-not-exist"]).ok
    assert provider.calls == []
    with pytest.raises(ValueError):
        categories.run(provider, source_ids=["source"] * 201)
    with pytest.raises(ValueError):
        categories.run(provider, source_ids=[False])


def test_category_analysis_uses_real_provider_json_budget_without_network(tmp_path, monkeypatch):
    import httpx
    from icarus_memory.providers import OpenAICompatible
    episodes, categories = setup(tmp_path)
    item = source(episodes)
    requests = []
    def reply(request):
        payload = json.loads(request.content)
        requests.append(payload)
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps({"categories": [{"category_id": "work", "block_id": "B1"}], "entities": []})}}]})
    provider = OpenAICompatible("synthetic-local", api_key="synthetic", base_url="http://127.0.0.1:11434/v1")
    monkeypatch.setattr(provider, "_client", lambda timeout: httpx.Client(transport=httpx.MockTransport(reply)))
    assert categories.run(provider, source_ids=[item.id]).ok
    assert requests[0]["max_tokens"] == 1200
    schema = requests[0]["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["categories"]["maxItems"] == 12
    assert schema["properties"]["entities"]["maxItems"] == 8
    assert categories.list_for(item.id)["status"] == "complete"


class RemoteQuoteProvider:
    is_local = False
    is_remote = True
    entity_anchor_mode = "block_quote"
    name = "chatgpt"
    model = "synthetic-chatgpt"

    def __init__(self, result_for_call):
        self.result_for_call = result_for_call
        self.calls = []

    def available(self):
        return True

    def complete_json(self, messages, *, max_tokens, schema):
        payload = json.loads(messages[-1]["content"])
        self.calls.append((payload, schema))
        result = self.result_for_call(payload, len(self.calls))
        return Reply(text=json.dumps(result))


def run_remote(categories, item, provider, permitted=lambda: True):
    from icarus_memory.source_processing_policy import ExplicitSourcePolicy
    policy = ExplicitSourcePolicy(provider, item.id, lambda _episode: permitted())
    return categories.run(provider, source_ids=[item.id], permitted=permitted,
                          processing_policy=lambda _snapshot: policy)


def test_chatgpt_categories_split_more_than_twenty_four_blocks_and_resolve_global_offsets(tmp_path):
    episodes, categories = setup(tmp_path)
    body = "Erster Abschnitt 🐦.\n\n" + "\n\n".join(
        f"Person{i:02d} arbeitet an Projekt{i:02d}." for i in range(25))
    item = source(episodes, body)

    def answer(payload, _number):
        entity = next(block for block in payload["blocks"] if "Person23" in block["text"] or "Person00" in block["text"])
        name = "Person23" if "Person23" in entity["text"] else "Person00"
        return {"categories": [], "entities": [
            {"kind": "person", "name": name, "block_id": entity["block_id"],
             "occurrence": 1, "role": "mentioned"}]}

    provider = RemoteQuoteProvider(answer)
    result = run_remote(categories, item, provider)

    assert result.ok
    assert len(provider.calls) == 2
    assert all(len(payload["blocks"]) <= 24 for payload, _schema in provider.calls)
    assert all(sum(len(block["text"]) for block in payload["blocks"]) <= 12_000
               for payload, _schema in provider.calls)
    assert all("start" not in block and "end" not in block
               for payload, _schema in provider.calls for block in payload["blocks"])
    entities = categories.list_for(item.id)["entities"]
    expected = {"Person00": body.index("Person00"), "Person23": body.index("Person23")}
    assert {entity["name"]: entity["start"] for entity in entities} == expected


def test_chatgpt_categories_split_long_single_paragraph_without_losing_global_offset(tmp_path):
    episodes, categories = setup(tmp_path)
    body = "🐦 " + ("ein synthetisches Wort " * 260) + "Ada arbeitet an Atlas."
    item = source(episodes, body)

    def answer(payload, _number):
        for block in payload["blocks"]:
            if "Ada" in block["text"]:
                return {"categories": [], "entities": [{
                    "kind": "person", "name": "Ada", "block_id": block["block_id"],
                    "occurrence": 1, "role": "mentioned"}]}
        return {"categories": [], "entities": []}

    provider = RemoteQuoteProvider(answer)
    result = run_remote(categories, item, provider)

    assert result.ok
    assert len(provider.calls) == 1
    payload, schema = provider.calls[0]
    assert len(payload["blocks"]) >= 2
    assert all(len(block["text"]) <= 4_000 for block in payload["blocks"])
    assert schema["properties"]["entities"]["items"]["properties"]["occurrence"] == {
        "type": "integer", "minimum": 1}
    ada = categories.list_for(item.id)["entities"]
    assert [(entity["name"], entity["start"]) for entity in ada] == [("Ada", body.index("Ada"))]


def test_chatgpt_remote_fragment_never_exceeds_exact_four_thousand_character_limit(tmp_path):
    episodes, categories = setup(tmp_path)
    body = ("x" * 3_999) + " Ada"
    item = source(episodes, body)
    provider = RemoteQuoteProvider(lambda payload, _number: {
        "categories": [], "entities": [{"kind": "person", "name": "Ada",
            "block_id": next(block["block_id"] for block in payload["blocks"] if "Ada" in block["text"]),
            "occurrence": 1, "role": "mentioned"}]})

    assert run_remote(categories, item, provider).ok
    assert all(len(block["text"]) <= 4_000 for payload, _schema in provider.calls
               for block in payload["blocks"])
    assert categories.list_for(item.id)["entities"][0]["start"] == body.index("Ada")


def test_chatgpt_entity_aggregation_across_sections_exceeds_per_call_limit(tmp_path):
    from icarus_memory.memory_categories import MAX_REMOTE_ENTITIES, MAX_REMOTE_TOPICS

    episodes, categories = setup(tmp_path)
    body = "\n\n".join(f"Person{i:02d} arbeitet an Atlas{i:02d}." for i in range(25))
    item = source(episodes, body)

    def answer(payload, _number):
        entities = []
        for block in payload["blocks"]:
            match = re.search(r"Person\d+", block["text"])
            if match and len(entities) < 8:
                entities.append({"kind": "person", "name": match[0], "block_id": block["block_id"],
                                 "occurrence": 1, "role": "mentioned"})
        return {"categories": [], "entities": entities}

    provider = RemoteQuoteProvider(answer)
    assert run_remote(categories, item, provider).ok
    assert len(categories.list_for(item.id)["entities"]) > 8
    assert MAX_REMOTE_ENTITIES == 128 and MAX_REMOTE_TOPICS == 192


def test_chatgpt_aggregate_entity_cap_fails_atomically(monkeypatch, tmp_path):
    import icarus_memory.memory_categories as category_module

    episodes, categories = setup(tmp_path)
    body = "\n\n".join(f"Person{i:02d} arbeitet an Atlas{i:02d}." for i in range(25))
    item = source(episodes, body)

    def answer(payload, _number):
        entities = []
        for block in payload["blocks"]:
            match = re.search(r"Person\d+", block["text"])
            if match and len(entities) < 8:
                entities.append({"kind": "person", "name": match[0], "block_id": block["block_id"],
                                 "occurrence": 1, "role": "mentioned"})
        return {"categories": [], "entities": entities}

    monkeypatch.setattr(category_module, "MAX_REMOTE_ENTITIES", 8)
    provider = RemoteQuoteProvider(answer)
    assert not run_remote(categories, item, provider).ok
    assert categories.list_for(item.id)["entities"] == []


@pytest.mark.parametrize("body,tags", [
    ("x" * 60_001, []),
    ("\n\n".join(f"Absatz {i}" for i in range(121)), []),
    ("Kurzer Originaltext", ["source:truncated"]),
])
def test_chatgpt_hard_source_caps_defer_without_request(tmp_path, body, tags):
    episodes, categories = setup(tmp_path)
    item = source(episodes, body, tags=tags)
    provider = RemoteQuoteProvider(lambda _payload, _number: {"categories": [], "entities": []})

    run_remote(categories, item, provider)

    assert provider.calls == []
    assert categories.list_for(item.id)["status"] == "deferred"


def test_chatgpt_repeated_exact_name_requires_and_uses_explicit_occurrence(tmp_path):
    episodes, categories = setup(tmp_path)
    item = source(episodes, "Ada sagte Hallo. Ada sagte Auf Wiedersehen.")
    provider = RemoteQuoteProvider(lambda _payload, _number: {
        "categories": [], "entities": [{"kind": "person", "name": "Ada", "block_id": "B1",
                                         "occurrence": 2, "role": "mentioned"}]})

    assert run_remote(categories, item, provider).ok
    entity = categories.list_for(item.id)["entities"][0]
    assert entity["start"] == item.body.rindex("Ada")


def test_chatgpt_encoded_sender_name_remains_a_separate_mention(tmp_path):
    episodes, categories = setup(tmp_path)
    item, _ = episodes.record(EpisodeKind.MESSAGE, "Arbeit", "Jörg prüft Atlas.",
        Provenance(SourceType.EMAIL, source_ref="synthetic-rfc2047"),
        participants=["=?UTF-8?Q?J=C3=B6rg?= <joerg@example.org>"])
    provider = RemoteQuoteProvider(lambda _payload, _number: {
        "categories": [], "entities": [{"kind": "person", "name": "Jörg", "block_id": "B1",
                                         "occurrence": 1, "role": "mentioned"}]})

    assert run_remote(categories, item, provider).ok
    assert categories.list_for(item.id)["entities"][0]["role"] == "mentioned"


def test_chatgpt_duplicate_name_without_occurrence_is_a_safe_validation_gap(tmp_path):
    from icarus_memory.memory_categories import SourceValidationError
    from icarus_memory.memory_categories import _interpret, _DEFAULTS
    from icarus_memory.source_processing_policy import ExplicitSourcePolicy

    episodes, _categories = setup(tmp_path)
    item = source(episodes, "Ada sagte Hallo. Ada sagte Auf Wiedersehen.")
    provider = RemoteQuoteProvider(lambda _payload, _number: {
        "categories": [], "entities": [{"kind": "person", "name": "Ada", "block_id": "B1",
                                         "role": "mentioned"}]})
    policy = ExplicitSourcePolicy(provider, item.id, lambda _episode: True)
    taxonomy = [{"id": row[0], "label": row[1], "description": row[2]} for row in _DEFAULTS]

    with pytest.raises(SourceValidationError) as exc:
        _interpret(provider, item, taxonomy, policy=policy)
    assert exc.value.reason == "entity_ambiguous"


def test_later_chatgpt_section_validation_failure_commits_no_partial_topics_or_entities(tmp_path):
    episodes, categories = setup(tmp_path)
    body = "\n\n".join(["Ada works on Atlas."] + [f"Block {i} is synthetic." for i in range(24)])
    item = source(episodes, body)

    def answer(payload, call):
        if call == 1:
            return {"categories": [{"category_id": "work", "block_id": "B1"}], "entities": [{
                "kind": "person", "name": "Ada", "block_id": "B1", "occurrence": 1,
                "role": "mentioned"}]}
        return {"categories": [{"category_id": "work", "block_id": "B1"}], "entities": [{
            "kind": "person", "name": "Missing Name", "block_id": "B1", "occurrence": 1,
            "role": "mentioned"}]}

    provider = RemoteQuoteProvider(answer)
    result = run_remote(categories, item, provider)

    assert not result.ok
    assert len(provider.calls) == 2
    assert categories.list_for(item.id)["categories"] == []
    assert categories.list_for(item.id)["entities"] == []
    assert provider.calls[0][0]["blocks"][0]["text"] == "Ada works on Atlas."


def test_chatgpt_rechecks_permission_before_each_category_section(tmp_path):
    episodes, categories = setup(tmp_path)
    body = "\n\n".join(f"Block {i} is synthetic." for i in range(25))
    item = source(episodes, body)
    permission = {"granted": True}

    def answer(payload, _number):
        permission["granted"] = False
        return {"categories": [], "entities": []}

    provider = RemoteQuoteProvider(answer)
    run_remote(categories, item, provider, permitted=lambda: permission["granted"])

    assert len(provider.calls) == 1
    assert categories.list_for(item.id)["categories"] == []
    assert categories.list_for(item.id)["entities"] == []
