"""An energy pause unwinds automatic jobs instead of retaining their locks."""
from datetime import datetime
import json
import threading

import pytest

from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.hintergrund import ModellAmpel, Steuerung, als_hintergrund
from icarus_memory.host_power import HostPower
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import ProposalStore
from icarus_memory.providers import Reply
from icarus_memory.restore_boundary import RuntimeBoundary
from icarus_memory.scheduler import JobResult, Scheduler
from icarus_memory.task_detection import TaskDetector


@pytest.mark.parametrize('interruption', ['battery', 'missing'])
@pytest.mark.parametrize('manual_pause', [False, True])
def test_energy_between_model_steps_releases_schedule_and_restore_locks(tmp_path, interruption, manual_pause):
    clock = [100.0]
    power = HostPower(tmp_path, expected=lambda: True, clock=lambda: clock[0])
    power.report('ac')
    ampel = ModellAmpel()
    scheduler = Scheduler()
    boundary = RuntimeBoundary(tmp_path)
    scheduler._runtime_boundary = boundary
    control = Steuerung(None, lambda: None, ruhe_s=0, external_gate=power.reason)
    scheduler.anschliessen(control)
    scheduler.configure(enabled=True, with_model=True)
    scheduler._last_at = datetime.now().astimezone()
    first = threading.Event()
    calls = []

    def work(ids):
        with ampel.aufruf():
            calls.append('first')
        if manual_pause:
            control.pausieren(True)
        if interruption == 'battery':
            power.report('battery')
        else:
            clock[0] += 91
        first.set()
        with ampel.aufruf():
            calls.append('second')
        return JobResult('synthetic', True, 'done')

    scheduler._run_prompt_working_memory = work
    scheduler.start()
    try:
        assert scheduler.request_working_memory('synthetic-source')
        assert first.wait(2)
        acquired = scheduler._run_lock.acquire(timeout=1)
        assert acquired, 'energy pause must release the scheduler job lock'
        scheduler._run_lock.release()
        exclusive = boundary.try_enter(exclusive=True)
        assert exclusive, 'energy pause must release the restore reader lease'
        boundary.leave(exclusive=True)
        assert calls == ['first']
        assert control.pausiert is manual_pause
        assert scheduler._thread.is_alive(), 'scheduler must return to its next tick'
        # Direct scheduler execution remains possible even while automatic work waits.
        assert scheduler.run_once(with_model=False).finished_at is not None
    finally:
        power.report('ac')
        scheduler.stop()


def test_stop_unwinds_a_model_wait_without_waiting_for_manual_resume(tmp_path):
    ampel = ModellAmpel()
    control = Steuerung(None, lambda: None, ruhe_s=0)
    scheduler = Scheduler()
    scheduler.anschliessen(control)
    scheduler.configure(enabled=True, with_model=True)
    scheduler._last_at = datetime.now().astimezone()
    waiting = threading.Event()
    calls = []

    def work(ids):
        control.pausieren(True)
        waiting.set()
        with ampel.aufruf():
            calls.append('model')
        return JobResult('synthetic', True, 'done')

    scheduler._run_prompt_working_memory = work
    scheduler.start()
    try:
        assert scheduler.request_working_memory('synthetic-source')
        assert waiting.wait(2)
        worker = scheduler._thread
        scheduler.stop(timeout=1)
        assert not worker.is_alive(), 'stop must interrupt the condition wait'
        assert calls == [], 'stopping must not authorize a waiting model request'
        assert scheduler._run_lock.acquire(timeout=1)
        scheduler._run_lock.release()
    finally:
        control.pausieren(False)
        scheduler.stop()


def test_task_detector_releases_analysis_lease_on_energy_pause_and_retries(tmp_path):
    power = HostPower(tmp_path, expected=lambda: True)
    power.report('battery')
    ampel = ModellAmpel()

    class Local:
        name, model, is_local = 'synthetic', 'synthetic', True
        def complete(self, messages, tools):
            with ampel.aufruf():
                return Reply(text=json.dumps({'items': []}))

    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    proposals = ProposalStore(tmp_path / 'proposals.sqlite3')
    episode = episodes.record(EpisodeKind.MESSAGE, 'Synthetic', 'Please read this synthetic source.',
                              Provenance(source_type=SourceType.USER_STATED))[0]
    detector = TaskDetector(episodes, proposals, Local(), threading.RLock())
    finished = threading.Event()
    outcome = []

    def detect():
        try:
            with als_hintergrund(power.reason):
                detector.run(with_model=True)
        except BaseException as exc:
            outcome.append(type(exc).__name__)
        finally:
            finished.set()

    worker = threading.Thread(target=detect)
    worker.start()
    try:
        assert finished.wait(1), 'energy pause must unwind the acquired analysis lease'
        assert outcome == ['BackgroundInterrupted']
        state = proposals.memory_analysis.snapshot(episode.id)
        assert (state['state'], state['lease_until']) == ('cancelled', 0)
        assert not proposals.task_analysis_done(episode.id, episode.digest)
        power.report('ac')
        with als_hintergrund(power.reason):
            report = detector.run(with_model=True)
        assert (report.analyzed, report.failed) == (1, 0)
    finally:
        power.report('ac')
        worker.join(2)
        episodes.close()
        proposals.close()


