"""Lokale Anzeigegruppen: Namen sind Hinweise, keine Unternehmensidentitäten.

Keine Netz-/Modellaufrufe und keine neue Faktenablage. Vollständige Bezüge und
reversible WorkspaceViews werden unmittelbar vor jedem Schreiben geprüft.
"""
import hashlib
import json
import re
from contextlib import contextmanager

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from .akten_routes import bausteine
from .bezuege import FINGERABDRUCK, GUELTIG_PARAMS
from .workspace_views import ViewChanged


# Ausschließlich begrenzte Anzeigevarianten; beliebige Geschäftszweige werden
# nicht anhand eines gemeinsamen ersten Worts verbunden.
_SUFFIXES = frozenset({'de', 'com', 'net', 'org', 'eu', 'uk', 'co', 'germany', 'deutschland',
                       'digital', 'service', 'services', 'gmbh', 'inc', 'ltd', 'se', 'ag', 'limited'})
_GENERIC = frozenset({'digital', 'service', 'services', 'company', 'group', 'global', 'international',
                      'deutsche', 'deutsch', 'deutschen', 'health', 'medical', 'media', 'mail', 'shop',
                      'bank', 'klinik', 'stadt', 'verein', 'online', 'the', 'die', 'der', 'das'})
_DOMAIN = re.compile(r'^(?:www\.)?([\w-]+)\.(?:de|com|net|org|eu|co\.uk|uk)$', re.I)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _name_key(name):
    name = name.strip().casefold()
    domain = _DOMAIN.fullmatch(name)
    if domain:
        return domain[1], True
    tokens = re.findall(r'[^\W_]+', name, re.UNICODE)
    if not tokens or len(tokens[0]) < 4 or tokens[0] in _GENERIC:
        return None
    if any(token not in _SUFFIXES for token in tokens[1:]):
        return None
    return tokens[0], len(tokens) == 1


def candidates(entries):
    """Reiner, deterministischer Kandidatenbau mit Wortgrenze und kurzem Anker."""
    buckets = {}
    for entry in sorted(entries, key=lambda value: value['id']):
        key = _name_key(entry['name'])
        if key and len(key[0]) >= 4 and key[0] not in _GENERIC:
            buckets.setdefault(key[0], []).append((entry, key[1]))
    result = []
    for root, rows in sorted(buckets.items()):
        if not 2 <= len(rows) <= 200 or not any(anchor for _, anchor in rows):
            continue
        members = sorted(entry['id'] for entry, _ in rows)
        names = sorted({entry['name'] for entry, _ in rows}, key=lambda name: (len(name), name.casefold()))
        identifier = digest(['organisation-display-v1', [(entry['id'], entry['name']) for entry, _ in rows]])
        result.append({'id': identifier, 'name': names[0].split('.')[0], 'members': members,
                       'reason': f'Lokale Namensregel: ähnliche Namen mit dem vollständigen Wort „{root}“ und begrenzten Namenszusätzen. Keine Prüfung von Rechtsperson oder Konzernzugehörigkeit.'})
    return result


def _records(store):
    # items/index haben absichtlich eine Anzeigegrenze von 2000; hier wird
    # einschließlich Tombstones vollständig geprüft, damit Undo CAS erhält.
    rows = store._conn.execute("SELECT kind,id,document,revision FROM view_records WHERE kind IN ('organisation_group','organisation_group_dismissal') ORDER BY kind,id").fetchall()
    return [{'kind': row['kind'], 'id': row['id'], 'revision': row['revision'],
             'data': json.loads(row['document']) if row['document'] is not None else None} for row in rows]


def _snapshot(app, bezuege, register_token):
    if bezuege.offene_zaehlen(register_token):
        raise HTTPException(409, 'Die Organisationsbasis wird aktualisiert. Bitte erneut laden.')
    # Alle geltenden aktuellen Quellen, korrigierte Zuordnungen gewinnen.
    rows = bezuege._conn.execute('SELECT l.sache, l.episode_id, ' + FINGERABDRUCK +
            ' AS fp FROM (' + bezuege._links() + ") l JOIN episodes e ON e.id=l.episode_id WHERE l.sache LIKE 'organisation:%' ORDER BY l.sache,l.episode_id",
            (*GUELTIG_PARAMS, *GUELTIG_PARAMS)).fetchall()
    by_id = {}
    for row in rows:
        by_id.setdefault(row['sache'], []).append([row['episode_id'], row['fp']])
    entries = [{'id': identifier, 'name': bezuege.beschriftung(identifier), 'sources': sources}
               for identifier, sources in sorted(by_id.items())]
    records = _records(app.state.workspace_views)
    groups = [row for row in records if row['kind'] == 'organisation_group' and row['data'] is not None]
    grouped = {member for group in groups for member in group['data']['members']}
    dismissed = {row['id'] for row in records if row['kind'] == 'organisation_group_dismissal' and row['data']}
    all_candidates = candidates(entries)
    candidate_names = {row['id']: row['name'] for row in all_candidates}
    suggestions = [row for row in all_candidates if row['id'] not in dismissed and not grouped.intersection(row['members'])]
    return {'entries': entries, 'total': len(entries), 'complete': True, 'suggestions': suggestions,
            'groups': groups, 'dismissals': [{**row, 'name': candidate_names.get(row['id'])} for row in records if row['kind'] == 'organisation_group_dismissal' and row['data']],
            'source_revision': digest(entries), 'groups_revision': digest(records)}


