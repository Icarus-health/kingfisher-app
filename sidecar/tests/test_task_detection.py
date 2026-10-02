"""Zusagen bleiben Vorschläge: Neustart, Entzug und Ausfälle sind überprüfbar."""
import json
import sqlite3
from threading import RLock
from types import SimpleNamespace

import pytest

from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import ProposalKind, ProposalState, ProposalStore, ProposalError
from icarus_memory.providers import Reply
from icarus_memory.task_detection import TaskDetector
from icarus_memory.consolidation import Consolidator

QUOTE = 'Ich schicke dir das Angebot bis Freitag.'


class Local:
    is_local = True
    name = 'test'
    model = 'local'

    def __init__(self):
        self.calls = 0
        self.hook = lambda: None
        self.items = [{'title': 'Angebot nachhalten', 'quote': QUOTE}]

    def complete(self, messages, tools):
        assert tools == []
        assert json.loads(messages[1]['content'])['body']
        self.calls += 1
        self.hook()
        return Reply(text=json.dumps({'items': self.items}))


@pytest.fixture
def env(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    proposals = ProposalStore(tmp_path / 'proposals.sqlite3')
    provider = Local()
    detector = TaskDetector(episodes, proposals, provider, RLock())
    yield SimpleNamespace(episodes=episodes, proposals=proposals, provider=provider, detector=detector, path=tmp_path)
    episodes.close()
    proposals.close()


def source(env, text=QUOTE, kind=EpisodeKind.MESSAGE, key='mail:one'):
    return env.episodes.record(kind, 'Angebot', text, Provenance(source_type=SourceType.USER_STATED), source_key=key)[0]


def test_restart_and_rejection_do_not_repeat_analysis(env):
    episode = source(env)
    report = env.detector.run(with_model=True)
    assert (report.analyzed, report.proposed) == (1, 1)
    proposal = env.proposals.pending(ProposalKind.TASK)[0]
    assert proposal.evidence[0].episode_id == episode.id
    assert proposal.evidence[0].quote == QUOTE
    assert proposal.evidence[0].digest == episode.digest
    env.proposals.reject(proposal.id)
    other = ProposalStore(env.path / 'proposals.sqlite3')
    try:
        assert TaskDetector(env.episodes, other, env.provider, RLock()).run(with_model=True).analyzed == 0
        assert other.get(proposal.id).state is ProposalState.REJECTED
        assert env.provider.calls == 1
    finally:
        other.close()


def test_empty_result_is_checkpointed_and_two_identical_sources_stay_independent(env):
    first = source(env)
    second = source(env, key='mail:two')
    env.provider.items = []
    assert env.detector.run(with_model=True).analyzed == 2
    assert env.proposals.task_analysis_done(first.id, first.digest)
    assert env.proposals.task_analysis_done(second.id, second.digest)
    assert env.detector.run(with_model=True).analyzed == 0


def test_cloud_and_disabled_model_never_receive_source(env):
    source(env)
    assert not env.detector.run(with_model=False).available
    env.provider.is_local = False
    assert not env.detector.run(with_model=True).available
    assert env.provider.calls == 0


def test_revocation_during_model_call_discards_result(env):
    episode = source(env)
    env.provider.hook = lambda: env.episodes.ignore(episode.id)
    assert env.detector.run(with_model=True).proposed == 0
    assert not env.proposals.task_analysis_done(episode.id, episode.digest)
    assert env.proposals.pending() == []


def test_permission_withdrawal_during_model_call_discards_result(env):
    source(env)
    allowed = [True]
    env.provider.hook = lambda: allowed.__setitem__(0, False)
    report = env.detector.run(with_model=True, permitted=lambda: allowed[0])
    assert report.cancelled
    assert env.proposals.pending() == []


def test_failure_is_retryable_and_does_not_stop_other_sources(env):
    source(env)
    source(env, key='mail:two')
    def fail_once():
        if env.provider.calls == 1:
            raise RuntimeError('PRIVATE SOURCE must not appear in report')
    env.provider.hook = fail_once
    report = env.detector.run(with_model=True)
    assert (report.failed, report.analyzed, report.proposed) == (1, 1, 1)
    assert 'PRIVATE' not in repr(report)
    assert env.detector.run(with_model=True).proposed == 1


def test_excluded_source_expires_pending_candidate_even_without_model(env):
    episode = source(env)
    env.detector.run(with_model=True)
    proposal = env.proposals.pending(ProposalKind.TASK)[0]
    env.episodes.ignore(episode.id)
    assert env.detector.run(with_model=False).superseded == 1
    assert env.proposals.get(proposal.id).state is ProposalState.SUPERSEDED


def test_task_cannot_be_accepted_as_personal_fact(env):
    source(env)
    env.detector.run(with_model=True)
    proposal = env.proposals.pending(ProposalKind.TASK)[0]
    with pytest.raises(ProposalError, match='Aufgabenpfad'):
        Consolidator(None, env.episodes, env.proposals).accept(proposal.id)
    assert env.proposals.get(proposal.id).state is ProposalState.PENDING


def test_summary_is_not_a_source_and_limit_preserves_backlog(env):
    source(env)
    source(env, key='mail:two')
    source(env, kind=EpisodeKind.SUMMARY, key='summary')
    assert env.detector.run(with_model=True, limit=1).analyzed == 1
    assert env.detector.run(with_model=True, limit=1).analyzed == 1
    assert env.detector.run(with_model=True, limit=1).analyzed == 0


def test_analysis_transaction_rolls_back_candidates_when_checkpoint_fails(env):
    episode = source(env)
    env.proposals._conn.execute("CREATE TRIGGER fail_checkpoint BEFORE INSERT ON task_analysis BEGIN SELECT RAISE(ABORT, 'test'); END")
    with pytest.raises(sqlite3.IntegrityError):
        env.detector.run(with_model=True)
    assert env.proposals.pending() == []
    assert not env.proposals.task_analysis_done(episode.id, episode.digest)
    env.proposals._conn.execute('DROP TRIGGER fail_checkpoint')
    assert env.detector.run(with_model=True).proposed == 1


def test_independent_connections_commit_one_analysis_without_reviving_rejection(env):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    episode = source(env)
    other = ProposalStore(env.path / 'proposals.sqlite3')
    barrier = Barrier(2)
    def commit(store):
        barrier.wait()
        return store.record_task_analysis(episode.id, episode.digest, env.provider.items, proposed_by='test')
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(commit, env.proposals)
            second = pool.submit(commit, other)
            assert sorted([first.result(), second.result()]) == [0, 1]
        candidate = other.pending(ProposalKind.TASK)[0]
        other.reject(candidate.id)
        assert env.proposals.record_task_analysis(episode.id, episode.digest, env.provider.items, proposed_by='test') == 0
        assert env.proposals.get(candidate.id).state is ProposalState.REJECTED
    finally:
        other.close()


def test_v1_migration_preserves_existing_proposal(env):
    old, _ = env.proposals.propose(ProposalKind.CONFLICT, 'Prüfen', 'Widerspruch', about=['existing-assertion'])
    path = env.path / 'old-proposals.sqlite3'
    with sqlite3.connect(path) as connection:
        env.proposals._conn.backup(connection)
        from icarus_memory.support_schema import PROPOSAL_TRIGGERS
        for trigger in PROPOSAL_TRIGGERS:
            connection.execute('DROP TRIGGER ' + trigger)
        connection.execute('DROP INDEX idx_proposals_produced')
        connection.execute('ALTER TABLE proposals DROP COLUMN produced_assertion_id')
        connection.execute('ALTER TABLE proposals DROP COLUMN support_authorization')
        connection.execute('DROP TABLE task_analysis')
        connection.execute('DROP TABLE task_scan_cursor')
        connection.execute('DROP TABLE memory_analysis_jobs')
        connection.execute('PRAGMA user_version = 1')
    migrated = ProposalStore(path)
    try:
        assert migrated.get(old.id).to_dict() == old.to_dict()
        assert not migrated.task_analysis_done('missing', 'sha256:x')
        assert migrated._conn.execute('PRAGMA user_version').fetchone()[0] == 5
    finally:
        migrated.close()


def test_failed_source_does_not_starve_backlog_after_restart(env):
    source(env)
    source(env, key='mail:two')
    ordered = env.episodes.analysis_batch()
    bad_id, good_id = ordered[0].id, ordered[1].id
    def fail():
        raise RuntimeError('Fehler')
    env.provider.hook = fail
    assert env.detector.run(with_model=True, limit=1).failed == 1
    assert env.proposals.task_scan_cursor() == bad_id
    reopened = ProposalStore(env.path / 'proposals.sqlite3')
    try:
        env.provider.hook = lambda: None
        detector = TaskDetector(env.episodes, reopened, env.provider, RLock())
        assert detector.run(with_model=True, limit=1).proposed == 1
        assert reopened.pending(ProposalKind.TASK)[0].evidence[0].episode_id == good_id
        # Am Ende beginnt der nächste Durchgang wieder vorn; Fehler bleiben prüfbar.
        assert detector.run(with_model=True, limit=1).analyzed == 0
        assert detector.run(with_model=True, limit=1).proposed == 1
    finally:
        reopened.close()


def test_scheduler_runs_detection_after_ingest_and_isolates_failure():
    from icarus_memory.scheduler import Scheduler, JobResult
    order = []
    def detect(with_model):
        assert with_model
        order.append('detect')
        raise RuntimeError('PRIVATE')
    scheduler = Scheduler(
        run_ingest=lambda: order.append('ingest') or [],
        run_task_detection=detect,
        run_backup=lambda: order.append('backup') or JobResult('backup', True, 'ok'),
    )
    report = scheduler.run_once(with_model=True)
    assert order == ['ingest', 'detect', 'backup']
    assert report.jobs[0].name == 'zusagen'
    assert not report.jobs[0].ok
    assert 'PRIVATE' not in report.summary()
    assert report.jobs[1].ok
