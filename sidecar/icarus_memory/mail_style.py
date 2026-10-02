"""Explicit writing examples and confirmed style preferences in existing stores.

No model training, sent-folder scan, automatic confirmation or person merging.
Contact scope is the exact reply address plus the sending account.
"""
from __future__ import annotations

import hashlib
import json
import re
from email.utils import getaddresses
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

from .episodes import AUSGEBLENDETE_ZUSTAENDE, EpisodeKind
from .model import Kind, Provenance, Sensitivity, SourceType

DOMAIN = 'mail_style'


class Rules(BaseModel):
    address: Literal['default', 'du', 'sie'] = 'default'
    length: Literal['default', 'short', 'detailed'] = 'default'
    emoji: Literal['default', 'yes', 'no'] = 'default'


class ProfileIn(BaseModel):
    scope: Literal['global', 'contact']
    rules: Rules
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)


class ExampleIn(BaseModel):
    text: str = Field(min_length=10, max_length=5000)
    original_suggestion: str | None = Field(default=None, max_length=5000)
    own_text_confirmed: Literal[True]


def contact(message):
    addresses = getaddresses([message.reply_to or message.sender])
    if len(addresses) != 1 or not re.fullmatch(r'[^\s@,<>]+@[^\s@,<>]+\.[^\s@,<>]+', addresses[0][1]):
        raise HTTPException(422, 'Keine eindeutige Kontaktadresse für das Stilgedächtnis.')
    address = addresses[0][1].casefold()
    key = hashlib.sha256(json.dumps([message.account_id, address]).encode()).hexdigest()
    return key, address


def _examples(app, key):
    return [e for e in app.state.episodes.all_episodes(limit=-1)
            if f'mail-style:{key}' in (e.tags or [])
            and e.state not in AUSGEBLENDETE_ZUSTAENDE]


def _profiles(app, key):
    result = {'global': None, 'contact': None}
    if not hasattr(app.state, 'store') or not hasattr(app.state, 'episodes'):
        return result
    for a in app.state.store.usable():
        data = a.structured or {}
        if data.get('domain') != DOMAIN or data.get('scope_key') not in {'global', key}:
            continue
        valid = True
        for eid in data.get('evidence_ids', []):
            try:
                e = app.state.episodes.get(eid)
                if e.state in AUSGEBLENDETE_ZUSTAENDE:
                    valid = False
            except Exception:
                valid = False
        if valid:
            scope = 'global' if data['scope_key'] == 'global' else 'contact'
            result[scope] = {'id': a.id, 'rules': data['rules'], 'evidence_ids': data.get('evidence_ids', [])}
    return result


def effective_style(app, message):
    try:
        key, _ = contact(message)
    except HTTPException:
        return {}
    profiles = _profiles(app, key)
    rules = {}
    for scope in ['global', 'contact']:
        if profiles[scope]:
            rules.update({k: v for k, v in profiles[scope]['rules'].items() if v != 'default'})
    return rules


def _proposal(examples):
    # Conservative repeatable observations, never free-text instructions from mail.
    unique = {re.sub(r'\s+', ' ', e.body).strip(): e for e in examples}
    sample = list(unique.values())[-20:]
    if len(sample) < 3:
        return None
    rules = Rules().model_dump()
    texts = [e.body for e in sample]
    informal = [bool(re.search(r'\b(du|dir|dich|dein\w*)\b', t, re.I)) for t in texts]
    formal = [bool(re.search(r'\b(Sie|Ihnen|Ihr\w*)\b', t)) for t in texts]
    if all(informal) and not any(formal):
        rules['address'] = 'du'
    elif all(formal) and not any(informal):
        rules['address'] = 'sie'
    if all(len(t.split()) <= 80 for t in texts):
        rules['length'] = 'short'
    elif all(len(t.split()) >= 150 for t in texts):
        rules['length'] = 'detailed'
    emoji = [bool(re.search('[\U0001F300-\U0001FAFF\u2600-\u27BF]', t)) for t in texts]
    if all(emoji):
        rules['emoji'] = 'yes'
    elif not any(emoji):
        rules['emoji'] = 'no'
    if all(v == 'default' for v in rules.values()):
        return None
    return {'rules': rules, 'evidence_ids': [e.id for e in sample]}