@contextmanager
def _current(app):
    # Registerbau vor der Episode-Sperre vermeidet eine umgekehrte Lockreihenfolge
    # zum bestehenden deterministischen Bezüge-Hintergrundfaden.
    with app.state.conversation_lock:
        bezuege, _ = bausteine(app)
        bezuege.aktualisieren()
        register_token = bezuege.register().token
        store = app.state.workspace_views
        with app.state.episodes._lock, store._lock:
            yield _snapshot(app, bezuege, register_token), store


class Basis(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_revision: str = Field(pattern=r'^[a-f0-9]{64}$')
    groups_revision: str = Field(pattern=r'^[a-f0-9]{64}$')


class Confirmation(Basis):
    candidate_id: str | None = Field(None, pattern=r'^[a-f0-9]{64}$')
    group_id: str | None = Field(None, min_length=1, max_length=1000)
    group_revision: StrictInt = Field(0, ge=0)
    name: str = Field(min_length=1, max_length=200)
    members: list[str] = Field(min_length=2, max_length=200)


def _basis(body, snapshot, *, groups=True):
    if body.source_revision != snapshot['source_revision'] or (groups and body.groups_revision != snapshot['groups_revision']):
        raise HTTPException(409, 'Quelle, Organisationsnamen oder Gruppen wurden verändert. Bitte Vorschau erneut prüfen.')


def register(app, guard):
    @app.get('/api/v1/organisation-group-suggestions', dependencies=guard)
    def overview():
        with _current(app) as (snapshot, _):
            # Fingerprints enthalten keine Quelltexte; die UI braucht nur Namen.
            return {**snapshot, 'entries': [{'id': row['id'], 'name': row['name']} for row in snapshot['entries']]}

    @app.post('/api/v1/organisation-group-suggestions/confirm', dependencies=guard)
    def confirm(body: Confirmation):
        if not body.name.strip() or len(set(body.members)) != len(body.members):
            raise HTTPException(422, 'Bitte einen Namen und unterschiedliche Organisationen wählen.')
        with _current(app) as (snapshot, store):
            _basis(body, snapshot, groups=False)
            if not set(body.members).issubset({row['id'] for row in snapshot['entries']}):
                raise HTTPException(409, 'Eine ausgewählte Organisation hat keine aktuelle zulässige Quelle mehr.')
            target = body.group_id or digest(['organisation-display-group-v1', sorted(body.members)])
            current = store.get('organisation_group', target)
            data = {'name': body.name.strip(), 'members': sorted(body.members)}
            # Derselbe bestätigte Klick bleibt auch nach Neustart idempotent,
            # ohne zwischenzeitliche Änderungen des Nutzers zu überschreiben.
            if current['data'] == data and (body.group_id is None or current['revision'] == body.group_revision + 1):
                return current
            _basis(body, snapshot)
            if body.group_id is None and current['data'] is not None:
                raise HTTPException(409, 'Diese Anzeigegruppe besteht bereits. Bitte ausdrücklich die bestehende Gruppe bearbeiten.')
            if body.group_id is not None and current['revision'] != body.group_revision:
                raise HTTPException(409, 'Diese Anzeigegruppe wurde geändert. Bitte neu prüfen.')
            if body.candidate_id and not any(row['id'] == body.candidate_id for row in snapshot['suggestions']):
                raise HTTPException(409, 'Dieser Vorschlag ist nicht mehr aktuell oder wurde bereits entschieden.')
            if any(group['id'] != target and set(group['data']['members']).intersection(body.members) for group in snapshot['groups']):
                raise HTTPException(409, 'Eine ausgewählte Organisation gehört bereits zu einer bestätigten Anzeigegruppe.')
            try:
                return store.put('organisation_group', target, data, current['revision'])
            except ViewChanged as exc:
                raise HTTPException(409, str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc

    @app.post('/api/v1/organisation-group-suggestions/{identifier}/dismiss', dependencies=guard)
    def dismiss(identifier: str, body: Basis):
        with _current(app) as (snapshot, store):
            _basis(body, snapshot, groups=False)
            current = store.get('organisation_group_dismissal', identifier)
            if current['data'] == {'dismissed': True}:
                return current
            _basis(body, snapshot)
            if not any(row['id'] == identifier for row in snapshot['suggestions']):
                raise HTTPException(409, 'Dieser Vorschlag wurde geändert. Bitte neu laden.')
            try:
                return store.put('organisation_group_dismissal', identifier, {'dismissed': True}, current['revision'])
            except ViewChanged as exc:
                raise HTTPException(409, str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc

    class UndoDismissal(BaseModel):
        model_config = ConfigDict(extra='forbid')
        revision: StrictInt = Field(ge=1)

    @app.post('/api/v1/organisation-group-suggestions/{identifier}/undo-dismissal', dependencies=guard)
    def undo_dismissal(identifier: str, body: UndoDismissal):
        try:
            return app.state.workspace_views.undo('organisation_group_dismissal', identifier, body.revision)
        except ViewChanged as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
