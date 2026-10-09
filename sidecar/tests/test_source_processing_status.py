"""Status liest Zeitplan und tatsächliche Schlange, nie das Gesprächsmodell."""
from types import SimpleNamespace

import pytest

from icarus_memory.working_memory_store import WorkingMemoryStore
from icarus_memory.scheduler import Scheduler
from tests.test_context_identity import core
from tests.test_source_answers_http import _api, _upload
from tests.test_conversation_retraction import _close_app


def _read(client, eid):
    response = client.get(f'/api/v1/episodes/{eid}')
    assert response.status_code == 200
    return response.json()['memory_status']


def _prepare(app, monkeypatch, standard):
    app.state.scheduler = Scheduler()
    app.state.settings.schedule.enabled = True
    app.state.settings.schedule.with_model = True
    app.state.settings.model_roles = {'hintergrund': {'modell': 'synthetisch-lokal:4b'}}
    app.state.agent._provider = None if standard == 'missing' else SimpleNamespace(is_local=False)
    # Das Lesen darf weder eine neue Rollenauflösung noch eine Modellprobe starten.
    def forbidden(*args, **kwargs):
        raise AssertionError('Statusabfrage darf keinen Anbieter prüfen oder aufrufen')
    monkeypatch.setattr('icarus_memory.model_roles.hintergrund_anbieter', forbidden)
    monkeypatch.setattr('icarus_memory.model_roles.Rollen.provider', forbidden)
    monkeypatch.setattr('icarus_memory.local_model_guard.verify_local_model', forbidden)


@pytest.mark.parametrize('standard', ['remote', 'missing'])
@pytest.mark.parametrize('observed', ['pending', 'queued', 'processing'])
def test_source_status_uses_queue_not_conversation_provider(core, tmp_path, monkeypatch, standard, observed):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        eid = _upload(client, 'Synthetischer Prüfauftrag ohne Frist.')
        _prepare(app, monkeypatch, standard)
        scheduler = app.state.scheduler
        with scheduler._lock:
            if observed == 'queued': scheduler._memory_pending[eid] = None
            elif observed == 'processing': scheduler._memory_active.add(eid)
        before = app.state.episodes.get(eid).digest
        assert _read(client, eid)['state'] == observed
        assert app.state.episodes.get(eid).digest == before
        assert WorkingMemoryStore(app.state.episodes).source_state(eid) == 'pending'
    finally:
        client.close(); _close_app(app)


@pytest.mark.parametrize('standard', ['remote', 'missing'])
def test_failed_source_with_enabled_schedule_is_not_reported_as_manually_paused(core, tmp_path, monkeypatch, standard):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        eid = _upload(client, 'Synthetischer Text.')
        WorkingMemoryStore(app.state.episodes).fail(app.state.episodes.support_snapshot(eid))
        _prepare(app, monkeypatch, standard)
        assert _read(client, eid)['state'] == 'failed'
    finally:
        client.close(); _close_app(app)


@pytest.mark.parametrize('pause_field', ['enabled', 'with_model'])
@pytest.mark.parametrize('observed, expected', [('queued', 'paused'), ('processing', 'processing')])
def test_disabled_schedule_retains_only_actual_inflight_processing(core, tmp_path, monkeypatch, pause_field, observed, expected):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        eid = _upload(client, 'Synthetischer Text.')
        _prepare(app, monkeypatch, 'remote')
        scheduler = app.state.scheduler
        with scheduler._lock:
            if observed == 'queued': scheduler._memory_pending[eid] = None
            else: scheduler._memory_active.add(eid)
        setattr(app.state.settings.schedule, pause_field, False)
        assert _read(client, eid)['state'] == expected
        assert getattr(app.state.settings.schedule, pause_field) is False
    finally:
        client.close(); _close_app(app)


@pytest.mark.parametrize('excluded', [False, True])
def test_current_source_store_state_wins_over_old_scheduler_entries(core, tmp_path, monkeypatch, excluded):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        eid = _upload(client, 'Synthetischer Text.')
        _prepare(app, monkeypatch, 'remote')
        store = WorkingMemoryStore(app.state.episodes)
        snapshot = app.state.episodes.support_snapshot(eid)
        assert store.commit(snapshot, [{'start':0,'end':len(snapshot.episode.body),'kind':'fact'}], model='synthetic')
        if excluded: app.state.episodes.ignore(eid)
        with app.state.scheduler._lock: app.state.scheduler._memory_active.add(eid)
        assert _read(client, eid)['state'] == ('excluded' if excluded else 'complete')
    finally:
        client.close(); _close_app(app)


@pytest.mark.parametrize('observed', ['queued', 'processing'])
def test_retry_queue_is_visible_despite_previous_failure(core, tmp_path, monkeypatch, observed):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        eid = _upload(client, 'Synthetischer Text.')
        store = WorkingMemoryStore(app.state.episodes)
        store.fail(app.state.episodes.support_snapshot(eid))
        _prepare(app, monkeypatch, 'remote')
        with app.state.scheduler._lock:
            if observed == 'queued': app.state.scheduler._memory_pending[eid] = None
            else: app.state.scheduler._memory_active.add(eid)
        assert _read(client, eid)['state'] == observed
        # Die lesende Anzeige verändert keinen früheren Fehler oder Retry.
        assert store.source_state(eid) == 'failed'
    finally:
        client.close(); _close_app(app)
