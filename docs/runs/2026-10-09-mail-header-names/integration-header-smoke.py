"""Isolated real-package smoke for mail header identity correction.

Run with the frozen package on PYTHONPATH, for example:
  PYTHONPATH=/path/to/frozen/sidecar python3 - < this_file.py
Only temporary SQLite stores and synthetic records are used. Stdout contains
aggregate booleans/counts only; no source text, names, or addresses are emitted.
"""
from __future__ import annotations

import json
import importlib.util
import sys
import tempfile
import types
from datetime import datetime, timezone
from email.utils import formataddr
from pathlib import Path

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
LEGACY_NAME = "=?utf-8?q?M=C3=BCller=2C_Jan?="
LEGACY_LABEL = "Müller, Jan"
LEGACY_ADDRESS = "jan@legacy.synthetic.example"
LEGACY_PARTICIPANT = f"{LEGACY_NAME} <{LEGACY_ADDRESS}>"
NEW_NAME = "Zoë Étoile"
NEW_ADDRESS = "zoe@unicode.synthetic.example"

stage = "imports"


def mail_record(store, title, body, name, address, *, source_ref, at=NOW):
    parsed = kontakte.kontakt(f"{name} <{address}>", "von")
    episode, created = store.record(
        EpisodeKind.MESSAGE,
        title,
        body,
        Provenance(SourceType.EMAIL, source_ref=source_ref, captured_at=at),
        occurred_at=at,
        participants=[kontakte.text_form(parsed)],
        contacts=[parsed],
        at=at,
    )
    if not created:
        raise AssertionError("synthetic record unexpectedly deduplicated")
    return episode


