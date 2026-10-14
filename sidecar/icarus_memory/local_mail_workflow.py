"""Gespeicherte Mail: lesender Überblick, begrenzte lokale Vorbereitung, Vorschlagsannahme.

Keine Provider-Mail wird gelesen und keine neue Originalquelle aufgenommen.
"""
from datetime import datetime, timezone
import hashlib
import json
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from . import local_model_guard
from .episodes import EpisodeKind, EpisodeError
from .model import SourceType
from .mail_briefing import _passages, _selected, SYSTEM, SCHEMA
from .mail_timeline import timings
from .proposals import ProposalKind, ProposalState, ProposalError
from .providers import ProviderError
from .task_detection import TaskDetector
from .task_candidates import TaskCandidates
from .task_project_hints import TaskProjectHints
from .task_review import current_task_context, task_context_matches, REVIEW_MARKER
from .workspace import WorkspaceError
from .workspace_views import ViewChanged

CACHE = 'saved_mail_briefing'


def _provider(app):
    from .model_roles import rollen_von
    return rollen_von(app).provider('frage')


def _key(identifier):
    return hashlib.sha256(identifier.encode()).hexdigest()


class PrepareIn(BaseModel):
    model_config = ConfigDict(extra='forbid')


class AcceptIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')
    source_digest: str = Field(pattern=r'^sha256:[a-f0-9]{64}$')
    title: str = Field(min_length=1, max_length=4096)
    project_id: str | None = Field(default=None, max_length=1000)
    new_project_name: str | None = Field(default=None, max_length=200)
    due: datetime | None = None
    waiting_for: str | None = Field(default=None, max_length=1024)


class _SingleSource:
    """Der vorhandene Detector arbeitet nur diese Quelle, ohne Scan-Cursor zu bewegen."""
    def __init__(self, episodes, identifier):
        self.episodes, self.identifier = episodes, identifier
    def __getattr__(self, name):
        return getattr(self.episodes, name)
    def task_rechecks(self):
        return [{'id': self.identifier}]
    def finish_task_recheck(self, row, *, completed):
        pass  # Kein Eingriff in die vorhandene Hintergrund-Wiedervorlage.


class _SourceProposals:
    """Vorhandene Projektprüfung liest ausschließlich Vorschläge dieser Mail."""
    def __init__(self, proposals, identifier):
        self.proposals, self.identifier = proposals, identifier
    def __getattr__(self, name):
        return getattr(self.proposals, name)
    def pending(self, kind, limit=2000):
        with self.proposals._lock:
            rows = self.proposals._conn.execute(
                "SELECT id FROM proposals WHERE state='pending' AND kind=? "
                "AND json_extract(document,'$.evidence[0].episode_id')=? ORDER BY created_at DESC,id DESC LIMIT ?",
                (kind.value, self.identifier, min(32, limit) if limit >= 0 else 32)).fetchall()
        return [self.proposals.get(row[0]) for row in rows]


