import threading
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from icarus_memory import world_routes


class Store:
    def usable(self):
        return []


class Episodes:
    def __init__(self): self.head = None; self.n = 0
    def source_head(self, _key): return None
    def record(self, *args, **kwargs):
        self.n += 1; return SimpleNamespace(id=f"e{self.n}"), True
    def advance_source_head(self, *args): pass
    def ignore(self, _episode_id): pass


class Claims:
    def invalidate_source(self, _episode_id): pass


def make(monkeypatch):
    monkeypatch.setattr("icarus_memory.world_monitor._validate_url", lambda url: url)
    monkeypatch.setattr(world_routes.config, "save", lambda *_args: None)
    app = FastAPI()
    app.state.settings = SimpleNamespace(world_sources=[])
    app.state.episodes = Episodes(); app.state.claims = Claims(); app.state.store = Store()
    app.state.conversation_lock = threading.RLock()
    monitor = world_routes.register_world_routes(app, [], lambda: __import__("pathlib").Path("/tmp"))
    return app, monitor


def test_get_is_empty_and_does_not_fetch(monkeypatch):
    app, monitor = make(monkeypatch)
    monitor.fetch = lambda _url: (_ for _ in ()).throw(AssertionError("GET must not fetch"))
    response = TestClient(app).get("/api/v1/world")
    assert response.status_code == 200 and response.json() == {"items": []}


def test_consent_then_refresh_and_disable(monkeypatch):
    app, monitor = make(monkeypatch)
    monitor.fetch = lambda _url: {"text": "public", "captured_at": "2026-01-01T00:00:00Z"}
    client = TestClient(app)
    added = client.post("/api/v1/world", json={"url": "https://example.test", "label": "Example", "topics": []})
    assert added.status_code == 201
    source_id = added.json()["id"]
    assert client.post(f"/api/v1/world/{source_id}/refresh").status_code == 200
    assert client.post(f"/api/v1/world/{source_id}/disable").status_code == 200


def test_topics_are_bounded(monkeypatch):
    app, _monitor = make(monkeypatch)
    response = TestClient(app).post("/api/v1/world", json={"url": "https://example.test", "label": "x", "topics": ["x" * 81]})
    assert response.status_code == 422


def test_restore_switches_settings_and_episode_stores(monkeypatch):
    app, original = make(monkeypatch)
    client = TestClient(app)
    original.add('https://old.test', 'Old', [])
    old_settings = app.state.settings
    app.state.settings = SimpleNamespace(world_sources=[])
    app.state.episodes = Episodes()
    assert client.get('/api/v1/world').json() == {'items': []}
    added = client.post('/api/v1/world', json={'url': 'https://new.test', 'label': 'New', 'topics': []})
    assert added.status_code == 201
    assert old_settings.world_sources[0]['label'] == 'Old'
    assert len(old_settings.world_sources) == 1
    assert app.state.settings.world_sources[0]['label'] == 'New'
    assert app.state.world_monitor.episodes is app.state.episodes
