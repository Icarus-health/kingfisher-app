"""An attachment is evidence only while its exact mail source remains usable."""
from contextlib import ExitStack

import pytest

from icarus_memory import source_index
from icarus_memory.claims import ClaimStore, KnowledgeService
from icarus_memory.episodes import EpisodeError, EpisodeKind, EpisodeState, EpisodeStore, sql_sichtbar
from icarus_memory.knowledge_render import KnowledgeInputBuild
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import Evidence, ProposalStore
from icarus_memory.source_versions import invalidate_with_corrections, track_source

KEY = "mail:" + "a" * 64
MARKER = "Aurorabeleg"


@pytest.fixture
def stores(tmp_path):
    with ExitStack() as stack:
        result = []
        for cls, name in ((EpisodeStore, "episodes"), (ClaimStore, "claims"), (ProposalStore, "proposals")):
            store = cls(tmp_path / (name + ".sqlite3"))
            stack.callback(store.close)
            result.append(store)
        yield tuple(result)


def mail(stores, text="Synthetic mail"):
    episodes, claims, _ = stores
    parent, _ = episodes.record(EpisodeKind.MESSAGE, "Mail", text,
        Provenance(SourceType.EMAIL, source_ref="qa:7.1"), source_key=KEY)
    track_source(episodes, claims, KEY, parent)
    return parent


def attachment(stores, parent, *, legacy=False, number=1):
    episodes, claims, _ = stores
    tags = ["anhang", "anhang:gelesen"]
    if not legacy:
        tags.append("mail-parent:" + parent.id)
    child, _ = episodes.record(EpisodeKind.DOCUMENT, "Synthetic attachment", MARKER,
        Provenance(SourceType.EMAIL, source_ref=f"qa:7.1#anhang:{number}:qa.pdf"),
        tags=tags, source_key=f"{KEY}:anhang:{number}")
    track_source(episodes, claims, f"{KEY}:anhang:{number}", child)
    return child


def accept(stores, source):
    episodes, claims, proposals = stores
    claims.entities.create("person", "Synthetic", explicit_id="person:qa")
    service = KnowledgeService(episodes=episodes, claims=claims, proposals=proposals)
    proposal, _ = service.propose(subject_ref="person:qa", predicate="audit_fact",
        value=MARKER, statement=MARKER, rationale="Synthetic explicit acceptance",
        evidence=[Evidence(source.id, MARKER, source.digest)])
    return service.accept(proposal.id, supersedes=[])


def retrieved(episodes):
    # Original search, the FTS read gate and visible analysis inventory all matter.
    direct = {row["id"] for row in episodes.mentions(MARKER)[0]}
    indexed = set(source_index.suchen(episodes._conn, MARKER).episoden)
    visible = {row[0] for row in episodes._conn.execute(f"SELECT id FROM episodes WHERE {sql_sichtbar()}")}
    return direct, indexed, visible


@pytest.mark.parametrize("legacy", [False, True])
def test_parent_exclusion_cascades_to_child_claim_and_source_search(stores, legacy):
    episodes, claims, _ = stores
    parent = mail(stores)
    child = attachment(stores, parent, legacy=legacy)
    claim = accept(stores, child)
    assert all(child.id in ids for ids in retrieved(episodes))
    invalidate_with_corrections(episodes, claims, parent.id)
    episodes.ignore(parent.id)
    assert episodes.get(child.id).state is EpisodeState.IGNORED
    assert not episodes.support_snapshot(child.id).current()
    assert claims.get(claim.id).status.value == "disputed"
    assert KnowledgeInputBuild(claims, episodes.support_snapshot).capture(claim.id) is None
    assert all(child.id not in ids for ids in retrieved(episodes))
    with pytest.raises(EpisodeError):
        episodes.reopen(child.id)


def test_parent_replacement_does_not_keep_absent_attachment_usable(stores):
    episodes, claims, _ = stores
    parent = mail(stores)
    child = attachment(stores, parent)
    claim = accept(stores, child)
    mail(stores, "New mail body without this attachment")
    assert episodes.get(child.id).state is EpisodeState.IGNORED
    assert claims.get(claim.id).status.value == "disputed"
    assert all(child.id not in ids for ids in retrieved(episodes))
    with pytest.raises(EpisodeError):
        episodes.reopen(child.id)


def test_parent_reopen_never_reopens_child_automatically(stores):
    episodes, _, _ = stores
    parent = mail(stores)
    child = attachment(stores, parent)
    episodes.ignore(parent.id)
    episodes.reopen(parent.id)
    assert episodes.get(child.id).state is EpisodeState.IGNORED
    assert not episodes.support_snapshot(child.id).current()