class SavedMailWorkflow:
    def __init__(self, app):
        self.app = app
        self.state = app.state
    def _source(self, identifier):
        try:
            source = self.state.episodes.get(identifier)
        except (EpisodeError, KeyError):
            raise HTTPException(404, 'Gespeicherte Mail nicht gefunden.') from None
        if source.kind is not EpisodeKind.MESSAGE or source.provenance.source_type is not SourceType.EMAIL:
            raise HTTPException(404, 'Gespeicherte Mail nicht gefunden.')
        context = current_task_context(self.state.episodes, identifier)
        if context is None:
            raise HTTPException(409, 'Diese Mailquelle wurde verändert oder ausgeschlossen. Bitte neu laden.')
        return source, context
    def _snapshot(self, identifier):
        source, context = self._source(identifier)
        timing = timings(self.state.episodes, [source], now=datetime.now(timezone.utc))[identifier]
        # Die Zeitklassifikation und Folgemails sind Teil des Prüfschritts, nicht des Originaltexts.
        material = ['saved-mail-v1',identifier,source.digest,context,source.project_id,timing['temporal_status'],timing['followup_episode_id']]
        stamp = hashlib.sha256(json.dumps(material,ensure_ascii=False).encode()).hexdigest()
        return source, context, timing, stamp
    def _hints(self):
        return TaskProjectHints(self.state.episodes,self.state.proposals,self.state.workspace,
                                self.state.workspace_views,self.state.conversation_lock)
    def visible(self, identifier):
        with self.state.conversation_lock:
            source, context, timing, stamp = self._snapshot(identifier)
            cache = self.state.workspace_views.get(CACHE,_key(identifier))['data']
            ready = cache is not None and cache['fingerprint']==stamp
            items=[]
            for proposal in _SourceProposals(self.state.proposals,identifier).pending(ProposalKind.TASK):
                if (len(proposal.evidence)!=1 or proposal.evidence[0].episode_id!=identifier
                        or proposal.evidence[0].digest!=source.digest
                        or proposal.evidence[0].quote not in source.body
                        or not task_context_matches(proposal,self.state.episodes)
                        or self.state.tasks.get(f't-suggestion-{proposal.id}') is not None):
                    continue
                items.append({**proposal.to_dict(),'project_suggestion':self._hints().visible(proposal),
                              'review_required':timing['temporal_status']!='recent' or proposal.task_context is None
                                  or not proposal.proposed_by.endswith(REVIEW_MARKER)})
            return {'episode_id':identifier,'source_digest':source.digest,'fingerprint':stamp,
                    **timing,'status':cache['status'] if ready else 'unprepared',
                    'quotes':cache['quotes'] if ready else [],'items':items[:32],
                    'projects':[{'id':p.id,'name':p.name} for p in self.state.workspace.projects() if p.is_open()],
                    'detail':'Ausgewählte Originalpassagen. Bitten sind Prüfhinweise; heutige Erledigung und Zuständigkeit bleiben zu prüfen.'
                             if ready else 'Noch kein kurzer Überblick vorbereitet. Diese einzelne Quelle kann lokal geprüft werden.'}
    def prepare(self, identifier, provider, *, permitted=lambda:True):
        with self.state.conversation_lock:
            source, context, timing, stamp=self._snapshot(identifier)
            previous=self.state.workspace_views.get(CACHE,_key(identifier))
            if previous['data'] and previous['data']['fingerprint']==stamp:
                return self.visible(identifier)
            if not permitted():
                raise HTTPException(409,'Die Freigabe wurde geändert.')
        if provider is None or not getattr(provider,'is_local',False):
            return {**self.visible(identifier),'status':'unavailable','detail':'Für diesen Überblick wird ein installiertes lokales Modell benötigt.'}
        passages,incomplete=_passages(source.body)
        incomplete=incomplete or 'source:truncated' in source.tags
        try:
            identity=local_model_guard.verify_local_model(provider)
            wrapped=local_model_guard.VerifiedLocalProvider(provider,permitted=permitted)
            quotes=[]
            if passages:
                reply=wrapped.complete_json([
                    {'role':'system','content':SYSTEM},
                    {'role':'user','content':json.dumps({'subject':source.title[:500],
                        'passages':[{'id':i,'text':p} for i,p in enumerate(passages)]},ensure_ascii=False)}],max_tokens=768,schema=SCHEMA)
                quotes,_,invalid=_selected(reply,passages)
                incomplete=incomplete or invalid
            def fresh():
                if not permitted(): return False
                try: return self._snapshot(identifier)[3]==stamp
                except HTTPException: return False
            if not fresh():
                raise HTTPException(409,'Die Quelle oder ihr Prüfkontext wurde geändert.')
            if not incomplete:
                report=TaskDetector(_SingleSource(self.state.episodes,identifier),self.state.proposals,wrapped,
                                    self.state.conversation_lock,tasks=self.state.tasks).run(
                    with_model=True,limit=1,rechecks_only=True,permitted=fresh)
                if report.cancelled:
                    raise HTTPException(409,'Die Quelle oder ihr Prüfkontext wurde geändert.')
                if report.failed or (not report.analyzed and not self.state.proposals.memory_analysis.completed(source, wrapped, context=context)):
                    raise ProviderError('Die Aufgabenprüfung konnte nicht abgeschlossen werden.')
                TaskProjectHints(self.state.episodes,_SourceProposals(self.state.proposals,identifier),
                                 self.state.workspace,self.state.workspace_views,self.state.conversation_lock).prepare(
                    wrapped,limit=2,permitted=fresh)
            if local_model_guard.verify_local_model(provider)!=identity:
                raise HTTPException(409,'Das lokale Modell wurde geändert.')
            with self.state.conversation_lock:
                if not fresh(): raise HTTPException(409,'Die Quelle oder ihr Prüfkontext wurde geändert.')
                self.state.workspace_views.put(CACHE,_key(identifier),{'fingerprint':stamp,'source_digest':source.digest,
                    'quotes':quotes,'status':'incomplete' if incomplete else 'ready'},previous['revision'])
            return self.visible(identifier)
        except ProviderError:
            with self.state.conversation_lock:
                if not permitted(): raise HTTPException(409,'Die Modellfreigabe wurde geändert.') from None
                return {**self.visible(identifier),'status':'unavailable',
                        'detail':'Die lokale Vorbereitung konnte nicht abgeschlossen werden. Bitte erneut versuchen.'}
    def accept(self, identifier, proposal_id, body):
        with self.state.conversation_lock:
            proposal=self.state.proposals.get(proposal_id)
            if len(proposal.evidence)!=1 or proposal.evidence[0].episode_id!=identifier:
                raise ProposalError('Der Vorschlag gehört nicht zu dieser Quelle.')
            existing=self.state.tasks.get(f't-suggestion-{proposal_id}')
            if proposal.state is not ProposalState.ACCEPTED and existing is None:
                source,_,_,stamp=self._snapshot(identifier)
                if stamp!=body.fingerprint or source.digest!=body.source_digest:
                    raise ProposalError('Die Quelle oder ihr Prüfkontext wurde geändert. Bitte neu laden.')
            return TaskCandidates(self.state.episodes,self.state.proposals,self.state.tasks,self.state.workspace,
                                  self.state.conversation_lock).accept(proposal_id,title=body.title,
                project_id=body.project_id,new_project_name=body.new_project_name,due=body.due,waiting_for=body.waiting_for).to_dict()


