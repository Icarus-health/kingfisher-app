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


DOC_EINKAUF = 'Alex Winter arbeitet im Einkauf der Firma A. Seine E-Mail-Adresse lautet alex.winter@firma-a.invalid.'
DOC_SCHULE = ('Eine andere Person heißt ebenfalls Alex Winter. Sie arbeitet an der Schule B. '
              'Ihre E-Mail-Adresse lautet a.winter@schule-b.invalid.')


def test_explicit_other_person_document_restores_omitted_original_without_sender_metadata():
    rows = [{'id': 'S1', 'text': DOC_EINKAUF, 'context': DOC_EINKAUF, 'participants': []},
            {'id': 'S2', 'text': DOC_SCHULE, 'context': DOC_SCHULE, 'participants': []}]
    ids, forced, hint = adjust_selection('Welche E-Mail-Adresse hat Alex Winter?', rows, ['S1'],
                                         candidate_ids=['S1', 'S2'])
    assert ids == ['S1', 'S2'] and forced == 'person'
    assert hint and 'Original' in hint


def test_explicit_document_peer_keeps_specific_question_and_does_not_invent_people():
    rows = [{'id': 'S1', 'text': DOC_EINKAUF, 'context': DOC_EINKAUF, 'participants': []},
            {'id': 'S2', 'text': DOC_SCHULE, 'context': DOC_SCHULE, 'participants': []}]
    assert adjust_selection('Welche E-Mail-Adresse hat Alex Winter aus dem Einkauf?', rows, ['S1'],
                            candidate_ids=['S1', 'S2']) == (['S1'], None, None)
    for later in [
        'Alex Winter hat seine E-Mail-Adresse geändert; seine neue Adresse lautet alex@neu.invalid.',
        'Alex Winter verwendet beruflich und privat mehrere E-Mail-Adressen.',
        'Es ist keine andere Person namens Alex Winter; lediglich seine E-Mail-Adresse hat sich geändert.',
        'Es ist nicht eine andere Person namens Alex Winter; seine E-Mail-Adresse hat sich geändert.',
        'Eine andere Person heißt ebenfalls Alex Winter ist falsch; seine E-Mail-Adresse hat sich geändert.',
        'Eine andere Person heißt ebenfalls Jana Schmidt. Ihre E-Mail-Adresse lautet jana@schule.invalid.',
    ]:
        rows[1].update(text=later, context=later)
        assert adjust_selection('Welche E-Mail-Adresse hat Alex Winter?', rows, ['S1'],
                                candidate_ids=['S1', 'S2']) == (['S1'], None, None)


def test_specific_document_question_is_not_reopened_by_more_sources_from_same_context():
    meeting = 'Heute um 14:00 Gespräch mit Alex Winter aus dem Einkauf der Firma A.'
    rows = [{'id': 'S1', 'text': DOC_EINKAUF, 'context': DOC_EINKAUF, 'participants': []},
            {'id': 'S2', 'text': DOC_SCHULE, 'context': DOC_SCHULE, 'participants': []},
            {'id': 'S3', 'text': meeting, 'context': meeting, 'participants': []}]
    assert adjust_selection('Welche E-Mail-Adresse hat Alex Winter aus dem Einkauf?', rows, ['S1'],
                            candidate_ids=['S1', 'S2', 'S3']) == (['S1'], None, None)
    ids, forced, _ = adjust_selection('Welche E-Mail-Adresse hat Alex Winter?', rows, ['S1'],
                                      candidate_ids=['S1', 'S2', 'S3'])
    assert ids == ['S1', 'S2'] and forced == 'person'


def test_lowercase_question_keeps_explicit_original_person_distinction():
    rows = [{'id': 'S1', 'text': DOC_EINKAUF, 'context': DOC_EINKAUF, 'participants': []},
            {'id': 'S2', 'text': DOC_SCHULE, 'context': DOC_SCHULE, 'participants': []}]
    ids, forced, _ = adjust_selection('welche e-mail-adresse hat alex winter?', rows, ['S1'],
                                      candidate_ids=['S1', 'S2'])
    assert ids == ['S1', 'S2'] and forced == 'person'


def test_lowercase_context_qualifier_keeps_an_already_specific_document_answer():
    rows = [{'id': 'S1', 'text': DOC_EINKAUF, 'context': DOC_EINKAUF, 'participants': []},
            {'id': 'S2', 'text': DOC_SCHULE, 'context': DOC_SCHULE, 'participants': []}]
    for question in ['Welche E-Mail-Adresse hat Alex Winter aus dem einkauf?',
                     'welche e-mail-adresse hat alex winter aus dem einkauf?']:
        assert adjust_selection(question, rows, ['S1'], candidate_ids=['S1', 'S2']) == (['S1'], None, None)


