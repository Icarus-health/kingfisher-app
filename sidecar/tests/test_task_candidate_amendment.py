"""Immutable, explicitly reviewed title corrections; entirely synthetic sources."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import sqlite3

from fastapi.testclient import TestClient
import pytest

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.aufgaben_von_selbst import pruefen
from icarus_memory.episodes import CHAT_LOOKUP_TAG, EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType, now
from icarus_memory.proposals import Evidence, ProposalError, ProposalKind, ProposalState, ProposalStore
from icarus_memory.server import create_app
from icarus_memory.task_detection import for_briefing
from icarus_memory.task_review import REVIEW_MARKER, current_task_context

QUOTE = 'Bitte sende die Unterlagen, idealerweise als PDF.'
OLD = 'Unterlagen als PDF senden'
TITLE = 'Unterlagen senden'


def add_bound(app, *, key='synthetic:amend', body=QUOTE):
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, 'Unterlagen', body,
        Provenance(source_type=SourceType.EMAIL, source_ref=key), source_key=key,
        occurred_at=now(),
        contacts=[{'adresse': 'sender@example.org', 'rolle': 'von'},
                  {'adresse': 'recipient@example.org', 'rolle': 'an', 'ich': True}])
    app.state.episodes.advance_source_head(key, app.state.episodes.source_head(key), episode.id)
    with app.state.proposals.transaction():
        app.state.proposals._record_task_candidates(
            episode.id, episode.digest, [{'title': OLD, 'quote': QUOTE}],
            proposed_by='synthetic/local' + REVIEW_MARKER,
            task_context=current_task_context(app.state.episodes, episode.id))
    candidate = next(p for p in app.state.proposals.pending(ProposalKind.TASK, limit=-1)
                     if p.evidence[0].episode_id == episode.id)
    return episode, candidate


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='synthetic'))
    episode, candidate = add_bound(app)
    return app, TestClient(app), episode, candidate


def payload(candidate, title=TITLE):
    evidence = candidate.evidence[0]
    return {'title': title, 'expected_statement': candidate.statement,
            'expected_episode_id': evidence.episode_id, 'expected_digest': evidence.digest,
            'expected_task_context': candidate.task_context}


def amend(env, title=TITLE, **changes):
    app, client, episode, candidate = env
    return client.post(f'/api/v1/task-candidates/{candidate.id}/amend',
                       json={**payload(candidate, title), **changes})


def proposal_rows(app):
    return [tuple(row) for row in app.state.proposals._conn.execute(
        'SELECT id,state,fingerprint,document FROM proposals ORDER BY id')]


def test_title_amendment_records_one_text_free_history_event(env, tmp_path, monkeypatch):
    from icarus_memory import logbuch
    history = logbuch.Logbuch(tmp_path / 'amendment-history.sqlite3')
    monkeypatch.setattr(logbuch, '_aktiv', history)
    try:
        response = amend(env)
        assert response.status_code == 200
        assert amend(env).json() == response.json()
        entries = [entry for entry in history.ereignisse(0)
                   if entry.art == 'aufgabenvorschlag_titel_korrigiert']
        assert len(entries) == 1
        assert entries[0].daten == {'id': env[3].id, 'nachfolger': response.json()['id']}
        assert QUOTE not in json.dumps(entries[0].daten)
    finally:
        history.close()


def test_optional_detail_amendment_preserves_source_and_history_without_task(env):
    app, client, episode, candidate = env
    source_before = app.state.episodes.support_snapshot(episode.id).fingerprint()
    original = candidate.to_dict()
    first_page = client.get('/api/v1/task-candidates/page').json()
    response = amend(env, '  ' + TITLE + '  ')
    assert response.status_code == 200, response.text
    successor = response.json()
    assert successor['id'] != candidate.id
    assert successor['statement'] == TITLE
    assert successor['state'] == 'pending'
    assert successor['produced'] is None and successor['decided_at'] is None
    assert successor['evidence'] == original['evidence']
    assert successor['task_context'] == candidate.task_context
    assert successor['task_amends'] == candidate.id
    assert successor['supersedes'] == []
    assert not successor['proposed_by'].endswith(REVIEW_MARKER)
    old = app.state.proposals.get(candidate.id).to_dict()
    assert old == {**original, 'state': 'superseded', 'decided_at': old['decided_at']}
    assert old['decided_at'] is not None
    assert app.state.tasks.all_tasks() == []
    assert app.state.episodes.support_snapshot(episode.id).fingerprint() == source_before
    assert list(app.state.store.alles()) == [] and app.state.claims.all_claims() == []
    page = client.get('/api/v1/task-candidates/page').json()
    assert page['total'] == 1 and page['items'][0]['id'] == successor['id']
    assert page['generation'] != first_page['generation']
    assert client.post(f'/api/v1/task-candidates/{candidate.id}/accept', json={'title': OLD}).status_code == 409
    assert client.post(f'/api/v1/task-candidates/{candidate.id}/reject').status_code == 409


@pytest.mark.parametrize('decision', ['pending', 'accepted', 'rejected'])
def test_same_retry_after_restart_preserves_current_successor_decision(env, decision):
    app, client, episode, candidate = env
    response = amend(env)
    assert response.status_code == 200, response.text
    successor = response.json()
    if decision == 'accepted':
        accepted = client.post(f"/api/v1/task-candidates/{successor['id']}/accept", json={'title': 'Eigener Titel'})
        assert accepted.status_code == 200, accepted.text
    elif decision == 'rejected':
        assert client.post(f"/api/v1/task-candidates/{successor['id']}/reject").status_code == 200
    current = app.state.proposals.get(successor['id']).to_dict()
    tasks_before = [t.to_dict() for t in app.state.tasks.all_tasks()]
    rows_before = proposal_rows(app)
    path = app.state.proposals._path
    app.state.proposals.close()
    app.state.proposals = ProposalStore(path)
    retry = amend(env)
    assert retry.status_code == 200, retry.text
    assert retry.json() == current
    assert proposal_rows(app) == rows_before
    assert [t.to_dict() for t in app.state.tasks.all_tasks()] == tasks_before


def test_identical_title_is_noop_after_checks(env):
    app, client, episode, candidate = env
    # The original has a now-disallowed optional detail: unchanged wording is
    # still a no-op, never a newly certified semantic review.
    before = proposal_rows(app)
    response = amend(env, OLD)
    assert response.status_code == 200, response.text
    assert response.json() == candidate.to_dict()
    assert proposal_rows(app) == before
    app.state.episodes.ignore(episode.id)
    assert amend(env, OLD).status_code == 409


def test_competing_edits_only_one_successor_and_successor_can_be_amended(env):
    app, client, episode, candidate = env
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda title: amend(env, title),
                                [TITLE, 'Unterlagen idealerweise als PDF senden']))
    assert sorted(response.status_code for response in replies) == [200, 409]
    successor = next(response.json() for response in replies if response.status_code == 200)
    assert len(app.state.proposals.pending(ProposalKind.TASK)) == 1
    next_title = 'Unterlagen idealerweise als PDF senden' if successor['statement'] == TITLE else TITLE
    followup = client.post(f"/api/v1/task-candidates/{successor['id']}/amend",
                           json=payload(app.state.proposals.get(successor['id']), next_title))
    assert followup.status_code == 200, followup.text
    assert followup.json()['task_amends'] == successor['id']
    assert app.state.tasks.all_tasks() == []


@pytest.mark.parametrize('state', [ProposalState.ACCEPTED, ProposalState.REJECTED, ProposalState.SUPERSEDED])
def test_terminal_original_is_not_reopened(env, state):
    app, client, episode, candidate = env
    getattr(app.state.proposals, {'accepted': 'accept', 'rejected': 'reject', 'superseded': 'supersede'}[state.value])(candidate.id)
    before = proposal_rows(app)
    assert amend(env).status_code == 409
    assert proposal_rows(app) == before


@pytest.mark.parametrize('case', ['legacy', 'produced', 'extra_evidence', 'missing_quote', 'not_task'])
def test_unsupported_candidate_shape_is_conflict_without_mutation(env, case):
    app, client, episode, candidate = env
    if case == 'legacy':
        candidate.task_context = None
    elif case == 'produced':
        candidate.produced = 't-existing'
    elif case == 'extra_evidence':
        candidate.evidence.append(Evidence(episode.id, QUOTE, episode.digest))
    elif case == 'missing_quote':
        candidate.evidence[0].quote = 'This quote is absent.'
    elif case == 'not_task':
        candidate, _ = app.state.proposals.propose(ProposalKind.CONFIRMATION, OLD,
            'Synthetic non-task', evidence=[Evidence(episode.id, QUOTE, episode.digest)])
        candidate.task_context = current_task_context(app.state.episodes, episode.id)
        env = app, client, episode, candidate
    app.state.proposals._put(candidate)
    # The request itself remains well-formed for the unsupported legacy case.
    changes = {'expected_task_context': '0' * 64} if case == 'legacy' else {}
    before = proposal_rows(app)
    assert amend(env, **changes).status_code == 409
    assert proposal_rows(app) == before
    assert app.state.tasks.all_tasks() == []


def test_partial_acceptance_crash_gap_is_preserved(env):
    app, client, episode, candidate = env
    task = app.state.tasks.from_suggestion(candidate.id, 'Already saved',
        Provenance(source_type=SourceType.USER_STATED, source_ref=f'episode:{episode.id}', captured_at=now()))
    before = proposal_rows(app)
    assert amend(env).status_code == 409
    assert proposal_rows(app) == before
    assert app.state.proposals.get(candidate.id).state is ProposalState.PENDING
    assert [t.to_dict() for t in app.state.tasks.all_tasks()] == [task.to_dict()]


@pytest.mark.parametrize('field,value', [('expected_statement', 'Changed old title'),
    ('expected_episode_id', 'e-missing'), ('expected_digest', 'sha256:' + '0' * 64),
    ('expected_task_context', '0' * 64)])
def test_stale_request_cas_is_conflict(env, field, value):
    app, client, episode, candidate = env
    before = proposal_rows(app)
    assert amend(env, **{field: value}).status_code == 409
    assert proposal_rows(app) == before


@pytest.mark.parametrize('change', ['contacts', 'tags', 'restored_contacts', 'head', 'digest',
                                    'ignored', 'archived', 'truncated', 'lookup', 'produced'])
def test_stale_or_ineligible_source_is_conflict(env, change):
    app, client, episode, candidate = env
    episodes = app.state.episodes
    if change in {'contacts', 'restored_contacts'}:
        contacts = [{'adresse': 'other@example.org', 'rolle': 'an'}]
        episodes.add_contacts(episode.id, contacts, [])
        if change == 'restored_contacts':
            episodes.remove_contacts(episode.id, contacts, [])
    elif change == 'tags':
        episodes.add_mail_headers(episode.id, ['mail:header:synthetic'])
    elif change == 'head':
        replacement, _ = episodes.record(EpisodeKind.MESSAGE, 'New head', QUOTE + ' Andere Fassung.',
                                         episode.provenance, source_key='synthetic:amend')
        episodes.advance_source_head('synthetic:amend', episode.id, replacement.id)
    elif change == 'digest':
        episode.body += ' Changed source.'
        episodes._put(episode)
    elif change == 'ignored':
        episodes.ignore(episode.id)
    elif change == 'archived':
        episodes.mark_consolidated(episode.id)
        assert episodes.archive_before(now() + timedelta(days=1)) == 1
    elif change in {'truncated', 'lookup'}:
        episodes.add_mail_headers(episode.id, ['source:truncated' if change == 'truncated' else CHAT_LOOKUP_TAG])
    elif change == 'produced':
        episode.produced = ['a-derived']
        episodes._put(episode)
    before = proposal_rows(app)
    assert amend(env).status_code == 409
    assert proposal_rows(app) == before
    assert app.state.tasks.all_tasks() == []


@pytest.mark.parametrize('title', ['', '   ', 'x' * 4097, 'Unterlagen bis morgen senden',
    'Unterlagen für 500 Euro senden', 'Unterlagen als PDF senden 2028', 'Unterlagen als PDF verschicken'])
def test_invalid_or_invented_titles_are_malformed(env, title):
    app, client, episode, candidate = env
    before = proposal_rows(app)
    assert amend(env, title).status_code == 422
    assert proposal_rows(app) == before


@pytest.mark.parametrize('changes', [{'unexpected': True}, {'title': 8}, {'expected_digest': 'bad'},
                                     {'expected_task_context': None}, {'expected_statement': ''}])
def test_request_rejects_extra_and_malformed_fields(env, changes):
    app, client, episode, candidate = env
    assert amend(env, **changes).status_code == 422
    assert app.state.proposals.get(candidate.id).state is ProposalState.PENDING


def test_separate_sources_with_equal_corrected_title_do_not_coalesce(env):
    app, client, episode, candidate = env
    second, other = add_bound(app, key='synthetic:another', body=QUOTE + ' Zweite Quelle.')
    first = amend(env)
    second_response = client.post(f'/api/v1/task-candidates/{other.id}/amend', json=payload(other))
    assert first.status_code == second_response.status_code == 200
    assert first.json()['id'] != second_response.json()['id']
    assert {p.evidence[0].episode_id for p in app.state.proposals.pending(ProposalKind.TASK)} == {episode.id, second.id}


def test_fault_after_successor_insert_rolls_back_both_proposals(env):
    app, client, episode, candidate = env
    before = proposal_rows(app)
    app.state.proposals._conn.execute("""CREATE TEMP TRIGGER fail_amend AFTER INSERT ON proposals
        WHEN json_extract(NEW.document,'$.task_amends') IS NOT NULL
        BEGIN SELECT RAISE(ABORT,'synthetic insert fault'); END""")
    with pytest.raises(sqlite3.IntegrityError, match='synthetic insert fault'):
        amend(env)
    assert proposal_rows(app) == before
    assert app.state.tasks.all_tasks() == []
    app.state.proposals._conn.execute('DROP TRIGGER fail_amend')
    assert amend(env).status_code == 200


def test_source_write_reservation_surrounds_successor_insert_and_proposal_commit(env, monkeypatch):
    app, client, episode, candidate = env
    other = EpisodeStore(app.state.episodes._path)
    other._conn.execute('PRAGMA busy_timeout=0')
    original = app.state.proposals._put
    observations = []
    def put(proposal, finger=None):
        if getattr(proposal, 'task_amends', None):
            assert app.state.episodes._conn.in_transaction
            with pytest.raises(sqlite3.OperationalError, match='locked'):
                other.ignore(episode.id)
            observations.append('source reserved during insert')
        return original(proposal, finger)
    monkeypatch.setattr(app.state.proposals, '_put', put)
    assert amend(env).status_code == 200
    assert observations == ['source reserved during insert']
    assert not app.state.episodes._conn.in_transaction
    other.ignore(episode.id)
    other.close()


def test_source_change_just_before_commit_rolls_back_amendment(env, monkeypatch):
    app, client, episode, candidate = env
    original = app.state.proposals._put
    before = proposal_rows(app)
    source_before = app.state.episodes.support_snapshot(episode.id).fingerprint()
    def put(proposal, finger=None):
        result = original(proposal, finger)
        if getattr(proposal, 'task_amends', None):
            app.state.episodes.add_contacts(episode.id, [{'adresse': 'race@example.org', 'rolle': 'an'}], [])
        return result
    monkeypatch.setattr(app.state.proposals, '_put', put)
    assert amend(env).status_code == 409
    assert proposal_rows(app) == before
    assert app.state.episodes.support_snapshot(episode.id).fingerprint() == source_before


def test_successor_requires_review_and_withdrawal_blocks_acceptance(env):
    app, client, episode, candidate = env
    response = amend(env)
    assert response.status_code == 200, response.text
    successor = app.state.proposals.get(response.json()['id'])
    verdict = pruefen(successor, episode, eigene=['recipient@example.org'], jetzt=now(),
                     zeitstatus='recent', aus_bestand=False, dublette=False, zurueckgenommen=False)
    assert not verdict.eindeutig and verdict.kuerzel == 'ungeprueft'
    brief = for_briefing(app.state.proposals, app.state.episodes)
    assert next(item for item in brief['items'] if item['id'] == successor.id)['review_required'] is True
    assert app.state.tasks.all_tasks() == []
    app.state.episodes.ignore(episode.id)
    assert client.post(f'/api/v1/task-candidates/{successor.id}/accept', json={'title': TITLE}).status_code == 409
    assert app.state.tasks.all_tasks() == []


def test_normal_detection_does_not_resurrect_original_or_add_a_duplicate(env):
    app, client, episode, candidate = env
    response = amend(env)
    assert response.status_code == 200, response.text
    before = proposal_rows(app)
    with app.state.proposals.transaction():
        assert app.state.proposals._record_task_candidates(episode.id, episode.digest,
            [{'title': OLD, 'quote': QUOTE}], proposed_by='synthetic/new-review' + REVIEW_MARKER,
            task_context=candidate.task_context) == 0
    assert proposal_rows(app) == before
    assert len(app.state.proposals.pending(ProposalKind.TASK)) == 1


@pytest.mark.parametrize('changed', ['missing', 'altered'])
def test_missing_or_altered_successor_is_not_recreated_or_overwritten(env, changed):
    app, client, episode, candidate = env
    response = amend(env)
    assert response.status_code == 200, response.text
    successor = app.state.proposals.get(response.json()['id'])
    if changed == 'missing':
        with app.state.proposals.transaction():
            app.state.proposals._conn.execute('DELETE FROM proposals WHERE id=?', (successor.id,))
    else:
        successor.statement = 'Synthetic tampering'
        app.state.proposals._put(successor)
    before = proposal_rows(app)
    assert amend(env).status_code == 409
    assert proposal_rows(app) == before


@pytest.mark.parametrize('invalidity', ['parent_ignored', 'parent_replaced', 'correction_invalidated'])
def test_invalid_parent_or_manual_correction_cannot_be_amended(env, invalidity):
    app, client, parent, original = env
    episodes = app.state.episodes
    if invalidity.startswith('parent_'):
        parent_key = 'mail:' + 'a' * 64
        parent, _ = add_bound(app, key=parent_key)
        key = parent_key + ':anhang:1'
        child, _ = episodes.record(EpisodeKind.DOCUMENT, 'Attachment', QUOTE + ' Attachment.',
            Provenance(source_type=SourceType.EMAIL, source_ref='synthetic:attachment'),
            tags=['anhang', 'anhang:gelesen', 'mail-parent:' + parent.id],
            source_key=key)
    else:
        parent_key = 'synthetic:amend'
        episodes.ignore(parent.id)
        fingerprint = episodes.support_snapshot(parent.id).support_fingerprint()
        key = 'source-correction:' + parent.id
        child, _ = episodes.record(EpisodeKind.MESSAGE, 'Manual correction', QUOTE + ' Correction.',
            Provenance(source_type=SourceType.MANUAL_CORRECTION, source_ref=key + ':' + fingerprint),
            tags=['source:correction'], source_key=key)
    episodes.advance_source_head(key, None, child.id)
    context = current_task_context(episodes, child.id)
    assert context is not None
    with app.state.proposals.transaction():
        app.state.proposals._record_task_candidates(child.id, child.digest,
            [{'title': OLD, 'quote': QUOTE}], proposed_by='synthetic/local' + REVIEW_MARKER,
            task_context=context)
    candidate = next(p for p in app.state.proposals.pending(ProposalKind.TASK)
                     if p.evidence[0].episode_id == child.id)
    if invalidity == 'parent_ignored':
        episodes.ignore(parent.id)
    else:
        replacement, _ = episodes.record(EpisodeKind.MESSAGE, 'New parent', 'Replacement body',
            parent.provenance, source_key=parent_key)
        episodes.advance_source_head(parent_key, parent.id, replacement.id)
    before = proposal_rows(app)
    response = client.post(f'/api/v1/task-candidates/{candidate.id}/amend', json=payload(candidate))
    assert response.status_code == 409, response.text
    assert proposal_rows(app) == before
    assert app.state.tasks.all_tasks() == []


def test_lineage_is_optional_and_only_task_documents_can_carry_it(env):
    app, client, episode, candidate = env
    assert 'task_amends' not in candidate.to_dict()
    document = candidate.to_dict()
    document['kind'] = 'confirmation'
    document['task_amends'] = candidate.id
    with pytest.raises(ProposalError, match='(?i)(task|aufgaben)'):
        ProposalStore._from_row({'document': json.dumps(document)})
