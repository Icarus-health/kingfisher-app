"""Abdeckung wird an Eingaben gemessen, nicht aus einem leeren Modelltext geraten."""
import json
from threading import RLock

import pytest

from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import ProposalKind, ProposalStore
from icarus_memory.providers import Reply
from icarus_memory.task_detection import TaskDetector


class Reader:
    is_local = True
    name = "synthetic"
    model = "bounded-reader"

    def __init__(self):
        self.inputs = []
        self.hook = lambda: None

    def complete(self, messages, tools):
        assert tools == []
        payload = json.loads(messages[1]["content"])
        body = payload["body"]
        if 'candidates' in payload:
            return Reply(text=json.dumps({'reviews': [
                {'id': item['id'], 'kind': 'request_to_recipient', 'title_supported': True}
                for item in payload['candidates']]}))
        self.inputs.append(body)
        self.hook()
        return Reply(text=json.dumps({"items": [
            {"title": line, "quote": line}
            for line in body.splitlines() if line.startswith("Bitte ")
        ]}))


@pytest.fixture
def memory(tmp_path):
    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    proposals = ProposalStore(tmp_path / "proposals.sqlite3")
    reader = Reader()
    yield episodes, proposals, reader
    episodes.close()
    proposals.close()


def put(episodes, body):
    return episodes.record(EpisodeKind.MESSAGE, "Fiktive Anfragen", body,
                           Provenance(source_type=SourceType.EMAIL), source_key="synthetic:one")[0]


def test_fourth_request_is_not_silently_dropped(memory):
    episodes, proposals, reader = memory
    put(episodes, "\n".join(f"Bitte Aufgabe {i} prüfen." for i in range(4)))
    report = TaskDetector(episodes, proposals, reader, RLock()).run(with_model=True)
    assert report.proposed == 4


def test_source_beyond_old_cutoff_resumes_after_restart(memory, tmp_path):
    episodes, proposals, reader = memory
    # Still exceeds the extraction window, while fitting the complete-mail review budget.
    body = "Hintergrund ohne Auftrag.\n" * 600 + "Bitte den letzten Entwurf prüfen."
    episode = put(episodes, body)
    detector = TaskDetector(episodes, proposals, reader, RLock())
    report = detector.run(with_model=True, limit=1)
    assert not proposals.task_analysis_done(episode.id, episode.digest)
    assert report.analyzed == 0
    other = ProposalStore(tmp_path / "proposals.sqlite3")
    try:
        for _ in range(20):
            TaskDetector(episodes, other, reader, RLock()).run(with_model=True, limit=1)
            if other.task_analysis_done(episode.id, episode.digest):
                break
        assert other.task_analysis_done(episode.id, episode.digest)
        assert any(p.statement == "Bitte den letzten Entwurf prüfen." for p in other.pending(ProposalKind.TASK))
        assert max(map(len, reader.inputs)) <= 8000
    finally:
        other.close()


def test_mail_over_complete_review_budget_is_not_certified(memory):
    episodes, proposals, reader = memory
    episode = put(episodes, 'Hintergrund ohne Auftrag.\n' * 1000 + 'Bitte den letzten Entwurf prüfen.')
    detector = TaskDetector(episodes, proposals, reader, RLock())
    for _ in range(10):
        detector.run(with_model=True, limit=1)
    assert not proposals.task_analysis_done(episode.id, episode.digest)
    assert proposals.pending(ProposalKind.TASK) == []


def test_unknown_authority_field_rejects_entire_output(memory):
    episodes, proposals, reader = memory
    episode = put(episodes, "Bitte den Entwurf prüfen.")
    reader.complete = lambda *args: Reply(text=json.dumps({
        "items": [{"title": "Prüfen", "quote": "Bitte den Entwurf prüfen.", "approved": True}]
    }))
    report = TaskDetector(episodes, proposals, reader, RLock()).run(with_model=True)
    assert report.failed == 1
    assert proposals.pending() == []
    assert not proposals.task_analysis_done(episode.id, episode.digest)


