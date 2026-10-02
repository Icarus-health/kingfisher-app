import pytest
from fastapi.testclient import TestClient
from types import SimpleNamespace

from icarus_memory import config
from icarus_memory.backends import MemoryBackend
from icarus_memory.server import create_app
from icarus_memory.store import SelfModelStore
from icarus_memory.local_model_guard import LocalModelIdentity
from icarus_memory.providers import ProviderError


class Provider:
    def __init__(self, local=True, model="test-local"):
        self.is_local = local
        self.model = model


class Scheduler:
    def __init__(self):
        self.config = None
        self.started = False
    def configure(self, **kwargs): self.config = kwargs
    def start(self): self.started = True
    def stop(self): self.started = False
    def state(self): return {"enabled": bool(self.config and self.config["enabled"]),
                             "with_model": bool(self.config and self.config["with_model"])}


class Agent:
    def __init__(self, provider): self.provider = provider
    def reset(self): pass


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("icarus_memory.local_model_guard.verify_local_model",
                        lambda provider: LocalModelIdentity(provider.model, "a" * 64))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id="test"), agent=Agent(Provider()))
    app.state.scheduler = Scheduler()
    app.state.consolidator = SimpleNamespace(run=lambda **_: None)
    app.state.summarizer = SimpleNamespace(run=lambda **_: None)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield app, client
    for name in ("audit", "tasks", "workspace", "episodes", "proposals", "conversations", "claims", "regeln"):
        store = getattr(app.state, name, None)
        if callable(getattr(store, "close", None)):
            store.close()


def test_enable_is_local_persisted_and_preserves_source_permissions(app_client, tmp_path):
    app, client = app_client
    plan = app.state.settings.schedule
    plan.mail_accounts = ["approved-mail"]
    plan.sources = {"/approved": "filesystem"}
    plan.backup = False
    response = client.put("/api/v1/memory/automation", json={"enabled": True})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["state"] == "active" and result["requested"] is True
    assert (plan.enabled, plan.with_model, plan.local_model_only) == (True, True, True)
    assert plan.mail_accounts == ["approved-mail"]
    assert plan.sources == {"/approved": "filesystem"} and plan.backup is False
    assert app.state.scheduler.config["with_model"] is True
    assert client.get("/api/v1/memory/automation").json()["state"] == "active"
    reloaded = config.load(tmp_path).schedule
    assert reloaded.local_model_only and reloaded.with_model and reloaded.enabled
    assert reloaded.mail_accounts == ["approved-mail"] and reloaded.sources == {"/approved": "filesystem"}


def test_legacy_active_is_neither_hidden_as_paused_nor_claimed_local(app_client, monkeypatch):
    app, client = app_client
    plan = app.state.settings.schedule
    plan.enabled = plan.with_model = True
    plan.local_model_only = False
    monkeypatch.setattr("icarus_memory.local_model_guard.verify_local_model",
                        lambda _provider: pytest.fail("legacy state must not claim local verification"))
    result = client.get("/api/v1/memory/automation").json()
    assert result["state"] == "legacy_active" and result["requested"] is False
    coverage = client.get("/api/v1/memory/coverage").json()
    assert coverage["working_memory_enabled"] is True
    assert coverage["automation"]["state"] == "legacy_active"


def test_legacy_upgrade_and_pause_preserve_existing_source_permissions(app_client):
    app, client = app_client
    plan = app.state.settings.schedule
    plan.enabled = plan.with_model = True
    plan.local_model_only = False
    plan.interval_minutes = 90
    plan.sources = {"/approved": "filesystem"}
    plan.mail_accounts = ["approved-mail"]
    plan.backup = False
    assert client.get("/api/v1/memory/automation").json()["state"] == "legacy_active"
    upgraded = client.put("/api/v1/memory/automation", json={"enabled": True})
    assert upgraded.status_code == 200 and upgraded.json()["state"] == "active"
    assert (plan.enabled, plan.with_model, plan.local_model_only) == (True, True, True)
    assert (plan.interval_minutes, plan.sources, plan.mail_accounts, plan.backup) == (
        90, {"/approved": "filesystem"}, ["approved-mail"], False)
    paused = client.put("/api/v1/memory/automation", json={"enabled": False})
    assert paused.status_code == 200 and paused.json()["state"] == "paused"
    assert plan.enabled and not plan.with_model and plan.local_model_only
    assert (plan.interval_minutes, plan.sources, plan.mail_accounts, plan.backup) == (
        90, {"/approved": "filesystem"}, ["approved-mail"], False)


