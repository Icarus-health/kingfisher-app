"""Eigene Berichtigungen ersetzen keinen Originaltext und bestätigen kein Wissen."""
import pytest

from tests.test_context_identity import core
from tests.test_source_answers_http import _api, _ask, _conversation, _upload
from tests.test_conversation_retraction import _close_app
from tests.test_working_memory_flow import classifier, run_working, TEXT, QUESTION
from icarus_memory.episodes import EpisodeState, EpisodeStore
from icarus_memory.model import SourceType
from icarus_memory.working_memory_store import WorkingMemoryStore

CORRECTED = 'Mainz: Anna liefert den Entwurf am 28. September 2026, nur wenn die Freigabe vorliegt. Die Freigabe fehlt noch.'


@pytest.fixture
def setup_correction(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    source = _upload(client, TEXT)
    run_working(app)
    yield app, client, provider, source
    client.close()
    _close_app(app)


def preview(client, source):
    response = client.get(f'/api/v1/memory/working/{source}/correction')
    assert response.status_code == 200, response.text
    return response.json()


def submit(client, source, state, body=CORRECTED):
    return client.post(f'/api/v1/memory/working/{source}/correction',
        json={'fingerprint': state['fingerprint'], 'body': body})


def test_corrected_source_is_immediately_retrievable_and_old_answer_disappears(setup_correction):
    app, client, provider, source = setup_correction
    conversation = _conversation(client)
    assert TEXT in _ask(client, conversation, QUESTION)['content']
    before_claims = app.state.claims.revision
    before_proposals = app.state.proposals.counts()
    before_calls = len(provider.calls)
    state = preview(client, source)
    assert state['body'] == TEXT
    response = submit(client, source, state)
    assert response.status_code == 201, response.text
    corrected_id = response.json()['episode_id']
    corrected = app.state.episodes.get(corrected_id)
    assert corrected.body == CORRECTED
    assert corrected.provenance.source_type is SourceType.MANUAL_CORRECTION
    assert corrected.provenance.source_ref.startswith(f'source-correction:{source}:')
    assert corrected.occurred_at is None
    assert corrected.participants == [] and corrected.project_id is None
    assert corrected.produced == []
    assert len(provider.calls) == before_calls
    assert app.state.claims.revision == before_claims
    assert app.state.proposals.counts() == before_proposals
    original = app.state.episodes.get(source)
    assert original.body == TEXT and original.state is EpisodeState.IGNORED
    old_answer = client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
    assert TEXT not in old_answer['content']
    new_answer = _ask(client, _conversation(client), QUESTION)
    assert CORRECTED in new_answer['content'] and TEXT not in new_answer['content']
    assert [ref['episode_id'] for ref in new_answer['metadata']['context']['working_answer']['refs']] == [corrected_id]


def test_withdrawal_and_restart_do_not_restore_original(setup_correction):
    app, client, provider, source = setup_correction
    corrected = submit(client, source, preview(client, source)).json()['episode_id']
    conversation = _conversation(client)
    assert CORRECTED in _ask(client, conversation, QUESTION)['content']
    assert client.post(f'/api/v1/episodes/{corrected}/ignore').status_code == 200
    assert CORRECTED not in client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]['content']
    reopened = EpisodeStore(app.state.episodes._path)
    try:
        assert reopened.get(source).state is EpisodeState.IGNORED
        assert reopened.get(corrected).state is EpisodeState.IGNORED
        assert WorkingMemoryStore(reopened).search('Mainz')['refs'] == []
    finally:
        reopened.close()


@pytest.mark.parametrize('body', ['', ' ', TEXT, 'a' * 12001], ids=['empty','whitespace','unchanged','oversize'])
def test_invalid_or_unchanged_correction_writes_nothing(setup_correction, body):
    app, client, _, source = setup_correction
    state = preview(client, source)
    before = app.state.episodes.counts()
    assert submit(client, source, state, body).status_code == 422
    assert app.state.episodes.counts() == before
    assert app.state.episodes.get(source).state is not EpisodeState.IGNORED


def test_stale_dialog_cannot_correct_withdrawn_source(setup_correction):
    app, client, _, source = setup_correction
    state = preview(client, source)
    app.state.episodes.ignore(source)
    before = app.state.episodes.counts()
    assert submit(client, source, state).status_code == 409
    assert app.state.episodes.counts() == before


def test_storage_failure_rolls_back_correction_and_exclusion(setup_correction, monkeypatch):
    app, client, _, source = setup_correction
    state = preview(client, source)
    before = app.state.episodes.counts()
    def fail(*args, **kwargs):
        raise RuntimeError('synthetischer Speicherausfall')
    monkeypatch.setattr(WorkingMemoryStore, 'commit', fail)
    with pytest.raises(RuntimeError, match='Speicherausfall'):
        submit(client, source, state)
    assert app.state.episodes.counts() == before
    assert app.state.episodes.get(source).state is not EpisodeState.IGNORED


