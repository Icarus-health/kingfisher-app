"""Authenticated preview/confirm/undo flow for the memory person view."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, StrictBool

from . import graph
from .entities import EntityError
from .identitaet import eigene_adressen
from .person_merges import preview


class Selection(BaseModel):
    member_ids: list[str] = Field(min_length=2, max_length=20)
    label: str = Field(min_length=1, max_length=500)


class Confirmation(Selection):
    preview_token: str = Field(min_length=1, max_length=64)
    confirmed: StrictBool


class UndoConfirmation(BaseModel):
    confirmed: StrictBool


def install_routes(app, guard):
    router = APIRouter(prefix='/api/v1/memory/person-merges', dependencies=guard)

    def prepare(body):
        raw = graph.build(episodes=app.state.episodes, workspace=app.state.workspace,
                          tasks=app.state.tasks, store=app.state.store,
                          knowledge=app.state.claims, group_people=False,
                          eigene=eigene_adressen(getattr(app.state, "settings", None)))
        active_ids = {member['id'] for record in app.state.claims.person_merges.list()
                      if not record['undone_at'] for member in record['members']}
        if active_ids.intersection(body.member_ids):
            raise EntityError('Eine Person ist bereits zusammengeführt. Bitte die Ansicht neu laden.')
        return preview(raw, body.member_ids, body.label)

    @router.get('')
    def list_merges():
        return {'merges': app.state.claims.person_merges.list()}

    @router.post('/preview')
    def preview_merge(body: Selection):
        try:
            return prepare(body)
        except EntityError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post('', status_code=201)
    def confirm_merge(body: Confirmation):
        try:
            with app.state.conversation_lock:
                proposed = prepare(body)
                if proposed['preview_token'] != body.preview_token:
                    raise EntityError('Die Akten haben sich geändert. Bitte eine neue Vorschau öffnen.')
                return app.state.claims.person_merges.confirm(proposed, confirmed=body.confirmed)
        except EntityError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post('/{merge_id}/undo')
    def undo_merge(merge_id: str, body: UndoConfirmation):
        try:
            with app.state.conversation_lock:
                return app.state.claims.person_merges.undo(merge_id, confirmed=body.confirmed)
        except EntityError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    app.include_router(router)
