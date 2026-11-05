"""Guarded local composer drafts, independent of the conversation/LLM lock."""
from __future__ import annotations

import uuid

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from .conversations import DraftConflict


class DraftIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: StrictStr = Field(max_length=20000)
    expected_revision: StrictInt = Field(ge=0, le=2**63 - 2)
    instance_id: StrictStr = Field(pattern=r'^[a-f0-9]{32}$')


class BindIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    instance_id: StrictStr = Field(pattern=r'^[a-f0-9]{32}$')
    expected_revision: StrictInt = Field(ge=0, le=2**63 - 2)


class HandoffIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    instance_id: StrictStr = Field(pattern=r'^[a-f0-9]{32}$')
    handoff_id: StrictStr = Field(pattern=r'^h-[a-f0-9]{32}$')


def register(app, guard) -> None:
    # Fresh per app registration. Never derive this from keys, configuration or
    # database contents, and never persist it alongside the durable draft text.
    instance_id = uuid.uuid4().hex
    app.state.conversation_draft_instance_id = instance_id

    def check_instance(value):
        if value != instance_id:
            raise HTTPException(409, detail={'code': 'draft_instance_changed',
                'message': 'Die App wurde neu gestartet. Bitte den gespeicherten Entwurf erneut laden.'})

    def invoke(action):
        try:
            return {**action(), 'instance_id': instance_id}
        except DraftConflict as error:
            raise HTTPException(409, detail={'code': 'draft_conflict',
                'message': 'Der Entwurf wurde inzwischen geändert. Bitte den gespeicherten Stand erneut laden.'}) from error
        except KeyError as error:
            raise HTTPException(404, detail='Gespräch nicht gefunden.') from error
        except ValueError as error:
            raise HTTPException(422, detail='Ungültige Entwurfsangaben.') from error

    @app.get('/api/v1/conversation-drafts/{composer_id}', dependencies=guard)
    def draft_get(composer_id: str):
        return invoke(lambda: app.state.conversations.draft_get(composer_id))

    @app.put('/api/v1/conversation-drafts/{composer_id}', dependencies=guard)
    def draft_put(composer_id: str, body: DraftIn):
        # Check before any Store access, including an otherwise idempotent retry.
        check_instance(body.instance_id)
        return invoke(lambda: app.state.conversations.draft_put(composer_id, body.text, body.expected_revision))

    @app.post('/api/v1/conversation-drafts/new/bind', dependencies=guard)
    def draft_bind(body: BindIn):
        check_instance(body.instance_id)
        return invoke(lambda: app.state.conversations.draft_bind(body.expected_revision))

    @app.post('/api/v1/conversation-drafts/{conversation_id}/handoff/start', dependencies=guard)
    def handoff_start(conversation_id: str, body: HandoffIn):
        check_instance(body.instance_id)
        return invoke(lambda: app.state.conversations.draft_handoff_start(conversation_id, body.handoff_id))

    @app.post('/api/v1/conversation-drafts/{conversation_id}/handoff/finish', dependencies=guard)
    def handoff_finish(conversation_id: str, body: HandoffIn):
        check_instance(body.instance_id)
        return invoke(lambda: app.state.conversations.draft_handoff_finish(conversation_id, body.handoff_id))
