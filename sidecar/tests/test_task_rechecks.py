"""Korrekturen dürfen hinter einem großen Erstimport nicht tagelang warten."""
import sqlite3

from tests.test_task_source_generation import context, source, CONTACT, TEXT
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.task_review import current_task_context
from icarus_memory.memory_analysis import analysis_version


def backlog(context, count=30):
    app, _, detector, _ = context
    for i in range(count):
        app.state.episodes.record(EpisodeKind.MESSAGE, f'Quelle {i}', TEXT,
            Provenance(source_type=SourceType.EMAIL), source_key=f'queue:{i}', contacts=[CONTACT])
    first = app.state.episodes.analysis_batch()[0]
    assert detector.run(with_model=True, limit=1).analyzed == 1
    return first


def test_correction_behind_large_backlog_is_reviewed_next_run(context):
    app, _, detector, _ = context
    first = backlog(context)
    app.state.episodes.remove_contacts(first.id, [CONTACT], [])
    assert detector.run(with_model=True, limit=2).analyzed == 2
    job = app.state.proposals.memory_analysis.snapshot(first.id)
    assert job['version'] == analysis_version(current_task_context(app.state.episodes, first.id))
    assert job['state'] == 'completed'


def test_correction_priority_survives_restart(context):
    app, _, detector, _ = context
    first = backlog(context)
    app.state.episodes.remove_contacts(first.id, [CONTACT], [])
    fresh = EpisodeStore(app.state.episodes._path)
    try:
        detector.episodes = fresh
        assert detector.run(with_model=True, limit=2).analyzed == 2
        assert app.state.proposals.memory_analysis.snapshot(first.id)['version'] == analysis_version(current_task_context(fresh, first.id))
    finally:
        fresh.close()


def test_disabled_model_does_not_consume_rechecks(context):
    app, _, detector, _ = context
    first = backlog(context)
    app.state.episodes.remove_contacts(first.id, [CONTACT], [])
    detector.run(with_model=False)
    assert detector.run(with_model=True, limit=2).analyzed == 2
    assert app.state.proposals.memory_analysis.snapshot(first.id)['version'] == analysis_version(current_task_context(app.state.episodes, first.id))


def test_rechecks_coalesce_preserve_position_and_reject_old_ack(context):
    app, _, _, _ = context
    first = source(context)
    app.state.episodes.remove_contacts(first.id, [CONTACT], [])
    [old] = app.state.episodes.task_rechecks()
    app.state.episodes.add_contacts(first.id, [CONTACT], [])
    [new] = app.state.episodes.task_rechecks()
    assert new['generation'] > old['generation']
    assert new['position'] == old['position']
    app.state.episodes.finish_task_recheck(old, completed=True)
    assert app.state.episodes.task_rechecks() == [new]
    app.state.episodes.finish_task_recheck(new, completed=True)
    assert app.state.episodes.task_rechecks() == []


def test_queue_change_rolls_back_with_source_transaction(context):
    app, _, _, _ = context
    episode = source(context)
    try:
        with app.state.episodes.transaction():
            app.state.episodes.remove_contacts(episode.id, [CONTACT], [])
            raise RuntimeError('Synthetic rollback')
    except RuntimeError:
        pass
    assert app.state.episodes.get(episode.id).contacts == [CONTACT]
    assert app.state.episodes.task_rechecks() == []


def test_v20_upgrade_preserves_sources_and_seeds_changed_generations(tmp_path):
    from icarus_memory.episodes import _MIGRATIONS
    from icarus_memory.migrations import run_migrations
    path = tmp_path / 'v20.sqlite3'
    conn = sqlite3.connect(path)
    run_migrations(conn, store='episodes', path=path, migrations=_MIGRATIONS[:20])
    conn.close()
    # A v20 source document taken from a separate real store; no production data.
    store = EpisodeStore(tmp_path / 'fixture.sqlite3')
    episode = store.record(EpisodeKind.MESSAGE, 'Vorhanden', TEXT,
        Provenance(source_type=SourceType.EMAIL), source_key='old:one')[0]
    row = dict(store._conn.execute('SELECT * FROM episodes WHERE id=?', (episode.id,)).fetchone())
    store.close()
    conn = sqlite3.connect(path)
    fields = list(row); row['support_generation'] = 3
    conn.execute(f"INSERT INTO episodes ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})", tuple(row[f] for f in fields))
    conn.commit(); before = conn.execute('SELECT * FROM episodes').fetchall(); conn.close()
    upgraded = EpisodeStore(path)
    try:
        assert upgraded._conn.execute('PRAGMA user_version').fetchone()[0] == 21
        assert [tuple(r) for r in upgraded._conn.execute('SELECT * FROM episodes')] == before
        [pending] = upgraded.task_rechecks()
        assert pending['id'] == episode.id and pending['generation'] == 3
    finally:
        upgraded.close()


