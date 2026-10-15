import json
import pytest
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.providers import Reply


class Local:
    is_local = True
    name = "synthetic"
    model = "synthetic"

    def complete_json(self, messages, *, max_tokens, schema):
        body = "".join(block["text"] for block in json.loads(messages[-1]["content"])["blocks"])
        names = ["Acme Team", "Anna Kranz", "Jane Doe"]
        entities = []
        for name in names:
            start = body.find(name)
            if start >= 0:
                entities.append({"kind": "person", "name": name, "start": start,
                                 "end": start + len(name), "role": "mentioned"})
        return Reply(text=json.dumps({"categories": [], "entities": entities}))


def setup(tmp_path):
    from icarus_memory.memory_categories import Categories, migrate, verify

    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    if not episodes._conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='memory_category_scan'").fetchone():
        with episodes.transaction():
            migrate(episodes._conn)
    verify(episodes._conn)
    return episodes, Categories(episodes)


def email(episodes, body="Acme Team wrote. Anna Kranz replies.", source_key="mail:test:1", participants=None):
    episode, _ = episodes.record(
        EpisodeKind.MESSAGE, "Synthetic message", body,
        Provenance(SourceType.EMAIL, source_ref="synthetic-mail"),
        occurred_at=datetime(2026, 10, 7, tzinfo=timezone.utc),
        participants=participants or ["Acme Team <info@example.org>"], source_key=source_key,
    )
    episodes.advance_source_head(source_key, None, episode.id)
    return episode


def test_people_mentions_endpoint_lists_only_source_grounded_non_generic_names(tmp_path):
    from icarus_memory.mail_intake_routes import register

    episodes, categories = setup(tmp_path)
    item = email(episodes)
    assert categories.run(Local(), source_ids=[item.id]).ok

    app = FastAPI()
    app.state.episodes = episodes
    register(app, [], lambda: tmp_path, lambda *_: None)
    response = TestClient(app).get("/api/v1/memory/people/mentions?limit=50")

    assert response.status_code == 200
    result = response.json()
    assert result["scanned_sources"] == 1
    assert result["total_in_scanned_sources"] == 1
    assert result["limited"] is False
    mention = result["items"][0]
    assert {key: mention[key] for key in ("name", "quote", "role", "episode_id", "title", "source_type")} == {
        "name": "Anna Kranz", "quote": "Anna Kranz", "role": "mentioned",
        "episode_id": item.id, "title": "Synthetic message", "source_type": "email",
    }
    assert datetime.fromisoformat(mention["occurred_at"]) == item.occurred_at
    assert datetime.fromisoformat(mention["recorded_at"]) == item.recorded_at


def test_people_mentions_hide_changed_and_withdrawn_sources(tmp_path):
    episodes, categories = setup(tmp_path)
    item = email(episodes)
    assert categories.run(Local(), source_ids=[item.id]).ok
    assert categories.person_mentions()["items"]

    changed = episodes.get(item.id)
    changed.body = "Acme Team wrote. A different person replies."
    episodes._put(changed)
    assert categories.person_mentions()["items"] == []

    # Recompute against the edited original, then withdraw it. Neither saved
    # span should survive the current-source projection.
    assert categories.run(Local(), source_ids=[item.id]).ok
    episodes.ignore(item.id)
    result = categories.person_mentions()
    assert result["items"] == []
    assert result["scanned_sources"] == 0


def test_named_human_in_marketplace_mail_body_remains_a_source_hint(tmp_path):
    episodes, categories = setup(tmp_path)
    item = email(episodes, body="Jane Doe sent a message through the marketplace.",
                 participants=["Marketplace <marketplace-messages@market.example>"])
    assert categories.run(Local(), source_ids=[item.id]).ok

    assert [entry["name"] for entry in categories.person_mentions()["items"]] == ["Jane Doe"]


def test_people_mentions_reports_bounded_scan_and_rejects_unbounded_limit(tmp_path):
    import pytest
    from icarus_memory.memory_categories import MAX_PERSON_MENTION_SCAN, MAX_PERSON_MENTIONS

    episodes, categories = setup(tmp_path)
    for index in range(MAX_PERSON_MENTION_SCAN + 1):
        episodes.record(EpisodeKind.MESSAGE, f"Message {index}", f"Synthetic source {index}.",
                        Provenance(SourceType.EMAIL, source_ref=f"mail:{index}"))

    result = categories.person_mentions()

    assert result["scanned_sources"] == MAX_PERSON_MENTION_SCAN
    assert result["limited"] is True
    with pytest.raises(ValueError):
        categories.person_mentions(MAX_PERSON_MENTIONS + 1)


@pytest.mark.parametrize(('literal','label','person'), [
    ('S&ouml;ren Kube', 'Sören Kube', True),
    ('Ren&#233;e M&#252;ller', 'Renée Müller', True),
    ('Anna &amp; Ben', 'Anna & Ben', True),
    ('Beispiel Gm&#98;H', 'Beispiel GmbH', False),
    ('Kundenserv&#105;ce', 'Kundenservice', False),
])
def test_encoded_person_labels_are_readable_without_changing_original_evidence(tmp_path, literal, label, person):
    episodes, categories = setup(tmp_path)
    item = email(episodes, body=literal+' schreibt.', participants=['Maildienst <noreply@example.org>'])
    before = episodes.get(item.id).to_dict()
    class Names:
        is_local = True
        name = model = 'synthetic'
        def complete_json(self, messages, **kwargs):
            return Reply(text=json.dumps({'categories':[], 'entities':[
                {'kind':'person','name':literal,'start':0,'end':len(literal),'role':'mentioned'}]}))
    assert categories.run(Names(), source_ids=[item.id]).ok
    entities = categories.list_for(item.id)['entities']
    mentions = categories.person_mentions()['items']
    assert [entity['name'] for entity in entities] == ([label] if person else [])
    assert [mention['name'] for mention in mentions] == ([label] if person else [])
    if person:
        assert entities[0]['quote'] == mentions[0]['quote'] == literal
        assert item.body[entities[0]['start']:entities[0]['end']] == literal
    assert episodes.get(item.id).to_dict() == before
    episodes.ignore(item.id)
    assert categories.person_mentions()['items'] == []


def test_encoded_generic_sender_label_cannot_become_a_person_after_decoding(tmp_path):
    episodes, categories = setup(tmp_path)
    item = email(episodes, body='Acme &amp; Co schreibt.', participants=['"Acme &amp; Co" <info@example.org>'])
    class Sender:
        is_local = True
        name = model = 'synthetic'
        def complete_json(self, messages, **kwargs):
            return Reply(text=json.dumps({'categories':[], 'entities':[
                {'kind':'person','name':'Acme &amp; Co','start':0,'end':13,'role':'mentioned'}]}))
    assert categories.run(Sender(), source_ids=[item.id]).ok
    assert categories.list_for(item.id)['entities'] == []
    assert categories.person_mentions()['items'] == []
