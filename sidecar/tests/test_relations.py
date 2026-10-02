"""Grenzfälle der kleinen, deterministischen Beziehungsschicht."""

from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory.relations import (
    canonical_predicate,
    intervals_overlap,
    predicates_equivalent,
    validate_interval,
    values_conflict,
)


def test_aliases_are_canonical_and_unknown_predicates_stay_conservative() -> None:
    assert canonical_predicate(" arbeitet_an ") == "works_on"
    assert canonical_predicate("ARBEITET_AN") == "works_on"
    assert canonical_predicate("hat_status") == "status"
    assert predicates_equivalent("kennt", "knows")
    assert canonical_predicate("  custom_fact ") == "  custom_fact "
    assert not predicates_equivalent("  custom_fact ", "custom_fact")
    assert values_conflict("custom_fact", "eins", "zwei")
    assert not values_conflict("custom_fact", "eins", "EINS")


def test_person_can_work_on_two_projects() -> None:
    assert not values_conflict("works_on", "Projekt Atlas", "Projekt Lumen")
    assert not values_conflict("arbeitet_an", "Projekt Atlas", "Projekt Lumen")
    assert not values_conflict(
        "works_on",
        "Atlas",
        "Lumen",
        "project:atlas",
        "project:lumen",
    )


def test_private_and_business_roles_are_multivalued() -> None:
    assert not values_conflict("has_role", "Privat: Vater", "Arbeit: Leiter")
    assert not values_conflict("hat_rolle", "Privat: Vater", "Arbeit: Leiter")


def test_status_is_single_valued_and_aliases_are_equivalent() -> None:
    assert values_conflict("status", "aktiv", "pausiert")
    assert values_conflict("hat_status", "aktiv", "pausiert")
    assert not values_conflict("status", "aktiv", " Aktiv ")


def test_same_target_rename_is_not_a_conflict() -> None:
    assert not values_conflict(
        "status",
        "Projekt Atlas",
        "Atlas (neu benannt)",
        "project:42",
        "project:42",
    )
    assert values_conflict(
        "status",
        "Projekt Atlas",
        "Projekt Lumen",
        "project:42",
        "project:43",
    )


def test_different_target_ids_conflict_even_when_labels_match() -> None:
    assert values_conflict("status", "aktiv", "aktiv", "status:1", "status:2")
    assert values_conflict("custom_fact", "gleich", "gleich", "target:1", "target:2")
    assert not values_conflict("works_on", "Projekt", "Projekt", "project:1", "project:2")


def test_half_open_intervals_overlap_only_interior() -> None:
    assert intervals_overlap(
        "2026-09-01T09:00:00+00:00",
        "2026-09-01T11:00:00+00:00",
        "2026-09-01T10:00:00+00:00",
        "2026-09-01T12:00:00+00:00",
    )
    assert not intervals_overlap(
        "2026-09-01T09:00:00+00:00",
        "2026-09-01T10:00:00+00:00",
        "2026-09-01T10:00:00+00:00",
        "2026-09-01T11:00:00+00:00",
    )
    assert not intervals_overlap(
        datetime(2026, 9, 1, 9, tzinfo=timezone.utc),
        datetime(2026, 9, 1, 10, tzinfo=timezone.utc),
        datetime(2026, 9, 1, 11, tzinfo=timezone.utc),
        datetime(2026, 9, 1, 12, tzinfo=timezone.utc),
    )


def test_intervals_normalize_timezones_and_allow_open_bounds() -> None:
    # 11:00+02:00 is the same instant as 09:00Z, so the intervals overlap.
    assert intervals_overlap(
        "2026-09-01T09:00:00Z",
        "2026-09-01T10:00:00Z",
        "2026-09-01T11:00:00+02:00",
        "2026-09-01T12:00:00+02:00",
    )
    assert intervals_overlap(None, "2026-09-01T10:00:00Z", "2026-09-01T09:59:00Z", None)
    assert intervals_overlap(None, None, "2026-09-01T09:00:00Z", "2026-09-01T10:00:00Z")


@pytest.mark.parametrize(
    ("valid_from", "valid_until"),
    [
        ("2026-09-01T10:00:00Z", "2026-09-01T10:00:00Z"),
        ("2026-09-01T11:00:00Z", "2026-09-01T10:00:00Z"),
        (datetime(2026, 9, 1, 10), "2026-09-01T11:00:00Z"),
        ("2026-09-01T10:00:00", "2026-09-01T11:00:00Z"),
        ("kein Zeitpunkt", None),
    ],
)
def test_invalid_intervals_are_rejected(valid_from, valid_until) -> None:
    with pytest.raises((TypeError, ValueError)):
        validate_interval(valid_from, valid_until)


def test_interval_validation_does_not_mutate_datetime_inputs() -> None:
    moment = datetime(2026, 9, 1, 10, tzinfo=timezone.utc)
    later = moment + timedelta(hours=1)
    validate_interval(moment, later)
    assert moment.tzinfo is timezone.utc
