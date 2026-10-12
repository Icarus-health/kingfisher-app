"""Lifecycle acceptance checks must detect state loss, not just print counts."""
from pathlib import Path
import socket
import subprocess
import sys

import pytest

import probe_memory_core_lifecycle as probe


def test_small_real_intake_worker_and_vector_lifecycle_without_network(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Lifecycle storage probe must not connect to models or mail servers')
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    events = []
    report = probe.run_lifecycle(tmp_path, size=120, progress=events.append)
    assert report['synthetic_only'] and not report['network_used'] and not report['llm_called']
    assert not report['embedding_quality_tested']
    assert len(report['assertions']) == 6
    assert all(check['passed'] for check in report['assertions'].values())
    assert report['assertions']['cross_label_duplicates']['duplicates'] == 12
    assert report['assertions']['durable_vector_restart']['total'] == 120
    assert report['source_count'] == 131  # 120 + 10 new + replacement; revoked original remains.
    assert report['original_preservation']['all_initial_payloads_checked'] == 120
    assert report['original_preservation']['all_originals_preserved']
    assert report['original_preservation']['new_mail_payloads_checked'] == 10
    assert len(set(report['original_preservation']['initial_inventory_by_stage'].values())) == 1
    assert report['final_progress'] == dict(total=129, done=129, skipped=0, retry=0, remaining=0)
    assert any(event['step'] == 'restart' for event in events)


def test_arbitrary_middle_original_mutation_is_detected_even_with_consistent_digest(tmp_path):
    import hashlib
    import json
    import sqlite3

    def sabotage(event):
        if event['step'] != 'before_final_preservation_check':
            return
        with sqlite3.connect(tmp_path / 'episodes.sqlite3') as connection:
            row = connection.execute("SELECT id,document FROM episodes WHERE title='Archiv 60'").fetchone()
            assert row is not None
            document = json.loads(row[1])
            document['body'] = 'Coherently tampered middle original; row count and identity unchanged.'
            document['digest'] = 'sha256:' + hashlib.sha256(document['body'].encode()).hexdigest()
            connection.execute('UPDATE episodes SET body=?,digest=?,document=? WHERE id=?',
                (document['body'], document['digest'], json.dumps(document), row[0]))

    with pytest.raises(AssertionError, match='original_content_changed_or_missing'):
        probe.run_lifecycle(tmp_path, size=120, progress=sabotage)


def test_dropped_classification_is_detected_instead_of_reporting_success(tmp_path, monkeypatch):
    from icarus_memory.scheduler import JobResult
    monkeypatch.setattr(probe, 'run', lambda *args, **kwargs: JobResult('gedaechtnis', True, 'sabotage'))
    with pytest.raises(AssertionError):
        probe.run_lifecycle(tmp_path, size=64)


def test_failed_classification_remains_visible_after_restart_and_retries_explicitly(tmp_path):
    path = tmp_path / 'episodes.sqlite3'
    episodes = probe.EpisodeStore(path)
    intake, reader = probe.Intake(episodes), probe.Reader(64)
    reader.fail = set()
    intake.start('synthetic-account', ['INBOX'])
    sources = intake.step('synthetic-account', reader, batch=1)
    assert len(sources) == 1

    class Failing(probe.Classifier):
        def complete_json(self, *args, **kwargs):
            self.calls += 1
            raise RuntimeError('synthetic private failure must not enter operational status')

    failed = Failing()
    result = probe.run(episodes, failed, probe.RLock(), source_ids=sources, stand=probe.Zwischenstand())
    assert not result.ok and 'private failure' not in result.detail
    assert probe.WorkingMemoryStore(episodes).progress()['retry'] == 1
    assert probe.WorkingMemoryStore(episodes).search('quasararchiv00064')['refs'] == []
    episodes.close()
    episodes = probe.EpisodeStore(path)
    try:
        memory = probe.WorkingMemoryStore(episodes)
        assert memory.progress()['remaining'] == memory.progress()['retry'] == 1
        assert memory.pending(episode_ids=sources) == []  # Persisted cooldown, no busy retry.
        provider = probe.Classifier()
        probe.run(episodes, provider, probe.RLock(), source_ids=sources, stand=probe.Zwischenstand())
        assert provider.calls == 0
        probe.Intake(episodes).retry('synthetic-account')
        assert probe.run(episodes, provider, probe.RLock(), source_ids=sources,
                         stand=probe.Zwischenstand()).ok
        assert provider.calls == 1
        assert memory.progress() == dict(total=1, done=1, skipped=0, retry=0, remaining=0)
        assert memory.search('quasararchiv00064')['refs'][0]['episode_id'] == sources[0]
    finally:
        episodes.close()


def test_restart_of_partial_long_source_replays_only_that_source_without_partial_references(tmp_path):
    from icarus_memory.episodes import EpisodeKind
    from icarus_memory.model import Provenance, SourceType
    from icarus_memory.working_memory_analysis import abschnitte_der
    path = tmp_path / 'episodes.sqlite3'
    episodes = probe.EpisodeStore(path)
    body = '\n\n'.join(f'Absatz {n}: ' + 'Die Prüfung zum Quasararchiv bleibt dokumentiert. ' * 16
                         for n in range(80))
    source, _ = episodes.record(EpisodeKind.DOCUMENT, 'Lange synthetische Quelle', body,
                                Provenance(SourceType.DOCUMENT, source_ref='synthetic:long'))
    plan = abschnitte_der(source)
    assert len(plan) > 2
    provider, stand = probe.Classifier(), probe.Zwischenstand()
    assert probe.run(episodes, provider, probe.RLock(), limit=1, abschnitte_je_lauf=2,
                     source_ids=[source.id], stand=stand).ok
    assert provider.calls == 2 and stand.offene() == [source.id]
    assert probe.WorkingMemoryStore(episodes).search('Quasararchiv')['refs'] == []
    episodes.close()
    episodes = probe.EpisodeStore(path)
    try:
        restarted, stand = probe.Classifier(), probe.Zwischenstand()
        for _ in range(len(plan)):
            assert probe.run(episodes, restarted, probe.RLock(), limit=1, abschnitte_je_lauf=2,
                             source_ids=[source.id], stand=stand).ok
            if probe.WorkingMemoryStore(episodes).source_state(source.id) == 'complete':
                break
        assert restarted.calls == len(plan)  # No persisted partial model work is claimed.
        assert probe.WorkingMemoryStore(episodes).search('Quasararchiv')['refs']
        assert episodes.get(source.id).body == body
        assert stand.offene() == []
    finally:
        episodes.close()


@pytest.mark.parametrize('size', [0, 63, True, '100'])
def test_invalid_size_is_rejected_before_creating_data(tmp_path, size):
    with pytest.raises(ValueError):
        probe.run_lifecycle(tmp_path, size=size)
    assert not (tmp_path / 'episodes.sqlite3').exists()


def test_existing_evidence_is_never_overwritten(tmp_path):
    output = tmp_path / 'report.json'
    output.write_text('existing evidence', encoding='utf-8')
    completed = subprocess.run([sys.executable, str(Path(probe.__file__)), '--sources', '64',
                                '--output', str(output)], text=True, capture_output=True)
    assert completed.returncode != 0
    assert 'must not be overwritten' in completed.stderr
    assert output.read_text(encoding='utf-8') == 'existing evidence'
