"""Focused controls for source-bound, same-name sender ambiguity."""

from icarus_memory.working_memory_identity import adjust_selection


def _row(identifier, mailbox, street, *, name="Nora Beck", participants=None, context=None, text=None):
    sender = f"{name} <{mailbox}>"
    return {
        "id": identifier,
        "participants": participants if participants is not None else [sender],
        "context": context if context is not None else (
            f"Von: {sender}\nAdresse: {street}, Deutschland.\n"
            f"Für Atelier Orion liefere ich die Stoff-Farbmuster."
        ),
        "text": text if text is not None else "Für Atelier Orion liefere ich die Stoff-Farbmuster.",
    }


def _nora_rows():
    return [
        _row("S1", "nora.park@example.test", "Parkstraße 8"),
        _row("S2", "nora.hafen@example.test", "Hafenweg 19"),
    ]


def test_two_coselected_nora_senders_require_person_clarification():
    ids, status, hint = adjust_selection(
        "Wann liefert Nora Beck die Stoff-Farbmuster für Atelier Orion?",
        _nora_rows(), ["S2", "S1"])
    assert ids == ["S2", "S1"]
    assert status == "person"
    assert "Personen" in hint


def test_qualified_original_address_narrows_to_one_existing_source():
    assert adjust_selection(
        "Wann liefert Nora Beck von der Parkstraße 8 die Stoff-Farbmuster für Atelier Orion?",
        _nora_rows(), ["S1", "S2"]
    ) == (["S1"], "reports", None)


def test_exact_mailbox_in_question_narrows_without_postal_header():
    rows = _nora_rows()
    rows[0]["context"] = "Keine Adresszeile vorhanden."
    assert adjust_selection(
        "Wann liefert Nora Beck <nora.hafen@example.test> die Stoff-Farbmuster?",
        rows, ["S1", "S2"]
    ) == (["S2"], "reports", None)


def test_quoted_display_name_in_original_sender_label_is_recognized():
    rows = _nora_rows()
    rows[0]["participants"] = ['"Nora Beck" <nora.park@example.test>']
    rows[0]["context"] = rows[0]["context"].replace(
        "Von: Nora Beck <", 'Von: "Nora Beck" <')
    assert adjust_selection(
        "Wann liefert Nora Beck von der Parkstraße 8 die Stoff-Farbmuster?",
        rows, ["S1", "S2"]
    ) == (["S1"], "reports", None)


def test_list_question_is_not_turned_into_person_clarification():
    question = "Wann liefern beide Nora Beck jeweils die Stoff-Farbmuster?"
    assert adjust_selection(question, _nora_rows(), ["S1", "S2"]) == (["S1", "S2"], None, None)


def test_two_explicit_mailboxes_or_conflicting_selectors_are_left_untouched():
    rows = _nora_rows()
    assert adjust_selection(
        "Wann liefern Nora Beck <nora.park@example.test>, <nora.hafen@example.test> die Muster?",
        rows, ["S1", "S2"]
    ) == (["S1", "S2"], None, None)
    assert adjust_selection(
        "Wann liefert Nora Beck <nora.park@example.test> von der Hafenweg 19 die Muster?",
        rows, ["S1", "S2"]
    ) == (["S1", "S2"], None, None)


def test_source_with_multiple_real_participants_is_not_collapsed_to_one_sender():
    rows = _nora_rows()
    rows[0]["participants"].append("Mira Vogt <mira@example.test>")
    assert adjust_selection("Wann liefert Nora Beck die Stoff-Farbmuster?", rows, ["S1", "S2"]) == (
        ["S1", "S2"], None, None)


def test_different_display_names_or_same_mailbox_do_not_trigger_guard():
    rows = _nora_rows()
    rows[1] = _row("S2", "mira@example.test", "Hafenweg 19", name="Mira Vogt")
    assert adjust_selection("Wann liefert Nora Beck die Stoff-Farbmuster?", rows, ["S1", "S2"]) == (
        ["S1", "S2"], None, None)
    rows = _nora_rows()
    rows[1] = _row("S2", "nora.park@example.test", "Hafenweg 19")
    assert adjust_selection("Wann liefert Nora Beck die Stoff-Farbmuster?", rows, ["S1", "S2"]) == (
        ["S1", "S2"], None, None)


