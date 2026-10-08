"""Real HTTP question/history flow through durable app-scoped search."""
from icarus_memory import working_memory_semantic
from tests.test_context_identity import core
from tests.test_conversation_retraction import _close_app
from tests.test_source_answers_http import _api, _upload, _ask, _conversation
from tests.test_working_memory_flow import classifier, run_working
from tests.test_working_memory_semantic import _selector_all
from tests.test_working_memory_semantic_service import Embedder
from icarus_memory.hintergrund import AMPEL

SOURCE = 'Die Zugangskarte liegt im Schrank neben dem Empfang.'
QUESTION = 'Wo finde ich den Ausweis zum Reinkommen?'


def test_http_uses_background_vectors_and_reopens_offline_without_embedding(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider); _selector_all(provider)
    try:
        identifier = _upload(client, SOURCE)
        run_working(app)
        monkeypatch.setenv('ICARUS_MEMORY_SEMANTIC', '1')
        from icarus_memory.working_memory_semantic_runtime import bind
        service = bind(app, app.state.agent)
        embedder = Embedder(app.state.episodes, app.state.conversation_lock, AMPEL)
        # Foreground caller holds the existing conversation lock; sources
        # still may never be locked during transport. Background is covered
        # independently by the service's lock/priority tests.
        def embed(texts):
            embedder.inputs.append(list(texts))
            return [[1., 0.] for _ in texts]
        embedder.embed = embed
        service._factory = lambda: embedder
        monkeypatch.setattr(working_memory_semantic, 'for_provider', lambda *args: (_ for _ in ()).throw(
            AssertionError('product must not initialize the diagnostic query-time source index')))
        assert service.index_batch().ok
        embedder.inputs.clear()
        conversation = _conversation(client)
        answer = _ask(client, conversation, QUESTION)
        assert SOURCE in answer['content']
        assert len(embedder.inputs) == 1
        assert embedder.inputs[0] == [QUESTION]
        assert answer['metadata']['context']['working_answer']['semantic_basis'][0]['episode_id'] == identifier
        embedder.inputs.clear()
        embedder.fail = True
        reopened = client.get(f'/api/v1/conversations/{conversation}')
        assert reopened.status_code == 200 and SOURCE in str(reopened.json())
        assert embedder.inputs == []
        app.state.episodes.ignore(identifier)
        withdrawn = client.get(f'/api/v1/conversations/{conversation}')
        assert SOURCE not in str(withdrawn.json())
        assert embedder.inputs == []
    finally:
        client.close(); _close_app(app)


def test_coverage_reports_semantic_progress_without_initializing_embedder(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        monkeypatch.setenv('ICARUS_MEMORY_SEMANTIC', '1')
        from icarus_memory.working_memory_semantic_runtime import bind
        service = bind(app, app.state.agent)
        calls = []
        service._factory = lambda: calls.append(True)
        from icarus_memory import memory_routes
        monkeypatch.setattr(memory_routes, 'rollen_von', lambda app: (_ for _ in ()).throw(
            AssertionError('coverage must not probe provider roles or model tags')))
        response = client.get('/api/v1/memory/coverage')
        assert response.status_code == 200
        progress = response.json()['semantic_index']
        assert progress['status'] == 'unavailable' and progress['indexed'] is None
        assert progress['identity_checked_at'] is None
        assert progress['model_name'] == 'bge-m3:latest'
        assert calls == []
    finally:
        client.close(); _close_app(app)


def test_scheduler_indexes_global_backlog_even_for_source_specific_work(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    try:
        _upload(client, SOURCE)
        run_working(app)  # existing callback, schedule remains disabled
        monkeypatch.setenv('ICARUS_MEMORY_SEMANTIC', '1')
        from icarus_memory.working_memory_semantic_runtime import bind
        service = bind(app, app.state.agent)
        embedder = Embedder(app.state.episodes, app.state.conversation_lock, AMPEL)
        service._factory = lambda: embedder
        callback = app.state.scheduler._run_working_memory
        callback(True, source_ids=['not-an-old-source'])
        assert embedder.inputs == []  # disabled schedule cannot activate indexing
        app.state.settings.schedule.enabled = True
        app.state.settings.schedule.with_model = True
        callback(True, source_ids=['not-an-old-source'])
        assert service.coverage()['indexed'] == 1
        assert SOURCE in embedder.inputs[0][0]
        assert len(embedder.inputs[0]) <= 8
        before = len(embedder.inputs)
        callback(False)
        assert len(embedder.inputs) == before
    finally:
        service = getattr(app.state, 'semantic_search', None)
        if service is not None:
            service.close()
        client.close(); _close_app(app)


def test_restore_lifecycle_rebinds_search_to_reopened_store(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        monkeypatch.setenv('ICARUS_MEMORY_SEMANTIC', '1')
        from icarus_memory.working_memory_semantic_runtime import bind
        from icarus_memory.server import _close_persistent_state, _reopen_persistent_state
        previous = bind(app, app.state.agent)
        original_store = app.state.episodes
        _close_persistent_state(app)
        assert previous._closed
        _reopen_persistent_state(app)
        current = app.state.semantic_search
        assert current is not previous
        assert current.episodes is app.state.episodes
        assert current.episodes is not original_store
        assert app.state.agent._working_memory_search is current
        assert previous.search_with_status(app.state.episodes, QUESTION).status == 'unavailable'
    finally:
        service = getattr(app.state, 'semantic_search', None)
        if service is not None:
            service.close()
        client.close(); _close_app(app)