def test_limit_one_alternates_across_restart_and_failures(context):
    app, provider, detector, _ = context
    first = backlog(context)
    second = app.state.episodes.analysis_batch(first.id)[0]
    app.state.episodes.remove_contacts(first.id, [CONTACT], [])
    complete = provider.complete
    def failing(messages, tools):
        import json
        if json.loads(messages[1]['content']).get('subject') == first.title:
            raise RuntimeError('Synthetic failed correction')
        return complete(messages, tools)
    provider.complete = failing
    assert detector.run(with_model=True, limit=1).failed == 1
    fresh = EpisodeStore(app.state.episodes._path)
    try:
        detector.episodes = fresh
        assert detector.run(with_model=True, limit=1).analyzed == 1
        assert app.state.proposals.memory_analysis.snapshot(second.id)['state'] == 'completed'
        assert fresh.task_rechecks()[0]['id'] == first.id
    finally:
        fresh.close()


def test_live_other_job_does_not_ack_pending_correction(context):
    app, provider, detector, _ = context
    first = backlog(context)
    second = app.state.episodes.analysis_batch(first.id)[0]
    app.state.episodes.remove_contacts(first.id, [CONTACT], [])
    lease = app.state.proposals.memory_analysis.acquire(second, provider, context=current_task_context(app.state.episodes, second.id))
    assert lease is not None
    assert detector.run(with_model=True, limit=2).analyzed == 0
    assert app.state.episodes.task_rechecks()[0]['id'] == first.id
    app.state.proposals.memory_analysis.abandon(lease)
    assert detector.run(with_model=True, limit=2).analyzed == 2
    assert app.state.episodes.task_rechecks() == []


def test_crash_after_job_commit_before_ack_is_idempotent(context, monkeypatch):
    import pytest
    app, provider, detector, _ = context
    episode = source(context)
    detector.run(with_model=True)
    app.state.episodes.remove_contacts(episode.id, [CONTACT], [])
    ack = app.state.episodes.finish_task_recheck
    def crash(row, *, completed):
        assert completed
        raise RuntimeError('Synthetic crash before ack')
    monkeypatch.setattr(app.state.episodes, 'finish_task_recheck', crash)
    with pytest.raises(RuntimeError, match='Synthetic crash before ack'):
        detector.run(with_model=True, limit=2)
    assert app.state.proposals.memory_analysis.snapshot(episode.id)['state'] == 'completed'
    assert len(app.state.episodes.task_rechecks()) == 1
    inputs = len(provider.inputs)
    monkeypatch.setattr(app.state.episodes, 'finish_task_recheck', ack)
    assert detector.run(with_model=True, limit=2).analyzed == 0
    assert app.state.episodes.task_rechecks() == []
    assert len(provider.inputs) == inputs


def test_failed_corrections_rotate_and_do_not_starve_other_corrections(context):
    app, provider, detector, _ = context
    first = backlog(context)
    assert detector.run(with_model=True, limit=1).analyzed == 1
    second = app.state.episodes.analysis_batch(first.id)[0]
    for e in (first, second):
        app.state.episodes.remove_contacts(e.id, [CONTACT], [])
    complete = provider.complete
    def failing(messages, tools):
        import json
        if json.loads(messages[1]['content']).get('subject') == first.title:
            raise RuntimeError('Synthetic failure')
        return complete(messages, tools)
    provider.complete = failing
    assert detector.run(with_model=True, limit=2).failed == 1
    assert app.state.episodes.task_rechecks()[0]['id'] == second.id
    detector.run(with_model=True, limit=2)
    assert app.state.proposals.memory_analysis.snapshot(second.id)['version'] == analysis_version(current_task_context(app.state.episodes, second.id))
    assert all(r['id'] != second.id for r in app.state.episodes.task_rechecks())


