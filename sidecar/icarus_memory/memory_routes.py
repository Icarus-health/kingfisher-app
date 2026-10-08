"""Begrenzte, lesende Eigentümeransicht auf Verarbeitung und Gedächtniszeit."""
from datetime import datetime, timedelta, timezone
from typing import Literal
import time
import json
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from .episodes import AUSGEBLENDETE_ZUSTAENDE, EpisodeError, EpisodeKind, sql_quelle
from .claims import ClaimError
from .model import Status
from .memory_analysis import VERSION
from .model_roles import hintergrund_anbieter, rollen_von
from .memory_history import aware, query_key, time_key, encode_cursor, decode_cursor, SCAN_BUDGET, ceiling_anchor, validate_anchor
from . import config
from .providers import ProviderError


class SourceCorrectionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')
    body: str = Field(min_length=1, max_length=12000)


#: Zustände, in denen das Sortieren vorgemerkt werden darf (`MemoryAutomationIn.vormerken`).
VORMERKBAR = ('model_missing', 'local_model_unavailable')


class MemoryAutomationIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool
    #: Einschalten, auch wenn das lokale Modell noch lädt: Es läuft, sobald das Modell bereit ist (Fremdprobe 3,
    #: Befund 3). Nur für ein fehlendes oder noch nicht bestätigtes lokales Modell, nie für eines im Internet.
    vormerken: bool = False


def coverage(episodes, proposals):
    # Keine Volltexte laden. Technische Quellobjekte sind nicht gleichbedeutend
    # mit unabhängigen Beweisen oder vollständig angebundenen Kanälen.
    total, rows = episodes.quellen_kopf(2000)
    counts = dict.fromkeys(("pending", "running", "partial", "completed", "failed", "excluded"), 0)
    truncated_sources = 0
    for row in rows:
        if row['state'] in AUSGEBLENDETE_ZUSTAENDE:
            counts['excluded'] += 1
            continue
        truncated_sources += int(row['source_truncated'])
        job = proposals.memory_analysis.snapshot(row['id'])
        if not job or job['digest'] != row['digest'] or job['version'] != VERSION:
            counts['pending'] += 1
        elif job['state'] == 'completed' and job['offset'] == job['total']:
            # Der empfangene Ausschnitt ist fertig geprüft. Die fehlenden Bytes
            # bleiben eine Quelllücke; denselben Ausschnitt erneut zu prüfen
            # würde sie nicht schließen und darf keinen neuen Job erzwingen.
            counts['partial' if row['source_truncated'] else 'completed'] += 1
        elif job['state'] == 'failed':
            counts['failed'] += 1
        elif job['state'] == 'running' and job['lease_until'] > time.time():
            counts['running'] += 1
        elif job['offset']:
            counts['partial'] += 1
        else:
            counts['pending'] += 1
    with episodes._lock:
        placeholders = ','.join('?' for _ in AUSGEBLENDETE_ZUSTAENDE)
        available = f"{sql_quelle()} AND state NOT IN ({placeholders})"
        valid_date = "julianday(occurred_at) IS NOT NULL AND (substr(occurred_at,-1)='Z' OR substr(occurred_at,-6,1) IN ('+','-'))"
        dates = []
        for order in ('ASC', 'DESC'):
            row = episodes._conn.execute(
                f"SELECT occurred_at FROM episodes WHERE {available} AND {valid_date} ORDER BY julianday(occurred_at) {order},id {order} LIMIT 1",
                tuple(AUSGEBLENDETE_ZUSTAENDE)).fetchone()
            dates.append(row['occurred_at'] if row else None)
        undated = episodes._conn.execute(
            f"SELECT COUNT(*) FROM episodes WHERE {available} AND NOT COALESCE(({valid_date}),0)",
            tuple(AUSGEBLENDETE_ZUSTAENDE)).fetchone()[0]
    source_dates = {'earliest': dates[0],
                    'latest': dates[1], 'undated': undated}
    return {'source_dates': source_dates, 'total_sources': total, 'sampled_sources': len(rows), 'counts': counts,
            'truncated': total > len(rows), 'analysis_version': VERSION,
            'truncated_sources': truncated_sources,
            'semantic_completeness': False, 'generated_at': datetime.now(timezone.utc).isoformat(),
            'scope': 'Aufgenommene Nachrichten und Dokumente; Prüfung auf Aufgabenvorschläge.',
            'detail': ('Verarbeitet bedeutet: Der Text wurde ausgewertet. Es beweist nicht, dass jede Bitte richtig erkannt wurde. Nicht angebundene Kanäle und fehlende Anlagen sind nicht enthalten.'
                       + (f' {truncated_sources} der gezeigten verfügbaren Quellen wurden beim Empfang gekürzt; für vollständige Abdeckung fehlt der restliche Originaltext.'
                          if truncated_sources else ''))}


