"""Additive guarded conversation search; register before the dynamic ID route."""
from __future__ import annotations

from typing import Any, Callable
from fastapi import FastAPI, HTTPException, Query
from .conversations import ConversationSummary


def register_conversation_search_routes(
    app: FastAPI, guard: list[Any], sanitize_summary: Callable[[ConversationSummary], dict[str, Any]],
) -> None:
    @app.get('/api/v1/conversations/page', dependencies=guard)
    def conversation_page(
        q: str = Query(default='', max_length=200),
        limit: int = Query(default=30, ge=1, le=100),
        cursor: str | None = Query(default=None, max_length=1000),
    ) -> dict[str, Any]:
        # Source validity and rows belong to one view of the conversation state.
        with app.state.conversation_lock:
            try:
                result = app.state.conversations.page(q=q, limit=limit, cursor=cursor)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            return {**result, 'conversations': [sanitize_summary(summary) for summary in result['conversations']]}
