"""Eine Erwähnung verknüpft eine Quelle, aber nicht sämtliche Aussagen darin."""
from copy import deepcopy

from icarus_memory.memory_categories import Categories
from tests.test_akten import akten, einordnen, neu_rechnen  # noqa: F401
from tests.test_bezuege import ICH, JETZT, Modell, quelle, stelle, welt  # noqa: F401

SENDER = 'Nora Becker <nora@redaktion.example>'
PERSON = 'person:a:nora@redaktion.example'
MENTION = 'person:n:tim faber'
CURRENT = 'Bitte senden Sie den Artikel bis Freitag. Die Abgabe erfolgt Ende Oktober.'
SIGNATURE = 'Geschäftsführung: Tim Faber.'


def _categorize(episodes, source, mentions):
    categories = Categories(episodes)
    categories.request_recheck([source.id])
    result = categories.run(Modell({'categories': [], 'entities': mentions}), source_ids=[source.id], limit=1)
    assert result.ok


def _signature_source(episodes):
    body = CURRENT + '\n\n' + SIGNATURE
    source = quelle(episodes, 'Artikelanfrage', body, [SENDER, f'Lea <{ICH}>'])
    einordnen(episodes, source, [(CURRENT, 'request')])
    _categorize(episodes, source, [stelle(body, 'Tim Faber')])
    return source


def _assert_no_personal_details(profile):
    assert profile['offen']['gesamt'] == 0
    assert profile['offen']['erledigt']['gesamt'] == 0
    assert profile['fristen']['gesamt'] == {'kommend': 0, 'verstrichen': 0, 'ersetzt': 0}
    assert profile['fristen']['ohne_datum']['gesamt'] == 0
    assert profile['stand_der_dinge'] == {'aktuell': None, 'vorher': [], 'vorher_gesamt': 0,
                                        'weitere': [], 'weitere_gesamt': 0}


def test_signature_mention_keeps_source_without_other_persons_request_or_deadline(welt, akten):
    episodes, _, bezuege = welt
    source = _signature_source(episodes)
    original = deepcopy(episodes.get(source.id).to_dict())
    profile = neu_rechnen(akten).akte(MENTION, jetzt=JETZT)
    _assert_no_personal_details(profile)
    assert profile['quellen']['gesamt'] == 1
    assert profile['verlauf']['eintraege'][0]['episode_id'] == source.id
    assert profile['verlauf']['eintraege'][0]['text'] is None
    assert any(x['sache'] == MENTION for x in bezuege.bezuege_der_quelle(source.id)['bezuege'])
    assert episodes.get(source.id).to_dict() == original


def test_actual_sender_keeps_current_request_and_unspecified_deadline(welt, akten):
    episodes, _, _ = welt
    _signature_source(episodes)
    profile = neu_rechnen(akten).akte(PERSON, jetzt=JETZT)
    assert [x['text'] for x in profile['offen']['eintraege']] == [CURRENT]
    assert any('Ende Oktober' in x['ausdruck'] for x in profile['fristen']['ohne_datum']['eintraege'])


def test_mentioned_person_only_gets_the_paragraph_with_their_evidence(welt, akten):
    episodes, _, _ = welt
    own = 'Tim Faber soll die Unterlagen bis zum 12. Oktober 2026 schicken.'
    body = CURRENT + '\n\n' + own
    source = quelle(episodes, 'Zwei verschiedene Bitten', body, [SENDER])
    einordnen(episodes, source, [(CURRENT, 'request'), (own, 'request')])
    _categorize(episodes, source, [stelle(body, 'Tim Faber')])
    profile = neu_rechnen(akten).akte(MENTION, jetzt=JETZT)
    assert [x['text'] for x in profile['offen']['eintraege']] == [own]
    assert profile['fristen']['ohne_datum']['gesamt'] == 0
    assert {x['datum'] for x in profile['fristen']['kommend']} == {'2026-10-12'}


def test_quoted_person_does_not_get_newer_request_or_current_status(welt, akten):
    episodes, _, _ = welt
    status = 'Die Einreichung ist jetzt abgeschlossen.'
    old = 'Tim Faber fragte im Jahr 2020 nach dem damaligen Entwurf.'
    body = CURRENT + '\n\n' + status + '\n\n' + old
    source = quelle(episodes, 'Nachricht mit Historie', body, [SENDER])
    einordnen(episodes, source, [(CURRENT, 'request'), (status, 'status'), (old, 'historical')])
    _categorize(episodes, source, [stelle(body, 'Tim Faber')])
    profile = neu_rechnen(akten).akte(MENTION, jetzt=JETZT)
    _assert_no_personal_details(profile)
    assert profile['verlauf']['eintraege'][0]['text'] is None
    assert profile['verlauf']['eintraege'][0]['episode_id'] == source.id


def test_same_name_resolved_to_known_address_does_not_expand_source_scope(welt, akten):
    episodes, _, _ = welt
    quelle(episodes, 'Kontakt', 'Guten Tag.', ['Tim Faber <tim@andere.example>'])
    source = _signature_source(episodes)
    profile = neu_rechnen(akten).akte('person:a:tim@andere.example', jetzt=JETZT)
    _assert_no_personal_details(profile)
    assert source.id in {x['episode_id'] for x in profile['verlauf']['eintraege']}