def timeline(episodes, claims, start, end, limit, cursor=None, basis="recorded"):
    """Best-effort live navigation; continuation repeats returned start/end.

    A changed/deleted ceiling anchor invalidates the cursor. Rights are checked
    per page, so this does not provide a transaction snapshot across stores.
    """
    if basis not in {'source', 'recorded'}:
        raise ValueError('Unbekannte Zeitachse.')
    aware(start)
    aware(end)
    if end <= start:
        raise ValueError('Das Ende muss nach dem Beginn liegen.')
    if not 1 <= limit <= 500:
        raise ValueError('Der Abruf ist auf 1 bis 500 Einträge begrenzt.')
    query = query_key('timeline', str(episodes._path.resolve()), str(claims._path.resolve()),
                      time_key(start), time_key(end), limit, basis)
    continuation = decode_cursor(cursor, query, 2) if cursor is not None else None
    with episodes._lock:
        source_ceiling = (continuation[1][0] if continuation else
                          episodes._conn.execute('SELECT COALESCE(MAX(rowid),0) FROM episodes').fetchone()[0])
        source_anchor = (continuation[2][0] if continuation else
                         ceiling_anchor(episodes._conn, 'episodes', 'rowid', source_ceiling))
        validate_anchor(episodes._conn, 'episodes', 'rowid', source_ceiling, source_anchor)
    with claims._lock:
        ceilings = continuation[1] if continuation else [
            source_ceiling,
            claims._conn.execute('SELECT COALESCE(MAX(revision),0) FROM knowledge_changes').fetchone()[0],
        ]
        anchors = continuation[2] if continuation else [
            source_anchor,
            ceiling_anchor(claims._conn, 'knowledge_changes', 'revision', ceilings[1]),
        ]
        validate_anchor(claims._conn, 'knowledge_changes', 'revision', ceilings[1], anchors[1])
        candidates = []
        # Each stream uses exactly the same total ordering as the final merge.
        # Filtering happens after scanning so hidden entries cannot strand a page.
        for conn, table, key, ceiling_column, ceiling in (
            (episodes._conn, 'episodes', "'source:' || id", 'rowid', ceilings[0]),
            (claims._conn, 'knowledge_changes', "'change:' || revision", 'revision', ceilings[1]),
        ):
            if basis == 'source' and table != 'episodes':
                continue
            stamp = ('occurred_at' if basis == 'source' else 'recorded_at') if table == 'episodes' else 'created_at'
            sql = (f'SELECT *, julianday({stamp}) AS sort_time, {key} AS sort_id FROM {table} '
                   f'WHERE julianday({stamp})>=julianday(?) AND julianday({stamp})<julianday(?) '
                   f'AND {ceiling_column}<=?')
            if basis == 'source':
                sql += f" AND {sql_quelle()} AND (substr(occurred_at,-1)='Z' OR substr(occurred_at,-6,1) IN ('+','-'))"
            params = [start.isoformat(), end.isoformat(), ceiling]
            if continuation:
                after_time, after_id = continuation[0]
                sql += f' AND (julianday({stamp})<? OR (julianday({stamp})=? AND ({key})<?))'
                params.extend([after_time, after_time, after_id])
            sql += ' ORDER BY sort_time DESC,sort_id DESC LIMIT ?'
            params.append(SCAN_BUDGET + 1)
            if table == 'episodes':
                with episodes._lock:
                    validate_anchor(episodes._conn, 'episodes', 'rowid', ceilings[0], anchors[0])
                    rows = conn.execute(sql, params).fetchall()
            else:
                rows = conn.execute(sql, params).fetchall()
            candidates.extend((row, table) for row in rows)
        candidates.sort(key=lambda pair: (pair[0]['sort_time'], pair[0]['sort_id']), reverse=True)
        items = []
        scanned = 0
        position = None
        gaps = {'unavailable_evidence': 0, 'missing_claim': 0}
        for row, table in candidates[:SCAN_BUDGET]:
            scanned += 1
            position = (row['sort_time'], row['sort_id'])
            if table == 'episodes':
                if (row['state'] in AUSGEBLENDETE_ZUSTAENDE
                        or row['kind'] == EpisodeKind.SUMMARY.value):
                    gaps['unavailable_evidence'] += 1
                    continue
                item = {'id': row['sort_id'], 'kind': 'source_received', 'title': row['title'],
                        'recorded_at': row['recorded_at'], 'occurred_at': row['occurred_at'],
                        'episode_id': row['id'], 'claim_id': None}
            else:
                try:
                    claim = claims.get(row['claim_id'])
                except ClaimError:
                    gaps['missing_claim'] += 1
                    continue
                try:
                    sources = [episodes.get(e.episode_id) for e in claim.evidence]
                except EpisodeError:
                    gaps['unavailable_evidence'] += 1
                    continue
                if (claim.status is Status.REDACTED or not sources
                        or any(source.state in AUSGEBLENDETE_ZUSTAENDE
                               or source.kind is EpisodeKind.SUMMARY or source.digest != evidence.digest
                               for source, evidence in zip(sources, claim.evidence))):
                    gaps['unavailable_evidence'] += 1
                    continue
                item = {'id': row['sort_id'], 'kind': row['action'], 'title': claim.statement,
                        'recorded_at': row['created_at'],
                        'occurred_at': claim.valid_from.isoformat() if claim.valid_from else None,
                        'claim_id': claim.id, 'episode_id': None}
            items.append(item)
            if len(items) == limit:
                break
        truncated = len(candidates) > scanned
        next_cursor = encode_cursor(query, position, ceilings, anchors) if truncated else None
    return {'items': items, 'truncated': truncated, 'next_cursor': next_cursor,
            'scanned': scanned, 'budget_truncated': truncated and scanned == SCAN_BUDGET,
            'gaps': gaps, 'gap_scope': 'page', 'consistency': 'best_effort_navigation',
            'start': start.isoformat(), 'end': end.isoformat(),
            'basis': basis, 'time_axis': 'occurred_at' if basis == 'source' else 'recorded_at',
            'detail': ('Originaldatum verfügbarer Quellen; Quellen ohne Datum sind hier nicht einsortiert.' if basis == 'source' else
                       'Zeitpunkt der Aufnahme oder Entscheidung. Ein älteres Quellendatum wird gesondert gezeigt.')}