@pytest.mark.parametrize("provider", [Provider(local=False), Provider(local=True, model="")])
def test_enable_rejects_remote_or_missing_model_without_mutation(app_client, provider):
    app, client = app_client
    app.state.agent.provider = provider
    before = (app.state.settings.schedule.enabled, app.state.settings.schedule.with_model,
              app.state.settings.schedule.local_model_only)
    response = client.put("/api/v1/memory/automation", json={"enabled": True})
    assert response.status_code == 409
    assert (app.state.settings.schedule.enabled, app.state.settings.schedule.with_model,
            app.state.settings.schedule.local_model_only) == before


def test_pause_only_disables_model_work_and_cloud_rewire_gates_scheduler(app_client):
    app, client = app_client
    plan = app.state.settings.schedule
    plan.enabled = True
    plan.with_model = True
    plan.local_model_only = True
    plan.sources = {"/approved": "filesystem"}
    plan.mail_accounts = ["approved-mail"]
    plan.backup = True
    response = client.put("/api/v1/memory/automation", json={"enabled": False})
    assert response.status_code == 200 and response.json()["state"] == "paused"
    assert plan.enabled and not plan.with_model and plan.local_model_only
    assert plan.sources == {"/approved": "filesystem"} and plan.mail_accounts == ["approved-mail"] and plan.backup
    plan.with_model = True
    app.state.agent.provider = Provider(local=False)
    from icarus_memory.server import _wire_scheduler
    _wire_scheduler(app)
    assert app.state.scheduler.config["enabled"] is True
    assert app.state.scheduler.config["with_model"] is False


def test_save_failure_rolls_back_schedule(app_client, monkeypatch):
    app, client = app_client
    old = (app.state.settings.schedule.enabled, app.state.settings.schedule.with_model,
           app.state.settings.schedule.local_model_only)
    monkeypatch.setattr("icarus_memory.memory_routes.config.save", lambda *_: (_ for _ in ()).throw(OSError("disk")))
    response = client.put("/api/v1/memory/automation", json={"enabled": True})
    assert response.status_code == 500
    assert (app.state.settings.schedule.enabled, app.state.settings.schedule.with_model,
            app.state.settings.schedule.local_model_only) == old


def test_enable_rejects_unverified_local_weights(app_client, monkeypatch):
    app, client = app_client
    monkeypatch.setattr("icarus_memory.local_model_guard.verify_local_model",
                        lambda _provider: (_ for _ in ()).throw(ProviderError("unverified")))
    response = client.put("/api/v1/memory/automation", json={"enabled": True})
    assert response.status_code == 409
    assert not app.state.settings.schedule.with_model


def test_status_reports_unavailable_weights_without_exposing_guard_error(app_client, monkeypatch):
    _app, client = app_client
    monkeypatch.setattr("icarus_memory.local_model_guard.verify_local_model",
                        lambda _provider: (_ for _ in ()).throw(ProviderError("synthetic guard detail")))
    response = client.get("/api/v1/memory/automation")
    assert response.status_code == 200
    assert response.json()["state"] == "local_model_unavailable"
    assert "synthetic" not in response.text


@pytest.mark.parametrize("provider", [Provider(local=True, model=""), Provider(local=False, model="")])
def test_vormerken_waehrend_das_modell_noch_laedt(app_client, provider):
    """Fremdprobe 3, Befund 3: Die Fertig-Seite verspricht die Einordnung, also schaltet sie das Sortieren ein, auch wenn
    das Sprachmodell noch lädt. Es läuft erst, wenn ein lokales Modell bereit ist; bis dahin nur der Vermerk."""
    app, client = app_client
    app.state.agent.provider = provider
    response = client.put("/api/v1/memory/automation", json={"enabled": True, "vormerken": True})
    assert response.status_code == 200, response.text
    assert response.json()["requested"] is True and response.json()["state"] == "model_missing"
    plan = app.state.settings.schedule
    assert plan.enabled and plan.with_model and plan.local_model_only
    # Ohne lokales Modell bekommt der Zeitplan keine Modellarbeit.
    assert app.state.scheduler.config["with_model"] is False


def test_vormerken_bei_unbestaetigtem_lokalem_modell(app_client, monkeypatch):
    app, client = app_client
    monkeypatch.setattr("icarus_memory.local_model_guard.verify_local_model",
                        lambda _provider: (_ for _ in ()).throw(ProviderError("lädt noch")))
    response = client.put("/api/v1/memory/automation", json={"enabled": True, "vormerken": True})
    assert response.status_code == 200 and response.json()["state"] == "local_model_unavailable"
    assert app.state.settings.schedule.with_model and app.state.settings.schedule.local_model_only


def test_ein_modell_im_internet_wird_nie_vorgemerkt(app_client):
    app, client = app_client
    app.state.agent.provider = Provider(local=False, model="fremd-im-netz")
    response = client.put("/api/v1/memory/automation", json={"enabled": True, "vormerken": True})
    assert response.status_code == 409
    assert not app.state.settings.schedule.with_model