def test_postal_selector_requires_matching_unquoted_original_header():
    rows = _nora_rows()
    rows[0]["context"] = (
        "Alte, zitierte Nachricht:\nVon: Nora Beck <nora.park@example.test>\n"
        "Adresse: Parkstraße 8, Leipzig.\n"
    )
    ids, status, _ = adjust_selection(
        "Wann liefert Nora Beck von der Parkstraße 8 die Stoff-Farbmuster?",
        rows, ["S1", "S2"])
    assert ids == ["S1", "S2"]
    assert status == "person"


def test_no_unselected_source_is_added_and_unknown_selection_is_untouched():
    question = "Wann liefert Nora Beck die Stoff-Farbmuster?"
    rows = _nora_rows()
    assert adjust_selection(question, rows, ["S1"]) == (["S1"], None, None)
    assert adjust_selection(question, rows, ["S1", "S9"]) == (["S1", "S9"], None, None)


def test_relevant_unselected_same_name_candidate_is_added_only_with_shared_topic_anchor():
    question = "Was hat Lena Vogt zur Keramikprobe entschieden?"
    rows = [
        _row("S1", "lena.atlas@example.test", "", name="Lena Vogt",
             text="Die Keramikproben wurden im Projekt Atlas freigegeben."),
        _row("S2", "lena.orion@example.test", "", name="Lena Vogt",
             text="Projekt Orion benötigt eine überarbeitete Keramikprobe; Freigabe steht aus."),
        _row("S3", "lena.vega@example.test", "", name="Lena Vogt",
             text="Im Projekt Vega ist noch nicht entschieden, ob die Rechnung bezahlt wird."),
    ]
    ids, status, hint = adjust_selection(question, rows, ["S2"], candidate_ids=["S1", "S2", "S3"])
    assert ids == ["S2", "S1"]
    assert status == "person"
    assert "Absenderadressen" in hint


def test_one_selected_candidate_without_shared_non_person_anchor_stays_unchanged():
    question = "Was hat Lena Vogt zur Keramikprobe entschieden?"
    rows = [
        _row("S1", "lena.atlas@example.test", "", name="Lena Vogt",
             text="Die Keramikproben wurden im Projekt Atlas freigegeben."),
        _row("S2", "lena.vega@example.test", "", name="Lena Vogt",
             text="Im Projekt Vega ist noch nicht entschieden, ob die Rechnung bezahlt wird."),
    ]
    assert adjust_selection(question, rows, ["S2"], candidate_ids=["S1", "S2"]) == (
        ["S2"], None, None)


def test_shared_action_verb_does_not_add_unrelated_same_name_candidate():
    question = "Wann liefert Lena Vogt die Keramikprobe?"
    rows = [
        _row("S1", "lena.atlas@example.test", "", name="Lena Vogt",
             text="Lena Vogt liefert Marmelade im Projekt Atlas."),
        _row("S2", "lena.orion@example.test", "", name="Lena Vogt",
             text="Lena Vogt liefert die Keramikprobe im Projekt Orion."),
    ]
    assert adjust_selection(question, rows, ["S2"], candidate_ids=["S1", "S2"]) == (
        ["S2"], None, None)


def test_explicit_project_scope_does_not_add_other_project_candidate():
    question = "Was hat Lena Vogt aus Projekt Orion zur Keramikprobe entschieden?"
    rows = [
        _row("S1", "lena.atlas@example.test", "", name="Lena Vogt",
             text="Projekt Atlas: Die Keramikproben wurden freigegeben."),
        _row("S2", "lena.orion@example.test", "", name="Lena Vogt",
             text="Projekt Orion: Eine überarbeitete Keramikprobe wird benötigt."),
    ]
    assert adjust_selection(question, rows, ["S2"], candidate_ids=["S1", "S2"]) == (
        ["S2"], None, None)