def register_mail_style(app, guard):
    def resolve(uid):
        mail = app.state.mail
        try:
            message = mail.message(uid)
        except Exception as exc:
            raise HTTPException(404, 'Mail nicht verfügbar.') from exc
        if message.uid != uid or app.state.mail is not mail:
            raise HTTPException(409, 'Mailkonto wurde geändert.')
        return mail, message, contact(message)

    def ensure_current(mail, message=None):
        if message is not None:
            from .mail_reply_suggestions import _fingerprint
            try:
                latest = mail.message(message.uid)
            except Exception as exc:
                raise HTTPException(409, "Die ursprüngliche Mail ist nicht mehr verfügbar.") from exc
            if _fingerprint(latest) != _fingerprint(message):
                raise HTTPException(409, "Die Mail wurde geändert. Bitte neu laden.")
        if app.state.mail is not mail:
            raise HTTPException(409, 'Mailkonto wurde geändert.')

    def state(key, address):
        examples = _examples(app, key)
        return {'contact': address, 'profiles': _profiles(app, key),
                'examples': [{'id': e.id, 'text': e.body, 'created_at': e.reference_time().isoformat()} for e in examples],
                'proposal': _proposal(examples)}

    @app.get('/api/v1/messages/{uid}/style', dependencies=guard)
    def get_style(uid: str):
        mail, _, (key, address) = resolve(uid)
        with app.state.conversation_lock:
            ensure_current(mail)
            return state(key, address)

    @app.post('/api/v1/messages/{uid}/style/examples', dependencies=guard)
    def add_example(uid: str, body: ExampleIn):
        mail, message, (key, address) = resolve(uid)
        text = body.text.strip()
        normalize = lambda s: re.sub(r'\s+', ' ', s).strip()
        if len(text) < 10 or (body.original_suggestion and normalize(text) == normalize(body.original_suggestion)):
            raise HTTPException(422, 'Unveränderte KI-Vorschläge sind keine eigenen Schreibbelege.')
        with app.state.conversation_lock:
            ensure_current(mail, message)
            if len(_examples(app, key)) >= 20:
                raise HTTPException(409, 'Bitte zuerst einen der 20 Schreibbelege zurücknehmen.')
            digest = hashlib.sha256(normalize(text).encode()).hexdigest()
            source = f'mail-style:{key}:{digest}'
            app.state.episodes.record(EpisodeKind.MESSAGE, 'Eigener Schreibbeleg', text,
                Provenance(source_type=SourceType.USER_STATED, source_ref=source, verbatim=text),
                tags=[f'mail-style:{key}'], source_key=source)
            return state(key, address)

    @app.put('/api/v1/messages/{uid}/style', dependencies=guard)
    def save_style(uid: str, body: ProfileIn):
        mail, message, (key, address) = resolve(uid)
        with app.state.conversation_lock:
            ensure_current(mail, message)
            ids = list(dict.fromkeys(body.evidence_ids))
            examples = _examples(app, key)
            if ids:
                proposal = _proposal(examples)
                if not proposal or set(ids) != set(proposal['evidence_ids']) or body.rules.model_dump() != proposal['rules']:
                    raise HTTPException(409, 'Der Lernvorschlag ist nicht mehr aktuell. Bitte neu laden.')
            scope_key = 'global' if body.scope == 'global' else key
            prior = [a.id for a in app.state.store.usable()
                     if (a.structured or {}).get('domain') == DOMAIN and a.structured.get('scope_key') == scope_key]
            label = 'allgemein' if body.scope == 'global' else f'{address} (Konto {message.account_id})'
            app.state.store.record(f'Bestätigter E-Mail-Schreibstil ({label}): {json.dumps(body.rules.model_dump(), ensure_ascii=False)}',
                Kind.PREFERENCE, Provenance(source_type=SourceType.USER_STATED, source_ref='ui:mail-style'),
                sensitivity=Sensitivity.SENSITIVE, supersedes=prior,
                structured={'domain': DOMAIN, 'scope_key': scope_key, 'rules': body.rules.model_dump(), 'evidence_ids': ids})
            return state(key, address)

    @app.delete('/api/v1/messages/{uid}/style/examples/{example_id}', dependencies=guard)
    def remove_example(uid: str, example_id: str):
        mail, message, (key, address) = resolve(uid)
        with app.state.conversation_lock:
            ensure_current(mail, message)
            if example_id not in {e.id for e in _examples(app, key)}:
                raise HTTPException(404, 'Schreibbeleg nicht gefunden.')
            app.state.episodes.ignore(example_id)
            # Retract derived preferences too, so general recall cannot reuse them.
            for a in app.state.store.usable():
                if (a.structured or {}).get('domain') == DOMAIN and example_id in a.structured.get('evidence_ids', []):
                    app.state.store.retract(a.id)
            return state(key, address)

    @app.delete('/api/v1/messages/{uid}/style/{scope}', dependencies=guard)
    def reset_style(uid: str, scope: Literal['global', 'contact']):
        mail, message, (key, address) = resolve(uid)
        with app.state.conversation_lock:
            ensure_current(mail, message)
            scope_key = 'global' if scope == 'global' else key
            for a in app.state.store.usable():
                if (a.structured or {}).get('domain') == DOMAIN and a.structured.get('scope_key') == scope_key:
                    app.state.store.retract(a.id)
            return state(key, address)