def test_non_person_file_keeps_the_existing_correspondence_context(welt, akten):
    episodes, _, _ = welt
    _signature_source(episodes)
    profile = neu_rechnen(akten).akte('organisation:redaktion', jetzt=JETZT)
    assert [x['text'] for x in profile['offen']['eintraege']] == [CURRENT]


def test_explicit_source_assignment_is_preserved(welt, akten):
    episodes, _, bezuege = welt
    source = _signature_source(episodes)
    bezuege.aktualisieren()
    bezuege.nutzer_setzen(source.id, MENTION, 'zu')
    before = bezuege.bezuege_der_quelle(source.id)
    profile = akten.akte(MENTION, jetzt=JETZT)
    assert profile['quellen']['gesamt'] == 1
    assert bezuege.bezuege_der_quelle(source.id) == before


def test_changed_mention_offsets_invalidate_cached_person_context(welt, akten):
    episodes, _, _ = welt
    first = 'Tim Faber soll die Freigabe bis Freitag schicken.'
    second = 'Tim Faber soll die Rechnung bis Montag prüfen.'
    body = first + '\n\n' + second
    source = quelle(episodes, 'Zwei belegte Textstellen', body, [SENDER])
    einordnen(episodes, source, [(first, 'request'), (second, 'request')])
    _categorize(episodes, source, [stelle(body, 'Tim Faber')])
    initial = neu_rechnen(akten).akte(MENTION, jetzt=JETZT)
    assert [x['text'] for x in initial['offen']['eintraege']] == [first]
    repeated = akten.akte(MENTION, jetzt=JETZT)
    assert repeated['aus_zwischenspeicher']
    _categorize(episodes, source, [stelle(body, 'Tim Faber', nach=len(first))])
    updated = neu_rechnen(akten).akte(MENTION, jetzt=JETZT)
    assert not updated['aus_zwischenspeicher']
    assert updated['eingabestand'] != initial['eingabestand']
    assert [x['text'] for x in updated['offen']['eintraege']] == [second]


def test_legacy_overview_cannot_reintroduce_an_unrelated_request(welt, akten, monkeypatch):
    import icarus_memory.akten as module
    from icarus_memory.lage import Lagen, eingabe_aus_akte
    episodes, _, bezuege = welt
    source = _signature_source(episodes)
    bezuege.aktualisieren()
    with monkeypatch.context() as old:
        old.setattr(module, 'AKTEN_VERSION', 5)
        old.setattr(module, '_personen_abschnitte', lambda _sache, _quellen, items: items)
        profile = akten.akte(MENTION, jetzt=JETZT)
        fingerprint = eingabe_aus_akte(profile).fingerabdruck
    lagen = Lagen(episodes, akten)
    source_fp = bezuege.quellen_von(MENTION)[0]['fp']
    lagen._speichern(MENTION, fingerprint, 'synthetic-old-model', {
        'saetze': [{'text': CURRENT, 'belege': [{'nummer': 1, 'episode_id': source.id, 'fp': source_fp}]}],
        'modell_name': 'synthetic-old-model', 'eingabe_quellen': [source.id], 'verworfen': 0})
    stored = lagen._zeile(MENTION)['daten']
    current = akten.akte(MENTION, jetzt=JETZT)
    assert lagen.ausstehend(MENTION, current)
    assert lagen.lage(MENTION, current) is None
    assert lagen._zeile(MENTION)['daten'] == stored


def test_source_linked_task_is_not_assigned_to_a_signature_mention(welt, akten):
    from types import SimpleNamespace
    from icarus_memory.akten_routes import aufgaben_zu
    from icarus_memory.model import Provenance, SourceType
    from icarus_memory.tasks import Task
    episodes, _, bezuege = welt
    source = _signature_source(episodes)
    task = Task('t-source', 'Artikel an Nora senden',
                Provenance(source_type=SourceType.USER_STATED, source_ref=f'episode:{source.id}'),
                JETZT, due=JETZT)
    tasks = SimpleNamespace(all_tasks=lambda **kw: [task], open_tasks=lambda **kw: [task])
    app = SimpleNamespace(state=SimpleNamespace(tasks=tasks))
    akten._aufgaben = lambda sache, ids: aufgaben_zu(app, bezuege, sache, ids)
    profile = neu_rechnen(akten).akte(MENTION, jetzt=JETZT)
    assert profile['aufgaben']['gesamt'] == 0
    assert akten.akte(PERSON, jetzt=JETZT)['aufgaben']['gesamt'] == 1
    # Die ausdrueckliche Aufgaben-Zustaendigkeit bleibt staerker als der Quellenfilter.
    task.wartet_auf = 'Tim Faber'
    assert akten.akte(MENTION, jetzt=JETZT)['aufgaben']['eintraege'][0]['id'] == task.id
    task.wartet_auf = None
    bezuege.nutzer_setzen(source.id, MENTION, 'zu')
    assert akten.akte(MENTION, jetzt=JETZT)['aufgaben']['gesamt'] == 1
    assert tasks.all_tasks() == [task]
