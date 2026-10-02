"""Zeit- und Beziehungsmetadaten für Wissensvorschläge."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from icarus_memory.proposals import (
    ProposalError,
    ProposalKind,
    ProposalStore,
    fingerprint,
)


UTC = timezone.utc
AT = datetime(2026, 9, 5, 10, tzinfo=UTC)


def _knowledge(store: ProposalStore, **changes):
    data = {
        "kind": ProposalKind.KNOWLEDGE,
        "statement": "Dr. Kranz arbeitet im Projekt Atlas.",
        "rationale": "In der Quelle genannt.",
        "about": ["episode:1"],
        "subject_ref": "person:kranz",
        "predicate": "works_on",
        "value": "Projekt Atlas",
        "at": AT,
    }
    data.update(changes)
    return store.propose(**data)


def test_relation_metadata_roundtrips_after_restart(tmp_path: Path) -> None:
    path = tmp_path / "proposals.sqlite3"
    start = datetime(2026, 9, 5, 12, tzinfo=timezone(timedelta(hours=2)))
    end = datetime(2026, 9, 5, 15, tzinfo=timezone(timedelta(hours=2)))

    store = ProposalStore(path)
    proposal, created = _knowledge(
        store,
        target_ref="Project:Atlas",
        valid_from=start,
        valid_until=end,
        depends_on=["Decision:Budget", "Approval:CEO"],
    )
    assert created
    assert proposal.target_ref == "Project:Atlas"
    assert proposal.valid_from == start
    assert proposal.valid_until == end
    assert proposal.depends_on == ["Decision:Budget", "Approval:CEO"]
    document = proposal.to_dict()
    assert document["target_ref"] == "Project:Atlas"
    assert document["depends_on"] == ["Decision:Budget", "Approval:CEO"]
    store.close()

    restarted = ProposalStore(path)
    loaded = restarted.get(proposal.id)
    assert loaded.target_ref == "Project:Atlas"
    assert loaded.valid_from == start
    assert loaded.valid_until == end
    assert loaded.depends_on == ["Decision:Budget", "Approval:CEO"]
    restarted.close()


def test_relation_metadata_changes_deduplication_identity(tmp_path: Path) -> None:
    store = ProposalStore(tmp_path / "proposals.sqlite3")
    common = {
        "target_ref": "Project:Atlas",
        "valid_from": AT,
        "valid_until": AT + timedelta(hours=1),
        "depends_on": ["Decision:Budget"],
    }
    first, created = _knowledge(store, **common)
    assert created

    duplicate, created = _knowledge(store, **common)
    assert not created
    assert duplicate.id == first.id

    changed_target, created = _knowledge(
        store, **{**common, "target_ref": "Project:Lumen"}
    )
    assert created
    changed_time, created = _knowledge(
        store,
        **{**common, "valid_from": AT + timedelta(minutes=1)},
    )
    assert created
    changed_dependency, created = _knowledge(
        store,
        **{**common, "depends_on": ["Decision:Risk"]},
    )
    assert created
    assert len(store.pending(ProposalKind.KNOWLEDGE)) == 4
    assert len({first.id, changed_target.id, changed_time.id, changed_dependency.id}) == 4
    store.close()


def test_legacy_fingerprint_stays_byte_exact() -> None:
    assert fingerprint(
        ProposalKind.ASSERTION,
        "  Aussage   Eins ",
        ["b", "a"],
    ) == "assertion|aussage eins|a,b"


@pytest.mark.parametrize(
    ("valid_from", "valid_until"),
    [
        (datetime(2026, 9, 5, 10), AT + timedelta(hours=1)),
        (AT + timedelta(hours=1), AT),
        (AT, AT),
    ],
)
def test_knowledge_rejects_invalid_intervals(
    tmp_path: Path,
    valid_from: datetime,
    valid_until: datetime,
) -> None:
    store = ProposalStore(tmp_path / "proposals.sqlite3")
    with pytest.raises(ProposalError, match="Gültigkeitsintervall"):
        _knowledge(store, valid_from=valid_from, valid_until=valid_until)
    assert store.pending() == []
    store.close()


def test_fingerprint_normalizes_interval_timezone_but_preserves_id_case() -> None:
    offset = timezone(timedelta(hours=2))
    first = fingerprint(
        ProposalKind.KNOWLEDGE,
        "Aussage",
        ["episode:1"],
        target_ref="Project:Atlas",
        valid_from=datetime(2026, 9, 5, 12, tzinfo=offset),
        valid_until=datetime(2026, 9, 5, 13, tzinfo=offset),
        depends_on=["Decision:Budget"],
    )
    second = fingerprint(
        ProposalKind.KNOWLEDGE,
        "Aussage",
        ["episode:1"],
        target_ref="Project:Atlas",
        valid_from=datetime(2026, 9, 5, 10, tzinfo=UTC),
        valid_until=datetime(2026, 9, 5, 11, tzinfo=UTC),
        depends_on=["Decision:Budget"],
    )
    assert first == second
    assert '"target_ref":"Project:Atlas"' in first
    assert '"depends_on":["Decision:Budget"]' in first
