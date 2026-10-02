"""Read and generate local person overviews without modifying original memory."""
import threading
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, StrictBool
from .person_digest_context import collect
from .person_digests import fingerprint, messages, validate, output_schema, choose_provider
from .model_roles import hintergrund_anbieter


class GenerateIn(BaseModel):
    refresh: StrictBool = False


def install_routes(app, guard):
    router = APIRouter(prefix='/api/v1/memory/person-digests', dependencies=guard)
    generation_lock = threading.Lock()

    def available(provider):
        return getattr(provider, 'is_local', False) and callable(getattr(provider, 'complete_json', None))

    def state(person_ref, context, provider):
        cached = app.state.claims.person_digests.cached(person_ref)
        current = bool(cached and cached[0] == fingerprint(context, provider))
        status = ('no_sources' if not context['source_count'] else 'unavailable' if not available(provider)
                  else 'ready' if current else 'stale' if cached else 'missing')
        return {'status': status, 'digest': cached[1] if status == 'ready' else None,
                **{key: context[key] for key in ('source_count', 'total_source_count', 'truncated')},
                'model': getattr(provider, 'model', '')}

    @router.get('/{person_ref}')
    def read(person_ref: str):
        return state(person_ref, collect(app, person_ref), choose_provider(app))

    @router.post('/{person_ref}')
    def generate(person_ref: str, body: GenerateIn = GenerateIn()):
        if not generation_lock.acquire(blocking=False):
            raise HTTPException(409, 'Es wird bereits ein KI-Überblick erstellt. Bitte kurz warten.')
        try:
            base_before = hintergrund_anbieter(app)
            provider = choose_provider(app)
            if not available(provider):
                raise HTTPException(503, 'Bitte ein lokales Modell verbinden. Es werden keine Daten an einen Cloud-Anbieter gesendet.')
            context = collect(app, person_ref)
            before = fingerprint(context, provider)
            current = state(person_ref, context, provider)
            if current['status'] == 'no_sources' or (current['status'] == 'ready' and not body.refresh):
                return current
            try:
                reply = provider.complete_json(messages(context), max_tokens=1100, schema=output_schema(context))
                digest = validate(reply, context, getattr(provider, 'model', ''))
            except Exception as exc:
                raise HTTPException(503, 'Das lokale Modell hat keinen ausreichend belegten Überblick geliefert. Bitte erneut versuchen.') from exc
            latest = collect(app, person_ref)
            if hintergrund_anbieter(app) is not base_before or before != fingerprint(latest, choose_provider(app)):
                raise HTTPException(409, 'Quellen oder Modell haben sich geändert. Bitte den Überblick neu erstellen.')
            app.state.claims.person_digests.save(person_ref, before, digest)
            return state(person_ref, latest, provider)
        finally:
            generation_lock.release()

    app.include_router(router)