def test_frozen_c3_same_generic_sender_and_text_only_projects_stays_open():
    question = "Was hat Lena Vogt zur Keramikprobe entschieden?"
    rows = [
        _row("S1", "team@example.test", "", name="Lena Vogt",
             text="Projekt Atlas: Die Keramikprobe ist freigegeben."),
        _row("S2", "team@example.test", "", name="Lena Vogt",
             text="Projekt Orion: Die Keramikprobe braucht eine Überarbeitung."),
    ]
    # Project names in prose plus one shared mailbox do not establish that
    # different source senders/persons exist. Keep this frozen case open.
    assert adjust_selection(question, rows, ["S2"], candidate_ids=["S1", "S2"]) == (
        ["S2"], None, None)


def test_mailbox_substring_cannot_choose_a_different_sender():
    assert adjust_selection(
        'Wann liefert Nora Beck <nora.park@example.test.evil> die Stoff-Farbmuster?',
        _nora_rows(), ['S1', 'S2']) == (['S1', 'S2'], None, None)


def test_prepare_and_render_use_sender_guard_before_exposing_a_single_current_report(tmp_path):
    import json
    from icarus_memory.claims import ClaimStore
    from icarus_memory.episodes import EpisodeKind, EpisodeStore
    from icarus_memory.model import Provenance, SourceType
    from icarus_memory.providers import Reply
    from icarus_memory.working_memory_answers import prepare, render
    from icarus_memory.working_memory_store import WorkingMemoryStore

    class SelectBoth:
        is_local = True
        def complete_json(self, messages, **kwargs):
            rows = json.loads(messages[-1]['content'])['sources']
            return Reply(text=json.dumps({'status': 'conflict', 'ids': [row['id'] for row in rows]}))

    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'knowledge.sqlite3')
    memory = WorkingMemoryStore(episodes)
    try:
        for row in _nora_rows():
            source, _ = episodes.record(EpisodeKind.MESSAGE, 'Farbmuster', row['context'],
                Provenance(SourceType.EMAIL), participants=row['participants'])
            assert memory.commit(episodes.support_snapshot(source.id),
                [{'start': 0, 'end': len(source.body), 'kind': 'commitment'}], model='synthetic')
        unclear = prepare('Wann liefert Nora Beck die Stoff-Farbmuster?', episodes, claims, SelectBoth())
        assert unclear['uncertainty'] == 'person'
        assert 'Welche der genannten Personen' in render(unclear, episodes, claims)[0]
        specific = prepare('Wann liefert Nora Beck von der Parkstraße 8 die Stoff-Farbmuster?', episodes, claims, SelectBoth())
        text, _, status = render(specific, episodes, claims)
        assert status == 'working_reports'
        assert 'Parkstraße 8' in text and 'Hafenweg 19' not in text
    finally:
        claims.close()
        episodes.close()


