"""Synthetic state tests for source-current knowledge clarification questions."""
from datetime import timedelta

import pytest
from fastapi import HTTPException

from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType, now
from icarus_memory.memory_questions import list_questions, resolve_question
from icarus_memory.proposals import Evidence, ProposalState
from tests.test_context_identity import AT, core
from tests.test_source_answers_http import _api
from tests.test_conversation_retraction import _close_app


def _runtime(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    return app, client


def _close_runtime(app, client):
    client.close()
    # These two stores belong to the function-scoped `core` fixture.
    app.state.episodes = app.state.claims = None
    _close_app(app)


def _candidate(app, subject_ref, quote, value, *, proposed_by="synthetic",
               depends_on=None, valid_from=None, valid_until=None):
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, "Synthetic source title", quote,
        Provenance(source_type=SourceType.EMAIL, source_ref=f"synthetic:{subject_ref}:{value}"),
        at=AT,
    )
    proposal, _ = app.state.knowledge_service.propose(
        subject_ref=subject_ref, predicate="synthetic_single_value", value=value,
        statement=f"Alex Winter has {value}.", rationale="Synthetic evidence",
        evidence=[Evidence(episode.id, quote, episode.digest)], proposed_by=proposed_by,
        depends_on=depends_on, valid_from=valid_from, valid_until=valid_until, at=AT,
    )
    return proposal, episode


def _active_claim(app, subject_ref, quote="Original synthetic fact", value="old"):
    proposal, episode = _candidate(app, subject_ref, quote, value)
    claim = app.state.knowledge_service.accept(proposal.id, supersedes=[], at=AT)
    return claim, episode


def _question(app, questions, candidate_id=None):
    return next(question for question in questions
                if candidate_id is None or candidate_id in {item["id"] for item in question["candidates"]})


def test_replaced_candidate_source_is_not_confirmable(core, tmp_path, monkeypatch):
    app, client = _runtime(core, tmp_path, monkeypatch)
    try:
        _active_claim(app, 'person:alex-opaque')
        provenance = Provenance(source_type=SourceType.EMAIL, source_ref='synthetic:versioned')
        source, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Versioned', 'Original value.',
                                               provenance, source_key='synthetic:versioned')
        app.state.episodes.advance_source_head('synthetic:versioned', None, source.id)
        candidate, _ = app.state.knowledge_service.propose(subject_ref='person:alex-opaque',
            predicate='synthetic_single_value', value='new', statement='A new value.', rationale='Synthetic',
            evidence=[Evidence(source.id, source.body, source.digest)])
        question = _question(app, list_questions(app), candidate.id)
        replacement, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Versioned', 'A replacement.', provenance,
                                                    source_key='synthetic:versioned')
        app.state.episodes.advance_source_head('synthetic:versioned', source.id, replacement.id)
        assert list_questions(app) == []
        with pytest.raises(HTTPException) as error:
            resolve_question(app, question['id'], stand=question['stand'], proposal_id=candidate.id)
        assert error.value.status_code == 409
    finally:
        _close_runtime(app, client)


def test_questions_include_only_current_exact_sources_with_unknown_occurred_time(
    core, tmp_path, monkeypatch
):
    app, client = _runtime(core, tmp_path, monkeypatch)
    try:
        claim, _ = _active_claim(app, "person:alex-opaque")
        candidate, source = _candidate(app, "person:alex-opaque", "Quoted source wording.", "new")
        questions = list_questions(app)
        question = _question(app, questions, candidate.id)

        assert question["subject_ref"] == "person:alex-opaque"
        assert question["stand"] and len(question["stand"]) == 64
        assert any(item["id"] == claim.id for item in question["active_claims"])
        presented = next(item for item in question["candidates"] if item["id"] == candidate.id)
        assert presented["sources"] == [{
            "episode_id": source.id,
            "title": "Synthetic source title",
            "quote": "Quoted source wording.",
            "occurred_at": None,
            "recorded_at": AT.astimezone().isoformat(),
        }]
        assert "PRIVATE-REGISTRY-LABEL" not in str(questions)
    finally:
        _close_runtime(app, client)


