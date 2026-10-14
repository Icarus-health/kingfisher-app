"""Vollständige lokale Dokumentablage: keine Graph-, Modell- oder Scanvorschau."""
import json
from contextlib import ExitStack
from datetime import datetime

from .episodes import CHAT_LOOKUP_TAG, AUSGEBLENDETE_ZUSTAENDE, sql_geltend
from .memory_categories import Categories
from .memory_source_search import literal_span


PREVIEW_LIMIT = 240


def _metadata(views):
    """Bestehenden Metadatenspeicher vollständig unter seinem Leselock lesen."""
    folders, assignments = [], {}
    for row in views._conn.execute(
            "SELECT kind,id,document,revision FROM view_records "
            "WHERE (kind='folder' AND document IS NOT NULL) OR kind='source_folder' ORDER BY id"):
        data = json.loads(row['document']) if row['document'] is not None else None
        if row['kind'] == 'folder':
            folders.append({'kind': 'folder', 'id': row['id'], 'revision': row['revision'], 'data': data})
        else:
            assignments[row['id']] = (data['folder_id'] if data else None, row['revision'])
    return folders, assignments


def _descendants(folders, identifier):
    children = {}
    for folder in folders:
        children.setdefault(folder['data']['parent_id'], []).append(folder['id'])
    result, pending = set(), [identifier]
    while pending:
        current = pending.pop()
        if current not in result:
            result.add(current)
            pending.extend(children.get(current, []))
    return result


def _preview(body, query):
    span = literal_span(body, query) if query else None
    start = max(0, span[0] - 60) if span else 0
    return body[start:start + PREVIEW_LIMIT]