def main() -> dict:
    global stage, kontakte, EpisodeKind, Provenance, SourceType
    assert importlib.util.find_spec("httpx") is not None, "Real dependency package required"
    from icarus_memory import bezuege, identitaet, kontakte, personenfrage
    from icarus_memory.episodes import EpisodeKind, EpisodeState, EpisodeStore
    from icarus_memory.model import Provenance, SourceType

    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="kingfisher-mail-header-smoke-") as temp:
        db = Path(temp) / "episodes.sqlite3"
        store = EpisodeStore(db)
        try:
            stage = "unicode_recipient_header"
            recipient = kontakte.kontakt(f"{NEW_NAME} <{NEW_ADDRESS}>", "an")
            wire_recipient = kontakte.text_form(recipient)
            reparsed_recipient = kontakte.kontakt(wire_recipient, "an")
            assert recipient == reparsed_recipient
            assert recipient["name"] == NEW_NAME and recipient["adresse"] == NEW_ADDRESS
            assert recipient["rolle"] == "an"
            assert wire_recipient == formataddr((NEW_NAME, NEW_ADDRESS))
            checks["new_unicode_recipient_roundtrip"] = True

            stage = "legacy_encoded_mail"
            legacy_body = "Synthetic original body: EMAIL is literal content; no header text is rewritten."
            legacy, created = store.record(
                EpisodeKind.MESSAGE,
                "Synthetic legacy mail",
                legacy_body,
                Provenance(SourceType.EMAIL, source_ref="synthetic:legacy", captured_at=NOW),
                occurred_at=NOW,
                participants=[LEGACY_PARTICIPANT],
                contacts=[{"name": LEGACY_NAME, "adresse": LEGACY_ADDRESS, "rolle": "von", "ich": False}],
                at=NOW,
            )
            assert created
            raw_legacy = store.get(legacy.id).to_dict()
            legacy_generation = store.support_snapshot(legacy.id).generation
            [legacy_mention] = identitaet.nennungen(store.get(legacy.id))
            assert legacy_mention.name == LEGACY_LABEL and legacy_mention.adresse == LEGACY_ADDRESS
            assert raw_legacy["participants"] == [LEGACY_PARTICIPANT]
            assert raw_legacy["contacts"][0]["name"] == LEGACY_NAME
            checks["legacy_encoded_contact_and_participant_project_without_rewrite"] = True

            stage = "metadata_only_header_correction"
            corrected = store.add_contacts(legacy.id, [recipient], [wire_recipient])
            corrected_before_reads = store.get(legacy.id).to_dict()
            generation_after_correction = store.support_snapshot(legacy.id).generation
            assert corrected_before_reads["body"] == raw_legacy["body"]
            assert corrected_before_reads["digest"] == raw_legacy["digest"]
            assert corrected_before_reads["provenance"] == raw_legacy["provenance"]
            assert corrected_before_reads["recorded_at"] == raw_legacy["recorded_at"]
            assert corrected_before_reads["occurred_at"] == raw_legacy["occurred_at"]
            assert corrected_before_reads["state"] == raw_legacy["state"]
            assert generation_after_correction == legacy_generation + 1
            assert any(c.get("adresse") == NEW_ADDRESS and c.get("name") == NEW_NAME
                       and c.get("rolle") == "an" for c in corrected_before_reads["contacts"])
            assert LEGACY_PARTICIPANT in corrected_before_reads["participants"]
            checks["header_correction_preserves_original_and_advances_generation_once"] = True

            stage = "same_name_distinct_addresses"
            north = mail_record(store, "Catering offer", "Synthetic offer body.", "Alex Winter",
                                "alex@north.synthetic.example", source_ref="synthetic:alex-north")
            lab = mail_record(store, "Labor report", "Synthetic lab body.", "Alex Winter",
                              "alex@lab.synthetic.example", source_ref="synthetic:alex-lab")
            ambiguity = personenfrage.unklare_person("Was schrieb Alex Winter?", store)
            assert ambiguity is not None
            assert {k.adresse for k in ambiguity.kandidaten} == {
                "alex@north.synthetic.example", "alex@lab.synthetic.example"}
            selected = personenfrage.kandidatenquellen(
                "Was schrieb Alex Winter zum Catering?", store)
            assert selected == [north.id] and lab.id not in selected
            directory = identitaet.Verzeichnis.aus(store.each_geltende())
            assert set(directory.adressen_zum_namen("Alex Winter")) == {
                "alex@north.synthetic.example", "alex@lab.synthetic.example"}
            checks["same_name_addresses_stay_distinct_and_question_can_disambiguate"] = True

            stage = "excluded_sources"
            ignored = mail_record(store, "Ignored note", "Synthetic ignored body.", "Riley Cedar",
                                  "riley@ignored.synthetic.example", source_ref="synthetic:ignored")
            withdrawn = mail_record(store, "Withdrawn note", "Synthetic withdrawn body.", "Jordan Vale",
                                    "jordan@withdrawn.synthetic.example", source_ref="synthetic:withdrawn")
            relations = bezuege.Bezuege(store)
            relations.nutzer_setzen(ignored.id, "person:a:riley@ignored.synthetic.example", "zu")
            relations.nutzer_setzen(withdrawn.id, "person:a:jordan@withdrawn.synthetic.example", "zu")
            store.ignore(ignored.id)
            store.ignore(withdrawn.id, grund="mail_withdrawn")
            assert store.get(ignored.id).state is EpisodeState.IGNORED
            assert store.get(withdrawn.id).state is EpisodeState.IGNORED
            assert any(t == "entzogen:mail_withdrawn" for t in store.get(withdrawn.id).tags)
            checks["user_ignored_and_source_withdrawn_states_recorded"] = True

            stage = "close_reopen"
            all_ids = [e.id for e in store.each_episode()]
            store.close()
            store = EpisodeStore(db)
            relations = bezuege.Bezuege(store)
            assert set(e.id for e in store.each_geltende()) == {legacy.id, north.id, lab.id}
            checks["close_reopen_persists_records_and_exclusions"] = True

            stage = "read_only_projection_and_bezuege"
            pre_read = {eid: store.get(eid).to_dict() for eid in all_ids}
            pre_generation = {eid: store.support_snapshot(eid).generation for eid in all_ids}
            current_legacy = store.get(legacy.id)
            projected = identitaet.nennungen(current_legacy)
            assert {n.adresse for n in projected} >= {LEGACY_ADDRESS, NEW_ADDRESS}
            assert any(n.name == NEW_NAME and n.rolle == "an" for n in projected)
            assert personenfrage.erwaehnte("Was hat Zoë Étoile geschrieben?", store)
            register = relations.register()
            assert register.verzeichnis.adressen_zum_namen("Riley Cedar") == []
            assert register.verzeichnis.adressen_zum_namen("Jordan Vale") == []
            assert register.verzeichnis.adressen_zum_namen("Alex Winter") == [
                "alex@lab.synthetic.example", "alex@north.synthetic.example"]
            assert personenfrage.erwaehnte("Was schrieb Riley Cedar?", store) == []
            assert personenfrage.erwaehnte("Was schrieb Jordan Vale?", store) == []
            assert personenfrage.kandidatenquellen("Was schrieb Riley Cedar?", store) == []
            assert personenfrage.kandidatenquellen("Was schrieb Jordan Vale?", store) == []
            assert relations.beschriftung(f"person:a:{LEGACY_ADDRESS}") == LEGACY_LABEL
            assert relations.bezuege_der_quelle(ignored.id) is None
            assert relations.bezuege_der_quelle(withdrawn.id) is None
            assert relations.quellen_von("person:a:riley@ignored.synthetic.example") == []
            assert relations.quellen_von("person:a:jordan@withdrawn.synthetic.example") == []
            relation_sync = relations.aktualisieren()
            assert relation_sync["offen"] == 0
            # Read/projection/index operations may maintain derived relations, but may not rewrite sources.
            post_read = {eid: store.get(eid).to_dict() for eid in all_ids}
            post_generation = {eid: store.support_snapshot(eid).generation for eid in all_ids}
            assert post_read == pre_read
            assert post_generation == pre_generation
            checks["identity_people_question_and_bezuege_exclude_ignored_and_withdrawn"] = True
            checks["read_projections_leave_originals_and_generation_unchanged"] = True

            stage = "non_email_literal"
            literal = "=?utf-8?q?M=C3=BCller=2C_Jan?="
            note, created = store.record(
                EpisodeKind.DOCUMENT,
                "Synthetic non-email note",
                "The literal EMAIL marker is body text; " + literal,
                Provenance(SourceType.DOCUMENT, source_ref="synthetic:document", captured_at=NOW),
                occurred_at=NOW,
                participants=[literal],
                contacts=[{"name": literal, "adresse": "literal@document.synthetic.example",
                           "rolle": "beteiligt", "ich": False}],
                at=NOW,
            )
            assert created
            [note_mention] = identitaet.nennungen(note)
            assert note_mention.name == literal
            assert kontakte.anzeigename(literal) == literal
            email_word = kontakte.kontakt("EMAIL", "an")
            assert email_word == {"name": "EMAIL", "adresse": "", "rolle": "an", "ich": False}
            assert store.get(note.id).body.endswith(literal)
            checks["non_email_rfc2047_and_EMAIL_literal_remain_literal"] = True

            stage = "final_reopen_readonly_check"
            note_before = store.get(note.id).to_dict()
            note_generation = store.support_snapshot(note.id).generation
            store.close()
            store = EpisodeStore(db)
            reread = store.get(note.id)
            assert reread.to_dict() == note_before
            assert store.support_snapshot(note.id).generation == note_generation
            checks["final_close_reopen_preserves_literal_source"] = True
        finally:
            try:
                store.close()
            except Exception:
                pass
    return {
        "passed": True,
        "synthetic_only": True,
        "network_used": False,
        "production_data_used": False,
        "checks": checks,
        "counts": {"identity_checks": len(checks), "synthetic_records": 6},
    }


try:
    result = main()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
except Exception as exc:
    print(json.dumps({"passed": False, "synthetic_only": True, "failed_stage": stage,
                      "error_type": type(exc).__name__}, sort_keys=True))
    sys.exit(1)