def test_full_output_budget_is_not_semantic_completion(memory):
    episodes, proposals, reader = memory
    episode = put(episodes, "\n".join(f"Bitte Aufgabe {i} prüfen." for i in range(32)))
    TaskDetector(episodes, proposals, reader, RLock()).run(with_model=True)
    assert not proposals.task_analysis_done(episode.id, episode.digest)


def test_revocation_discards_even_uncited_input(memory):
    episodes, proposals, reader = memory
    episode = put(episodes, "Bitte den Entwurf prüfen.")
    reader.hook = lambda: episodes.ignore(episode.id)
    TaskDetector(episodes, proposals, reader, RLock()).run(with_model=True)
    assert proposals.pending() == []
    assert not proposals.task_analysis_done(episode.id, episode.digest)


def test_expired_lease_rejects_old_worker_and_new_worker_commits_once(memory, tmp_path):
    episodes, proposals, reader = memory
    episode = put(episodes, "Bitte den Entwurf prüfen.")
    other = ProposalStore(tmp_path / "proposals.sqlite3")
    try:
        old = proposals.memory_analysis.acquire(episode, reader, at=10, lease_seconds=5)
        assert other.memory_analysis.acquire(episode, reader, at=12) is None
        new = other.memory_analysis.acquire(episode, reader, at=16)
        items = [{"title": "Prüfen", "quote": episode.body}]
        assert proposals.memory_analysis.finish(old, items, len(episode.body), proposed_by="test", at=17) is None
        assert other.memory_analysis.finish(new, items, len(episode.body), proposed_by="test", at=17) == (1, True)
        assert other.memory_analysis.finish(new, items, len(episode.body), proposed_by="test", at=18) is None
        assert len(proposals.pending()) == 1
    finally:
        other.close()


def test_changed_model_has_separate_processing_but_preserves_rejection(memory):
    episodes, proposals, reader = memory
    episode = put(episodes, "Bitte den Entwurf prüfen.")
    detector = TaskDetector(episodes, proposals, reader, RLock())
    detector.run(with_model=True)
    candidate = proposals.pending()[0]
    proposals.reject(candidate.id)
    reader.model = "new-model"
    detector.run(with_model=True)
    detector.run(with_model=True)
    assert len(reader.inputs) == 2
    assert proposals.pending() == []
    assert proposals.memory_analysis.snapshot(episode.id)["state"] == "completed"


def test_other_background_source_waits_for_active_inference(memory):
    episodes, proposals, reader = memory
    first = put(episodes, 'Bitte den ersten Entwurf prüfen.')
    second = put(episodes, 'Bitte den zweiten Entwurf prüfen.')
    running = proposals.memory_analysis.acquire(first, reader, at=10)
    assert running is not None
    assert proposals.memory_analysis.acquire(second, reader, at=11) is None
    proposals.memory_analysis.finish(running, [], len(first.body), proposed_by='test', at=12)
    assert proposals.memory_analysis.acquire(second, reader, at=13) is not None


def test_worker_uses_bounded_json_when_provider_supports_it(memory):
    episodes, proposals, reader = memory
    put(episodes, 'Bitte den Entwurf prüfen.')
    reader.complete = lambda *args: pytest.fail('Unbegrenzter Aufruf statt JSON-Budget')
    def bounded(messages, *, max_tokens, schema):
        assert max_tokens <= 1200
        assert schema['additionalProperties'] is False
        return Reply(text='{"items":[]}')
    reader.complete_json = bounded
    assert TaskDetector(episodes, proposals, reader, RLock()).run(with_model=True).analyzed == 1


def test_archived_during_model_call_discards_result(memory):
    from icarus_memory.episodes import EpisodeState
    episodes, proposals, reader = memory
    episode = put(episodes, 'Bitte den Entwurf prüfen.')
    def archive():
        changed = episodes.get(episode.id)
        changed.state = EpisodeState.ARCHIVED
        episodes._put(changed)
    reader.hook = archive
    TaskDetector(episodes, proposals, reader, RLock()).run(with_model=True)
    assert proposals.pending() == []
    assert not proposals.task_analysis_done(episode.id, episode.digest)