def test_ambiguous_legacy_child_is_blocked_even_if_it_was_never_ignored(stores):
    episodes, _, _ = stores
    parent = mail(stores)
    child = attachment(stores, parent, legacy=True)
    # Simulate a pre-fix historical second version without relying on new cascade.
    second, _ = episodes.record(EpisodeKind.MESSAGE, "Mail", "Other version",
        Provenance(SourceType.EMAIL, source_ref="qa:7.1"), source_key=KEY)
    episodes.advance_source_head(KEY, parent.id, second.id)
    assert episodes.get(child.id).state is EpisodeState.NEW
    assert not episodes.support_snapshot(child.id).current()
    assert all(child.id not in ids for ids in retrieved(episodes))
    with pytest.raises(EpisodeError):
        episodes.reopen(child.id)


def test_exact_parent_tag_does_not_rebind_to_another_mail_version(stores):
    episodes, _, _ = stores
    parent = mail(stores)
    child = attachment(stores, parent)
    second, _ = episodes.record(EpisodeKind.MESSAGE, "Mail", "Other version",
        Provenance(SourceType.EMAIL, source_ref="qa:7.1"), source_key=KEY)
    episodes.advance_source_head(KEY, parent.id, second.id)
    assert not episodes.support_snapshot(child.id).current()
    assert all(child.id not in ids for ids in retrieved(episodes))


def test_attachment_support_ignores_advisory_parent_metadata_but_tracks_permission(stores):
    episodes, claims, _ = stores
    parent = mail(stores)
    child = attachment(stores, parent)
    claim = accept(stores, child)
    unrelated, _ = episodes.record(EpisodeKind.DOCUMENT, "Other", "Other text", Provenance(SourceType.DOCUMENT))
    before = episodes.support_snapshot(child.id)
    other = episodes.support_snapshot(unrelated.id)
    episodes.add_mail_headers(parent.id, ["mail-test:changed"])
    episodes.set_mail_attachment_report(parent.id, {"abruf_vollstaendig": False})
    after = episodes.support_snapshot(child.id)
    assert after.current()
    assert after.support_fingerprint() == before.support_fingerprint()
    assert after.fingerprint() == before.fingerprint()
    assert claims.get(claim.id).status.value == "active"
    assert KnowledgeInputBuild(claims, episodes.support_snapshot).capture(claim.id) is not None
    assert episodes.support_snapshot(unrelated.id).support_fingerprint() == other.support_fingerprint()
    episodes.ignore(parent.id)
    withdrawn = episodes.support_snapshot(child.id)
    assert not withdrawn.current()
    assert withdrawn.support_fingerprint() != before.support_fingerprint()


def test_child_correction_is_invalidated_with_parent_and_its_claim(stores):
    from icarus_memory.source_corrections import correct, preview
    episodes, claims, _ = stores
    parent = mail(stores)
    child = attachment(stores, parent)
    state = preview(episodes, claims, child.id)
    correction_id = correct(episodes, claims, child.id, state["fingerprint"], MARKER + " corrected")
    claim = accept(stores, episodes.get(correction_id))
    assert episodes.support_snapshot(correction_id).current()
    invalidate_with_corrections(episodes, claims, parent.id)
    episodes.ignore(parent.id)
    assert not episodes.support_snapshot(correction_id).current()
    assert claims.get(claim.id).status.value == "disputed"
    assert KnowledgeInputBuild(claims, episodes.support_snapshot).capture(claim.id) is None
    assert all(correction_id not in ids for ids in retrieved(episodes))
    with pytest.raises(EpisodeError):
        episodes.reopen(correction_id)


def test_parent_correction_invalidates_accepted_child_evidence(stores):
    from icarus_memory.source_corrections import correct, preview
    episodes, claims, _ = stores
    parent = mail(stores)
    child = attachment(stores, parent)
    claim = accept(stores, child)
    state = preview(episodes, claims, parent.id)
    correction_id = correct(episodes, claims, parent.id, state["fingerprint"], "Corrected parent mail")
    assert episodes.support_snapshot(correction_id).current()
    assert claims.get(claim.id).status.value == "disputed"
    assert not episodes.support_snapshot(child.id).current()
    assert all(child.id not in ids for ids in retrieved(episodes))