def test_partial_correction_keeps_queue_and_rotates(context):
    app, provider, detector, _ = context
    # Exakt belegte Zusage in jedem Segment; vollständige Quelle ist größer als eine Seite.
    long_text = (TEXT + '\n') * 700
    app.state.episodes.record(EpisodeKind.MESSAGE, 'Lange Quelle', long_text,
        Provenance(source_type=SourceType.EMAIL), source_key='long:one', contacts=[CONTACT])
    first = app.state.episodes.analysis_batch()[0]
    detector.run(with_model=True, limit=1)
    app.state.episodes.remove_contacts(first.id, [CONTACT], [])
    report = detector.run(with_model=True, limit=1)
    assert report.analyzed == 0
    [queued] = app.state.episodes.task_rechecks()
    job = app.state.proposals.memory_analysis.snapshot(first.id)
    assert job['state'] == 'pending' and 0 < job['offset'] < job['total']
    assert queued['id'] == first.id


def test_during_review_correction_cannot_be_acknowledged(context):
    app, provider, detector, _ = context
    first = backlog(context)
    app.state.episodes.remove_contacts(first.id, [CONTACT], [])
    [old] = app.state.episodes.task_rechecks()
    complete = provider.complete
    def correct(messages, tools):
        import json
        if 'candidates' in json.loads(messages[1]['content']):
            app.state.episodes.add_contacts(first.id, [CONTACT], [])
        return complete(messages, tools)
    provider.complete = correct
    detector.run(with_model=True, limit=1)
    [pending] = app.state.episodes.task_rechecks()
    assert pending['generation'] > old['generation']
    assert app.state.proposals.memory_analysis.snapshot(first.id)['state'] == 'cancelled'


def test_queue_is_bounded_and_excluded_source_uses_no_model(context):
    app, provider, detector, _ = context
    first = source(context)
    app.state.episodes.ignore(first.id)
    calls = len(provider.inputs)
    detector.run(with_model=True, limit=2)
    assert app.state.episodes.task_rechecks() == []
    assert len(provider.inputs) == calls
    for i in range(25):
        episode = app.state.episodes.record(EpisodeKind.MESSAGE, str(i), TEXT,
            Provenance(source_type=SourceType.EMAIL), source_key=f'bounded:{i}', contacts=[CONTACT])[0]
        app.state.episodes.remove_contacts(episode.id, [CONTACT], [])
    assert len(app.state.episodes.task_rechecks(limit=100000)) == 20


def test_migration_failure_rolls_back_queue_and_version(tmp_path):
    import pytest
    from dataclasses import replace
    from icarus_memory.episodes import _MIGRATIONS
    from icarus_memory.migrations import run_migrations, MigrationError
    path = tmp_path / 'rollback.sqlite3'; conn = sqlite3.connect(path)
    run_migrations(conn, store='episodes', path=path, migrations=_MIGRATIONS[:20])
    def fail(connection):
        raise sqlite3.DatabaseError('Synthetic verification failure')
    migrations = (*_MIGRATIONS[:20], replace(_MIGRATIONS[20], verify=fail))
    with pytest.raises(MigrationError):
        run_migrations(conn, store='episodes', path=path, migrations=migrations)
    assert conn.execute('PRAGMA user_version').fetchone()[0] == 20
    assert conn.execute("SELECT name FROM sqlite_schema WHERE name LIKE 'task_recheck%' OR name LIKE 'trg_task_recheck%'").fetchall() == []
    conn.close()


def test_reopen_after_excluded_ack_is_prioritized_behind_backlog(context):
    app, _, detector, _ = context
    first = backlog(context)
    app.state.episodes.ignore(first.id)
    detector.run(with_model=True, limit=2)
    assert app.state.episodes.task_rechecks() == []
    app.state.episodes.reopen(first.id)
    assert detector.run(with_model=True, limit=2).analyzed == 2
    assert app.state.proposals.memory_analysis.snapshot(first.id)['version'] == analysis_version(current_task_context(app.state.episodes, first.id))
