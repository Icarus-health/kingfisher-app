"""Eine korrigierte Beteiligung darf alte Aufgabenprüfung nicht frisch erscheinen lassen."""
import json
from datetime import datetime, timezone
import sqlite3

from fastapi.testclient import TestClient
import pytest

from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import ProposalKind
from icarus_memory.providers import Reply
from icarus_memory.server import create_app
from icarus_memory.task_detection import TaskDetector, for_briefing

TEXT = 'Ich sende dir den Bericht.'
CONTACT = {'rolle': 'von', 'ich': True, 'adresse': 'own@example.test'}


class LocalReview:
    is_local = True
    name = 'synthetic'
    model = 'identity-review'

    def __init__(self):
        self.inputs = []
        self.forced_kind = None
        self.supported = True

    def complete(self, messages, tools):
        assert tools == []
        payload = json.loads(messages[1]['content'])
        self.inputs.append(payload)
        if 'candidates' in payload:
            kind = self.forced_kind or ('own_commitment' if payload['own_source'] else 'other_person')
            return Reply(text=json.dumps({'reviews': [
                {'id': row['id'], 'kind': kind, 'title_supported': self.supported}
                for row in payload['candidates']]}))
        return Reply(text=json.dumps({'items': [{'title': 'Bericht senden', 'quote': TEXT}]}))


@pytest.fixture
def context(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path / 'synthetic'))
    app = create_app()
    provider = LocalReview()
    detector = TaskDetector(app.state.episodes, app.state.proposals, provider,
                            app.state.conversation_lock, tasks=app.state.tasks)
    with TestClient(app) as client:
        yield app, provider, detector, client


def source(context, *, own=True):
    app, _, _, _ = context
    return app.state.episodes.record(EpisodeKind.MESSAGE, 'Bericht', TEXT,
        Provenance(source_type=SourceType.EMAIL), source_key='synthetic:one',
        occurred_at=datetime.now(timezone.utc), contacts=[CONTACT] if own else [])[0]


def test_removed_own_identity_hides_stale_suggestion_and_rejects_acceptance(context):
    app, provider, detector, client = context
    episode = source(context)
    assert detector.run(with_model=True).proposed == 1
    [candidate] = app.state.proposals.pending(ProposalKind.TASK)
    app.state.episodes.remove_contacts(episode.id, [CONTACT], [])
    assert for_briefing(app.state.proposals, app.state.episodes)['items'] == []
    assert client.get('/api/v1/task-candidates/page').json()['items'] == []
    result = client.post(f'/api/v1/task-candidates/{candidate.id}/accept', json={'title': candidate.statement})
    assert result.status_code == 409
    assert app.state.tasks.all_tasks() == []
    assert app.state.episodes.get(episode.id).body == TEXT


def test_identity_change_after_empty_result_is_reanalyzed_after_restart(context):
    app, provider, detector, client = context
    episode = source(context, own=False)
    assert detector.run(with_model=True).proposed == 0
    app.state.episodes.add_contacts(episode.id, [CONTACT], [])
    restarted = create_app()
    try:
        fresh_detector = TaskDetector(restarted.state.episodes, restarted.state.proposals,
                                      provider, restarted.state.conversation_lock, tasks=restarted.state.tasks)
        assert fresh_detector.run(with_model=True).proposed == 1
        assert provider.inputs[-1]['own_source'] is True
        assert fresh_detector.run(with_model=True).analyzed == 0
    finally:
        restarted.state.scheduler.stop()


def test_same_contact_restored_requires_fresh_review_not_old_candidate(context):
    app, provider, detector, client = context
    episode = source(context)
    detector.run(with_model=True)
    [old] = app.state.proposals.pending(ProposalKind.TASK)
    app.state.episodes.remove_contacts(episode.id, [CONTACT], [])
    app.state.episodes.add_contacts(episode.id, [CONTACT], [])
    assert for_briefing(app.state.proposals, app.state.episodes)['items'] == []
    report = detector.run(with_model=True)
    assert report.analyzed == 1 and report.proposed == 1
    [fresh] = app.state.proposals.pending(ProposalKind.TASK)
    assert fresh.id != old.id
    assert client.post(f'/api/v1/task-candidates/{old.id}/accept', json={'title': old.statement}).status_code == 409


def test_changed_metadata_is_not_counted_as_current_processing(context):
    app, provider, detector, client = context
    episode = source(context)
    detector.run(with_model=True)
    assert client.get('/api/v1/memory/coverage').json()['counts']['completed'] == 1
    app.state.episodes.remove_contacts(episode.id, [CONTACT], [])
    counts = client.get('/api/v1/memory/coverage').json()['counts']
    assert counts['completed'] == 0 and counts['pending'] == 1
    assert detector.run(with_model=True).analyzed == 1
    assert client.get('/api/v1/memory/coverage').json()['counts']['completed'] == 1