def test_explicit_document_peer_requires_full_original_and_honours_candidate_exclusions():
    rows = [{'id': 'S1', 'text': DOC_EINKAUF, 'context': DOC_EINKAUF, 'participants': []},
            {'id': 'S2', 'text': 'Ihre E-Mail-Adresse lautet a.winter@schule-b.invalid.',
             'context': DOC_SCHULE, 'participants': []}]
    ids, forced, _ = adjust_selection('Welche E-Mail-Adresse hat Alex Winter?', rows, ['S1'],
                                      candidate_ids=['S1', 'S2'])
    assert ids == ['S1', 'S2'] and forced == 'person'
    assert adjust_selection('Welche E-Mail-Adresse hat Alex Winter?', rows, ['S1'],
                            candidate_ids=['S1']) == (['S1'], None, None)
    rows[1]['andere_person'] = {'gemeinte_adresse': 'alex.winter@firma-a.invalid'}
    assert adjust_selection('Welche E-Mail-Adresse hat Alex Winter?', rows, ['S1'],
                            candidate_ids=['S1', 'S2']) == (['S1'], None, None)


def test_explicit_document_person_guard_reopens_legacy_and_preserves_specific_answers(tmp_path):
    import copy
    from icarus_memory import working_memory_answers as answers
    from icarus_memory.claims import ClaimStore
    from icarus_memory.episodes import EpisodeKind, EpisodeStore
    from icarus_memory.model import Provenance, SourceType
    from icarus_memory.working_memory_store import WorkingMemoryStore
    from tests.test_satzantwort import Skript
    episodes, claims = EpisodeStore(tmp_path / 'document-e.sqlite3'), ClaimStore(tmp_path / 'document-k.sqlite3')
    try:
        ids = []
        for title, body in [('Einkauf', DOC_EINKAUF), ('Schule', DOC_SCHULE)]:
            source, _ = episodes.record(EpisodeKind.DOCUMENT, title, body, Provenance(SourceType.DOCUMENT))
            assert source.participants == []
            assert WorkingMemoryStore(episodes).commit(episodes.support_snapshot(source.id),
                [{'start': 0, 'end': len(body), 'kind': 'fact'}], model='synthetic')
            ids.append(source.id)
        provider = Skript({'status': 'nichts_vorliegend', 'saetze': []},
                         auswahl=lambda user: [row['id'] for row in user['sources'] if row['title'] == 'Einkauf'])
        answer = answers.prepare('Welche E-Mail-Adresse hat Alex Winter?', episodes, claims, provider,
                                 semantic_search=None, saetze=True)
        assert answer['status'] == 'unclear' and answer['uncertainty'] == 'person'
        assert {ref['episode_id'] for ref in answer['refs']} == set(ids)
        assert provider.satzanfragen == []
        text, links, status = answers.render(answer, episodes, claims)
        assert status == 'working_unclear' and DOC_EINKAUF in text and DOC_SCHULE in text
        assert 'Welche der genannten Personen' in text
        assert {link['episode_id'] for link in links} == set(ids)
        legacy = copy.deepcopy(answer)
        legacy.update(status='reports', uncertainty='none', refs=[ref for ref in legacy['refs'] if ref['episode_id'] == ids[0]])
        assert not answers._fresh(legacy, episodes, claims)
        reopened = answers.project_message({'role': 'assistant', 'content': 'Alex Winter hat alex.winter@firma-a.invalid.',
            'metadata': {'context': {'working_answer': legacy}}}, episodes, claims)
        assert reopened['metadata']['context']['answer_contract']['status'] == 'working_unavailable'
        assert 'alex.winter@firma-a.invalid' not in reopened['content']
        specific = answers.prepare('Welche E-Mail-Adresse hat Alex Winter aus dem Einkauf?', episodes, claims,
                                   provider, semantic_search=None, saetze=True)
        assert specific['status'] == 'reports'
        assert [ref['episode_id'] for ref in specific['refs']] == [ids[0]]
        compact, linked, status = answers.render(specific, episodes, claims)
        assert status == 'working_reports' and 'nicht verlässlich beantworten' in compact
        assert [link['episode_id'] for link in linked] == [ids[0]]
        assert episodes.get(linked[0]['episode_id']).body == DOC_EINKAUF
        episodes.ignore(ids[1])
        assert answers.render(answer, episodes, claims)[2] == 'working_unavailable'
        assert episodes.get(ids[1]).body == DOC_SCHULE
    finally:
        claims.close()
        episodes.close()
