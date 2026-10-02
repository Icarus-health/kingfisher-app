"""Closed, explicit working preferences in the existing SelfModelStore.

No inferred personality, free-text policy, contact-name matching or new authority.
Current-turn instructions are ephemeral. Conflicting equally specific rules are
withheld instead of selecting whichever row happened to arrive last.
"""
import re
from .model import Kind, Provenance, SourceType, Status
from . import model
from .self_model_basis import eligible

DOMAIN = 'working_profile'
VALUES = {'answer_length': {'short': 'kurz', 'detailed': 'ausführlich'},
          'address': {'du': 'du', 'sie': 'Sie'},
          'emoji': {'yes': 'Emojis erlaubt', 'no': 'ohne Emojis'}}
TASKS = {'analysis': 'Analysen', 'mail': 'E-Mails', 'planning': 'Planung'}


def is_profile(assertion):
    return isinstance(getattr(assertion, 'structured', None), dict) and assertion.structured.get('domain') == DOMAIN


def validate(key, value, scope, scope_key):
    if (key not in VALUES or value not in VALUES[key] or scope not in {'global','task'}
            or (scope == 'global' and scope_key is not None)
            or (scope == 'task' and scope_key not in TASKS)):
        raise ValueError('Ungültige Arbeitsvorliebe oder unbekannter Bereich.')


def statement_for(key, value, scope, scope_key):
    label = {'answer_length':'Antwortlänge', 'address':'Anrede', 'emoji':'Emojis'}[key]
    area = 'Allgemein' if scope == 'global' else TASKS[scope_key]
    return f'Arbeitsvorliebe ({area}): {label} — {VALUES[key][value]}.'


def save(store, *, key, value, scope='global', scope_key=None, source_ref=None, expires_at=None):
    validate(key, value, scope, scope_key)
    previous = [a.id for a in store.usable() if is_profile(a) and
        all(a.structured.get(k) == v for k, v in [('key',key),('scope',scope),('scope_key',scope_key)])]
    return store.record(statement_for(key, value, scope, scope_key),
        Kind.PREFERENCE, Provenance(source_type=SourceType.USER_STATED, source_ref=source_ref),
        structured={'domain':DOMAIN, 'key':key, 'value':value, 'scope':scope, 'scope_key':scope_key},
        supersedes=previous, expires_at=expires_at)


_OVERRIDE = re.compile(r'^(?:bitte )?(?:heute|diesmal|für diese antwort) (?:bitte )?(?:antworte )?(kurz|ausführlich|detailliert)(?:\s*[:.!]|$)', re.I)


def task_for(message):
    # Only an explicit leading task sets scope; quoted document text cannot.
    text = _OVERRIDE.sub('', message.strip(), count=1).strip().casefold()
    if re.match(r'(?:bitte )?(?:schreib\w*|entwirf)\b[^.\n]*\b(?:mail|e-mail|antwort)\b', text): return 'mail'
    if re.match(r'(?:bitte )?(?:analysiere|analyse|architektur)\b', text): return 'analysis'
    if re.match(r'(?:bitte )?(?:plane|planung)\b', text): return 'planning'
    return None


def current_overrides(message):
    match = _OVERRIDE.match(message.strip())
    return {'answer_length':'short' if match[1].casefold() == 'kurz' else 'detailed'} if match else {}


def resolve(store, *, task=None, message='', at=None):
    at = at or model.now()
    groups = {}
    # A derived view must not materialize expiry on unrelated canonical rows.
    for assertion in store.export().assertions:
        if assertion.status is not Status.ACTIVE or not eligible(assertion, at):
            continue
        if (not is_profile(assertion) or assertion.kind is not Kind.PREFERENCE
                or assertion.derived_from or assertion.episode_support):
            continue
        if assertion.provenance.source_type not in {SourceType.USER_STATED, SourceType.MANUAL_CORRECTION}:
            continue
        data = assertion.structured
        try: validate(data.get('key'), data.get('value'), data.get('scope'), data.get('scope_key'))
        except (ValueError, TypeError): continue
        if assertion.statement != statement_for(data['key'], data['value'], data['scope'], data['scope_key']):
            continue
        if data['scope'] == 'task' and data['scope_key'] != task:
            continue
        groups.setdefault(data['key'], []).append(assertion)
    overrides = current_overrides(message)
    result = {'rules':{}, 'ids':[], 'conflicts':[], 'overrides':overrides}
    for key, choices in groups.items():
        if key in overrides:
            continue
        specific = [a for a in choices if a.structured['scope'] == 'task']
        choices = specific or choices
        values = {a.structured['value'] for a in choices}
        if len(values) > 1:
            result['conflicts'].append(key)
        else:
            result['rules'][key] = values.pop()
            result['ids'].append(min(a.id for a in choices))
    result['ids'].sort()
    result['conflicts'].sort()
    return result


def register(app, guard):
    from fastapi import HTTPException
    from pydantic import BaseModel, ConfigDict
    from typing import Literal
    from datetime import datetime

    class PreferenceIn(BaseModel):
        model_config = ConfigDict(extra='forbid')
        key: Literal['answer_length','address','emoji']
        value: str
        scope: Literal['global','task'] = 'global'
        scope_key: Literal['analysis','mail','planning'] | None = None
        expires_at: datetime | None = None

    @app.get('/api/v1/working-profile', dependencies=guard)
    def get_profile(task: str | None = None):
        if task is not None and task not in TASKS:
            raise HTTPException(422, 'Unbekannter Aufgabenbereich.')
        return {'effective': resolve(app.state.store, task=task),
                'items': [a.to_dict() for a in app.state.store.export().assertions if is_profile(a)]}

    @app.put('/api/v1/working-profile', dependencies=guard)
    def put_profile(body: PreferenceIn):
        with app.state.conversation_lock:
            try:
                saved = save(app.state.store, **body.model_dump(), source_ref='working-profile:explicit-user')
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
        return {'assertion': saved.to_dict()}

    @app.delete('/api/v1/working-profile/{identifier}', dependencies=guard)
    def retract_profile(identifier: str):
        with app.state.conversation_lock:
            try:
                item = app.state.store.get(identifier)
                if not is_profile(item): raise ValueError('Keine Arbeitsvorliebe.')
                result = app.state.store.retract(identifier)
            except (ValueError, KeyError):
                raise HTTPException(404, 'Arbeitsvorliebe nicht gefunden.') from None
        return {'assertion': result.to_dict()}