def prepare_background(app, provider, *, limit=1, permitted=lambda:True):
    """Höchstens zwei aktuelle Mailquellen pro vorhandenem lokalen Hintergrundtakt."""
    service=SavedMailWorkflow(app)
    from .local_mail_routes import _BASE
    attempted=0
    with app.state.conversation_lock, app.state.episodes._lock:
        rows=app.state.episodes._conn.execute(f'SELECT e.id FROM episodes e WHERE {_BASE} ORDER BY e.recorded_at DESC LIMIT 100').fetchall()
    for row in rows:
        if attempted>=max(0,min(limit,2)) or not permitted(): break
        try:
            if service.visible(row[0])['status']!='unprepared': continue
            attempted+=1
            service.prepare(row[0],provider,permitted=permitted)
        except (HTTPException,ViewChanged):
            continue
    return attempted


def register(app, guard):
    service=SavedMailWorkflow(app)
    @app.get('/api/v1/local-mail/{episode_id}/workflow',dependencies=guard)
    def visible(episode_id:str):
        return service.visible(episode_id)
    @app.post('/api/v1/local-mail/{episode_id}/workflow/prepare',dependencies=guard)
    def prepare(episode_id:str,body:PrepareIn=PrepareIn()):
        with app.state.conversation_lock:
            provider=_provider(app)
            configuration=tuple(getattr(provider,k,None) for k in ('model','base_url','is_local'))
        def permitted():
            return _provider(app) is provider and tuple(getattr(provider,k,None) for k in ('model','base_url','is_local'))==configuration
        try:
            return service.prepare(episode_id,provider,permitted=permitted)
        except ViewChanged as exc: raise HTTPException(409,'Die Vorbereitung wurde inzwischen geändert. Bitte neu laden.') from exc
    @app.post('/api/v1/local-mail/{episode_id}/workflow/tasks/{proposal_id}/accept',dependencies=guard)
    def accept(episode_id:str,proposal_id:str,body:AcceptIn):
        try: return service.accept(episode_id,proposal_id,body)
        except (ProposalError,EpisodeError) as exc: raise HTTPException(409,str(exc)) from exc
        except (WorkspaceError,ValueError) as exc: raise HTTPException(422,str(exc)) from exc
