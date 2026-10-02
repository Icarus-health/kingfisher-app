"""Local model qualification and scoped handoffs over the existing agent boundary."""
from datetime import datetime, timezone, timedelta
import re
import time
import httpx
from fastapi import HTTPException
from pydantic import BaseModel
from . import config
from .agent import Agent
from .model_routing import Candidate, RESEARCH_TOOLS
from .providers import OpenAICompatible, ProviderError
from .routing_provider import RoutedProvider


class RoutingSwitch(BaseModel):
    enabled: bool


def _current_profiles(app, provider=None):
    """Return persisted profiles with verification valid for the given provider (default: the live one)."""
    provider = provider if provider is not None else app.state.agent.provider
    endpoint = getattr(provider, 'base_url', '').rstrip('/') if provider is not None else ''
    now = datetime.now(timezone.utc)
    profiles = []
    for raw in app.state.settings.routing_profiles:
        profile = dict(raw)
        profile_endpoint = profile.get('endpoint', '')
        valid = profile.get('verified') is True and isinstance(profile_endpoint, str) and profile_endpoint.rstrip('/') == endpoint
        try:
            checked = datetime.fromisoformat(str(profile.get('checked_at', '')))
            if checked.tzinfo is None:
                checked = checked.replace(tzinfo=timezone.utc)
            valid = valid and timedelta(0) <= now - checked <= timedelta(days=14)
        except (TypeError, ValueError):
            valid = False
        profile['verified'] = valid
        profiles.append(profile)
    return profiles


def qualify_local_models(provider, nur=None):
    """Prüft lokale Modelle auf Werkzeugfähigkeit; mit `nur` allein dieses eine Modell."""
    if provider is None or not provider.is_local or not isinstance(provider, OpenAICompatible):
        raise ValueError('Bitte zuerst ein lokales Ollama-Modell verbinden.')
    base = provider.base_url.rstrip('/')
    root = base[:-3] if base.endswith('/v1') else base
    with httpx.Client(timeout=10, follow_redirects=False) as client:
        response = client.get(root + '/api/tags')
        response.raise_for_status()
        models = response.json().get('models', [])
        if nur:
            models = [m for m in models if m.get('name') in {nur, nur + ':latest'}]
        eligible = []
        for item in sorted(models, key=lambda x: (x.get('size', 0), x.get('name', '')))[:20]:
            name = item.get('name', '')
            if not isinstance(name, str) or not name:
                continue
            shown = client.post(root + '/api/show', json={'model': name})
            shown.raise_for_status()
            caps = shown.json().get('capabilities', [])
            if 'completion' in caps and 'tools' in caps:
                eligible.append(item)
        eligible.sort(key=lambda x: (x['name'] != provider.model, x.get('size', 0)))
        results = []
        for item in eligible[:3]:
            model = OpenAICompatible(item['name'], base_url=base,
                trusted_local_hosts=[httpx.URL(base).host])
            started = time.monotonic()
            try:
                reply = model.complete([
                    {'role': 'system', 'content': 'Use the supplied readiness tool with value ready. Do not answer with prose.'},
                    {'role': 'user', 'content': 'Call readiness(value="ready").'}],
                    [{'name': 'readiness', 'description': 'Local readiness check; no action.',
                     'parameters': {'type': 'object', 'properties': {'value': {'type': 'string', 'enum': ['ready']}}, 'required': ['value']}}])
                ok = (len(reply.tool_calls) == 1
                      and reply.tool_calls[0].name == 'readiness'
                      and reply.tool_calls[0].arguments == {'value': 'ready'})
            except ProviderError:
                ok = False
            results.append({'model': item['name'], 'endpoint': base,
                'capabilities': ['text', 'tools'] if ok else [], 'verified': ok,
                'latency_ms': int((time.monotonic() - started) * 1000),
                'size_bytes': int(item.get('size', 0)),
                'checked_at': datetime.now(timezone.utc).isoformat()})
    return results


