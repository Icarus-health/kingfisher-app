from datetime import datetime, timezone
from fastapi.testclient import TestClient
from icarus_memory.server import create_app
from icarus_memory.providers import OpenAICompatible, Reply, ToolCall
from icarus_memory import config
from icarus_memory import routing_runtime


def test_scoped_research_handoff_persists_and_forbids_writes(monkeypatch, tmp_path):
    monkeypatch.setenv('ICARUS_PROVIDER', 'ollama')
    monkeypatch.setenv('ICARUS_BASE_URL', 'http://127.0.0.1:11434/v1')
    monkeypatch.setenv('ICARUS_MODEL', 'local-default')
    calls = []
    def complete(self, messages, tools):
        calls.append((self.model, messages, tools))
        if len(calls) == 1:
            return Reply(tool_calls=[ToolCall('denied', 'aufgabe_anlegen', {'title': 'Forbidden'})])
        return Reply(text='Result after denied action', model=self.model)
    monkeypatch.setattr(OpenAICompatible, 'complete', complete)
    app = create_app()
    with TestClient(app) as client:
        app.state.settings.routing_profiles = [{'model': 'small-local', 'endpoint': 'http://127.0.0.1:11434/v1',
            'capabilities': ['text', 'tools'], 'verified': True, 'latency_ms': 10, 'size_bytes': 100,
            'checked_at': datetime.now(timezone.utc).isoformat()}]
        app.state.settings.routing_enabled = True
        conv = client.post('/api/v1/conversations', json={'title': 'Routing'}).json()
        conversation_id = conv.get('id') or conv['conversation']['id']
        response = client.post(f'/api/v1/conversations/{conversation_id}/messages', json={'message': 'Recherchiere die nächsten Schritte'})
        assert response.status_code == 201, response.text
        answer = response.json()['messages'][-1]
        routing = answer['metadata']['context']['routing']
        assert routing['to'] == 'research'
        assert 'aufgabe_anlegen' not in routing['allowed_tools']
        assert routing['trace'][-1]['model'] == 'small-local'
        assert client.get(f'/api/v1/conversations/{conversation_id}').json()['messages'][-1]['metadata'] == answer['metadata']
        assert any(e['tool'] == 'agent_handoff' for e in app.state.audit.entries())
        assert all('aufgabe_anlegen' not in [t['name'] for t in tools] for _, _, tools in calls)


def test_routing_config_roundtrip():
    settings = config.Settings(routing_enabled=True, routing_profiles=[{'model': 'local'}], world_sources=[{'id': 'source'}])
    loaded = config.Settings.from_dict(settings.to_dict())
    assert loaded.routing_enabled and loaded.routing_profiles == settings.routing_profiles
    assert loaded.world_sources == settings.world_sources


def test_stale_and_malformed_profiles_are_not_enabled(monkeypatch):
    monkeypatch.setenv('ICARUS_PROVIDER', 'ollama')
    monkeypatch.setenv('ICARUS_BASE_URL', 'http://127.0.0.1:11434/v1')
    monkeypatch.setenv('ICARUS_MODEL', 'local-default')
    app = create_app()
    with TestClient(app) as client:
        app.state.settings.routing_enabled = True
        app.state.settings.routing_profiles = [
            {'model': 'old', 'endpoint': 'http://127.0.0.1:11434/v1', 'verified': True,
             'checked_at': '2020-01-01T00:00:00+00:00'},
            {'model': 'bad', 'endpoint': None, 'verified': 'true', 'checked_at': 'invalid'},
        ]
        status = client.get('/api/v1/routing').json()
        assert status['enabled'] is True
        assert status['ready'] is False
        assert all(profile['verified'] is False for profile in status['profiles'])
        response = client.post('/api/v1/routing', json={'enabled': True})
        assert response.status_code == 422


def test_verify_rejects_configuration_change_during_probe(monkeypatch):
    monkeypatch.setenv('ICARUS_PROVIDER', 'ollama')
    monkeypatch.setenv('ICARUS_BASE_URL', 'http://127.0.0.1:11434/v1')
    monkeypatch.setenv('ICARUS_MODEL', 'local-default')
    app = create_app()
    def probe(_provider):
        app.state.settings.model = 'changed-while-probing'
        return []
    monkeypatch.setattr(routing_runtime, 'qualify_local_models', probe)
    with TestClient(app) as client:
        response = client.post('/api/v1/routing/verify')
        assert response.status_code == 409


def test_chief_write_is_policy_held_until_approval(monkeypatch):
    monkeypatch.setenv('ICARUS_PROVIDER', 'ollama')
    monkeypatch.setenv('ICARUS_BASE_URL', 'http://127.0.0.1:11434/v1')
    monkeypatch.setenv('ICARUS_MODEL', 'local-default')
    calls = []
    def complete(self, messages, tools):
        if not calls:
            calls.append('requested')
            return Reply(tool_calls=[ToolCall('mail', 'mail_senden', {'to': 'a@b.test', 'subject': 'S', 'body': 'B'})])
        return Reply(text='Erledigt', model=self.model)
    monkeypatch.setattr(OpenAICompatible, 'complete', complete)
    app = create_app()
    app.state.settings.routing_profiles = [{'model': 'local-default', 'endpoint': 'http://127.0.0.1:11434/v1',
        'capabilities': ['text', 'tools'], 'verified': True, 'latency_ms': 10, 'size_bytes': 100,
        'checked_at': datetime.now(timezone.utc).isoformat()}]
    app.state.settings.routing_enabled = True
    sent = []
    app.state.agent._tools['mail_senden'].run = lambda **arguments: sent.append(arguments) or 'sent'
    with TestClient(app) as client:
        conv = client.post('/api/v1/conversations', json={'title': 'Chief'}).json()
        cid = conv.get('id') or conv['conversation']['id']
        response = client.post(f'/api/v1/conversations/{cid}/messages', json={'message': 'Sende die Mail'})
        assert response.status_code == 201
        payload = response.json()
        action = payload['action_requests'][0]
        assert action['state'] == 'pending'
        assert calls == ['requested']
        assert payload['messages'][-1]['metadata']['context']['routing']['to'] == 'chief_of_staff'
        assert sent == []
        resolved = client.post(f"/api/v1/conversations/{cid}/approvals/{action['id']}",
                               json={'granted': True, 'confirmation': action['confirmation_phrase']})
        assert resolved.status_code == 200
        assert sent == [{'to': 'a@b.test', 'subject': 'S', 'body': 'B'}]


def test_readiness_rejects_extra_tool_calls(monkeypatch):
    import httpx
    real_client = httpx.Client
    def respond(request):
        if request.url.path == '/api/tags':
            return httpx.Response(200, json={'models': [{'name': 'synthetic', 'size': 1}]})
        return httpx.Response(200, json={'capabilities': ['completion', 'tools']})
    monkeypatch.setattr(routing_runtime.httpx, 'Client', lambda **kwargs:
                        real_client(transport=httpx.MockTransport(respond)))
    response = Reply(tool_calls=[ToolCall('one', 'readiness', {'value': 'ready'}),
                                ToolCall('two', 'mail_senden', {'to': 'synthetic@example.invalid'})])
    monkeypatch.setattr(OpenAICompatible, 'complete', lambda *args: response)
    model = OpenAICompatible('synthetic', base_url='http://127.0.0.1:11434/v1')
    assert routing_runtime.qualify_local_models(model)[0]['verified'] is False
    response.tool_calls.pop()
    assert routing_runtime.qualify_local_models(model)[0]['verified'] is True
