"""Guarded preview and explicit execution routes for Google calendar actions."""
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .calendar_actions import ActionError, CalendarActions


class DraftIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: str
    source_id: str = Field(min_length=1, max_length=128)
    title: str | None = Field(default=None, max_length=500)
    start: str | None = Field(default=None, max_length=64)
    end: str | None = Field(default=None, max_length=64)
    event_id: str | None = Field(default=None, max_length=1024)
    send_updates: str


class ExecuteIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirmed: bool
    stand: str = Field(min_length=64, max_length=64)


def install_routes(app, guard, data_dir, rebuild=None, *, provider=None):
    actions = CalendarActions(data_dir() / 'calendar-actions.sqlite3',
        lambda: app.state.settings, app.state.google_oauth, provider)
    app.state.calendar_actions = actions

    @app.get('/api/v1/calendar-actions/sources', dependencies=guard)
    def sources():
        return actions.sources()

    @app.post('/api/v1/calendar-actions/drafts', dependencies=guard, status_code=201)
    def draft(body: DraftIn):
        try:
            return actions.draft(**body.model_dump())
        except ActionError as exc:
            raise HTTPException(exc.status, str(exc)) from None

    @app.get('/api/v1/calendar-actions/drafts/{action_id}', dependencies=guard)
    def get_draft(action_id: str):
        try:
            return actions.get(action_id)
        except ActionError as exc:
            raise HTTPException(exc.status, str(exc)) from None

    @app.post('/api/v1/calendar-actions/drafts/{action_id}/execute', dependencies=guard)
    def execute(action_id: str, body: ExecuteIn):
        try:
            result = actions.execute(action_id, **body.model_dump())
            if result['status'] == 'done' and rebuild:
                rebuild()
            return result
        except ActionError as exc:
            raise HTTPException(exc.status, str(exc)) from None
