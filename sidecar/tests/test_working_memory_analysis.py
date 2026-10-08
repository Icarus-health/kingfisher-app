import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from icarus_memory.providers import ProviderError, Reply
from icarus_memory.working_memory_analysis import (
    MAX_BLOCKS, MAX_BLOCK_CHARS, MAX_BODY_CHARS, UnsupportedSource, interpret,
)
from icarus_memory.working_memory_store import MAX_SOURCE_CHARS


class LocalReader:
    is_local = True

    def __init__(self, output=None):
        self.calls = []
        self.output = output

    def complete_json(self, messages, *, max_tokens, schema):
        self.calls.append((messages, max_tokens, schema))
        return Reply(text=json.dumps(self.output) if self.output is not None else '{"items":[]}')


class Faktenleser(LocalReader):
    """Ordnet jeden Block als `fact` ein, wie viele es auch sind."""

    def complete_json(self, messages, *, max_tokens, schema):
        self.calls.append((messages, max_tokens, schema))
        bloecke = json.loads(messages[1]["content"])["blocks"]
        return Reply(text=json.dumps({"items": [{"block_id": b["block_id"], "kind": "fact"} for b in bloecke]}))


def episode(body, **kwargs):
    data = dict(body=body, title="Besprechung", occurred_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
                recorded_at=datetime(2026, 9, 21, tzinfo=timezone.utc), kind="message",
                provenance=SimpleNamespace(to_dict=lambda: {"source_type": "email", "source_ref": "mail:123"}),
                participants=["Ada"], project_id="P1", tags=[])
    data.update(kwargs)
    return SimpleNamespace(**data)


def test_classifies_every_original_paragraph_once_with_offsets_and_context():
    body = "Bitte morgen prüfen.\n\nWenn es klappt, melde ich mich.\n\nAlter Verlauf: erledigt."
    reader = LocalReader({"items": [
        {"block_id": "B1", "kind": "request"},
        {"block_id": "B2", "kind": "conditional"},
        {"block_id": "B3", "kind": "irrelevant"},
    ]})
    result = interpret(reader, episode(body))
    assert result == [
        {"start": 0, "end": 20, "kind": "request"},
        {"start": 22, "end": 53, "kind": "conditional"},
    ]
    messages, max_tokens, schema = reader.calls[0]
    assert max_tokens <= 1200
    assert schema["additionalProperties"] is False
    payload = json.loads(messages[1]["content"])
    assert payload["source"]["title"] == "Besprechung"
    assert payload["source"]["occurred_at"] == "2026-09-20T00:00:00+00:00"
    assert payload["source"]["provenance"]["source_ref"] == "mail:123"
    assert [block["text"] for block in payload["blocks"]] == [
        "Bitte morgen prüfen.", "Wenn es klappt, melde ich mich.", "Alter Verlauf: erledigt."]
    assert "Bitte" in messages[0]["content"]


def test_empty_body_never_calls_model():
    reader = LocalReader()
    assert interpret(reader, episode(" \n\t ")) == []
    assert reader.calls == []


@pytest.mark.parametrize("body,tags", [
    ("x" * (MAX_SOURCE_CHARS + 1), []),
    ("short", ["source:truncated"]),
])
def test_over_budget_or_truncated_sources_fail_before_model(body, tags):
    reader = LocalReader()
    with pytest.raises(UnsupportedSource):
        interpret(reader, episode(body, tags=tags))
    assert reader.calls == []


def test_die_alte_grenze_von_12000_zeichen_gilt_nicht_mehr():
    """Eine Quelle über 12.000 Zeichen wird eingeordnet, in Abschnitten; bis zur Obergrenze, nicht darüber."""
    reader = Faktenleser()
    absaetze = [f"Absatz {n}: " + "wort " * 60 for n in range(60)]
    body = "\n\n".join(absaetze)
    assert len(body) > MAX_BODY_CHARS
    items = interpret(reader, episode(body))
    assert len(reader.calls) > 1, "mehrere Abschnitte, mehrere Aufrufe"
    assert len(items) == len(absaetze), "jeder Absatz genau einmal, trotz Überlappung"
    assert all(body[i["start"]:i["end"]].startswith("Absatz") for i in items)


