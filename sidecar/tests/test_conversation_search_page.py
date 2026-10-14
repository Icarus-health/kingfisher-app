from datetime import datetime, timezone
from threading import RLock

import pytest
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient

from icarus_memory.conversations import ConversationStore


def test_content_search_paginates_beyond_first_hundred_with_stable_ties(tmp_path):
    store = ConversationStore(tmp_path / 'chat.sqlite3')
    at = datetime(2026, 10, 14, tzinfo=timezone.utc)
    ids = []
    for n in range(105):
        c = store.create(f'Titel {n}', at=at)
        store.add_message(c.id, 'user', 'älterer Inhalt: Küchenplanung', at=at)
        store.add_message(c.id, 'user', 'letzte Nachricht', at=at)
        ids.append(c.id)
    pages = []
    cursor = None
    while True:
        page = store.page(q='Küchenplanung', limit=30, cursor=cursor)
        assert page['total'] == 105
        pages.extend(x.id for x in page['conversations'])
        cursor = page['next_cursor']
        if not cursor:
            break
    assert pages == sorted(ids, reverse=True)
    assert len(set(pages)) == 105
    store.close()


def test_search_escapes_wildcards_and_checks_query_cursor(tmp_path):
    store = ConversationStore(tmp_path / 'chat.sqlite3')
    c = store.create('100%_\\ erledigt')
    store.create('100abc erledigt')
    assert [s.id for s in store.page(q='%_\\')['conversations']] == [c.id]
    first = store.page(limit=1, q='100')
    with pytest.raises(ValueError, match='Cursor'):
        store.page(q='anderer Inhalt', cursor=first['next_cursor'])
    with pytest.raises(ValueError, match='Cursor'):
        store.page(cursor='broken')
    with pytest.raises(ValueError):
        store.page(q='x' * 201)
    with pytest.raises(ValueError):
        store.page(limit=101)
    store.close()


def test_unsafe_assistant_memory_content_never_becomes_search_preview(tmp_path):
    store = ConversationStore(tmp_path / 'chat.sqlite3')
    c = store.create('Planung')
    store.add_message(c.id, 'user', 'sicherer Benutzertext')
    store.add_message(c.id, 'assistant', 'ALTE VERTRAULICHE ANTWORT', metadata={
        'context': {'answer_mode': 'memory_evidence', 'knowledge_claim_ids': ['withdrawn']}})
    page = store.page(q='Planung')
    assert 'ALTE VERTRAULICHE' not in page['conversations'][0].preview
    assert store.page(q='ALTE VERTRAULICHE')['total'] == 0
    store.close()


def test_page_route_uses_guard_sanitizer_and_parameter_bounds(tmp_path):
    from icarus_memory.conversation_search_routes import register_conversation_search_routes
    app = FastAPI()
    app.state.conversation_lock = RLock()
    app.state.conversations = ConversationStore(tmp_path / 'chat.sqlite3')
    app.state.conversations.create('Rohtext')
    authorized = False
    def guard():
        if not authorized:
            raise HTTPException(status_code=401)
    def sanitized(summary):
        value = summary.to_dict()
        value['title'] = 'Quelle zurückgezogen'
        value['preview'] = 'Nicht mehr verwendet'
        return value
    register_conversation_search_routes(app, [Depends(guard)], sanitized)
    client = TestClient(app)
    assert client.get('/api/v1/conversations/page').status_code == 401
    authorized = True
    response = client.get('/api/v1/conversations/page')
    assert response.status_code == 200
    assert response.json()['conversations'][0]['title'] == 'Quelle zurückgezogen'
    assert response.json()['conversations'][0]['preview'] == 'Nicht mehr verwendet'
    assert response.json()['total'] == 1
    for query in ('limit=101', 'limit=0', 'q=' + 'x' * 201, 'cursor=bad'):
        assert client.get('/api/v1/conversations/page?' + query).status_code == 422
    app.state.conversations.close()
