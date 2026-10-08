"""Product binding for durable local search, separate from diagnostic adapters."""
import json
import os
from contextlib import nullcontext


def enabled():
    return os.environ.get('ICARUS_MEMORY_SEMANTIC') == '1'


def bind(app, agent, *, ampel=None):
    from .working_memory_semantic_service import SemanticService
    previous = getattr(app.state, 'semantic_search', None)
    if previous is not None:
        previous.close()

    def configuration():
        # Pure snapshot: role provider() can probe Ollama and must only run
        # within the service model gate, never during coverage/permission reads.
        standard = getattr(app.state, 'standard_provider', agent.provider)
        return (id(app.state.agent), id(standard), getattr(standard, 'base_url', None),
                json.dumps(app.state.settings.model_roles, sort_keys=True),
                os.environ.get('ICARUS_TRUSTED_LOCAL_MODEL_HOSTS', ''), enabled())

    def factory():
        from .model_roles import rollen_von, ollama_wurzel
        from .local_embeddings import LocalEmbedder
        roles = rollen_von(app)
        provider = roles.provider('einbettung')
        if (getattr(provider, 'is_local', False) is not True
                or roles.cloud_modell_im_weg('einbettung')):
            raise ValueError('local embedding role unavailable')
        trusted = tuple(host.strip() for host in os.environ.get(
            'ICARUS_TRUSTED_LOCAL_MODEL_HOSTS', '').split(',') if host.strip())
        return LocalEmbedder(base_url=ollama_wurzel(getattr(provider, 'base_url', 'http://127.0.0.1:11434/v1')),
                             trusted_local_hosts=trusted, model=roles.einbettung_modell(),
                             timeout=30, keep_alive='15s')

    service = SemanticService(app.state.episodes, factory, configuration=configuration,
                              enabled=enabled, permission_lock=app.state.conversation_lock, ampel=ampel)
    app.state.semantic_search = service
    # Explicit None blocks the diagnostic fallback in the disabled product.
    agent._working_memory_search = service if enabled() else None
    return service


def search(app):
    return getattr(app.state, 'semantic_search', None) if enabled() else None


def request(app):
    service = search(app)
    return service.request() if service is not None else nullcontext()


def coverage(app):
    from .model_roles import einbettung_modell, lese_wahlen
    from .hintergrund import GRUND_TEXT
    service = getattr(app.state, 'semantic_search', None)
    status = service.coverage() if service is not None else {
        'status': 'unavailable' if enabled() else 'disabled', 'model_key': None,
        'identity_checked_at': None, 'total': None, 'indexed': None, 'pending': None,
        'failed': None, 'updated_at': None, 'source_pending': None}
    status['model_name'] = einbettung_modell(lese_wahlen(app.state.settings.model_roles))
    plan = app.state.settings.schedule
    scheduler = getattr(app.state, 'scheduler', None)
    control = getattr(scheduler, '_steuerung', None)
    reason = control.sperre() if control is not None else None
    status['pause_reason'] = (GRUND_TEXT.get(reason) if reason else None)
    if not plan.enabled or not plan.with_model:
        status['pause_reason'] = 'Die automatische Vorbereitung ist pausiert. Bereits vorbereitete Abschnitte bleiben durchsuchbar.'
    return status