def test_prepare_adds_only_relevant_omitted_sender_candidate_and_withdrawal_invalidates(tmp_path):
    import json
    from icarus_memory.claims import ClaimStore
    from icarus_memory.episodes import EpisodeKind, EpisodeStore
    from icarus_memory.model import Provenance, SourceType
    from icarus_memory.providers import Reply
    from icarus_memory.working_memory_answers import prepare, render, _fresh
    from icarus_memory.working_memory_store import WorkingMemoryStore

    question = "Was hat Lena Vogt zur Keramikprobe entschieden?"
    rows = [
        {"mailbox": "lena.atlas@example.test", "project": "atlas",
         "body": "Die Keramikproben wurden im Projekt Atlas freigegeben."},
        {"mailbox": "lena.orion@example.test", "project": "orion",
         "body": "Projekt Orion benötigt eine überarbeitete Keramikprobe; Freigabe steht aus."},
        {"mailbox": "lena.vega@example.test", "project": "vega",
         "body": "Im Projekt Vega ist noch nicht entschieden, ob die Rechnung bezahlt wird."},
    ]

    class SelectOrion:
        is_local = True
        def complete_json(self, messages, **kwargs):
            sources = json.loads(messages[-1]["content"])["sources"]
            selected = next(row["id"] for row in sources if row.get("project_id") == "orion")
            return Reply(text=json.dumps({"status": "reports", "ids": [selected]}))

    episodes = EpisodeStore(tmp_path / "episodes.sqlite3")
    claims = ClaimStore(tmp_path / "knowledge.sqlite3")
    memory = WorkingMemoryStore(episodes)
    ids = []
    try:
        for row in rows:
            sender = f"Lena Vogt <{row['mailbox']}>"
            source, _ = episodes.record(EpisodeKind.MESSAGE, "Keramikprobe", row["body"],
                Provenance(SourceType.EMAIL), participants=[sender], project_id=row["project"])
            ids.append(source.id)
            assert memory.commit(episodes.support_snapshot(source.id),
                [{"start": 0, "end": len(source.body), "kind": "fact"}], model="synthetic")

        answer = prepare(question, episodes, claims, SelectOrion())
        assert answer["uncertainty"] == "person"
        assert {ref["episode_id"] for ref in answer["refs"]} == set(ids[:2])
        rendered, _, _ = render(answer, episodes, claims)
        assert "Projekt Atlas" in rendered and "Projekt Orion" in rendered
        assert "Projekt Vega" not in rendered

        episodes.ignore(ids[0])
        assert not _fresh(answer, episodes, claims)
        unavailable, _, status = render(answer, episodes, claims)
        assert status == "working_unavailable"
        assert "Grundlage" in unavailable
    finally:
        claims.close()
        episodes.close()


def test_negated_address_does_not_select_the_excluded_sender():
    assert adjust_selection(
        'Wann liefert Nora Beck, nicht die von der Parkstraße 8?',
        _nora_rows(), ['S1', 'S2']) == (['S1', 'S2'], None, None)


def test_conjunction_between_objects_keeps_a_singular_person_question():
    ids, status, _ = adjust_selection('Wann liefert Nora Beck Muster und Rechnung?',
        _nora_rows(), ['S1', 'S2'])
    assert ids == ['S1', 'S2'] and status == 'person'


from tests.test_context_identity import core


def test_coselected_confirmed_claim_does_not_disable_sender_guard(core):
    import json
    from icarus_memory.episodes import EpisodeKind
    from icarus_memory.model import Provenance, SourceType
    from icarus_memory.providers import Reply
    from icarus_memory.working_memory_answers import prepare
    from icarus_memory.working_memory_store import WorkingMemoryStore
    _, provider, episodes, claims, accept = core
    confirmed, _ = accept('person:nora', 'Nora Beck liefert die Stoff-Farbmuster für Atelier Orion.')
    memory = WorkingMemoryStore(episodes)
    for row in _nora_rows():
        source, _ = episodes.record(EpisodeKind.MESSAGE, 'Farbmuster', row['context'],
            Provenance(SourceType.EMAIL), participants=row['participants'])
        assert memory.commit(episodes.support_snapshot(source.id),
            [{'start': 0, 'end': len(source.body), 'kind': 'commitment'}], model='synthetic')
    def select_all(messages, **kwargs):
        rows = json.loads(messages[-1]['content'])['sources']
        assert any(row['id'].startswith('K') for row in rows)
        return Reply(text=json.dumps({'status': 'conflict', 'ids': [row['id'] for row in rows]}))
    provider.complete_json = select_all
    answer = prepare('Wann liefert Nora Beck die Stoff-Farbmuster?', episodes, claims, provider)
    assert answer['uncertainty'] == 'person'
    assert confirmed.id in answer['claim_basis']
    scoped = prepare('Wann liefert Nora Beck von der Parkstraße 8 die Stoff-Farbmuster?', episodes, claims, provider)
    assert len(scoped['refs']) == 1
    assert scoped['uncertainty'] == 'conflict'  # A K contradiction is not silently dismissed.
