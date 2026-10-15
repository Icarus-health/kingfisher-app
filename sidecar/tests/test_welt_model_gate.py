"""The separate news worker must respect live local model permissions."""
from types import SimpleNamespace
import threading
from contextlib import contextmanager

import pytest

from icarus_memory.welt_briefing_routes import dienst
from icarus_memory.welt_feeds import Eintrag
from icarus_memory.welt_meldungen import Sache, Treffer, waehlen
from icarus_memory.local_model_guard import LocalModelIdentity


class LocalModel:
    name = 'synthetic'
    model = 'installed-model'
    base_url = 'http://127.0.0.1:11434/v1'
    is_local = True

    def __init__(self):
        self.requests = []

    def complete_json(self, messages, **kwargs):
        self.requests.append(messages)
        return SimpleNamespace(text='{"betrifft":false}', tool_calls=[])


def configured(monkeypatch):
    selected = [LocalModel()]
    control = SimpleNamespace(reason=None)
    control.sperre = lambda: control.reason
    app = SimpleNamespace(state=SimpleNamespace(
        episodes=object(), hintergrund=control,
        settings=SimpleNamespace(schedule=SimpleNamespace(enabled=True, with_model=True)),
    ))
    from icarus_memory import model_roles
    from icarus_memory import local_model_guard
    # The model/metadata boundary is synthetic; real weight verification has
    # its own transport tests. Exercise actual news selection and live guards.
    monkeypatch.setattr(local_model_guard, 'verify_local_model',
                        lambda provider: LocalModelIdentity(provider.model, 'a' * 64))
    monkeypatch.setattr(model_roles, 'rollen_von', lambda app: SimpleNamespace(provider=lambda role: selected[0]))
    hit = Treffer(Eintrag('news', 'Klinikum baut aus', 'Klinikum', 'https://news.example/1', None),
                  'feed', 'Fachzeitung', Sache('organisation:klinikum', 'organisation', 'Klinikum', ('Klinikum',)),
                  300, True)
    return app, selected, control, hit


@pytest.mark.parametrize('reason', [
    'pausiert', 'speicherdruck', 'akku', 'energie_unbekannt', 'speicher_unbekannt',
    'storage_low', 'storage_unknown', 'nutzer', 'antwort',
])
def test_world_model_blocked_by_live_controller_keeps_name_match(monkeypatch, reason):
    app, selected, control, hit = configured(monkeypatch)
    requests = selected[0].requests
    control.reason = reason
    assert waehlen([hit], dienst(app)._anbieter()) is hit
    assert requests == []


@pytest.mark.parametrize('change', ['pause', 'disable', 'model_permission', 'role', 'model', 'controller_missing'])
def test_world_provider_rechecks_permissions_before_every_request(monkeypatch, change):
    app, selected, control, hit = configured(monkeypatch)
    requests = selected[0].requests
    checked = dienst(app)._anbieter()
    assert waehlen([hit], checked) is None  # permitted model can veto a name match
    requests.clear()
    if change == 'pause':
        control.reason = 'pausiert'
    elif change == 'disable':
        app.state.settings.schedule.enabled = False
    elif change == 'model_permission':
        app.state.settings.schedule.with_model = False
    elif change == 'role':
        selected[0] = LocalModel()
    elif change == 'model':
        selected[0].model = 'changed'
    else:
        del app.state.hintergrund
    assert waehlen([hit], checked) is hit
    assert requests == []


def test_world_model_missing_controller_falls_back_without_transport(monkeypatch):
    app, selected, _, hit = configured(monkeypatch)
    requests = selected[0].requests
    del app.state.hintergrund
    assert waehlen([hit], dienst(app)._anbieter()) is hit
    assert requests == []


def test_permitted_world_model_can_veto_name_match_through_actual_adapter(monkeypatch):
    from icarus_memory import model_roles
    from tests.test_local_model_guard import provider, wire

    original = provider()
    app = SimpleNamespace(state=SimpleNamespace(
        episodes=object(), hintergrund=SimpleNamespace(sperre=lambda: None),
        settings=SimpleNamespace(schedule=SimpleNamespace(enabled=True, with_model=True)),
    ))
    monkeypatch.setattr(model_roles, 'rollen_von', lambda app: SimpleNamespace(provider=lambda role: original))
    requests, _, _ = wire(monkeypatch, chat='{"betrifft":false}')
    hit = Treffer(Eintrag('news', 'Klinikum baut aus', 'Klinikum', 'https://news.example/1', None),
                  'feed', 'Fachzeitung', Sache('organisation:klinikum', 'organisation', 'Klinikum', ('Klinikum',)),
                  300, True)

    assert waehlen([hit], dienst(app)._anbieter()) is None
    assert sum(request.url.path == '/v1/chat/completions' for request in requests) == 1


