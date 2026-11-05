"""Read-only historical recovery viewer; no application stores or integrations."""
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
from fastapi import FastAPI, Request, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict


class PreflightInput(BaseModel):
    model_config = ConfigDict(extra='forbid')

TABLES = {'tasks.sqlite3': 'tasks', 'knowledge.sqlite3': 'knowledge_claims',
          'episodes.sqlite3': 'episodes', 'self-model.sqlite3': 'assertions',
          'conversations.sqlite3': 'conversation_messages', 'workspace.sqlite3': 'notes',
          'procedures.sqlite3': 'procedures', 'rueckmeldungen.sqlite3': 'rueckmeldung'}


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
    preflight_lock = threading.Lock()

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

    def preflight_auth(request: Request):
        if not expected:
            raise HTTPException(503, 'Die Sicherungsprüfung benötigt einen geschützten lokalen Zugang.')
        auth(request)

    @app.post('/api/v1/recovery/preflight', dependencies=[Depends(preflight_auth)])
    def preflight(body: PreflightInput):
        if not preflight_lock.acquire(blocking=False):
            raise HTTPException(409, 'Eine Sicherungsprüfung läuft bereits.')
        try:
            from .recovery_preflight import preflight as inspect
            return inspect(root)
        finally:
            preflight_lock.release()

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
        response = HTMLResponse('''<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Kingfisher – Wiederherstellung</title>
<style>
:root{font-family:system-ui,-apple-system,sans-serif;color:#223344;background:#f1f3f5;color-scheme:light}
body{margin:0}main{max-width:820px;margin:48px auto;padding:0 24px 48px}h1{font-size:30px;margin:8px 0 16px;letter-spacing:-.6px}
h2{font-size:18px;margin:0 0 12px}p{line-height:1.55}.brand{color:#27647d;font-weight:650;letter-spacing:.08em;font-size:12px}
.lead{color:#4b5b69;max-width:650px}.panel{background:#fff;padding:24px;margin:24px 0;border:1px solid #dae1e7;border-radius:16px}
.badge{display:inline-block;font-size:12px;background:#e9eff3;padding:5px 9px;border-radius:8px}.muted{color:#536676;font-size:14px}
button,select{font:inherit;border:1px solid #b5c3cd;border-radius:8px;padding:9px 14px;background:#fff;color:inherit;max-width:100%}
button{cursor:pointer}button.primary{color:#fff;background:#205e7b;border-color:#205e7b}button:disabled{opacity:.55;cursor:default}
:focus-visible{outline:3px solid #2e7aaf;outline-offset:3px}summary{cursor:pointer;padding:8px 0}li{padding:5px 0;line-height:1.5}
.tools{display:flex;align-items:center;gap:10px;flex-wrap:wrap}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;background:#f5f7f8;padding:12px;border-radius:8px}
[hidden]{display:none!important}@media(max-width:600px){main{margin-top:24px;padding:0 16px 24px}.panel{padding:18px}h1{font-size:26px}}
</style></head><body><main>
<div class="brand">KINGFISHER</div><h1>Deine Sicherung prüfen</h1>
<span class="badge">Historischer Stand · nur Einsicht</span>
<p class="lead">Hier liegt ein historischer Sicherungsstand vor. Prüfe, was lesbar ist und ob vorhandene Vergleichsstände davon abweichen.</p>
<section class="panel" aria-labelledby="check-title"><h2 id="check-title">Sicherungsprüfung</h2>
<button id="check" class="primary">Sicherung prüfen</button>
<p id="check-status" role="status" aria-live="polite">Die Prüfung verändert nichts und startet keine Modelle oder Verbindungen.</p>
<div id="result" hidden></div>
<p class="muted">Spätere Korrekturen können fehlen. Auch gleiche Daten sind noch keine Freigabe für einen neuen Arbeitsbestand.</p></section>
<details class="panel"><summary>Gesicherte Einträge ansehen</summary>
<div class="tools"><label for="stores">Datenbereich</label><select id="stores" disabled></select><button id="load" disabled>Anzeigen</button></div>
<p id="record-status" role="status" aria-live="polite"></p><pre id="records" hidden></pre>
<div class="tools"><button id="previous" disabled>Zurück</button><button id="next" disabled>Weitere Einträge</button></div></details>
</main><script>
const $=id=>document.getElementById(id),s=$('stores'),r=$('records');
const labels={'tasks.sqlite3':'Aufgaben','knowledge.sqlite3':'Gedächtnis','episodes.sqlite3':'Originalquellen',
'self-model.sqlite3':'Bestätigte Angaben','conversations.sqlite3':'Gespräche','workspace.sqlite3':'Projekte und Notizen',
'workspace-views.sqlite3':'Ablage und Ansichten','procedures.sqlite3':'Skills','rueckmeldungen.sqlite3':'Korrekturen',
'regeln.sqlite3':'Dauerfreigaben','proposals.sqlite3':'Vorschläge','audit.sqlite3':'Aktionsnachweise',
'mac-calendar.sqlite3':'Mac-Kalender','calendar-actions.sqlite3':'Kalenderaktionen','gespraeche.sqlite3':'Transkriptzuordnung',
'logbuch.sqlite3':'Verlauf','lint.sqlite3':'Pflegehinweise','cloud-memory-jobs.sqlite3':'Cloudpakete',
'einstellungen.json':'Einstellungen','schluessel.icarus':'Verschlüsselter Schlüsselspeicher'};
const statuses={verified:'lesbar',missing:'in diesem Stand nicht vorhanden',symlink:'Verknüpfung – nicht geprüft',
non_regular:'kein reguläres Datenformat',sidecar_present:'Schreibstand nicht eindeutig',corrupt:'beschädigt',
unsupported_schema:'benötigt eine andere App-Version',limit_exceeded:'Prüfgrenze erreicht',unreadable:'nicht lesbar',
changed_during_read:'während der Prüfung verändert'};
async function get(url,options){const response=await fetch(url,options);if(!response.ok)throw Error(response.status===401?'Zugang abgelaufen. Öffne diese Ansicht erneut.':response.status===409?(url.startsWith('/api/v1/recovery/records?')?'Dieser historische Datenbereich lässt sich mit dieser App-Version nicht lesen.':'Eine Prüfung läuft bereits.'):response.status===503?'Der geschützte lokale Zugang ist noch nicht eingerichtet.':'Laden nicht abgeschlossen. Bitte erneut versuchen.');return response.json()}
function element(tag,text){const el=document.createElement(tag);el.textContent=text;return el}
function details(title){const box=document.createElement('details');box.append(element('summary',title));return box}
function fileList(files){const ul=document.createElement('ul');for(const f of files)ul.append(element('li',(labels[f.name]||'Datenbereich')+': '+(statuses[f.status]||'ungeklärt')));return ul}
$('check').onclick=async()=>{const button=$('check');button.disabled=true;$('result').hidden=true;$('result').replaceChildren();$('check-status').textContent='Sicherung wird gelesen und verglichen …';
try{const report=await get('/api/v1/recovery/preflight',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
const files=report.restored.files,readable=files.filter(f=>f.status==='verified').length,missing=files.filter(f=>f.status==='missing').length;
const unstable=report.unresolved.includes('changed_during_read')||report.unresolved.includes('inventory_incomplete')||report.unresolved.includes('invalid_restore_marker')||report.unresolved.includes('invalid_directory')||report.unresolved.includes('unreadable_directory');
$('check-status').textContent=unstable?'Der Stand ist noch ungeklärt. Bitte die Befunde prüfen und anschließend erneut prüfen.':readable+' Bereiche lesbar · '+missing+' nicht enthalten · '+(files.length-readable-missing)+' ungeklärt';
const result=$('result');const fs=details('Geprüfte Datenbereiche');fs.append(fileList(files));result.append(fs);
if(!report.comparison_groups.length)result.append(element('p','Kein zusätzlicher Vergleichsstand vorhanden. Spätere Änderungen bleiben ungeklärt.'));
for(const group of report.comparison_groups){const d=details('Vergleichsstand '+group.group);d.append(element('p','Herkunft und zeitliche Reihenfolge sind noch nicht bestätigt.'));
if(group.unresolved.includes('changed_during_read'))d.append(element('p','Während der Prüfung verändert. Dieser Vergleich muss wiederholt werden.'));
else if(group.unresolved.includes('group_limit_exceeded'))d.append(element('p','Prüfgrenze erreicht. Dieser Stand wurde noch nicht verglichen.'));
else{const valid=group.tables.filter(t=>t.status==='compared'),changed=valid.filter(t=>t.changed_rows||t.only_in_restored||t.only_in_comparison);
d.append(element('p',changed.length+' Tabellen mit Abweichungen · '+group.tables.filter(t=>t.status!=='compared').length+' Tabellen ungeklärt.'));
const ul=document.createElement('ul');for(const t of changed)ul.append(element('li',(labels[t.store]||'Datenbereich')+' · '+t.table+': '+t.changed_rows+' geändert, '+t.only_in_restored+' nur in der Sicherung, '+t.only_in_comparison+' nur im Vergleichsstand.'));d.append(ul);d.append(fileList(group.files));}
result.append(d)}result.hidden=false;
}catch(error){$('check-status').textContent=error.message}finally{button.disabled=false}};
let offset=0,nextOffset=null,recordsReady=false,recordsBusy=false;
s.disabled=true;$('load').disabled=true;
async function loadRecords(start){if(!recordsReady||recordsBusy||!s.value)return;recordsBusy=true;s.disabled=true;$('load').disabled=true;$('previous').disabled=true;$('next').disabled=true;$('record-status').textContent='Einträge werden geladen …';
try{const data=await get('/api/v1/recovery/records?store='+encodeURIComponent(s.value)+'&offset='+start);offset=start;nextOffset=data.next_offset;r.textContent=JSON.stringify(data.items,null,2);r.hidden=false;$('record-status').textContent=data.items.length?'Einträge '+(start+1)+'–'+(start+data.items.length):'Keine Einträge vorhanden.'}
catch(error){$('record-status').textContent=error.message;r.hidden=true}finally{recordsBusy=false;s.disabled=false;$('load').disabled=false;$('previous').disabled=offset===0;$('next').disabled=nextOffset===null}}
$('load').onclick=()=>loadRecords(0);$('previous').onclick=()=>loadRecords(Math.max(0,offset-50));$('next').onclick=()=>{if(nextOffset!==null)loadRecords(nextOffset)};
s.onchange=()=>{offset=0;nextOffset=null;r.hidden=true;$('record-status').textContent='';$('previous').disabled=true;$('next').disabled=true};
get('/api/v1/recovery/status').then(data=>{for(const name of data.stores||[]){const o=element('option',labels[name]||name);o.value=name;s.append(o)}recordsReady=s.options.length>0;s.disabled=!recordsReady||recordsBusy;$('load').disabled=!recordsReady||recordsBusy}).catch(error=>{$('record-status').textContent=error.message;$('load').disabled=true});
</script></body></html>''')
        if expected:
            response.set_cookie('kingfisher_session', expected, httponly=True, samesite='strict', path='/api')
        return response

    @app.api_route('/{path:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'], dependencies=[Depends(auth)])
    def blocked(path: str):
        raise HTTPException(423, 'Historischer Sicherungsstand: nur Einsicht erlaubt; keine Modell-, Import- oder Aktionsfreigabe.')
    return app