def test_confirmed_task_survives_later_identity_correction(context):
    app, provider, detector, client = context
    episode = source(context)
    detector.run(with_model=True)
    [candidate] = app.state.proposals.pending(ProposalKind.TASK)
    task = client.post(f'/api/v1/task-candidates/{candidate.id}/accept', json={'title': 'Explizit eigene Aufgabe'}).json()
    app.state.episodes.remove_contacts(episode.id, [CONTACT], [])
    detector.run(with_model=False)
    assert app.state.tasks.get(task['id']).title == 'Explizit eigene Aufgabe'
    assert len(app.state.tasks.all_tasks()) == 1


@pytest.mark.parametrize('kind,supported,extra', [
    ('information', True, 'Update: Der Auftrag ist abgesagt.'),
    ('unclear', True, 'Das gilt nur, falls die Freigabe kommt.'),
    ('other_person', True, 'Das war die Zusage eines anderen Absenders.'),
    ('own_commitment', False, 'Der vorgeschlagene Titel ist nicht vom Zitat gedeckt.'),
])
def test_controlled_negative_review_never_becomes_own_task(context, kind, supported, extra):
    # Prüft das echte Persistieren des Urteils, nicht die Qualität eines echten Modells.
    app, provider, detector, client = context
    app.state.episodes.record(EpisodeKind.MESSAGE, 'Bericht', TEXT + '\n' + extra,
        Provenance(source_type=SourceType.EMAIL), contacts=[CONTACT],
        source_key='synthetic:negative', occurred_at=datetime.now(timezone.utc))
    provider.forced_kind = kind
    provider.supported = supported
    report = detector.run(with_model=True)
    assert (report.analyzed, report.proposed, report.failed) == (1, 0, 0)
    assert extra in provider.inputs[-1]['body']
    assert client.get('/api/v1/task-candidates').json() == []
    assert app.state.tasks.all_tasks() == []


def test_generation_changed_and_restored_during_review_cannot_commit(context):
    app, provider, detector, client = context
    episode = source(context)
    complete = provider.complete
    def changed(messages, tools):
        result = complete(messages, tools)
        if 'candidates' in provider.inputs[-1]:
            app.state.episodes.remove_contacts(episode.id, [CONTACT], [])
            app.state.episodes.add_contacts(episode.id, [CONTACT], [])
        return result
    provider.complete = changed
    report = detector.run(with_model=True)
    assert report.analyzed == report.proposed == 0
    assert app.state.proposals.pending(ProposalKind.TASK) == []
    assert client.get('/api/v1/memory/coverage').json()['counts']['completed'] == 0


def test_rejected_legacy_candidate_is_not_revived(context):
    app, provider, detector, client = context
    episode = source(context)
    app.state.proposals.record_task_analysis(episode.id, episode.digest,
        [{'title': 'Bericht senden', 'quote': TEXT}], proposed_by='legacy/task-review-v1')
    [old] = app.state.proposals.pending(ProposalKind.TASK)
    app.state.proposals.reject(old.id)
    assert detector.run(with_model=True).proposed == 0
    assert app.state.proposals.get(old.id).state.value == 'rejected'
    assert app.state.proposals.pending(ProposalKind.TASK) == []


def test_legacy_pending_is_manual_until_fresh_review_then_one_bound_candidate(context):
    app, provider, detector, client = context
    episode = source(context)
    app.state.proposals.record_task_analysis(episode.id, episode.digest,
        [{'title': 'Bericht senden', 'quote': TEXT}], proposed_by='legacy/task-review-v1')
    [old] = app.state.proposals.pending(ProposalKind.TASK)
    assert for_briefing(app.state.proposals, app.state.episodes)['items'][0]['review_required'] is True
    assert detector.run(with_model=True).proposed == 1
    [fresh] = app.state.proposals.pending(ProposalKind.TASK)
    assert fresh.id != old.id and fresh.task_context is not None
    assert app.state.proposals.get(old.id).state.value == 'superseded'
    assert for_briefing(app.state.proposals, app.state.episodes)['items'][0]['review_required'] is False


def test_source_behind_cursor_stays_blocked_and_is_reviewed_next_scan(context):
    app, provider, detector, client = context
    source(context)
    app.state.episodes.record(EpisodeKind.MESSAGE, 'Zweite Quelle', TEXT,
        Provenance(source_type=SourceType.EMAIL), source_key='synthetic:two', contacts=[CONTACT])
    first, second = app.state.episodes.analysis_batch()
    assert detector.run(with_model=True, limit=1).analyzed == 1
    app.state.episodes.remove_contacts(first.id, [CONTACT], [])
    assert all(item['episode_id'] != first.id for item in for_briefing(app.state.proposals, app.state.episodes)['items'])
    assert detector.run(with_model=True, limit=1).analyzed == 1
    # Ein vorhandener Backlog wird weiter abgearbeitet; die Cursor-Runde wird anschließend geschlossen.
    assert detector.run(with_model=True, limit=1).analyzed == 0
    assert detector.run(with_model=True, limit=1).analyzed == 1
    assert provider.inputs[-1]['own_source'] is False



