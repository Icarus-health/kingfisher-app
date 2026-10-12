"""Neue Post darf beim Aufgabenprüfen nicht hinter dem Erstbestand warten.

Brüche: keine atomare Live-Wiedervorlage; Aufgaben nur im großen Zeitplanlauf;
Pause/Modellfreigabe ignoriert; zweite Modellarbeit parallel zur laufenden Arbeit.
Nur der Postfachtransport und Modellurteile sind künstlich, Stores und Zeitplan echt.
"""
from datetime import datetime, timezone
from threading import Event
from types import SimpleNamespace
import time

import pytest
from icarus_memory import episodes as episode_module
from icarus_memory.connectors.mail import Message
from icarus_memory.mail_intake import Intake
from icarus_memory.proposals import ProposalKind
from icarus_memory.scheduler import JobResult, Scheduler
from icarus_memory.task_detection import for_briefing
from tests.test_task_source_generation import context, LocalReview, TEXT
from tests.test_mail_intake import Reader


class Incoming(Reader):
    count = 30
    def message_in_folder(self, folder, uid):
        return Message(uid, 'Neue Bitte', 'Lea <lea@example.test>',
            datetime.now(timezone.utc), TEXT, False, body=TEXT)


def capture_live(context, monkeypatch):
    app, provider, detector, _ = context
    provider.forced_kind = 'request_to_recipient'
    intake = Intake(app.state.episodes); reader = Incoming()
    intake.start('synthetic', ['INBOX'])
    intake.step('synthetic', reader, batch=2)
    first = app.state.episodes.analysis_batch()[0]
    app.state.proposals.advance_task_scan(first.id)
    reader.count = 31
    # Die neue Quelle liegt sicher hinter dem alten Scan-Zeiger, unabhängig von UUID-Zufall.
    with monkeypatch.context() as patch:
        patch.setattr(episode_module, 'uuid', SimpleNamespace(uuid4=lambda: SimpleNamespace(hex='0'*32)))
        [ident] = intake.step('synthetic', reader, batch=1)
    assert ident < first.id
    assert intake.db.execute("SELECT status FROM mail_intake_items WHERE account='synthetic' AND lane='live' AND uid=31").fetchone()[0] == 'captured'
    return intake, reader, ident


def test_new_live_mail_behind_cursor_is_reviewed_next_bounded_run(context, monkeypatch):
    app, provider, detector, _ = context
    _, _, ident = capture_live(context, monkeypatch)
    assert detector.run(with_model=True, limit=2).analyzed >= 1
    job = app.state.proposals.memory_analysis.snapshot(ident)
    assert job is not None and job['state'] == 'completed'
    assert [row['episode_id'] for row in for_briefing(app.state.proposals, app.state.episodes)['items']] == [ident]
    assert app.state.tasks.all_tasks() == []


def test_task_check_runs_between_full_passes_despite_waiting_upload(context, monkeypatch):
    from icarus_memory import scheduler as module
    app, provider, detector, _ = context
    _, _, ident = capture_live(context, monkeypatch)
    monkeypatch.setattr(module, 'TICK_SECONDS', 0.001)
    checked = Event()
    def check():
        detector.run(with_model=True, limit=2)
        if app.state.proposals.memory_analysis.snapshot(ident): checked.set()
        return JobResult('zusagen')
    plan = Scheduler(); plan._run_priority_tasks = check
    plan.configure(enabled=True, with_model=True); plan._last_at = datetime.now(timezone.utc)
    plan._memory_pending['synthetic-upload'] = None
    plan._next_memory_at = time.monotonic()+60
    plan.start()
    try:
        assert checked.wait(1), 'Aktuelle Aufgabe wartete auf den großen Zeitplanlauf.'
        assert app.state.proposals.memory_analysis.snapshot(ident)['state'] == 'completed'
    finally:
        plan.stop()


@pytest.mark.parametrize('enabled,with_model,stopped', [(False,True,False),(True,False,False),(True,True,True)])
def test_priority_tasks_respect_schedule_model_and_stop(context, monkeypatch, enabled, with_model, stopped):
    app, _, detector, _ = context
    _, _, ident = capture_live(context, monkeypatch)
    plan = Scheduler(); plan._run_priority_tasks = lambda: detector.run(with_model=True, limit=2)
    plan.configure(enabled=enabled, with_model=with_model)
    if stopped: plan._stop.set()
    plan._run_background_tasks()
    assert app.state.proposals.memory_analysis.snapshot(ident) is None
    assert any(row['id']==ident for row in app.state.episodes.task_rechecks())


@pytest.mark.parametrize('reason', ['pausiert','akku','aktivitaet','antwort'])
def test_priority_tasks_respect_activity_power_and_manual_pause(context, monkeypatch, reason):
    app, _, detector, _ = context
    _, _, ident = capture_live(context, monkeypatch)
    plan = Scheduler(); plan._run_priority_tasks = lambda: detector.run(with_model=True, limit=2)
    plan.configure(enabled=True, with_model=True)
    plan._steuerung = SimpleNamespace(sperre=lambda:reason)
    plan._run_background_tasks()
    assert app.state.proposals.memory_analysis.snapshot(ident) is None
    assert any(row['id']==ident for row in app.state.episodes.task_rechecks())


def test_priority_tasks_cannot_run_beside_other_model_work(context, monkeypatch):
    app, _, detector, _ = context
    _, _, ident = capture_live(context, monkeypatch)
    plan = Scheduler(); plan._run_priority_tasks = lambda: detector.run(with_model=True, limit=2)
    plan.configure(enabled=True, with_model=True)
    with plan._run_lock:
        plan._run_background_tasks()
        assert app.state.proposals.memory_analysis.snapshot(ident) is None
    plan._run_background_tasks()
    assert app.state.proposals.memory_analysis.snapshot(ident)['state'] == 'completed'