def test_resolve_chosen_candidate_accepts_and_supersedes_listed_current_claim(
    core, tmp_path, monkeypatch
):
    app, client = _runtime(core, tmp_path, monkeypatch)
    try:
        old, _ = _active_claim(app, "person:alex-opaque")
        chosen, _ = _candidate(app, "person:alex-opaque", "Choose this synthetic source.", "new")
        competing, _ = _candidate(app, "person:alex-opaque", "Other synthetic source.", "other")
        question = _question(app, list_questions(app), chosen.id)

        result = resolve_question(app, question["id"], stand=question["stand"], proposal_id=chosen.id)

        assert result["decision"] == "accepted"
        assert result["claim"]["proposal_id"] == chosen.id
        assert result["claim"]["supersedes"] == [old.id]
        assert app.state.claims.get(old.id).status.value == "superseded"
        assert app.state.proposals.get(competing.id).state is ProposalState.SUPERSEDED
    finally:
        _close_runtime(app, client)


def test_resolve_keep_existing_rejects_pending_without_creating_a_claim(
    core, tmp_path, monkeypatch
):
    app, client = _runtime(core, tmp_path, monkeypatch)
    try:
        old, _ = _active_claim(app, "person:alex-opaque")
        candidate, _ = _candidate(app, "person:alex-opaque", "Synthetic alternative.", "new")
        question = _question(app, list_questions(app), candidate.id)
        claim_ids = {item.id for item in app.state.claims.by_subject(old.subject_ref, include_inactive=True)}

        result = resolve_question(app, question["id"], stand=question["stand"], proposal_id=None)

        assert result["decision"] == "kept"
        assert result["claim_ids"] == [old.id]
        assert app.state.claims.by_subject(old.subject_ref, include_inactive=True)[0].status.value == "active"
        assert app.state.proposals.get(candidate.id).state is ProposalState.REJECTED
        assert {item.id for item in app.state.claims.by_subject(old.subject_ref, include_inactive=True)} == claim_ids
    finally:
        _close_runtime(app, client)


def test_stale_question_stand_refuses_resolution_without_writes(core, tmp_path, monkeypatch):
    app, client = _runtime(core, tmp_path, monkeypatch)
    try:
        old, _ = _active_claim(app, "person:alex-opaque")
        first, _ = _candidate(app, "person:alex-opaque", "First synthetic alternative.", "new")
        question = _question(app, list_questions(app), first.id)
        second, _ = _candidate(app, "person:alex-opaque", "Later synthetic alternative.", "later")

        with pytest.raises(HTTPException) as error:
            resolve_question(app, question["id"], stand=question["stand"], proposal_id=first.id)

        assert error.value.status_code == 409
        assert app.state.claims.by_subject(old.subject_ref, include_inactive=True) == [old]
        assert app.state.proposals.get(first.id).state is ProposalState.PENDING
        assert app.state.proposals.get(second.id).state is ProposalState.PENDING
    finally:
        _close_runtime(app, client)


def test_source_withdrawal_between_list_and_decision_returns_conflict(core, tmp_path, monkeypatch):
    app, client = _runtime(core, tmp_path, monkeypatch)
    try:
        old, _ = _active_claim(app, "person:alex-opaque")
        candidate, source = _candidate(app, "person:alex-opaque", "Synthetic source to withdraw.", "new")
        question = _question(app, list_questions(app), candidate.id)
        app.state.episodes.ignore(source.id)

        with pytest.raises(HTTPException) as error:
            resolve_question(app, question["id"], stand=question["stand"], proposal_id=candidate.id)

        assert error.value.status_code == 409
        assert app.state.claims.by_subject(old.subject_ref, include_inactive=True) == [old]
        assert app.state.proposals.get(candidate.id).state is ProposalState.PENDING
    finally:
        _close_runtime(app, client)