def install_routes(app, guard):
    router = APIRouter(prefix='/api/v1/memory', dependencies=guard)
    automation_observation = None

    @router.get('/coverage')
    def read_coverage():
        with app.state.conversation_lock:
            from .working_memory_store import WorkingMemoryStore
            result = coverage(app.state.episodes, app.state.proposals)
            result['working_memory'] = WorkingMemoryStore(app.state.episodes).coverage()
            progress = WorkingMemoryStore(app.state.episodes).progress()
            from .server import _working_memory_pace
            progress['estimate_seconds'] = _working_memory_pace(app).estimate(progress['remaining'])
            result['working_memory_progress'] = progress
            from .working_memory_semantic_runtime import coverage as semantic_coverage
            result['semantic_index'] = semantic_coverage(app)
            result['automation'] = automation_status(pending=result['working_memory']['pending'], probe=False)
            result['working_memory_enabled'] = result['automation']['state'] in {'active', 'legacy_active'}
            return result

    def automation_status(*, verified=None, pending=None, probe=True):
        nonlocal automation_observation
        plan = app.state.settings.schedule
        observation_key = (id(app.state.agent), json.dumps(app.state.settings.model_roles, sort_keys=True),
                           json.dumps(asdict(plan), sort_keys=True))
        if not probe:
            # Automatic progress polling never contacts model endpoints.
            # A previous explicit model check remains an observation, not a
            # new verification; changed settings discard it immediately.
            if automation_observation is not None and automation_observation[0] == observation_key:
                return dict(automation_observation[1], pending=pending)
            requested = bool(plan.enabled and plan.with_model and plan.local_model_only)
            legacy = bool(plan.enabled and plan.with_model and not plan.local_model_only)
            return {'state': 'legacy_active' if legacy else 'unverified' if requested else 'paused',
                    'requested': requested, 'pending': pending, 'model': None, 'cloud_modell': None}

        rollen = rollen_von(app)
        # Die Hintergrundarbeit läuft mit dem Anbieter der Rolle `hintergrund`, und der ist immer lokal.
        # Ohne ihn zeigt der Standard nur, warum nichts läuft („nicht lokal“ oder „kein Modell“).
        provider = rollen.provider('hintergrund') or rollen.standard()
        local = bool(getattr(provider, 'is_local', False))
        model = str(getattr(provider, 'model', '') or '').strip()
        requested = bool(plan.enabled and plan.with_model and plan.local_model_only)
        legacy_active = bool(plan.enabled and plan.with_model and not plan.local_model_only)
        # Ein Modell, das Ollama an seinen Server weiterreicht, ist keine lokale KI: eigener Zustand mit Namen.
        cloud_modell = rollen.cloud_modell_im_weg('hintergrund')
        if legacy_active:
            state = 'legacy_active'
        elif cloud_modell:
            state = 'cloud_ueber_ollama'
        elif not model:
            state = 'model_missing'
        elif not local:
            state = 'wrong_model'
        else:
            from .local_model_guard import verify_local_model
            if verified is None:
                try:
                    verify_local_model(provider)
                except ProviderError:
                    verified = False
                else:
                    verified = True
            state = ('active' if requested else 'paused') if verified else 'local_model_unavailable'
        if pending is None:
            from .working_memory_store import WorkingMemoryStore
            pending = WorkingMemoryStore(app.state.episodes).coverage()['pending']
        result = {'state': state, 'requested': requested, 'pending': pending,
                  'model': model if local and model and not cloud_modell else None,
                  'cloud_modell': cloud_modell}
        automation_observation = (observation_key, result)
        return result

    @router.get('/automation')
    def read_automation():
        with app.state.conversation_lock:
            return automation_status()

    @router.put('/automation')
    def set_automation(body: MemoryAutomationIn):
        with app.state.conversation_lock:
            plan = app.state.settings.schedule
            previous = (plan.enabled, plan.with_model, plan.local_model_only)
            provider = hintergrund_anbieter(app)
            if body.enabled:
                modell = str(getattr(provider, 'model', '') or '').strip()
                lokal = bool(getattr(provider, 'is_local', False))
                # Vorgemerkt wird nur, was ohnehin auf diesem Rechner liefe: kein Modell (es lädt noch) oder ein
                # lokales, das noch nicht antwortet. Ein gewähltes Modell im Internet bleibt eine eigene Entscheidung.
                vormerkbar = body.vormerken and automation_status()['state'] in VORMERKBAR
                if not lokal and not vormerkbar:
                    raise HTTPException(409, 'Für die automatische Einordnung muss ein lokales Modell eingerichtet sein.')
                if not modell and not vormerkbar:
                    raise HTTPException(409, 'Bitte zuerst ein lokales Modell einrichten.')
                if lokal and modell:
                    from .local_model_guard import verify_local_model
                    try:
                        verify_local_model(provider)
                    except ProviderError as exc:
                        if not vormerkbar:
                            raise HTTPException(409, 'Ein installiertes lokales Modell konnte nicht bestätigt werden.') from exc
                # `local_model_only` hält jede Modellarbeit auf diesem Rechner, auch wenn später ein anderes Modell kommt.
                plan.enabled = True
                plan.with_model = True
                plan.local_model_only = True
            else:
                # Nur Modellaufgaben pausieren. Aufnahme, Quellenfreigaben und
                # Backups behalten ihre bestehenden Einstellungen.
                plan.with_model = False
            try:
                from .server import _data_dir
                config.save(_data_dir(), app.state.settings)
            except Exception:
                plan.enabled, plan.with_model, plan.local_model_only = previous
                raise
            from .server import _wire_scheduler
            _wire_scheduler(app)
            return automation_status(verified=None if body.vormerken or not body.enabled else True)

    @router.post('/working/{episode_id}/dismiss')
    def dismiss_working(episode_id: str):
        from .working_memory_store import WorkingMemoryStore
        with app.state.conversation_lock:
            try:
                app.state.episodes.get(episode_id)
            except EpisodeError as exc:
                raise HTTPException(status_code=404, detail='Unbekannte Quelle') from exc
            changed = WorkingMemoryStore(app.state.episodes).dismiss(episode_id)
            return {'dismissed': True, 'changed': changed}

    @router.get('/working/{episode_id}/correction')
    def preview_correction(episode_id: str):
        from .source_corrections import preview
        with app.state.conversation_lock:
            try:
                return preview(app.state.episodes, app.state.claims, episode_id)
            except (EpisodeError, ValueError) as exc:
                raise HTTPException(409, str(exc)) from exc

    @router.post('/working/{episode_id}/correction', status_code=201)
    def correct_source(episode_id: str, body: SourceCorrectionIn):
        from .source_corrections import correct
        with app.state.conversation_lock:
            try:
                identifier = correct(app.state.episodes, app.state.claims, episode_id,
                                     body.fingerprint, body.body)
                return {'episode_id': identifier, 'original_excluded': True}
            except EpisodeError as exc:
                raise HTTPException(409, str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc

    @router.get('/timeline')
    def read_timeline(start: datetime | None = None, end: datetime | None = None,
                      basis: Literal['source', 'recorded'] = 'recorded',
                      limit: int = Query(default=100, ge=1, le=500),
                      cursor: str | None = Query(default=None, max_length=2048,
                          description="Bei Fortsetzung start und end aus der ersten Antwort erneut angeben.")):
        now = datetime.now(timezone.utc)
        try:
            if cursor is not None and (start is None or end is None):
                raise ValueError('Für einen Timeline-Cursor müssen start und end aus der ersten Antwort erneut angegeben werden.')
            with app.state.conversation_lock:
                return timeline(app.state.episodes, app.state.claims, start or now - timedelta(days=30),
                                end or now + timedelta(seconds=1), limit, cursor=cursor, basis=basis)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get('/as-known')
    def read_known(known_at: datetime, valid_at: datetime | None = None,
                   reference: str | None = Query(default=None, max_length=300),
                   limit: int = Query(default=100, ge=1, le=500),
                   cursor: str | None = Query(default=None, max_length=2048)):
        try:
            with app.state.conversation_lock:
                return app.state.claims.as_known_at(known_at, episodes=app.state.episodes,
                    valid_at=valid_at, reference=reference, limit=limit, cursor=cursor)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    app.include_router(router)