def test_already_orphaned_legacy_child_correction_is_excluded_from_sql_reads(stores):
    from icarus_memory.source_corrections import correct, preview
    episodes, claims, _ = stores
    parent = mail(stores)
    child = attachment(stores, parent, legacy=True)
    state = preview(episodes, claims, child.id)
    correction_id = correct(episodes, claims, child.id, state["fingerprint"], MARKER + " corrected")
    assert all(correction_id in ids for ids in retrieved(episodes))
    # Pre-upgrade state: the parent head changed without today's withdrawal cascade.
    second, _ = episodes.record(EpisodeKind.MESSAGE, "Mail", "Other version",
        Provenance(SourceType.EMAIL, source_ref="qa:7.1"), source_key=KEY)
    episodes.advance_source_head(KEY, parent.id, second.id)
    assert not episodes.support_snapshot(correction_id).current()
    assert all(correction_id not in ids for ids in retrieved(episodes))


def test_ordinary_source_correction_remains_available_through_sql_reads(stores):
    from icarus_memory.source_corrections import correct, preview
    episodes, claims, _ = stores
    source, _ = episodes.record(EpisodeKind.DOCUMENT, "Original", MARKER, Provenance(SourceType.DOCUMENT))
    state = preview(episodes, claims, source.id)
    correction_id = correct(episodes, claims, source.id, state["fingerprint"], MARKER + " corrected")
    assert episodes.get(source.id).state is EpisodeState.IGNORED
    assert episodes.support_snapshot(correction_id).current()
    assert all(correction_id in ids for ids in retrieved(episodes))


def test_mail_attachment_report_is_advisory_idempotent_and_ignored_source_safe(stores):
    episodes, _, _ = stores
    parent = mail(stores)
    original = episodes.support_snapshot(parent.id)
    report = {"version": 1, "complete": False, "omitted": 1}
    updated = episodes.set_mail_attachment_report(parent.id, report)
    assert (updated.body, updated.digest, updated.state) == (parent.body, parent.digest, parent.state)
    first = episodes.support_snapshot(parent.id)
    assert first.generation == original.generation + 1
    assert first.support_fingerprint() != original.support_fingerprint()
    episodes.set_mail_attachment_report(parent.id, dict(reversed(list(report.items()))))
    assert episodes.support_snapshot(parent.id).generation == first.generation
    episodes.set_mail_attachment_report(parent.id, {"version": 1, "complete": True})
    assert len([tag for tag in episodes.get(parent.id).tags if tag.startswith("mail:attachments:")]) == 1
    episodes.ignore(parent.id)
    ignored = episodes.support_snapshot(parent.id)
    episodes.set_mail_attachment_report(parent.id, report)
    assert episodes.support_snapshot(parent.id).fingerprint() == ignored.fingerprint()


@pytest.mark.parametrize("withdraw_parent", [False, True])
def test_withdrawal_reason_preserves_consistent_snapshots_and_explicit_reopen(stores, withdraw_parent):
    episodes, _, _ = stores
    parent = mail(stores)
    child = attachment(stores, parent)
    withdrawn = parent if withdraw_parent else child
    episodes.ignore(withdrawn.id, grund="mail-anlage-entfallen")
    for source in ([parent, child] if withdraw_parent else [child]):
        snapshot = episodes.support_snapshot(source.id)
        assert not snapshot.current()
        assert "entzogen:mail-anlage-entfallen" in snapshot.episode.tags
        assert (snapshot.episode.body, snapshot.episode.digest) == (source.body, source.digest)
    if withdraw_parent:
        episodes.reopen(parent.id)
    episodes.reopen(child.id)
    assert episodes.support_snapshot(child.id).current()
    assert episodes.support_snapshot(parent.id).source_key == KEY
    assert episodes.support_snapshot(child.id).source_key == KEY + ":anhang:1"


def test_child_inventory_uses_exact_binding_and_never_guesses_legacy_parent(stores):
    episodes, _, _ = stores
    parent = mail(stores)
    legacy = attachment(stores, parent, legacy=True)
    bound = attachment(stores, parent, number=2)
    assert set(episodes.mail_attachment_children(parent.id)) == {legacy.id, bound.id}
    second, _ = episodes.record(EpisodeKind.MESSAGE, "Mail", "Second version",
        Provenance(SourceType.EMAIL, source_ref="qa:7.1"), source_key=KEY)
    episodes.advance_source_head(KEY, parent.id, second.id)
    assert episodes.mail_attachment_children(parent.id) == [bound.id]
    assert episodes.mail_attachment_children(second.id) == []
