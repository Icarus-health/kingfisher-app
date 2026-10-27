"""Bounded task pages from one SQLite read snapshot, with literal Unicode search."""
import base64
import binascii
import hashlib
import json


class TaskPageChanged(ValueError):
    pass


def query_page(connection, view='mine', *, project_id=None, q='', limit=200, cursor=None, ids=None, auswahl=None,
               projekte=None):
    """`ids` begrenzt auf diese Aufgaben (Bereichsfilter, `zaehlung.ids_im_bereich`); `auswahl` benennt diese Begrenzung
    im Stand, damit ein Cursor nur in der Auswahl gilt, aus der er stammt. `projekte` ({Kennung: Name}) lässt die Suche
    auch den Projektnamen finden (Persona-Prüfung, Paket S, Befund 7: „Nordlicht“ fand keine Aufgabe des Projekts
    „Restrukturierung Nordlicht“); gesucht wird außerdem in der Person einer Aufgabe."""
    if view not in ('mine', 'waiting', 'done') or type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError('Ungültige Aufgabenansicht oder Seitengröße.')
    if not isinstance(q, str) or len(q) > 200:
        raise ValueError('Die Suche darf höchstens 200 Zeichen enthalten.')
    terms = q.casefold().split()
    connection.create_function('kf_casefold', 1, lambda value: str(value or '').casefold(), deterministic=True)
    connection.execute('BEGIN')
    try:
        latest = connection.execute('SELECT sequence, recorded_at, task_id FROM task_events ORDER BY sequence DESC LIMIT 1').fetchone()
        state = [list(latest) if latest else [], view, project_id or None, terms, limit]
        if auswahl is not None:
            state.append(auswahl)
        stand = hashlib.sha256(json.dumps(state, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        offset = 0
        if cursor is not None:
            try:
                if not isinstance(cursor, str) or not cursor or len(cursor) > 2048:
                    raise ValueError()
                value = json.loads(base64.b64decode(cursor.encode(), altchars=b'-_', validate=True))
                if not isinstance(value, list) or len(value) != 2 or type(value[0]) is not int or not 0 < value[0] <= 10_000_000 or not isinstance(value[1], str):
                    raise ValueError()
                offset = value[0]
            except (ValueError, UnicodeError, binascii.Error):
                raise ValueError('Die Aufgabenseite ist ungültig. Bitte neu laden.') from None
            if value[1] != stand:
                raise TaskPageChanged('Der Aufgabenbestand oder die Auswahl wurde geändert. Bitte die Liste neu laden.')
        conditions, params = ['status = ?'], ['done' if view == 'done' else 'open']
        waiting = "json_extract(document, '$.wartet_auf')"
        if view != 'done':
            conditions.append(waiting + (' IS NOT NULL' if view == 'waiting' else ' IS NULL'))
        if project_id:
            conditions.append('project_id = ?')
            params.append(project_id)
        if ids is not None:
            conditions.append('id IN (SELECT value FROM json_each(?))')
            params.append(json.dumps(sorted(ids)))
        searchable = ("kf_casefold(title || char(10) || COALESCE(json_extract(document, '$.notes'), '') || char(10) || COALESCE("
                      + waiting + ", '') || char(10) || COALESCE(json_extract(document, '$.person'), ''))")
        namen = {str(k): str(v or '').casefold() for k, v in (projekte or {}).items()}
        for term in terms:
            treffer = sorted(k for k, name in namen.items() if term in name)
            if treffer:
                conditions.append('(instr(' + searchable + ', ?) > 0 OR project_id IN (SELECT value FROM json_each(?)))')
                params.extend([term, json.dumps(treffer)])
            else:
                conditions.append('instr(' + searchable + ', ?) > 0')
                params.append(term)
        where = ' AND '.join(conditions)
        total = connection.execute('SELECT COUNT(*) FROM tasks WHERE ' + where, params).fetchone()[0]
        if cursor is not None and offset >= total:
            raise ValueError('Die Aufgabenseite liegt außerhalb der Auswahl. Bitte neu laden.')
        if view == 'waiting':
            order = "COALESCE(julianday(json_extract(document, '$.wartet_seit')), julianday(created_at)), id"
        elif view == 'done':
            order = "COALESCE(julianday(json_extract(document, '$.done_at')), julianday(created_at)) DESC, id"
        else:
            order = 'due IS NULL, julianday(due), julianday(created_at), id'
        rows = connection.execute('SELECT document FROM tasks WHERE ' + where + ' ORDER BY ' + order + ' LIMIT ? OFFSET ?', [*params, limit, offset]).fetchall()
        next_offset = offset + len(rows)
        next_cursor = base64.urlsafe_b64encode(json.dumps([next_offset, stand], separators=(',', ':')).encode()).decode() if next_offset < total else None
        return {'rows': rows, 'total': total, 'next_cursor': next_cursor, 'stand': stand, 'limit': limit}
    finally:
        connection.rollback()