def scoped_agent(app, message):
    base = app.state.agent
    if not app.state.settings.routing_enabled:
        return base, None
    provider = base.provider
    if provider is None or not provider.is_local or not isinstance(provider, OpenAICompatible):
        raise ProviderError('Die lokale Modellauswahl benötigt ein verbundenes lokales Modell.')
    role = 'research' if re.match(r'^\s*(recherchiere|recherchier|recherchiere bitte|research)\b', message, re.I) else 'chief_of_staff'
    pairs = []
    for profile in _current_profiles(app):
        try:
            checked = datetime.fromisoformat(profile['checked_at'])
            age = datetime.now(timezone.utc) - checked
            if not profile['verified'] or profile['endpoint'] != provider.base_url or not timedelta(0) <= age <= timedelta(days=14):
                continue
            candidate = Candidate(profile['model'], profile['model'], True,
                frozenset(profile['capabilities']), 0, profile['size_bytes'], profile['latency_ms'])
            local = OpenAICompatible(candidate.model, base_url=provider.base_url,
                trusted_local_hosts=[httpx.URL(provider.base_url).host])
            pairs.append((candidate, local))
        except (KeyError, TypeError, ValueError):
            continue
    if not pairs:
        raise ProviderError('Keine aktuell geprüften lokalen Modelle verfügbar. Bitte die Modellprüfung wiederholen.')
    routed = RoutedProvider(provider, pairs, task=role, local_only=True, audit=app.state.audit)
    allowed = RESEARCH_TOOLS if role == 'research' else frozenset(base.tool_names)
    agent = base.scoped(routed, allowed)
    return agent, {'from': 'chief_of_staff', 'to': role,
        'reason': 'Geprüfte lokale Werkzeugfähigkeit; bevorzugt kleineres Modell, dann gemessene Prüfzeit.',
        'allowed_tools': agent.tool_names, 'history_shared': role != 'research', 'trace': routed.trace}


def register_routing_routes(app, guard, data_dir):
    @app.get('/api/v1/routing', dependencies=guard)
    def status():
        profiles = _current_profiles(app)
        enabled = app.state.settings.routing_enabled and any(p['verified'] for p in profiles)
        return {'enabled': app.state.settings.routing_enabled, 'ready': enabled, 'profiles': profiles}

    @app.post('/api/v1/routing/verify', dependencies=guard)
    def verify():
        # Only model-readiness text is sent. No personal context or tools execute.
        provider_before = app.state.agent.provider
        before_signature = (
            getattr(provider_before, 'base_url', ''), getattr(provider_before, 'model', ''),
            getattr(app.state.settings, 'provider', ''), getattr(app.state.settings, 'model', ''),
            getattr(app.state.settings, 'endpoint', ''),
        )
        try:
            profiles = qualify_local_models(provider_before)
        except (ValueError, httpx.HTTPError) as exc:
            raise HTTPException(422, 'Lokale Modelle konnten nicht geprüft werden. Bitte Ollama prüfen.') from exc
        with app.state.conversation_lock:
            provider_after = app.state.agent.provider
            after_signature = (
                getattr(provider_after, 'base_url', ''), getattr(provider_after, 'model', ''),
                getattr(app.state.settings, 'provider', ''), getattr(app.state.settings, 'model', ''),
                getattr(app.state.settings, 'endpoint', ''),
            )
            if before_signature != after_signature:
                raise HTTPException(409, 'Die Modellkonfiguration wurde während der Prüfung geändert. Bitte erneut prüfen.')
            app.state.settings.routing_profiles = profiles
            config.save(data_dir(), app.state.settings)
        return {'profiles': profiles, 'enabled': app.state.settings.routing_enabled,
                'ready': any(p.get('verified') for p in profiles)}

    @app.post('/api/v1/routing', dependencies=guard)
    def configure(body: RoutingSwitch):
        with app.state.conversation_lock:
            profiles = _current_profiles(app)
            if body.enabled and not any(p.get('verified') for p in profiles):
                raise HTTPException(422, 'Bitte zuerst lokale Modelle prüfen.')
            app.state.settings.routing_enabled = body.enabled
            config.save(data_dir(), app.state.settings)
        return status()