def document_page(state, *, q='', folder_id='', project_id='', source_area='', project_area='', offset=0, limit=25):
    """Alle geltenden Dokumente/Notizen lesen, danach exakt filtern und paginieren.

    Die drei Speicher werden nur gelesen. Gemeinsam gehaltene bestehende Locks
    verhindern Zwischenstände bei Quellenentzug, Notizänderung oder Zuordnung.
    Vollständiger Suchtext bleibt im lokalen Speicher; Antworten tragen Auszüge.
    """
    episodes, workspace, views = state.episodes, state.workspace, state.workspace_views
    folded = q.strip().casefold()
    with ExitStack() as stack:
        stack.enter_context(state.conversation_lock)
        stack.enter_context(episodes._lock)
        stack.enter_context(workspace._lock)
        stack.enter_context(views._lock)
        folders, assignments = _metadata(views)
        descendants = _descendants(folders, folder_id) if folder_id and folder_id != 'unassigned' else set()
        project_rows = workspace._conn.execute(
            "SELECT id,area,status,json_extract(document,'$.name') AS name FROM projects").fetchall()
        projects = {row['id']: dict(row) for row in project_rows}
        # Unanalysierte Dokumente haben keine Kategorie. Vorhandene Hinweise und
        # explizite Korrekturen immer über den Fingerprint-geprüften Kern lesen.
        annotated = {row[0] for row in episodes._conn.execute(
            "SELECT episode_id FROM memory_category_sources UNION SELECT episode_id FROM memory_category_corrections")}
        categories = Categories(episodes)
        options_projects, options_source_areas, options_project_areas = {}, {}, set()
        matches = []

        def consider(identifier, kind, title, body, project, moment, source_areas, revision=None):
            record = projects.get(project)
            area = record['area'] if record else None
            folder, folder_revision = assignments.get(identifier, (None, 0))
            if record:
                options_projects[project] = {'id': project, 'name': record['name'], 'status': record['status']}
            if area:
                options_project_areas.add(area)
            for category in source_areas:
                options_source_areas[category['id']] = category['label']
            if (folded and folded not in title.casefold() and folded not in body.casefold()
                    or project_id and project != project_id
                    or project_area and area != project_area
                    or source_area and source_area not in {item['id'] for item in source_areas}
                    or folder_id == 'unassigned' and folder is not None
                    or folder_id and folder_id != 'unassigned' and folder not in descendants):
                return
            matches.append({'id': identifier, 'kind': kind, 'title': title,
                'preview': _preview(body, folded), 'project_id': project,
                'project_name': record['name'] if record else None, 'project_area': area,
                'source_areas': [item['id'] for item in source_areas], 'folder_id': folder,
                'source_folder_revision': folder_revision, 'revision': revision, 'recorded_at': moment})

        rows = episodes._conn.execute(
            f"SELECT e.id FROM episodes e WHERE {sql_geltend('e')} "
            "AND e.kind='document' AND e.state != 'archived' "
            "AND NOT EXISTS (SELECT 1 FROM json_each(e.document,'$.tags') tag WHERE tag.value=?)",
            (CHAT_LOOKUP_TAG,))
        for row in rows:
            try:
                snapshot = episodes.support_snapshot(row['id'])
            except ValueError:
                continue  # Unstimmige/entzogene Belege niemals als aktuell anbieten.
            if not snapshot or not snapshot.current() or snapshot.episode.state in AUSGEBLENDETE_ZUSTAENDE:
                continue
            episode = snapshot.episode
            hints = categories.list_for(episode.id)['categories'] if episode.id in annotated else []
            consider('episode:' + episode.id, 'episode', episode.title, episode.body,
                episode.project_id, (episode.occurred_at or episode.recorded_at).isoformat(), hints)
        for row in workspace._conn.execute(
                "SELECT id,title,body,project_id,updated_at,json_extract(document,'$.revision') AS revision "
                "FROM notes n WHERE NOT EXISTS (SELECT 1 FROM json_each(n.document,'$.tags') tag WHERE tag.value=?)",
                (CHAT_LOOKUP_TAG,)):
            consider('note:' + row['id'], 'note', row['title'], row['body'], row['project_id'], row['updated_at'], [], row['revision'])
        matches.sort(key=lambda item: (datetime.fromisoformat(item['recorded_at']).timestamp(), item['id']), reverse=True)
        total = len(matches)
        return {'items': matches[offset:offset + limit], 'total': total,
            'has_more': offset + limit < total, 'limit': limit, 'offset': offset,
            'options': {'folders': folders,
                'projects': sorted(options_projects.values(), key=lambda item: (item['name'].casefold(), item['id'])),
                'source_areas': [{'id': key, 'label': value} for key, value in sorted(options_source_areas.items())],
                'project_areas': sorted(options_project_areas)}}


def register(app, guard):
    from fastapi import HTTPException, Query

    @app.get('/api/v1/workspace-document-folders', dependencies=guard)
    def folders():
        try:
            views = app.state.workspace_views
            with views._lock:
                rows = views._conn.execute(
                    "SELECT id,document,revision FROM view_records WHERE kind='folder' AND document IS NOT NULL ORDER BY id")
                return {'folders': [{'kind': 'folder', 'id': row['id'], 'revision': row['revision'],
                    'data': json.loads(row['document'])} for row in rows]}
        except Exception:
            raise HTTPException(503, 'Ordner gerade nicht erreichbar. Bitte erneut laden.') from None

    @app.get('/api/v1/workspace-documents', dependencies=guard)
    def documents(q: str = Query('', max_length=200), folder_id: str = Query('', max_length=1000),
            project_id: str = Query('', max_length=1000), source_area: str = Query('', max_length=1000),
            project_area: str = Query('', max_length=1000), offset: int = Query(0, ge=0, le=100_000_000),
            limit: int = Query(25, ge=1, le=100)):
        try:
            return document_page(app.state, q=q, folder_id=folder_id, project_id=project_id,
                source_area=source_area, project_area=project_area, offset=offset, limit=limit)
        except Exception:
            # Keine Pfade, Inhalte oder fremden Fehlermeldungen in UI/Antwort.
            raise HTTPException(503, 'Dokumentablage gerade nicht erreichbar. Bitte erneut laden.') from None
