"""Worker capabilities stay scoped, bounded and dependent on current evidence."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import threading

import pytest

from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.procedures import ProcedureStore
from icarus_memory.harness_broker import Broker, BridgeError


@pytest.fixture
def setup(tmp_path):
    episodes = EpisodeStore(tmp_path / 'sources.sqlite3')
    procedures = ProcedureStore(tmp_path / 'skills.sqlite3')
    clock = [0.0]
    broker = Broker(episodes, procedures, clock=lambda: clock[0], max_grants=2)
    def put(body, title='Künstliche Quelle'):
        return episodes.record(EpisodeKind.DOCUMENT, title, body,
            Provenance(source_type=SourceType.DOCUMENT))[0]
    yield broker, episodes, procedures, clock, put
    procedures.close()
    episodes.close()


def issue(broker, *sources, **changes):
    return broker.issue('Wo liegt die Zugangskarte?', area='analysis',
                        sources=[e.id for e in sources], **changes)


def test_only_selected_and_discovered_originals_can_be_opened(setup):
    broker, _, _, _, put = setup
    selected = put('Die Zugangskarte liegt in Fach A42.')
    secret = put('Die Zugangskarte ist privat und nicht freigegeben.')
    grant = issue(broker, selected)
    with pytest.raises(BridgeError):
        broker.invoke(grant['token'], 'source_excerpt', {'id': selected.id, 'start': 0, 'end': 10})
    found = broker.invoke(grant['token'], 'memory_search', {'query': 'Zugangskarte'})
    assert [e['id'] for e in found['items']] == [selected.id]
    quote = broker.invoke(grant['token'], 'source_excerpt', {'id': selected.id, 'start': 4, 'end': 16})
    assert quote['quote'] == selected.body[4:16]
    assert quote['status'] == 'source_reports_unconfirmed'
    with pytest.raises(BridgeError):
        broker.invoke(grant['token'], 'source_excerpt', {'id': secret.id, 'start': 0, 'end': 10})
    assert found['scope'] == 'selected_originals_literal'
    assert secret.id not in str(found)


def test_selected_original_opens_generic_question_without_a_literal_hit(setup):
    broker, episodes, _, _, put = setup
    selected = put('  Äpfel\nliegen in Fach A42.\r\n' + 'α' * 410, title='Ablage')
    secret = put('VERTRAULICH: nicht ausgewähltes Original', title='Privat')
    before = [episodes.get(e.id).to_dict() for e in (selected, secret)]
    grant = broker.issue('Fasse das bitte zusammen.', area='analysis', sources=[selected.id])
    found = broker.invoke(grant['token'], 'memory_search', {'query': 'zusammen'})
    assert found['items'] == []
    with pytest.raises(BridgeError):
        broker.invoke(grant['token'], 'source_excerpt', {'id': selected.id, 'start': 0, 'end': 10})

    original = broker.invoke(grant['token'], 'selected_original', {})

    assert datetime.fromisoformat(original.pop('recorded_at')) == selected.recorded_at
    assert original == dict(id=selected.id, title='Ablage', quote=selected.body[:400],
        start=0, end=400, fingerprint=episodes.belegbarer_snapshot(selected.id).support_fingerprint(),
        occurred_at=None, source_type='document',
        status='source_reports_unconfirmed', source_length=439, partial_coverage=True)
    assert secret.id not in str(original) and 'VERTRAULICH' not in str(original)
    tail = broker.invoke(grant['token'], 'source_excerpt', {'id': selected.id, 'start': 400, 'end': 439})
    assert tail['quote'] == 'α' * 39
    with pytest.raises(BridgeError):
        broker.invoke(grant['token'], 'source_excerpt', {'id': secret.id, 'start': 0, 'end': 10})
    assert [episodes.get(e.id).to_dict() for e in (selected, secret)] == before


@pytest.mark.parametrize('body,want_end,want_partial,want_status', [
    ('', 0, False, 'no_source_text'),
    ('kurzer Originaltext', 19, False, 'source_reports_unconfirmed'),
    ('🙂' * 400, 400, False, 'source_reports_unconfirmed'),
    ('🙂' * 401, 400, True, 'source_reports_unconfirmed'),
])
def test_selected_original_reports_exact_character_coverage(setup, body, want_end, want_partial, want_status):
    broker, _, _, _, put = setup
    source = put(body)
    grant = issue(broker, source)
    result = broker.invoke(grant['token'], 'selected_original', {})
    assert result['id'] == source.id
    assert result['quote'] == body[:400]
    assert (result['start'], result['end']) == (0, want_end)
    assert result['source_length'] == len(body)
    assert result['partial_coverage'] is want_partial
    assert result['status'] == want_status


@pytest.mark.parametrize('args', [None, [], '', {'id': 'any'}, {'query': 'Original'},
    {'start': 0, 'end': 400}, {'sources': []}])
def test_selected_original_accepts_only_empty_arguments(setup, args):
    broker, _, _, _, put = setup
    source = put('Original')
    grant = issue(broker, source)
    with pytest.raises(BridgeError): broker.invoke(grant['token'], 'selected_original', args)
    with pytest.raises(BridgeError):
        broker.invoke(grant['token'], 'source_excerpt', {'id': source.id, 'start': 0, 'end': 1})


def test_selected_original_refuses_multi_source_grants_without_discovery(setup):
    broker, _, _, _, put = setup
    first, second = put('Erstes Original'), put('Zweites Original')
    grant = issue(broker, first, second)
    with pytest.raises(BridgeError): broker.invoke(grant['token'], 'selected_original', {})
    for source in (first, second):
        with pytest.raises(BridgeError):
            broker.invoke(grant['token'], 'source_excerpt', {'id': source.id, 'start': 0, 'end': 1})
    found = broker.invoke(grant['token'], 'memory_search', {'query': 'Original'})
    assert {item['id'] for item in found['items']} == {first.id, second.id}


def test_selected_original_shares_total_tool_quota_and_ninth_call_refuses(setup):
    broker, _, _, _, put = setup
    grant = issue(broker, put('Original'))
    for _ in range(7): broker.invoke(grant['token'], 'skills_select', {})
    assert broker.invoke(grant['token'], 'selected_original', {})['quote'] == 'Original'
    with pytest.raises(BridgeError, match='Werkzeuggrenze'):
        broker.invoke(grant['token'], 'selected_original', {})


def test_selected_original_does_not_relax_existing_excerpt_bounds(setup):
    broker, _, _, _, put = setup
    source = put('x' * 401)
    grant = issue(broker, source)
    broker.invoke(grant['token'], 'selected_original', {})
    for start, end in ((0, 401), (400, 402), (-1, 1), (True, 2), (0, 0)):
        with pytest.raises(BridgeError):
            broker.invoke(grant['token'], 'source_excerpt', {'id': source.id, 'start': start, 'end': end})
    assert broker.invoke(grant['token'], 'source_excerpt', {'id': source.id, 'start': 400, 'end': 401})['quote'] == 'x'


@pytest.mark.parametrize('stage', ['before', 'after_snapshot'])
@pytest.mark.parametrize('change', ['withdraw', 'replace', 'cancel', 'expire', 'revoke_skill', 'conflicting_skill'])
def test_selected_original_withholds_text_when_authority_changes(setup, monkeypatch, stage, change):
    broker, episodes, procedures, clock, _ = setup
    provenance = Provenance(source_type=SourceType.DOCUMENT)
    source = episodes.record(EpisodeKind.DOCUMENT, 'Original', 'PRIVATE_OLD_TEXT', provenance,
                             source_key='local-fixture-original')[0]
    episodes.advance_source_head('local-fixture-original', None, source.id)
    candidate = procedures.propose(skill())
    procedures.accept(candidate['id'])
    grant = broker.issue('Schreibe eine Zunftmail.', area='mail', sources=[source.id])

    def mutate():
        if change == 'withdraw': episodes.ignore(source.id)
        elif change == 'replace':
            replacement = episodes.record(EpisodeKind.DOCUMENT, 'Original', 'PRIVATE_NEW_TEXT', provenance,
                                         source_key='local-fixture-original')[0]
            episodes.advance_source_head('local-fixture-original', source.id, replacement.id)
        elif change == 'cancel': broker.cancel(grant['id'])
        elif change == 'expire': clock[0] = 120
        elif change == 'revoke_skill': procedures.revoke(candidate['id'])
        else: procedures.accept(procedures.propose(skill('zunftmail-zwei'))['id'])

    if stage == 'before':
        mutate()
    else:
        read = episodes.belegbarer_snapshot
        reads = 0
        def snapshot_then_change(*args, **kwargs):
            nonlocal reads
            snap = read(*args, **kwargs)
            reads += 1
            if reads == 2: mutate()  # After preflight and the actual original read.
            return snap
        monkeypatch.setattr(episodes, 'belegbarer_snapshot', snapshot_then_change)

    with pytest.raises(BridgeError) as error:
        broker.invoke(grant['token'], 'selected_original', {})
    assert 'PRIVATE' not in str(error.value)
    assert broker.current(grant['token']) is False


@pytest.mark.parametrize('args', [{'query':'a'}, {'query':'x'*201}, {'query':'Zugangskarte', 'url':'http://other'},
    {'query':12}, {'query':'Zugangskarte\x00'}, {'query':['Zugangskarte']}])
def test_invalid_search_is_rejected_without_implicit_coercion(setup, args):
    broker, _, _, _, put = setup
    grant = issue(broker, put('Zugangskarte'))
    with pytest.raises(BridgeError):
        broker.invoke(grant['token'], 'memory_search', args)


@pytest.mark.parametrize('name', ['shell', 'mail_send', 'read_mcp_resource', 'memory_write'])
def test_no_general_tools_or_write_authority(setup, name):
    broker, _, _, _, put = setup
    grant = issue(broker, put('Zugangskarte'))
    with pytest.raises(BridgeError):
        broker.invoke(grant['token'], name, {})


def test_expiry_revocation_and_instance_restart_invalidate_token(setup):
    broker, episodes, procedures, clock, put = setup
    source = put('Zugangskarte')
    first = issue(broker, source, ttl=10)
    clock[0] = 10
    with pytest.raises(BridgeError): broker.invoke(first['token'], 'skills_select', {})
    second = issue(broker, source)
    broker.cancel(second['id'])
    with pytest.raises(BridgeError): broker.invoke(second['token'], 'skills_select', {})
    third = issue(broker, source)
    new = Broker(episodes, procedures)
    with pytest.raises(BridgeError): new.invoke(third['token'], 'skills_select', {})


def test_all_scoped_source_changes_invalidate_even_earlier_context(setup):
    broker, episodes, _, _, put = setup
    first, second = put('Zugangskarte'), put('Termin am Dienstag')
    grant = issue(broker, first, second)
    broker.invoke(grant['token'], 'memory_search', {'query':'Zugangskarte'})
    episodes.ignore(second.id)
    with pytest.raises(BridgeError): broker.invoke(grant['token'], 'skills_select', {})


def test_current_observation_is_not_released_as_original_evidence(setup):
    broker, episodes, _, _, _ = setup
    source = episodes.record(EpisodeKind.OBSERVATION, 'Abgeleitete Notiz', 'Zugangskarte A42',
                             Provenance(source_type=SourceType.DOCUMENT))[0]
    assert episodes.support_snapshot(source.id).current()
    assert episodes.belegbarer_snapshot(source.id) is None
    with pytest.raises(BridgeError): issue(broker, source)


def skill(name='zunftmail'):
    return dict(name=name, title='Offizielle Zunftmail', area='mail',
        description='Offizielle Mail im Zunftkontext vorbereiten.', triggers=['zunftmail'],
        steps=['Anlass prüfen.', 'Entwurf gegenlesen.'], positive='Schreibe eine Zunftmail.',
        negative='Schreibe eine private Mail.')


def test_approved_skills_follow_request_and_revocation_is_terminal(setup):
    broker, _, procedures, _, put = setup
    candidate = procedures.propose(skill())
    procedures.accept(candidate['id'])
    grant = broker.issue('Schreibe eine Zunftmail.', area='mail', sources=[put('Anlass').id])
    selected = broker.invoke(grant['token'], 'skills_select', {})
    assert [e['name'] for e in selected['contextual']] == ['zunftmail']
    selected['refs'].clear()  # Caller cannot mutate authority kept by broker.
    procedures.revoke(candidate['id'])
    with pytest.raises(BridgeError): broker.invoke(grant['token'], 'skills_select', {})


def test_new_conflicting_skill_also_invalidates_old_selection(setup):
    broker, _, procedures, _, put = setup
    procedures.accept(procedures.propose(skill())['id'])
    grant = broker.issue('Schreibe eine Zunftmail.', area='mail', sources=[put('Anlass').id])
    procedures.accept(procedures.propose(skill('zunftmail-zwei'))['id'])
    with pytest.raises(BridgeError): broker.invoke(grant['token'], 'skills_select', {})


def test_request_scope_cannot_be_changed_by_skill_tool_arguments(setup):
    broker, _, procedures, _, put = setup
    procedures.accept(procedures.propose(skill())['id'])
    grant = issue(broker, put('Anlass'))
    assert not broker.invoke(grant['token'], 'skills_select', {})['contextual']
    with pytest.raises(BridgeError):
        broker.invoke(grant['token'], 'skills_select', {'message':'Schreibe eine Zunftmail.'})


def test_bounded_grants_and_tool_calls(setup):
    broker, _, _, clock, put = setup
    source = put('Zugangskarte')
    grant = issue(broker, source)
    issue(broker, source)
    with pytest.raises(BridgeError): issue(broker, source)
    for _ in range(8): broker.invoke(grant['token'], 'skills_select', {})
    with pytest.raises(BridgeError): broker.invoke(grant['token'], 'skills_select', {})
    clock[0] = 121
    assert issue(broker, source)['token'] != grant['token']


def test_model_checks_dependencies_after_inference_and_does_not_refund_failed_call(setup):
    broker, episodes, _, _, put = setup
    source = put('Zugangskarte')
    grant = issue(broker, source)
    def infer():
        episodes.ignore(source.id)
        return 'A stale answer'
    with pytest.raises(BridgeError): broker.model(grant['token'], infer)


def test_cancellation_is_not_blocked_by_slow_model(setup):
    broker, _, _, _, put = setup
    grant = issue(broker, put('Zugangskarte'))
    ready, finish = threading.Event(), threading.Event()
    def infer():
        ready.set()
        assert finish.wait(3)
        return 'Withheld answer'
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(broker.model, grant['token'], infer)
        assert ready.wait(3)
        broker.cancel(grant['id'])
        finish.set()
        with pytest.raises(BridgeError): pending.result()


def test_model_quota_is_atomic_and_exceptions_do_not_refund_it(setup):
    broker, _, _, _, put = setup
    grant = issue(broker, put('Zugangskarte'))
    def fail(): raise ValueError('provider failed')
    for _ in range(3):
        with pytest.raises(ValueError): broker.model(grant['token'], fail)
    with pytest.raises(BridgeError): broker.model(grant['token'], lambda:'must not run')


@pytest.mark.parametrize('change', [dict(sources=[]), dict(sources=['missing']), dict(ttl=0),
    dict(ttl=121), dict(area='shell'), dict(request=''), dict(ttl=True)])
def test_invalid_admission_fails_closed(setup, change):
    broker, _, _, _, put = setup
    args = dict(request='Finde Zugangskarte', area='analysis', sources=[put('Zugangskarte').id])
    with pytest.raises(BridgeError): broker.issue(**(args | change))