@pytest.mark.parametrize('reason', ['pausiert', 'speicherdruck'])
def test_queued_world_request_revocation_prevents_model_transport(monkeypatch, reason):
    from icarus_memory import hintergrund, model_roles
    from tests.test_local_model_guard import provider, wire

    queued = threading.Event()
    modes = []

    class Gate(hintergrund.ModellAmpel):
        def aufruf(self):
            modes.append(hintergrund.im_hintergrund())
            queued.set()
            return super().aufruf()

    gate = Gate()
    monkeypatch.setattr(hintergrund, 'AMPEL', gate)
    control = SimpleNamespace(reason=None)
    control.sperre = lambda: control.reason
    original = provider()
    app = SimpleNamespace(state=SimpleNamespace(
        episodes=object(), hintergrund=control,
        settings=SimpleNamespace(schedule=SimpleNamespace(enabled=True, with_model=True)),
    ))
    monkeypatch.setattr(model_roles, 'rollen_von', lambda app: SimpleNamespace(provider=lambda role: original))
    requests, _, _ = wire(monkeypatch, chat='{"betrifft":false}')
    hit = Treffer(Eintrag('news', 'Klinikum baut aus', 'Klinikum', 'https://news.example/1', None),
                  'feed', 'Fachzeitung', Sache('organisation:klinikum', 'organisation', 'Klinikum', ('Klinikum',)),
                  300, True)
    selected = dienst(app)._anbieter()
    results, errors = [], []

    def run():
        try:
            results.append(waehlen([hit], selected))
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=run, daemon=True)
    with gate.hintergrund():
        worker.start()
        assert queued.wait(2), 'The actual adapter must reach the occupied model gate'
        assert not any(r.url.path == '/v1/chat/completions' for r in requests)
        control.reason = reason
    worker.join(3)
    assert not worker.is_alive()
    assert errors == []
    assert not any(r.url.path == '/v1/chat/completions' for r in requests)
    assert results == [hit]
    assert modes == [True]
    assert gate.belegt() == {'vorne': 0, 'hinten': 0}


@pytest.mark.parametrize('reason', [None, 'pausiert', 'speicherdruck'])
def test_world_permission_is_checked_after_model_preparation_before_transport(monkeypatch, reason):
    from icarus_memory import hintergrund, model_roles, ollama_memory
    from tests.test_local_model_guard import provider, wire

    gate = hintergrund.ModellAmpel()
    monkeypatch.setattr(hintergrund, 'AMPEL', gate)
    control = SimpleNamespace(reason=None)
    control.sperre = lambda: control.reason
    original = provider()
    app = SimpleNamespace(state=SimpleNamespace(
        episodes=object(), hintergrund=control,
        settings=SimpleNamespace(schedule=SimpleNamespace(enabled=True, with_model=True)),
    ))
    monkeypatch.setattr(model_roles, 'rollen_von', lambda app: SimpleNamespace(provider=lambda role: original))
    requests, _, _ = wire(monkeypatch, chat='{"betrifft":false}')
    occupied = []

    @contextmanager
    def prepare(provider):
        occupied.append(gate.belegt())
        control.reason = reason  # live permission can change while model memory is prepared
        yield

    monkeypatch.setattr(ollama_memory, 'managed_model', prepare)
    hit = Treffer(Eintrag('news', 'Klinikum baut aus', 'Klinikum', 'https://news.example/1', None),
                  'feed', 'Fachzeitung', Sache('organisation:klinikum', 'organisation', 'Klinikum', ('Klinikum',)),
                  300, True)
    result = waehlen([hit], dienst(app)._anbieter())
    assert sum(r.url.path == '/v1/chat/completions' for r in requests) == (1 if reason is None else 0)
    assert result is (None if reason is None else hit)
    assert occupied == [{'vorne': 0, 'hinten': 1}]
    assert gate.belegt() == {'vorne': 0, 'hinten': 0}
