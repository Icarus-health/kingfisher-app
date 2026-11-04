"""Kurzlebige Einmalwahl; Controller halten dabei ihren conversation_lock.

Der Browser erhält nur einen zufälligen Verweis und Titel. Auftrag, Anbieter
und Quellenstände kommen ausschließlich aus dem vorherigen Serveraufruf.
"""
from collections import OrderedDict
from copy import deepcopy
import json
import secrets
import time

from pydantic import BaseModel, ConfigDict, Field

from .procedures import ProcedureError


class ProcedureChoiceIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    token: str = Field(min_length=20, max_length=200)
    id: str = Field(min_length=1, max_length=200)


def provider_state(provider):
    result = {key:getattr(provider, key, None) for key in ('name','model','base_url','is_local')}
    try:
        result['permitted'] = bool(getattr(provider, '_verified_local_permitted', lambda: True)())
    except Exception:
        result['permitted'] = False
    return result


def chat_state(app):
    settings = app.state.settings
    return json.dumps({'provider':provider_state(app.state.agent.provider),
        'settings':{key:getattr(settings, key, None) for key in (
            'provider','model','endpoint','model_roles','routing_enabled','routing_profiles')}},
        sort_keys=True, default=str)


def _cache(app):
    if not hasattr(app.state, 'procedure_choices'):
        app.state.procedure_choices = OrderedDict()
    return app.state.procedure_choices


def offer(app, selection, *, scope, request, owners, state):
    options = [{'id':item['id'], 'label':item['title'], 'version':item['version'],
                'name':item['name']} for item in selection['choices']]
    options.append({'id':'core', 'label':'Diesmal ohne persönlichen Ablauf'})
    token = secrets.token_urlsafe(32)
    cache = _cache(app)
    cache[token] = {'scope':scope, 'request':request, 'owners':dict(owners),
        'state':deepcopy(state), 'options':options, 'created':time.monotonic(),
        'signature':selection['choice_signature']}
    while len(cache) > 64:
        cache.popitem(last=False)
    return {'token':token, 'options':options}


def take(app, choice, *, scope, owners, state, request=None, label=None):
    entry = _cache(app).pop(choice.token, None)
    option = next((item for item in entry['options'] if item['id'] == choice.id), None) if entry else None
    if (entry is None or option is None or entry['scope'] != scope
            or not provider_state(owners.get('provider'))['permitted']
            or not 0 <= time.monotonic() - entry['created'] <= 600
            or set(entry['owners']) != set(owners)
            or any(entry['owners'][key] is not value for key,value in owners.items())
            or entry['state'] != state
            or (request is not None and entry['request'] != request)
            or (label is not None and option['label'] != label)):
        raise ProcedureError('Diese Ablaufwahl ist nicht mehr aktuell. Bitte den Auftrag erneut stellen.')
    return entry['request'], {'id':choice.id, 'signature':entry['signature']}