@pytest.mark.parametrize("body", [
    ("a\n\n" * MAX_BLOCKS) + "b",
    "x" * (MAX_BLOCK_CHARS + 1),
])
def test_zu_viele_oder_zu_grosse_absaetze_gehen_in_abschnitten_durch(body):
    reader = Faktenleser()
    items = interpret(reader, episode(body))
    assert reader.calls and items
    assert all(i["end"] <= len(body) and body[i["start"]:i["end"]].strip() for i in items)


@pytest.mark.parametrize("output", [
    {"items": []},
    {"items": [{"block_id": "B2", "kind": "fact"}]},
    {"items": [{"block_id": "B1", "kind": "fact"}, {"block_id": "B1", "kind": "fact"}]},
    {"items": [{"block_id": "B1", "kind": "invented"}]},
    {"items": [{"block_id": "B1", "kind": "fact", "approved": True}]},
    {"items": [{"block_id": "B1", "kind": "fact"}], "other": True},
])
def test_invalid_classification_rejects_entire_result(output):
    with pytest.raises(ProviderError):
        interpret(LocalReader(output), episode("A fact."))


def test_malformed_tool_call_and_nonlocal_provider_fail_closed():
    for reply in (Reply(text="not json"), Reply(text='{"items":[{"block_id":"B1","kind":"fact"}]}',
                                              tool_calls=[{"name": "write"}])):
        reader = LocalReader()
        reader.complete_json = lambda *args, **kwargs: reply
        with pytest.raises(ProviderError):
            interpret(reader, episode("A fact."))
    reader = LocalReader()
    reader.is_local = False
    with pytest.raises(ProviderError):
        interpret(reader, episode("A fact."))


def test_complete_fallback_only_without_json_capability():
    class Legacy:
        is_local = True

        def complete(self, messages, tools):
            assert tools == []
            return Reply(text='{"items":[{"block_id":"B1","kind":"status"}]}')

    assert interpret(Legacy(), episode("Done.")) == [{"start": 0, "end": 5, "kind": "status"}]

    class Failing(LocalReader):
        def complete_json(self, *args, **kwargs):
            raise ProviderError("offline")

        def complete(self, *args):
            pytest.fail("Must not fall back after JSON failure")

    with pytest.raises(ProviderError, match="offline"):
        interpret(Failing(), episode("Done."))


def test_conditional_clause_across_blank_line_stays_one_block():
    reader = LocalReader({"items": [{"block_id": "B1", "kind": "conditional"}]})
    body = "Wenn die Lieferung kommt,\n\ndann rufe ich an."
    assert interpret(reader, episode(body)) == [{"start": 0, "end": len(body), "kind": "conditional"}]


def test_metadata_budget_fails_without_truncating_source_context():
    reader = LocalReader()
    with pytest.raises(UnsupportedSource):
        interpret(reader, episode("A fact.", title="x" * 5000))
    assert reader.calls == []


def test_classification_instruction_distinguishes_personal_requests_and_source_speaker_commitments():
    reader = LocalReader({"items": [{"block_id": "B1", "kind": "commitment"}]})
    result = interpret(reader, episode("Ich sende Ihnen die Unterlagen bis Freitag."))

    assert result == [{"start": 0, "end": len("Ich sende Ihnen die Unterlagen bis Freitag."), "kind": "commitment"}]
    instruction = reader.calls[0][0][0]["content"].casefold()
    assert "werbung" in instruction and "bewerten" in instruction
    assert "signatur" in instruction and "disclaimer" in instruction
    assert "sprecher" in instruction and "niemals automatisch" in instruction
