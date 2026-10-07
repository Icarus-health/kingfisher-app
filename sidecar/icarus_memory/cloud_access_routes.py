"""Write-only regional credentials. Preparation never calls or enables a model."""
import os
from copy import deepcopy

from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from . import config
from .secrets import KeychainError


PROVIDERS = {
    'mistral': ('Mistral', 'MISTRAL_API_KEY', 'https://api.eu.mistral.ai/v1'),
    'openrouter': ('OpenRouter', 'OPENROUTER_API_KEY', 'https://eu.openrouter.ai/api/v1'),
}


class CloudAccessIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    api_key: SecretStr | None = None
    model: str = Field(default='', pattern=r'^[A-Za-z0-9._:/-]{0,128}$')



def register(app, guard, data_dir, rebuild):
    def store():
        keychain = getattr(app.state, 'keychain', None)
        if keychain is None or not keychain.available:
            raise HTTPException(409, 'Der verschlüsselte Schlüsselspeicher ist nicht verfügbar. Bitte die App-Einrichtung prüfen.')
        return keychain

    def status():
        keychain = getattr(app.state, 'keychain', None)
        return {'storage_available': bool(keychain and keychain.available),
                'providers': [{'id': identifier, 'label': label, 'endpoint': endpoint,
                               'key_present': bool(os.environ.get(name)),
                               'model': app.state.settings.cloud_models.get(identifier, '')}
                              for identifier, (label, name, endpoint) in PROVIDERS.items()],
                'notice': 'Speichern bereitet den Zugang vor. Es aktiviert keine Cloud-Nutzung und überträgt keine Quellen. Der Zugang ist noch nicht getestet.'}

    def pause_agent():
        # An existing Agent captures its answer provider. Clear that reference
        # before rebuilding, so even an interrupted rebuild cannot reuse consent.
        agent = getattr(app.state, 'agent', None)
        if agent is not None:
            agent._provider = None
            agent._frage_anbieter = lambda: None
        app.state.rollen = None

    def change(identifier, body=None):
        if identifier not in PROVIDERS:
            raise HTTPException(404, 'Unbekannter Cloudanbieter.')
        if body and body.api_key is not None:
            raw = body.api_key.get_secret_value()
            if not 1 <= len(raw) <= 4096 or any(ord(c) < 33 or ord(c) > 126 for c in raw):
                raise HTTPException(422, 'Bitte einen gültigen API-Schlüssel ohne Leerzeichen eingeben.')
        keychain = store()
        name = PROVIDERS[identifier][1]
        settings = app.state.settings
        with app.state.conversation_lock:
            try:
                old_key = keychain.get(name)
            except KeychainError:
                raise HTTPException(409, 'Der Schlüsselspeicher konnte nicht gelesen werden.') from None
            old_env = os.environ.get(name)
            old_models, old_roles = deepcopy(settings.cloud_models), deepcopy(settings.model_roles)
            affected_roles = any(value.get('anbieter') == identifier for value in old_roles.values())
            new_key = body.api_key.get_secret_value() if body and body.api_key else old_env or old_key
            if body and not new_key:
                raise HTTPException(422, 'Bitte zuerst einen API-Schlüssel eingeben.')
            try:
                if body:
                    keychain.set(name, new_key)
                    settings.cloud_models[identifier] = body.model
                else:
                    keychain.delete(name)
                    settings.cloud_models.pop(identifier, None)
                changed = not body or new_key != old_env or body.model != old_models.get(identifier, '')
                if changed:
                    # Changing credentials or the prepared model requires fresh role consent.
                    settings.model_roles = {role: ({'local_only': True} if value.get('anbieter') == identifier else value)
                                            for role, value in settings.model_roles.items()}
                config.save(data_dir(), settings)
            except (KeychainError, OSError, ValueError):
                settings.cloud_models, settings.model_roles = old_models, old_roles
                try:
                    if old_key is None:
                        keychain.delete(name)
                    else:
                        keychain.set(name, old_key)
                except KeychainError:
                    # Fail closed if the storage itself stopped accepting writes.
                    os.environ.pop(name, None)
                    settings.model_roles = {role: ({'local_only': True} if value.get('anbieter') == identifier else value)
                                            for role, value in settings.model_roles.items()}
                    if affected_roles:
                        pause_agent()
                    raise HTTPException(409, 'Speichern fehlgeschlagen. Der Zugang ist für diesen Programmlauf deaktiviert; bitte vor erneuter Nutzung prüfen.') from None
                raise HTTPException(409, 'Der Zugang konnte nicht gespeichert werden; die vorherigen Einstellungen bleiben erhalten.') from None
            if body:
                os.environ[name] = new_key
            else:
                os.environ.pop(name, None)
            if changed and affected_roles:
                pause_agent()
                try:
                    rebuild()
                except Exception:
                    pause_agent()
                    raise HTTPException(409, 'Die Zugangsdaten wurden geändert, aber die KI konnte nicht neu eingerichtet werden. Fragen sind bis zum Neustart pausiert.') from None
        return status()

    @app.get('/api/v1/models/cloud-access', dependencies=guard)
    def get_access():
        with app.state.conversation_lock:
            return status()

    @app.put('/api/v1/models/cloud-access/{identifier}', dependencies=guard)
    async def put_access(identifier: str, request: Request):
        # Never echo a malformed credential through FastAPI's validation-error input field.
        raw = await request.body()
        if len(raw) > 16384:
            raise HTTPException(422, 'Die Eingabe ist zu groß.')
        try:
            body = CloudAccessIn.model_validate_json(raw)
        except ValidationError:
            raise HTTPException(422, 'Bitte API-Schlüssel und Modellname prüfen.') from None
        return await run_in_threadpool(change, identifier, body)

    @app.delete('/api/v1/models/cloud-access/{identifier}', dependencies=guard)
    def delete_access(identifier: str):
        return change(identifier)