def test_accepted_bound_task_is_not_offered_again_after_contact_restore(context):
    app, provider, detector, client = context
    episode = source(context)
    detector.run(with_model=True)
    [candidate] = app.state.proposals.pending(ProposalKind.TASK)
    task = client.post(f'/api/v1/task-candidates/{candidate.id}/accept', json={'title': candidate.statement}).json()
    app.state.episodes.remove_contacts(episode.id, [CONTACT], [])
    app.state.episodes.add_contacts(episode.id, [CONTACT], [])
    assert detector.run(with_model=True).proposed == 0
    assert app.state.proposals.pending(ProposalKind.TASK) == []
    assert app.state.tasks.get(task['id']).title == candidate.statement


@pytest.mark.parametrize('relationship', ['head', 'parent', 'correction'])
def test_unbound_legacy_still_requires_valid_source_relationship(context, relationship):
    app, provider, detector, client = context
    episodes = app.state.episodes
    if relationship == 'head':
        episode = source(context)
        episodes.advance_source_head('synthetic:one', None, episode.id)
        other = episodes.record(EpisodeKind.MESSAGE, 'Andere Fassung', 'Neuer Inhalt.',
            Provenance(source_type=SourceType.EMAIL), source_key='synthetic:one')[0]
        episodes.advance_source_head('synthetic:one', episode.id, other.id)
    elif relationship == 'parent':
        key = 'mail:' + 'a' * 64
        parent = episodes.record(EpisodeKind.MESSAGE, 'Parent', 'Anbei.',
            Provenance(source_type=SourceType.EMAIL), source_key=key)[0]
        episodes.advance_source_head(key, None, parent.id)
        episode = episodes.record(EpisodeKind.DOCUMENT, 'Anhang', TEXT,
            Provenance(source_type=SourceType.EMAIL), source_key=key + ':anhang:1',
            tags=['anhang', 'mail-parent:' + parent.id])[0]
        # Der Anhang bleibt unverändert, aber die veröffentlichte Elternfassung wechselt.
        other = episodes.record(EpisodeKind.MESSAGE, 'Neuer Parent', 'Neue Mail.',
            Provenance(source_type=SourceType.EMAIL), source_key=key)[0]
        episodes.advance_source_head(key, parent.id, other.id)
    else:
        from icarus_memory.source_corrections import correct, preview
        original = source(context)
        episodes.advance_source_head('synthetic:one', None, original.id)
        state = preview(episodes, app.state.claims, original.id)
        corrected_id = correct(episodes, app.state.claims, original.id, state['fingerprint'], TEXT + ' Neue Angaben.')
        episode = episodes.get(corrected_id)
        assert episodes.support_snapshot(episode.id).correction_valid is True
        episodes.remove_contacts(original.id, [CONTACT], [])
        assert episodes.support_snapshot(episode.id).correction_valid is False
    app.state.proposals.record_task_analysis(episode.id, episode.digest,
        [{'title': 'Bericht senden', 'quote': episode.body}], proposed_by='legacy/task-review-v1')
    [candidate] = app.state.proposals.pending(ProposalKind.TASK)
    assert client.get('/api/v1/task-candidates/page').json()['items'] == []
    assert client.post(f'/api/v1/task-candidates/{candidate.id}/accept', json={'title': candidate.statement}).status_code == 409
    assert episodes.get(episode.id).body == episode.body
    assert app.state.tasks.all_tasks() == []



def test_failed_checkpoint_preserves_legacy_pending_and_no_duplicate(context):
    app, provider, detector, client = context
    episode = source(context)
    app.state.proposals.record_task_analysis(episode.id, episode.digest,
        [{'title': 'Bericht senden', 'quote': TEXT}], proposed_by='legacy/task-review-v1')
    [old] = app.state.proposals.pending(ProposalKind.TASK)
    app.state.proposals._conn.execute("CREATE TRIGGER fail_checkpoint BEFORE INSERT ON task_analysis BEGIN SELECT RAISE(ABORT, 'synthetic'); END")
    with pytest.raises(sqlite3.IntegrityError):
        detector.run(with_model=True)
    [remaining] = app.state.proposals.pending(ProposalKind.TASK)
    assert remaining.id == old.id and remaining.task_context is None
    app.state.proposals._conn.execute('DROP TRIGGER fail_checkpoint')
    assert detector.run(with_model=True).proposed == 1