def test_live_capture_checkpoint_failure_rolls_back_its_recheck(context, monkeypatch):
    app, _, _, _ = context
    intake, reader, ident = capture_live(context, monkeypatch)
    before = app.state.episodes.task_rechecks()
    original = intake._captured
    def crash(item, episode_id, created):
        original(item, episode_id, created)
        if item['lane']=='live': raise RuntimeError('synthetic checkpoint failure')
    monkeypatch.setattr(intake, '_captured', crash)
    reader.count=32
    intake.step('synthetic', reader, batch=2)
    assert app.state.episodes.task_rechecks() == before
    row=intake.db.execute("SELECT status,episode_id FROM mail_intake_items WHERE account='synthetic' AND lane='live' AND uid=32").fetchone()
    assert tuple(row)==('failed',None)
    assert app.state.episodes.get(ident).body==TEXT


def test_live_recheck_survives_restart_and_disabled_detection(context, monkeypatch):
    from icarus_memory.episodes import EpisodeStore
    app, _, detector, _ = context
    _, _, ident = capture_live(context, monkeypatch)
    detector.run(with_model=False)
    fresh=EpisodeStore(app.state.episodes._path)
    try:
        assert any(row['id']==ident for row in fresh.task_rechecks())
        detector.episodes=fresh
        detector.run(with_model=True,limit=2)
        assert app.state.proposals.memory_analysis.snapshot(ident)['state']=='completed'
        assert all(row['id']!=ident for row in fresh.task_rechecks())
    finally:
        fresh.close()


def test_restore_inspection_prevents_background_tasks(context, monkeypatch, tmp_path):
    from icarus_memory.restore_boundary import RuntimeBoundary, RestorePending, mark_pending
    app, _, detector, _ = context
    _, _, ident=capture_live(context,monkeypatch)
    directory=tmp_path/'synthetic-recovery'
    mark_pending(directory,'synthetic restore')
    plan=Scheduler();plan._run_priority_tasks=lambda: detector.run(with_model=True,limit=2)
    plan.configure(enabled=True,with_model=True);plan._runtime_boundary=RuntimeBoundary(directory)
    with pytest.raises(RestorePending):plan._run_background_tasks()
    assert app.state.proposals.memory_analysis.snapshot(ident) is None


def test_wired_background_job_does_not_read_unrelated_proposal_sources(context, monkeypatch):
    from icarus_memory.episodes import EpisodeKind
    from icarus_memory.model import Provenance, SourceType
    app, _, _, _=context
    _, _, ident=capture_live(context,monkeypatch)
    old=app.state.episodes.record(EpisodeKind.MESSAGE,'Unbeteiligte alte Quelle',TEXT,
        Provenance(source_type=SourceType.EMAIL),source_key='synthetic:unrelated')[0]
    app.state.proposals.record_task_analysis(old.id,old.digest,[{'title':'Bericht senden','quote':TEXT}],proposed_by='synthetic')
    accesses=[];original=app.state.episodes.get
    def get(identifier):
        accesses.append(identifier)
        return original(identifier)
    monkeypatch.setattr(app.state.episodes,'get',get)
    # Echte Verdrahtung; das App-Modell ist aus, daher kein externer Aufruf.
    assert app.state.agent.provider is None
    app.state.scheduler._run_priority_tasks()
    assert old.id not in accesses, 'Der kurze Takt las unbeteiligte Vorschlagsquellen.'


def test_priority_only_attempts_do_not_scan_or_process_unrelated_history(context, monkeypatch):
    app, provider, detector, _=context
    _, _, ident=capture_live(context,monkeypatch)
    history=[e.id for e in app.state.episodes.analysis_batch() if e.id!=ident]
    original=app.state.episodes.analysis_batch
    def forbidden(*args,**kwargs):
        pytest.fail('Der kurze Aufgabenlauf darf nicht den Rohquellenbestand durchgehen.')
    monkeypatch.setattr(app.state.episodes,'analysis_batch',forbidden)
    report=detector.run(with_model=True,limit=2,rechecks_only=True)
    assert report.analyzed==1
    assert app.state.proposals.memory_analysis.snapshot(ident)['state']=='completed'
    assert all(app.state.proposals.memory_analysis.snapshot(old) is None for old in history)
    before=len(provider.inputs)
    detector.run(with_model=True,limit=2,rechecks_only=True)
    assert len(provider.inputs)==before
    monkeypatch.setattr(app.state.episodes,'analysis_batch',original)


def test_restore_inspection_does_not_kill_priority_scheduler_thread(context, monkeypatch, tmp_path):
    from icarus_memory import scheduler as module
    from icarus_memory.restore_boundary import RuntimeBoundary,mark_pending
    monkeypatch.setattr(module,'TICK_SECONDS',0.001)
    directory=tmp_path/'synthetic-scheduler-recovery';mark_pending(directory,'synthetic restore')
    plan=Scheduler();plan._run_priority_tasks=lambda:pytest.fail('Model work during restore inspection')
    plan._runtime_boundary=RuntimeBoundary(directory)
    plan.configure(enabled=True,with_model=True);plan._last_at=datetime.now(timezone.utc)
    ticks=[];second=Event()
    def light():
        ticks.append(1)
        if len(ticks)>=2:second.set()
    plan._nebenbei=light
    plan.start()
    try:
        assert second.wait(1),'Wiederherstellung stoppte den Zeitplanfaden.'
    finally:
        plan.stop()