def test_direct_model_request_ignores_automatic_energy_pause(tmp_path):
    power = HostPower(tmp_path, expected=lambda: True)
    power.report('battery')
    ampel = ModellAmpel()
    with ampel.aufruf():
        assert ampel.belegt() == {'vorne': 1, 'hinten': 0}


def test_memory_pause_preserves_committed_sources_and_retries_pending_without_backoff(tmp_path):
    from icarus_memory.hintergrund import BackgroundInterrupted
    from icarus_memory.working_memory_store import WorkingMemoryStore
    from icarus_memory.working_memory_worker import Zwischenstand, run

    power = HostPower(tmp_path, expected=lambda: True)
    power.report('ac')
    ampel = ModellAmpel()

    class Local:
        name, model, is_local = 'synthetic', 'synthetic', True
        calls = 0
        def complete_json(self, messages, **kwargs):
            with ampel.aufruf():
                self.calls += 1
                payload = json.loads(messages[1]['content'])
                items = [{'block_id': f'B{number}', 'kind': 'fact'}
                         for number, _ in enumerate(payload['blocks'], 1)]
                if self.calls == 1:
                    power.report('battery')
                return Reply(text=json.dumps({'items': items}))

    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    originals = [episodes.record(EpisodeKind.MESSAGE, name, body,
        Provenance(SourceType.CHAT, source_ref='chat:synthetic'))[0]
        for name, body in [('first', 'Synthetic first source.'), ('second', 'Synthetic second source.')]]
    provider = Local()
    memory = WorkingMemoryStore(episodes)
    try:
        with pytest.raises(BackgroundInterrupted), als_hintergrund(power.reason):
            run(episodes, provider, threading.RLock(), stand=Zwischenstand())
        assert provider.calls == 1
        coverage = memory.coverage()
        assert (coverage['complete'], coverage['failed']) == (1, 0)
        assert len(memory.pending()) == 1
        assert [episodes.get(item.id).body for item in originals] == [
            'Synthetic first source.', 'Synthetic second source.']
        power.report('ac')
        with als_hintergrund(power.reason):
            run(episodes, provider, threading.RLock(), stand=Zwischenstand())
        assert provider.calls == 2
        assert memory.coverage()['complete'] == 2
    finally:
        episodes.close()


def test_memory_pause_keeps_finished_sections_for_ac_resume(tmp_path):
    from icarus_memory.hintergrund import BackgroundInterrupted
    from icarus_memory.working_memory_analysis import abschnitte_der
    from icarus_memory.working_memory_store import WorkingMemoryStore, source_fingerprint
    from icarus_memory.working_memory_worker import Zwischenstand, run
    from icarus_memory.memory_analysis import model_key

    power = HostPower(tmp_path, expected=lambda: True)
    power.report('ac')
    ampel = ModellAmpel()

    class Local:
        name, model, is_local = 'synthetic', 'synthetic', True
        def __init__(self):
            self.sections = []
        def complete_json(self, messages, **kwargs):
            with ampel.aufruf():
                payload = json.loads(messages[1]['content'])
                self.sections.append(payload['abschnitt']['nr'])
                items = [{'block_id': f'B{number}', 'kind': 'fact'}
                         for number, _ in enumerate(payload['blocks'], 1)]
                if len(self.sections) == 1:
                    power.report('battery')
                return Reply(text=json.dumps({'items': items}))

    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    body = '\n\n'.join(f'Synthetic paragraph {number}. ' + 'Synthetic content. ' * 50
                         for number in range(40))
    episode = episodes.record(EpisodeKind.MESSAGE, 'Synthetic long source', body,
        Provenance(SourceType.CHAT, source_ref='chat:synthetic'))[0]
    provider = Local()
    stand = Zwischenstand()
    memory = WorkingMemoryStore(episodes)
    snapshot = memory.pending()[0]
    section_count = len(abschnitte_der(episode))
    assert section_count > 1
    try:
        with pytest.raises(BackgroundInterrupted), als_hintergrund(power.reason):
            run(episodes, provider, threading.RLock(), stand=stand)
        assert len(stand.holen(episode.id, source_fingerprint(snapshot), model_key(provider))) == 1
        assert memory.coverage()['failed'] == 0
        assert episodes.get(episode.id).body == body
        power.report('ac')
        with als_hintergrund(power.reason):
            run(episodes, provider, threading.RLock(), stand=stand, abschnitte_je_lauf=section_count)
        assert provider.sections == list(range(1, section_count + 1))
        assert memory.coverage()['complete'] == 1
    finally:
        episodes.close()