def test_existing_produced_knowledge_requires_existing_claim_correction(setup_correction):
    app, client, _, source = setup_correction
    state = preview(client, source)
    app.state.episodes.mark_consolidated(source, produced=['existing:fact'])
    before = app.state.episodes.counts()
    assert submit(client, source, state).status_code == 409
    assert client.get(f'/api/v1/memory/working/{source}/correction').status_code == 409
    assert app.state.episodes.counts() == before
    assert app.state.episodes.get(source).state is not EpisodeState.IGNORED


def test_duplicate_submission_and_same_text_sources_stay_separate(setup_correction):
    from icarus_memory.model import Provenance
    from icarus_memory.episodes import EpisodeKind
    app, client, _, source = setup_correction
    state = preview(client, source)
    unrelated, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Andere Quelle', CORRECTED,
        Provenance(SourceType.CHAT, source_ref='other:source'), source_key='other:source')
    app.state.episodes.advance_source_head('other:source', None, unrelated.id)
    response = submit(client, source, state)
    assert response.status_code == 201
    assert response.json()['episode_id'] != unrelated.id
    count = app.state.episodes.counts()
    assert submit(client, source, state).status_code == 409
    assert app.state.episodes.counts() == count
    assert app.state.episodes.get(unrelated.id).state is not EpisodeState.IGNORED


def test_changed_metadata_rejects_old_correction_dialog(setup_correction):
    app, client, _, source = setup_correction
    state = preview(client, source)
    item = app.state.episodes.get(source)
    item.participants.append('Zusätzliche Person')
    app.state.episodes._put(item)
    count = app.state.episodes.counts()
    assert submit(client, source, state).status_code == 409
    assert app.state.episodes.counts() == count


def test_original_cannot_reopen_and_corrected_revision_replaces_first(setup_correction):
    app, client, _, source = setup_correction
    first = submit(client, source, preview(client, source)).json()['episode_id']
    assert client.post(f'/api/v1/episodes/{source}/reopen').status_code == 409
    second = submit(client, first, preview(client, first),
        CORRECTED.replace('28. September', '29. September')).json()['episode_id']
    found = WorkingMemoryStore(app.state.episodes).search('Mainz')['refs']
    assert [ref['episode_id'] for ref in found] == [second]
    assert client.post(f'/api/v1/episodes/{first}/reopen').status_code == 409
    assert client.post(f'/api/v1/episodes/{second}/ignore').status_code == 200
    assert WorkingMemoryStore(app.state.episodes).search('Mainz')['refs'] == []
    assert client.post(f'/api/v1/episodes/{source}/reopen').status_code == 409


def test_withdrawing_original_invalidates_all_corrections_and_saved_answers(setup_correction):
    app, client, _, source = setup_correction
    first = submit(client, source, preview(client, source)).json()['episode_id']
    updated = CORRECTED.replace('28. September', '29. September')
    second = submit(client, first, preview(client, first), updated).json()['episode_id']
    conversation = _conversation(client)
    assert updated in _ask(client, conversation, QUESTION)['content']
    # Das Original ist bereits wegen der Berichtigung ignored. Trotzdem muss
    # ein späterer ausdrücklicher Entzug die abgeleiteten Berichtigungen sperren.
    assert client.post(f'/api/v1/episodes/{source}/ignore').status_code == 200
    assert not app.state.episodes.support_snapshot(first).current()
    assert not app.state.episodes.support_snapshot(second).current()
    assert WorkingMemoryStore(app.state.episodes).search('Mainz')['refs'] == []
    old = client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
    assert updated not in old['content']


def test_new_original_version_makes_bound_correction_stale(setup_correction):
    from icarus_memory.model import Provenance
    from icarus_memory.episodes import EpisodeKind
    app, client, _, uploaded = setup_correction
    app.state.episodes.ignore(uploaded)
    initial, _ = app.state.episodes.record(EpisodeKind.DOCUMENT, 'Versioniertes Dokument', TEXT,
        Provenance(SourceType.DOCUMENT), source_key='document:versioned')
    app.state.episodes.advance_source_head('document:versioned', None, initial.id)
    source = initial.id
    original = app.state.episodes.support_snapshot(source)
    assert original.source_key
    correction = submit(client, source, preview(client, source)).json()['episode_id']
    newer, _ = app.state.episodes.record(EpisodeKind.DOCUMENT, original.episode.title,
        'Mainz: Der Entwurf ist angekommen.', Provenance(SourceType.DOCUMENT),
        source_key=original.source_key)
    app.state.episodes.advance_source_head(original.source_key, source, newer.id)
    assert not app.state.episodes.support_snapshot(correction).current()
    assert client.get(f'/api/v1/episodes/{correction}').json()['correction_current'] is False
    assert WorkingMemoryStore(app.state.episodes).search('Mainz')['refs'] == []
    assert app.state.episodes.get(correction).body == CORRECTED


