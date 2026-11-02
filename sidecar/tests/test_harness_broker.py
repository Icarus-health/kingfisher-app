"""Worker capabilities stay scoped, bounded and dependent on current evidence."""
from concurrent.futures import ThreadPoolExecutor
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