def test_status_reports_missing_model_when_provider_is_unconfigured(app_client):
    app, client = app_client
    app.state.agent.provider = None
    result = client.get("/api/v1/memory/automation").json()
    assert result["state"] == "model_missing"
    assert result["model"] is None


@pytest.mark.parametrize('change', ['pause', 'in_place_model'])
def test_background_provider_is_invalidated_before_request(app_client, monkeypatch, change):
    from icarus_memory import server
    from icarus_memory.local_model_guard import VerifiedLocalProvider

    app, client = app_client
    plan = app.state.settings.schedule
    plan.enabled = plan.with_model = plan.local_model_only = True
    app.state.agent.provider.complete_json = lambda *_args, **_kwargs: pytest.fail("model request escaped pause")
    server._wire_scheduler(app)
    captured = {}

    class Detector:
        def __init__(self, _episodes, _proposals, provider, _lock, tasks=None): captured["provider"] = provider
        def run(self, **_kwargs): return SimpleNamespace(available=True, cancelled=False, analyzed=0,
                                                         proposed=0, failed=0)

    monkeypatch.setattr(server, "TaskDetector", Detector)
    app.state.scheduler._run_task_detection(True)
    provider = captured["provider"]
    assert isinstance(provider, VerifiedLocalProvider)
    assert provider._permitted()
    if change == 'pause':
        assert client.put("/api/v1/memory/automation", json={"enabled": False}).status_code == 200
    else:
        app.state.agent.provider.model = 'changed-model'
    assert not provider._permitted()
    with pytest.raises(ProviderError):
        provider.complete_json([{"role": "user", "content": "synthetic"}])


def test_existing_mail_ai_opt_in_stays_local_and_independent_of_memory_pause(app_client, monkeypatch):
    from icarus_memory import config, mail_filter, server
    from icarus_memory.connectors.mail import Message
    from icarus_memory.local_model_guard import VerifiedLocalProvider

    app, _client = app_client
    plan = app.state.settings.schedule
    plan.enabled = True
    plan.with_model = False
    plan.local_model_only = True
    plan.mail_accounts = ["inbox"]
    app.state.settings.mail_accounts = [config.MailAccountSettings(
        id="inbox", label="Synthetic", imap_host="localhost", user="synthetic")]
    app.state.settings.mail_filter = {"ai_enabled": True, "block_newsletters": False}
    provider_calls = []
    app.state.agent.provider.complete_json = lambda *_args, **_kwargs: (
        provider_calls.append("local") or SimpleNamespace(
            text='{"category":"important","confidence":0.95}', tool_calls=[]))
    class Reader:
        def pending_uids(self, **_kwargs): return ["1"]
        def message(self, uid): return Message(uid=uid, subject="Synthetic", sender="sender@example.org",
            date=None, preview="Local test", unread=True, body="Local test")
    reader = Reader()
    app.state.mail = SimpleNamespace(reader_for=lambda _account: reader)
    monkeypatch.setattr(server, "file_roots_from_env", lambda _value: [])
    providers_seen = []
    original_classify = mail_filter.classify
    monkeypatch.setattr(mail_filter, "classify", lambda message, selected, provider=None: (
        providers_seen.append(provider) or original_classify(message, selected, provider)))
    server._wire_scheduler(app)
    app.state.scheduler._run_ingest()
    assert providers_seen and isinstance(providers_seen[0], VerifiedLocalProvider)
    assert provider_calls == ["local"]
    assert app.state.settings.mail_filter["ai_enabled"] is True
    screened_provider = providers_seen[0]
    assert screened_provider._permitted()
    app.state.agent.provider = Provider(local=False, model="remote")
    server._wire_scheduler(app)
    assert not screened_provider._permitted()
    with pytest.raises(ProviderError):
        screened_provider.complete_json([{"role": "user", "content": "synthetic"}])
    assert provider_calls == ["local"]


def test_legacy_schedule_defaults_local_model_only_false():
    schedule = config.Settings.from_dict({"schedule": {"enabled": True, "with_model": True}}).schedule
    assert schedule.local_model_only is False


@pytest.mark.parametrize(("provider", "expected"), [
    (Provider(local=False), "wrong_model"),
    (Provider(local=True, model=""), "model_missing"),
])
def test_status_explains_why_saved_request_is_not_running(app_client, provider, expected):
    app, client = app_client
    plan = app.state.settings.schedule
    plan.enabled = plan.with_model = plan.local_model_only = True
    app.state.agent.provider = provider
    result = client.get("/api/v1/memory/automation").json()
    assert result["requested"] is True
    assert result["state"] == expected