def test_relative_words_do_not_acquire_today_as_new_reference_time(setup_correction):
    app, client, _, source = setup_correction
    corrected = submit(client, source, preview(client, source),
        'Mainz: Anna liefert morgen. Das Datum dieser Angabe ist noch offen.').json()['episode_id']
    assert app.state.episodes.get(corrected).occurred_at is None


def test_alternative_when_question_uses_the_same_correction_context(setup_correction):
    app, client, _, source = setup_correction
    corrected = submit(client, source, preview(client, source)).json()['episode_id']
    answer = _ask(client, _conversation(client), 'Zu welchem Termin ist Annas Entwurf für Mainz vorgesehen?')
    assert CORRECTED in answer['content']
    assert answer['metadata']['context']['working_answer']['refs'][0]['episode_id'] == corrected


def test_original_withdrawal_disputes_claim_from_correction_in_profile(setup_correction):
    from icarus_memory.proposals import Evidence
    app, client, _, source = setup_correction
    correction = submit(client, source, preview(client, source)).json()['episode_id']
    entity = app.state.claims.entities.create('person', 'Anna')
    item = app.state.episodes.get(correction)
    proposal, _ = app.state.knowledge_service.propose(subject_ref=entity['id'],
        predicate='reports', value=CORRECTED, statement=CORRECTED,
        rationale='Ausdrücklich bestätigte Testangabe',
        evidence=[Evidence(item.id, item.body, item.digest)])
    claim = app.state.knowledge_service.accept(proposal.id, supersedes=[])
    url = f"/api/v1/memory/registry/{entity['id']}"
    assert [entry['id'] for entry in client.get(url).json()['claims']] == [claim.id]
    assert client.post(f'/api/v1/episodes/{source}/reopen').status_code == 409
    assert app.state.claims.get(claim.id).status.value == 'active'
    assert client.post(f'/api/v1/episodes/{source}/ignore').status_code == 200
    assert app.state.claims.get(claim.id).status.value == 'disputed'
    assert client.get(url).json()['claims'] == []


def test_source_replacement_invalidates_claim_from_correction(setup_correction):
    from icarus_memory.proposals import Evidence
    from icarus_memory.model import Provenance
    from icarus_memory.episodes import EpisodeKind
    from icarus_memory.source_versions import track_source
    app, client, _, _ = setup_correction
    original, _ = app.state.episodes.record(EpisodeKind.DOCUMENT, 'Dokument', TEXT,
        Provenance(SourceType.DOCUMENT), source_key='document:replace')
    track_source(app.state.episodes, app.state.claims, 'document:replace', original)
    correction = submit(client, original.id, preview(client, original.id)).json()['episode_id']
    entity = app.state.claims.entities.create('person', 'Anna')
    item = app.state.episodes.get(correction)
    proposal, _ = app.state.knowledge_service.propose(subject_ref=entity['id'],
        predicate='reports', value=CORRECTED, statement=CORRECTED, rationale='Testangabe',
        evidence=[Evidence(item.id, item.body, item.digest)])
    claim = app.state.knowledge_service.accept(proposal.id, supersedes=[])
    newer, _ = app.state.episodes.record(EpisodeKind.DOCUMENT, 'Dokument', 'Mainz: Entwurf angekommen.',
        Provenance(SourceType.DOCUMENT), source_key='document:replace')
    track_source(app.state.episodes, app.state.claims, 'document:replace', newer)
    assert app.state.claims.get(claim.id).status.value == 'disputed'


def test_missing_original_document_with_correction_is_not_skipped(setup_correction, tmp_path):
    from icarus_memory.model import Provenance
    from icarus_memory.episodes import EpisodeKind
    from icarus_memory.source_versions import source_key, track_source, exclude_missing_documents
    app, client, _, _ = setup_correction
    folder = tmp_path / 'vault'
    folder.mkdir()
    key = source_key(folder, 'vault:removed.md')
    original, _ = app.state.episodes.record(EpisodeKind.DOCUMENT, 'Dokument', TEXT,
        Provenance(SourceType.DOCUMENT, source_ref='vault:removed.md'), source_key=key)
    track_source(app.state.episodes, app.state.claims, key, original)
    correction = submit(client, original.id, preview(client, original.id)).json()['episode_id']
    assert app.state.episodes.support_snapshot(correction).current()
    assert exclude_missing_documents(app.state.episodes, app.state.claims, folder, 'markdown') == 1
    assert not app.state.episodes.support_snapshot(correction).current()
    assert exclude_missing_documents(app.state.episodes, app.state.claims, folder, 'markdown') == 0
