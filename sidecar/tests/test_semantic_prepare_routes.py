"""Explicit bounded search preparation must not activate heavy classification."""
import threading
from types import SimpleNamespace

import pytest

from tests.test_context_identity import core
from tests.test_source_answers_http import _api
from tests.test_conversation_retraction import _close_app
from tests.test_working_memory_semantic_index import add
from tests.test_working_memory_semantic_service import Embedder
from icarus_memory.hintergrund import AMPEL
from icarus_memory.memory_categories import Categories
from icarus_memory.working_memory_store import WorkingMemoryStore
from icarus_memory.working_memory_semantic_runtime import bind

URL = '/api/v1/memory/semantic/prepare'


def setup(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    monkeypatch.setenv('KINGFISHER_DURABLE_MEMORY_SEARCH', '1')
    service = bind(app, app.state.agent)
    embedder = Embedder(app.state.episodes, app.state.conversation_lock, AMPEL)
    service._factory = lambda: embedder
    app.state.hintergrund = SimpleNamespace(sperre=lambda: None)
    monkeypatch.setattr('icarus_memory.storage_capacity.reason', lambda _: None)
    provider.complete_json = lambda *a, **k: pytest.fail('heavy classification called')
    monkeypatch.setattr('icarus_memory.working_memory_worker.run',
                        lambda *a, **k: pytest.fail('working-memory classification called'))
    monkeypatch.setattr(Categories, 'run', lambda *a, **k: pytest.fail('categories called'))
    return app, client, service, embedder


def test_prepare_only_bounded_vectors_and_preserves_sources(core, tmp_path, monkeypatch):
    app, client, service, embedder = setup(core, tmp_path, monkeypatch)
    try:
        for n in range(10):
            source = add(app.state.episodes, f'Die Zugangskarte {n} liegt im Tresor.')
            memory = WorkingMemoryStore(app.state.episodes)
            memory.commit(memory._snapshot(source.id),
                          [{'start': 0, 'end': len(source.body), 'kind': 'fact'}],
                          model='chatgpt:gpt-6.1-sol', explicit_recheck=True)
            Categories(app.state.episodes).correct(source.id, ['personal'])
        before = '\n'.join(app.state.episodes._conn.iterdump())
        response = client.post(URL)
        assert response.status_code == 200
        assert response.json()['status'] == 'prepared'
        assert response.json()['semantic_index']['indexed'] == 8
        assert len(embedder.inputs) == 1
        assert len(embedder.inputs[0]) == 8
        assert '\n'.join(app.state.episodes._conn.iterdump()) == before
        assert client.post(URL).json()['semantic_index']['indexed'] == 10
        assert client.post(URL).json()['semantic_index']['pending'] == 0
        assert len(embedder.inputs) == 2
        assert client.post(URL, headers={'X-Icarus-Token': 'wrong'}).status_code == 401
    finally:
        client.close(); _close_app(app)


@pytest.mark.parametrize('reason', ['pausiert', 'speicherdruck', 'speicher_unbekannt', 'storage_low'])
def test_prepare_waits_before_any_model_transport(core, tmp_path, monkeypatch, reason):
    app, client, service, embedder = setup(core, tmp_path, monkeypatch)
    try:
        add(app.state.episodes)
        app.state.hintergrund.sperre = lambda: reason
        result = client.post(URL).json()
        assert result['status'] == 'waiting' and result['reason'] == reason
        assert embedder.entered == 0
    finally:
        client.close(); _close_app(app)


def test_prepare_checks_storage_independently(core, tmp_path, monkeypatch):
    app, client, service, embedder = setup(core, tmp_path, monkeypatch)
    try:
        monkeypatch.setattr('icarus_memory.storage_capacity.reason', lambda _: 'storage_unknown')
        assert client.post(URL).json()['reason'] == 'storage_unknown'
        assert embedder.entered == 0
    finally:
        client.close(); _close_app(app)


@pytest.mark.parametrize('change', ['pause', 'configuration', 'service', 'disabled', 'storage'])
def test_prepare_revocation_during_transport_never_commits(core, tmp_path, monkeypatch, change):
    app, client, service, embedder = setup(core, tmp_path, monkeypatch)
    try:
        add(app.state.episodes)
        def revoke():
            if change == 'pause': app.state.hintergrund.sperre = lambda: 'pausiert'
            if change == 'configuration': app.state.settings.model_roles = {'changed': {}}
            if change == 'service': app.state.semantic_search = None
            if change == 'disabled': monkeypatch.setenv('KINGFISHER_DURABLE_MEMORY_SEARCH', '0')
            if change == 'storage': monkeypatch.setattr('icarus_memory.storage_capacity.reason', lambda _: 'storage_low')
        embedder.after_embed = revoke
        result = client.post(URL).json()
        assert result['status'] in {'waiting', 'not_ready'}
        assert service._index.coverage()['indexed'] == 0
    finally:
        service.close(); client.close(); _close_app(app)


def test_prepare_single_flight(core, tmp_path, monkeypatch):
    app, client, service, embedder = setup(core, tmp_path, monkeypatch)
    entered, release = threading.Event(), threading.Event()
    try:
        add(app.state.episodes)
        def wait():
            entered.set()
            assert release.wait(5)
        embedder.after_embed = wait
        answers = []
        thread = threading.Thread(target=lambda: answers.append(client.post(URL)))
        thread.start()
        assert entered.wait(5)
        result = client.post(URL).json()
        assert result['status'] == 'waiting' and result['reason'] == 'busy'
        release.set(); thread.join(5)
        assert answers[0].json()['semantic_index']['indexed'] == 1
        assert len(embedder.inputs) == 1
    finally:
        release.set(); client.close(); _close_app(app)


def test_prepare_disabled_is_explicit(core, tmp_path, monkeypatch):
    app, client, service, embedder = setup(core, tmp_path, monkeypatch)
    try:
        monkeypatch.setenv('KINGFISHER_DURABLE_MEMORY_SEARCH', '0')
        assert client.post(URL).json()['status'] == 'not_ready'
        assert embedder.entered == 0
    finally:
        client.close(); _close_app(app)


def test_prepare_unavailable_embedder_reports_not_ready(core, tmp_path, monkeypatch):
    app, client, service, embedder = setup(core, tmp_path, monkeypatch)
    try:
        add(app.state.episodes)
        embedder.fail = True
        result = client.post(URL).json()
        assert result['status'] == 'not_ready'
        assert not result['job']['ok']
        assert service._index.coverage()['indexed'] == 0
    finally:
        client.close(); _close_app(app)


def test_prepare_restore_inspection_never_loads_embedding(core, tmp_path, monkeypatch):
    from icarus_memory.restore_boundary import mark_pending
    app, client, service, embedder = setup(core, tmp_path, monkeypatch)
    try:
        mark_pending(app.state.runtime_boundary.directory, 'test restore')
        assert client.post(URL).status_code == 423
        assert embedder.entered == 0
    finally:
        client.close(); _close_app(app)


def browser_setup(core, tmp_path, monkeypatch):
    from icarus_memory.hintergrund import Steuerung
    ui = tmp_path / 'ui'
    ui.mkdir()
    (ui / 'index.html').write_text('<!doctype html><title>Test</title>')
    monkeypatch.setenv('ICARUS_UI_DIR', str(ui))
    app, client, service, embedder = setup(core, tmp_path, monkeypatch)
    control = Steuerung(None, lambda: app.state.episodes, ruhe_s=600)
    app.state.hintergrund = control
    client.headers.pop('X-Icarus-Token')
    page = client.get('/today')
    assert 'kingfisher_session=' in page.headers['set-cookie']
    return app, client, service, embedder, control


def test_manual_browser_prepare_does_not_block_itself_as_recent_input(core, tmp_path, monkeypatch):
    app, client, service, embedder, control = browser_setup(core, tmp_path, monkeypatch)
    try:
        add(app.state.episodes)
        assert control.sperre() is None
        result = client.post(URL).json()
        assert result['status'] == 'prepared'
        assert result['semantic_index']['indexed'] == 1
        # Real middleware still records the click; automatic jobs remain idle.
        assert control.sperre() == 'nutzer'
    finally:
        client.close(); _close_app(app)


@pytest.mark.parametrize('reason', ['pausiert', 'speicherdruck', 'speicher_unbekannt',
                                    'akku', 'energie_unbekannt', 'storage_low', 'antwort'])
def test_manual_browser_prepare_keeps_real_controller_restrictions(core, tmp_path, monkeypatch, reason):
    from contextlib import nullcontext
    app, client, service, embedder, control = browser_setup(core, tmp_path, monkeypatch)
    try:
        add(app.state.episodes)
        if reason == 'pausiert':
            control.pausieren(True)
        elif reason != 'antwort':
            control.external_gate = lambda: reason
        with control.aktivitaet.antwort() if reason == 'antwort' else nullcontext():
            result = client.post(URL).json()
            assert result['status'] == 'waiting' and result['reason'] == reason
            assert embedder.entered == 0
    finally:
        client.close(); _close_app(app)


@pytest.mark.parametrize('reason', ['pausiert', 'speicherdruck', 'antwort'])
def test_browser_prepare_rechecks_real_controller_after_embedding(core, tmp_path, monkeypatch, reason):
    app, client, service, embedder, control = browser_setup(core, tmp_path, monkeypatch)
    answer = None
    try:
        add(app.state.episodes)
        def revoke():
            nonlocal answer
            if reason == 'pausiert':
                control.pausieren(True)
            elif reason == 'antwort':
                answer = control.aktivitaet.antwort()
                answer.__enter__()
            else:
                control.external_gate = lambda: reason
        embedder.after_embed = revoke
        result = client.post(URL).json()
        assert result['status'] == 'waiting' and result['reason'] == reason
        assert service._index.coverage()['indexed'] == 0
    finally:
        if answer is not None:
            answer.__exit__(None, None, None)
        client.close(); _close_app(app)
