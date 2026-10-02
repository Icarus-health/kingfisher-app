"""Der Agent wird an genau einer Stelle mit den Zusatzobjekten und Speichern der App verdrahtet."""
import re
from pathlib import Path

from fastapi.testclient import TestClient

from icarus_memory import agent_verdrahtung, server
from icarus_memory.backends import MemoryBackend
from icarus_memory.model_roles import rollen_von
from icarus_memory.server import create_app
from icarus_memory.store import SelfModelStore

ZUSAETZE = ('_runtime_boundary', '_projects', '_termine', '_mappe', '_eigene', '_frage_anbieter')
SPEICHER = ('_store', '_episodes', '_knowledge', '_knowledge_conflicts', '_snapshot_provider', '_support_resolver')


def _schliessen(app):
    for name in ("audit", "tasks", "workspace", "episodes", "proposals", "conversations", "claims", "regeln"):
        speicher = getattr(app.state, name, None)
        if callable(getattr(speicher, "close", None)):
            speicher.close()


def _fehlend(agent, namen):
    return [name for name in namen if getattr(agent, name, None) is None]


def test_der_start_verdrahtet_alles(monkeypatch):
    monkeypatch.setenv("ICARUS_PROVIDER", "ollama")
    monkeypatch.setenv("ICARUS_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("ICARUS_MODEL", "standard-modell")
    app = create_app()
    try:
        agent = app.state.agent
        assert _fehlend(agent, ZUSAETZE) == [] and _fehlend(agent, SPEICHER) == []
        assert agent._frage_anbieter() is None  # keine Rolle `frage` zugewiesen: Rückfall
        assert app.state.consolidator._provider is rollen_von(app).provider("hintergrund")
        assert app.state.summarizer._provider is rollen_von(app).provider("hintergrund")
    finally:
        _schliessen(app)


def test_ein_eingesetzter_agent_bekommt_dieselbe_verdrahtung():
    class Agent:
        provider = None
        _store = None

        def reset(self):
            pass

    eingesetzt = Agent()
    eingesetzt._store = SelfModelStore(MemoryBackend(), subject_id="test")
    app = create_app(eingesetzt._store, agent=eingesetzt)
    try:
        assert app.state.agent is eingesetzt
        assert _fehlend(eingesetzt, ZUSAETZE) == [] and _fehlend(eingesetzt, SPEICHER) == []
        assert app.state.consolidator is not None and app.state.summarizer is not None
    finally:
        _schliessen(app)


def test_neuaufbau_der_speicher_verdrahtet_neu():
    class Agent:
        provider = None

        def __init__(self, store):
            self._store = store
            self.zurueckgesetzt = 0

        def reset(self):
            self.zurueckgesetzt += 1

    store = SelfModelStore(MemoryBackend(), subject_id="test")
    agent = Agent(store)
    app = create_app(store, agent=agent)
    try:
        for name in (*ZUSAETZE, *SPEICHER):
            setattr(agent, name, None)
        app.state.consolidator = app.state.summarizer = None
        server._close_persistent_state(app)
        server._reopen_persistent_state(app)
        assert _fehlend(agent, ZUSAETZE) == [] and _fehlend(agent, SPEICHER) == []
        assert agent._episodes is app.state.episodes and agent._knowledge is app.state.claims
        assert app.state.consolidator._episodes is app.state.episodes
        assert app.state.summarizer._episodes is app.state.episodes
        assert agent.zurueckgesetzt >= 1
    finally:
        _schliessen(app)


def test_server_setzt_keine_agentenfelder_selbst():
    """Wer ein neues Zusatzobjekt braucht, ergänzt `verdrahte_zusaetze`, nicht eine dritte Stelle."""
    text = Path(server.__file__).read_text(encoding='utf-8')
    treffer = re.findall(r"\bagent\._(?:projects|termine|mappe|eigene|frage_anbieter|pruefung|episodes|knowledge|"
                         r"snapshot_provider|support_resolver|runtime_boundary)\s*=", text)
    assert treffer == [], treffer
    assert set(agent_verdrahtung.__all__) == {'baue_hintergrund', 'pruef_tor', 'satzpruefung_stand', 'verdrahte_speicher',
                                             'verdrahte_zusaetze'}
