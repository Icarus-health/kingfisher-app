"""History throttling must be distinguishable from actual mailbox capture."""
from contextlib import closing

from icarus_memory.episodes import EpisodeStore
from icarus_memory.mail_intake import Intake
from icarus_memory.mail_stand import konto_stand
from icarus_memory.working_memory_store import WorkingMemoryStore
from .test_mail_intake import Reader
from .test_mail_global_pause import intake_client


def test_history_wait_is_reported_at_the_same_boundary_that_stops_capture(tmp_path):
    with closing(EpisodeStore(tmp_path / 'episodes.sqlite3')) as episodes:
        intake = Intake(episodes); reader = Reader(); reader.count = 260
        intake.start('a', ['INBOX'])
        for _ in range(4): intake.step('a', reader, batch=50)
        assert not intake.status('a')['history_waiting_for_analysis']
        source_id = intake.step('a', reader, batch=1)[0]
        before = intake.status('a')
        assert before['history_waiting_for_analysis'] and before['step'] == 'waiting_analysis'
        assert before['folders'][0]['captured'] == 201
        assert intake.step('a', reader, batch=10) == []
        status = konto_stand('Probe', intake=before)
        assert status['zustand'] == 'wartet'
        assert status['gelesen'] == 201 and status['gesamt'] == 260
        assert 'Einordnung' in status['satz']
        memory = WorkingMemoryStore(episodes)
        snapshot = memory.pending(episode_ids=[source_id])[0]
        assert memory.commit(snapshot, [{'start': 0, 'end': len(snapshot.episode.body), 'kind': 'fact'}], model='synthetic')
        assert not intake.status('a')['history_waiting_for_analysis']
        assert intake.step('a', reader, batch=1)


def test_live_mail_continues_during_history_wait_but_pause_keeps_priority(tmp_path):
    with closing(EpisodeStore(tmp_path / 'episodes.sqlite3')) as episodes:
        intake = Intake(episodes); reader = Reader(); reader.count = 260
        intake.start('a', ['INBOX'])
        for _ in range(5): intake.step('a', reader, batch=50)
        assert intake.status('a')['history_waiting_for_analysis']
        reader.count = 261
        assert intake.step('a', reader, batch=10)
        assert episodes._conn.execute('SELECT status FROM mail_intake_items WHERE uid=261').fetchone()[0] == 'captured'
        intake.pause('a', True)
        status = intake.status('a')
        assert status['step'] == 'paused'
        assert konto_stand('Probe', intake=status)['zustand'] == 'pausiert'


def test_global_pause_overrides_history_wait_and_resume_restores_wait(intake_client):
    from .test_mail_global_pause import snapshots
    client, state = intake_client
    state['history_waiting_for_analysis'] = True
    assert snapshots(client)[1]['zustand'] == 'wartet'
    client.post('/api/v1/hintergrund/pause')
    intake, report = snapshots(client)
    assert report['zustand'] == 'pausiert'
    assert (report['gelesen'], report['gesamt']) == (20, 100)
    assert not intake['accounts'][0]['paused']
    client.post('/api/v1/hintergrund/weiter')
    assert snapshots(client)[1]['zustand'] == 'wartet'