def test_withdrawn_active_claim_evidence_is_not_offered_as_current(core, tmp_path, monkeypatch):
    app, client = _runtime(core, tmp_path, monkeypatch)
    try:
        old, old_source = _active_claim(app, "person:alex-opaque")
        candidate, _ = _candidate(app, "person:alex-opaque", "Synthetic current alternative.", "new")
        question = _question(app, list_questions(app), candidate.id)
        app.state.episodes.ignore(old_source.id)

        assert list_questions(app) == []
        with pytest.raises(HTTPException) as error:
            resolve_question(app, question["id"], stand=question["stand"], proposal_id=candidate.id)
        assert error.value.status_code == 409
        assert app.state.claims.get(old.id).status.value == "active"
        assert app.state.proposals.get(candidate.id).state is ProposalState.PENDING
    finally:
        _close_runtime(app, client)


def test_dependency_source_withdrawal_hides_candidate_even_when_claim_status_stays_active(
    core, tmp_path, monkeypatch
):
    app, client = _runtime(core, tmp_path, monkeypatch)
    try:
        _active_claim(app, "person:alex-opaque")
        foundation, foundation_source = _active_claim(app, "person:foundation-opaque")
        candidate, _ = _candidate(
            app, "person:alex-opaque", "Synthetic dependent alternative.", "new",
            depends_on=[foundation.id],
        )
        assert _question(app, list_questions(app), candidate.id)
        app.state.episodes.ignore(foundation_source.id)

        # The direct store mutation leaves claim status ACTIVE; availability must
        # still follow the source chain rather than that status alone.
        assert app.state.claims.get(foundation.id).status.value == "active"
        assert list_questions(app) == []
    finally:
        _close_runtime(app, client)


def test_dependency_source_generation_is_bound_to_question_stand(
    core, tmp_path, monkeypatch
):
    app, client = _runtime(core, tmp_path, monkeypatch)
    try:
        _active_claim(app, "person:alex-opaque")
        foundation, foundation_source = _active_claim(app, "person:foundation-opaque")
        candidate, _ = _candidate(
            app, "person:alex-opaque", "Synthetic dependent alternative.", "new",
            depends_on=[foundation.id],
        )
        first = _question(app, list_questions(app), candidate.id)
        app.state.episodes.ignore(foundation_source.id)
        app.state.episodes.reopen(foundation_source.id)

        second = _question(app, list_questions(app), candidate.id)

        assert second["stand"] != first["stand"]
    finally:
        _close_runtime(app, client)


def test_future_and_expired_candidates_are_not_presented_as_current_conflicts(
    core, tmp_path, monkeypatch
):
    app, client = _runtime(core, tmp_path, monkeypatch)
    try:
        _active_claim(app, "person:alex-opaque")
        moment = now()
        future, _ = _candidate(
            app, "person:alex-opaque", "Synthetic future alternative.", "future",
            valid_from=moment + timedelta(days=1),
        )
        expired, _ = _candidate(
            app, "person:alex-opaque", "Synthetic expired alternative.", "expired",
            valid_until=moment - timedelta(days=1),
        )

        pending_sets = [
            {item["id"] for item in question["candidates"]}
            for question in app.state.knowledge_service.clarifications()
        ]
        assert any(future.id in items for items in pending_sets)
        assert any(expired.id in items for items in pending_sets)
        current_sets = [
            {item["id"] for item in question["candidates"]}
            for question in list_questions(app)
        ]
        assert all(future.id not in items and expired.id not in items for items in current_sets)
    finally:
        _close_runtime(app, client)


def test_same_display_name_with_distinct_subject_refs_stays_two_questions(
    core, tmp_path, monkeypatch
):
    app, client = _runtime(core, tmp_path, monkeypatch)
    try:
        subjects = ("person:alex-purchase", "person:alex-school")
        for subject in subjects:
            _active_claim(app, subject, quote="Alex Winter has old value.", value="old")
            _candidate(app, subject, "Alex Winter has another value.", "new")

        questions = list_questions(app)

        assert {item["subject_ref"] for item in questions} == set(subjects)
        assert len(questions) == 2
    finally:
        _close_runtime(app, client)


def test_lint_only_conflicts_are_left_for_the_separate_lint_review(
    core, tmp_path, monkeypatch
):
    app, client = _runtime(core, tmp_path, monkeypatch)
    try:
        _active_claim(app, "person:alex-opaque")
        _candidate(app, "person:alex-opaque", "Lint-generated alternative.", "new", proposed_by="lint")

        assert list_questions(app) == []
    finally:
        _close_runtime(app, client)
