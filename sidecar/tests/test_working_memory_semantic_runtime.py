"""Product wiring uses the embedding role and never the legacy lazy index."""
from types import SimpleNamespace
import importlib
import pytest
from icarus_memory import config
from tests.test_working_memory_semantic_service import Embedder
from icarus_memory.hintergrund import ModellAmpel
from tests.test_working_memory_semantic_index import add


def runtime():
    try:
        return importlib.import_module('icarus_memory.working_memory_semantic_runtime')
    except ModuleNotFoundError:
        pytest.fail('Product semantic runtime is missing')


def test_binding_uses_local_embedding_role_and_closes_replaced_service(tmp_path, monkeypatch):
    import threading
    from icarus_memory import EpisodeStore
    from icarus_memory import model_roles, local_embeddings
    monkeypatch.setenv('ICARUS_MEMORY_SEMANTIC', '1')
    episodes = EpisodeStore(tmp_path/'episodes.sqlite3')
    lock, ampel = threading.Lock(), ModellAmpel()
    embedding_provider = SimpleNamespace(is_local=True, base_url='http://localhost:11434/v1')
    roles = SimpleNamespace(provider=lambda role: embedding_provider if role=='einbettung' else None,
                            einbettung_modell=lambda: 'embedding:test', cloud_modell_im_weg=lambda role: None)
    monkeypatch.setattr(model_roles, 'rollen_von', lambda app: roles)
    created = []
    def factory(**kwargs):
        created.append(kwargs)
        return Embedder(episodes, lock, ampel)
    monkeypatch.setattr(local_embeddings, 'LocalEmbedder', factory)
    agent = SimpleNamespace(provider=SimpleNamespace(is_local=False, model='cloud-answer'))
    app = SimpleNamespace(state=SimpleNamespace(episodes=episodes, agent=agent,
        conversation_lock=lock, settings=config.Settings()))
    service = runtime().bind(app, agent, ampel=ampel)
    assert created == []
    assert agent._working_memory_search is service
    add(episodes)
    assert service.index_batch().ok
    assert created[0]['model'] == 'embedding:test'
    assert created[0]['base_url'] == 'http://localhost:11434'
    assert created[0]['keep_alive'] == '15s'
    assert runtime().coverage(app)['indexed'] == 1
    before = len(created)
    runtime().coverage(app)
    assert len(created) == before
    next_service = runtime().bind(app, agent, ampel=ampel)
    assert service.coverage()['status'] == 'disabled'
    assert agent._working_memory_search is next_service
    next_service.close(); episodes.close()


def test_disabled_product_binding_explicitly_blocks_legacy_fallback(tmp_path, monkeypatch):
    import threading
    from icarus_memory import EpisodeStore
    monkeypatch.delenv('ICARUS_MEMORY_SEMANTIC', raising=False)
    episodes = EpisodeStore(tmp_path/'episodes.sqlite3')
    agent = SimpleNamespace(provider=None)
    app = SimpleNamespace(state=SimpleNamespace(episodes=episodes, agent=agent,
        conversation_lock=threading.Lock(), settings=config.Settings()))
    service = runtime().bind(app, agent)
    assert agent._working_memory_search is None
    assert runtime().search(app) is None
    assert runtime().coverage(app)['status'] == 'disabled'
    service.close(); episodes.close()


def test_product_embedding_retention_is_sent_to_local_transport():
    import httpx
    import json
    from icarus_memory.local_embeddings import LocalEmbedder
    requests = []
    def respond(request):
        if request.url.path == '/api/tags':
            return httpx.Response(200, json={'models': [{'name': 'embedding:test', 'digest': 'a'*64}]})
        assert request.url.path == '/api/embed'
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={'model': 'embedding:test', 'embeddings': [[1., 0.]]})
    with LocalEmbedder(model='embedding:test', keep_alive='15s', transport=httpx.MockTransport(respond)) as embedder:
        assert embedder.embed(['synthetic']) == [[1., 0.]]
    assert requests == [{'model': 'embedding:test', 'input': ['synthetic'], 'truncate': False, 'keep_alive': '15s'}]
