"""Read-only historical recovery viewer; no application stores or integrations."""
import json
import os
from pathlib import Path
import secrets
import sqlite3
from fastapi import FastAPI, Request, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse

TABLES = {'tasks.sqlite3': 'tasks', 'knowledge.sqlite3': 'knowledge_claims',
          'episodes.sqlite3': 'episodes', 'self-model.sqlite3': 'assertions',
          'conversations.sqlite3': 'conversation_messages', 'workspace.sqlite3': 'notes'}


def assertion_count(directory):
    path = Path(directory) / 'self-model.sqlite3'
    if not path.is_file() or path.is_symlink():
        return 0
    try:
        with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as conn:
            return conn.execute('SELECT COUNT(*) FROM assertions').fetchone()[0]
    except sqlite3.DatabaseError:
        return None


def create_inspection_app(directory):
    root = Path(directory)
    app = FastAPI(title='Kingfisher — historischer Sicherungsstand', docs_url=None, redoc_url=None, openapi_url=None)
    expected = os.environ.get('ICARUS_SIDECAR_TOKEN')

    def auth(request: Request):
        supplied = [request.headers.get('x-icarus-token'), request.cookies.get('kingfisher_session')]
        if expected is not None and not any(value is not None and secrets.compare_digest(value, expected) for value in supplied):
            raise HTTPException(401, 'Ungültiges Token')

    @app.get('/health')
    def health():
        return {'status': 'ok', 'mode': 'inspection', 'operational': False}

    @app.get('/api/v1/recovery/status', dependencies=[Depends(auth)])
    def status():
        return {'mode': 'inspection', 'operational': False,
                'detail': 'Historischer Sicherungsstand. Spätere Korrekturen und entzogene Rechte sind möglicherweise nicht enthalten.',
                'stores': [name for name in TABLES if (root / name).is_file() and not (root / name).is_symlink()]}

    @app.get('/api/v1/recovery/records', dependencies=[Depends(auth)])
    def records(store: str, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        if store not in TABLES or not (root / store).is_file() or (root / store).is_symlink():
            raise HTTPException(404, 'Historischer Datenbereich nicht vorhanden.')
        try:
            with sqlite3.connect((root / store).resolve().as_uri() + '?mode=ro', uri=True) as conn:
                conn.row_factory = sqlite3.Row
                conn.execute('PRAGMA query_only=ON')
                rows = conn.execute('SELECT * FROM "' + TABLES[store] + '" LIMIT ? OFFSET ?', (limit + 1, offset)).fetchall()
        except sqlite3.DatabaseError:
            raise HTTPException(409, 'Dieser historische Datenbereich lässt sich mit dieser Version nicht lesen.') from None
        return {'historical': True, 'operational': False, 'store': store,
                'items': [{key: ('[Binärdaten]' if isinstance(value, bytes) else value) for key, value in dict(row).items()} for row in rows[:limit]],
                'next_offset': offset + limit if len(rows) > limit else None}

    @app.get('/')
    @app.get('/today')
    def index():
        response = HTMLResponse('''<!doctype html><html lang="de"><meta charset="utf-8"><title>Kingfisher – Wiederherstellung</title>
<h1>Historischer Sicherungsstand</h1><p>Die Daten bleiben erhalten. Modelle, Verbindungen, Zeitpläne und Aktionen sind ausgeschaltet.</p>
<p>Spätere Korrekturen und entzogene Rechte können fehlen. Diese Ansicht bestätigt deshalb keine heutige Gültigkeit.</p>
<label>Datenbereich <select id="stores"></select></label> <button id="load">Anzeigen</button><pre id="records"></pre>
<p>Einzelne Originale können nach ausdrücklicher Prüfung über die normale Aufnahme einer aktuellen Kingfisher-Instanz neu eingebracht werden. Alte Dauerfreigaben werden nicht übernommen.</p>
<script>const s=document.getElementById('stores'),r=document.getElementById('records');
fetch('/api/v1/recovery/status').then(x=>x.json()).then(x=>{for(const n of x.stores||[]){const o=document.createElement('option');o.value=n;o.textContent=n;s.append(o)}});
document.getElementById('load').onclick=()=>fetch('/api/v1/recovery/records?store='+encodeURIComponent(s.value)).then(x=>x.json()).then(x=>r.textContent=JSON.stringify(x,null,2));</script></html>''')
        if expected:
            response.set_cookie('kingfisher_session', expected, httponly=True, samesite='strict', path='/api')
        return response

    @app.api_route('/{path:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'], dependencies=[Depends(auth)])
    def blocked(path: str):
        raise HTTPException(423, 'Historischer Sicherungsstand: nur Einsicht erlaubt; keine Modell-, Import- oder Aktionsfreigabe.')
    return app
