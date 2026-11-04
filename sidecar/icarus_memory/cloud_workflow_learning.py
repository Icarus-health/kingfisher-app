"""One reviewed correction packet, a shared cloud budget, and inactive skills only."""
from __future__ import annotations

from contextlib import closing, contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
import threading
import time
import uuid

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError
from starlette.concurrency import run_in_threadpool

from .cloud_import_budget import MODEL, MistralBudgetError
from .procedures import ProcedureError
from .providers import ProviderError, _json_transport_timeout
from .workflow_learning import LearningInput, current, dependency, prepare, synthesize


class ReviewError(ValueError):
    pass


@dataclass
class Preview:
    packet: LearningInput
    credential: str | None
    budget: dict
    expires: float


class CloudWorkflowLearning:
    def __init__(self, app, directory):
        self.app = app
        self.path = Path(directory) / 'cloud-workflow-control.sqlite3'
        self._lock = threading.RLock()
        self._previews = {}
        self._thread = None
        with self._db() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, state TEXT NOT NULL, sources TEXT NOT NULL,
                requests INTEGER NOT NULL DEFAULT 0, result TEXT, message TEXT NOT NULL DEFAULT '',
                created REAL NOT NULL)''')
            # Capabilities never survive restart. No automatic replay of paid work.
            conn.execute("UPDATE jobs SET state='interrupted',message='Die Prüfung wurde unterbrochen. Bitte den Kostenstand prüfen.' WHERE state='running'")

    @contextmanager
    def _db(self):
        # A connection context commits but does not close, so close explicitly.
        with closing(sqlite3.connect(self.path,timeout=10)) as conn:
            conn.row_factory = sqlite3.Row
            with conn:
                yield conn

    def budget(self):
        return self.app.state.mistral_source_budget_factory()

    def credential(self):
        return self.app.state.mistral_source_credential()

    def packet(self, area):
        for row in self.app.state.rueckmeldungen.workflow_candidates(area):
            if dependency(self.app,'feedback:'+row['id']):
                packet = prepare(self.app,row,cache_namespace='corrections-mistral-'+MODEL+'-v1:')
                if isinstance(packet,LearningInput):
                    return packet
        raise ReviewError('Noch keine drei passenden, aktuellen Arbeitskorrekturen zur Prüfung vorhanden.')

    def _job(self, identifier=None):
        with self._db() as conn:
            row = conn.execute('SELECT * FROM jobs '+('WHERE id=?' if identifier else 'ORDER BY created DESC LIMIT 1'),
                               (identifier,) if identifier else ()).fetchone()
        if not row:
            return None
        result = json.loads(row['result']) if row['result'] else None
        # A status read must not resurrect an answer derived from withdrawn data.
        if result and any(dependency(self.app,k)!=v for k,v in json.loads(row['sources']).items()):
            result = {'status':'changed'}
        return {'id':row['id'],'state':row['state'],'requests':row['requests'],
                'message':row['message'],'result':result}

    def status(self):
        counts = {}
        for area in ('mail','planning','analysis'):
            try:
                counts[area] = len(self.packet(area).records)
            except ReviewError:
                counts[area] = 0
        return {'provider':'mistral','model':MODEL,'available':self.credential()['available'],
                'budget':self.budget().status(),'job':self._job(),'candidates':counts}

    def preview(self, area):
        with self.app.state.conversation_lock, self._lock:
            packet = self.packet(area)
            credential = self.credential()
            budget = self.budget().status()
            now = time.time()
            self._previews = {k:v for k,v in self._previews.items() if v.expires > now}
            if len(self._previews) >= 16:
                raise ReviewError('Zu viele offene Vorschauen. Bitte später erneut prüfen.')
            identifier = uuid.uuid4().hex
            self._previews[identifier] = Preview(packet,credential['credential_revision'],budget,now+900)
            return {'preview_id':identifier,'available':credential['available'],'model':MODEL,
                    'payload':json.loads(packet.messages[-1]['content']),'budget':budget,
                    'max_requests':2,'expires_at':now+900}

    def _permitted(self, identifier, preview):
        try:
            self.app.state.runtime_boundary.check()
            return (self._job(identifier)['state']=='running'
                    and self.credential()['credential_revision']==preview.credential
                    and self.budget().matches(preview.budget['budget_id'],preview.budget['revision'],preview.budget['price_id'])
                    and current(self.app,preview.packet))
        except Exception:
            return False

    def start(self, identifier, consent):
        if consent is not True:
            raise ReviewError('Bitte die Weitergabe dieser Vorschau ausdrücklich bestätigen.')
        with self.app.state.conversation_lock, self._lock:
            existing = self._job(identifier)
            if existing:
                return {'job':existing}
            preview = self._previews.get(identifier)
            credential = self.credential()
            budget = self.budget().status()
            if (not preview or preview.expires <= time.time() or not credential['available']
                    or not credential['credential_revision'] or credential['credential_revision']!=preview.credential
                    or not budget['ready']
                    or not self.budget().matches(preview.budget['budget_id'],preview.budget['revision'],preview.budget['price_id'])
                    or not current(self.app,preview.packet)):
                raise ReviewError('Zugang, Kostenlimit oder Grundlage fehlt oder wurde verändert. Bitte Vorschau erneut öffnen.')
            with self._db() as conn:
                if conn.execute("SELECT 1 FROM jobs WHERE state='running'").fetchone():
                    raise ReviewError('Eine Ablaufprüfung läuft bereits.')
                conn.execute('INSERT INTO jobs(id,state,sources,created) VALUES(?,?,?,?)',
                             (identifier,'running',json.dumps(preview.packet.sources),time.time()))
            self._previews.pop(identifier)
            self._thread = threading.Thread(target=self._run,args=(identifier,preview),daemon=True)
            self._thread.start()
            return {'job':self._job(identifier)}

    def _run(self, identifier, preview):
        app = self.app
        acquired = False
        try:
            with app.state.runtime_boundary.operation():
                acquired = app.state.workflow_learning_lock.acquire(blocking=False)
                if not acquired:
                    raise ReviewError('Eine lokale Ablaufprüfung läuft bereits. Bitte später erneut prüfen.')
                provider = app.state.mistral_source_provider_factory('mistral',MODEL,
                    job_id='learning_'+identifier,budget_id=preview.budget['budget_id'],
                    budget_revision=preview.budget['revision'],price_id=preview.budget['price_id'])
                # A local answering model does not grant a cloud role its higher ceiling.
                remote = app.state.agent.scoped(provider,frozenset())
                def permitted():
                    return self._permitted(identifier,preview)
                def generate(messages, schema):
                    with app.state.conversation_lock:
                        if not permitted():
                            raise ReviewError('Die Freigabe oder Grundlage wurde verändert.')
                        remote.assert_egress_allowed(messages)
                        with self._db() as conn:
                            changed = conn.execute("UPDATE jobs SET requests=requests+1 WHERE id=? AND state='running' AND requests<2",(identifier,)).rowcount
                            if not changed:
                                raise ReviewError('Die erlaubte Anzahl an Prüfungen wurde erreicht.')
                    def before_send():
                        with app.state.conversation_lock:
                            remote.assert_egress_allowed(messages)
                            if not permitted():
                                raise ReviewError('Die Freigabe oder Grundlage wurde verändert.')
                    reply = provider.complete_json_guarded(messages,max_tokens=1200,schema=schema,
                        before_send=before_send,still_permitted=permitted)
                    _json_transport_timeout(60)
                    return reply
                def finished(result):
                    with self._db() as conn:
                        conn.execute("UPDATE jobs SET state='complete',result=? WHERE id=? AND state='running'",
                                     (json.dumps(result),identifier))
                synthesize(app,preview.packet,generate,permitted,on_result=finished)
        except Exception as error:
            if isinstance(error,MistralBudgetError):
                message = ('Kosten oder Freigabe konnten nicht sicher bestätigt werden. Bitte den Mistral-Kostenstand prüfen; es wird nicht automatisch wiederholt.')
            elif isinstance(error,ReviewError):
                message = str(error)
            else:
                message = 'Kein geprüfter Ablauf entstanden. Bitte Grundlage und Freigabe erneut prüfen.'
            with self._db() as conn:
                conn.execute("UPDATE jobs SET state='failed',message=? WHERE id=? AND state='running'",(message,identifier))
        finally:
            if acquired:
                app.state.workflow_learning_lock.release()

    def revoke(self, identifier=None, *, readback=True):
        with self.app.state.conversation_lock, self._lock:
            with self._db() as conn:
                conn.execute("UPDATE jobs SET state='cancelled',message='Abgebrochen. Bereits übertragene Anfragen können Kosten verursacht haben.' WHERE state='running'"+
                             (' AND id=?' if identifier else ''),(identifier,) if identifier else ())
            self._previews.clear()
        return self.status() if readback else None

    def origin(self, identifier):
        with self._db() as conn:
            row = conn.execute("SELECT 1 FROM jobs WHERE state='complete' AND json_extract(result,'$.proposal_id')=?",(identifier,)).fetchone()
        return {'provider':'mistral','model':MODEL} if row else None


class PreviewIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    area: str = Field(pattern='^(mail|planning|analysis)$')


class StartIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    preview_id: str = Field(pattern='^[a-f0-9]{32}$')
    consent: StrictBool


class RevokeIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    job_id: str = Field(pattern='^[a-f0-9]{32}$')


def register(app, guard, data_dir):
    lock = threading.Lock()
    def manager():
        with lock:
            value = getattr(app.state,'cloud_workflow_learning',None)
            if value is None:
                value = CloudWorkflowLearning(app,data_dir())
                app.state.cloud_workflow_learning = value
            return value
    app.state.procedure_cloud_origin = lambda identifier: manager().origin(identifier)
    def invoke(fn):
        try:
            return fn(manager())
        except (ReviewError,ProcedureError) as exc:
            raise HTTPException(409,str(exc)) from None
        except (ProviderError,sqlite3.Error,OSError):
            raise HTTPException(409,'Prüfung oder Kostenstand derzeit nicht verfügbar. Bitte später erneut prüfen.') from None
    async def body_of(request, model):
        raw = await request.body()
        if len(raw) > 1024:
            raise HTTPException(422,'Die Eingabe zur Ablaufprüfung ist zu groß.')
        try:
            return model.model_validate_json(raw)
        except ValidationError:
            raise HTTPException(422,'Bitte Bereich, Vorschau und Zustimmung prüfen.') from None
    @app.get('/api/v1/procedure-learning/status',dependencies=guard)
    def status():
        return invoke(lambda service:service.status())
    @app.post('/api/v1/procedure-learning/preview',dependencies=guard)
    async def preview(request: Request):
        body = await body_of(request,PreviewIn)
        return await run_in_threadpool(invoke,lambda service:service.preview(body.area))
    @app.post('/api/v1/procedure-learning/start',dependencies=guard)
    async def start(request: Request):
        body = await body_of(request,StartIn)
        if body.consent is not True:
            raise HTTPException(422,'Bitte die Weitergabe dieser Vorschau ausdrücklich bestätigen.')
        return await run_in_threadpool(invoke,lambda service:service.start(body.preview_id,body.consent))
    @app.post('/api/v1/procedure-learning/revoke',dependencies=guard)
    async def revoke(request: Request):
        body = await body_of(request,RevokeIn)
        return await run_in_threadpool(invoke,lambda service:service.revoke(body.job_id))
