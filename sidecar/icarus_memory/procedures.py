"""Kleine lokale Verfahrensbibliothek; Fakten und Befugnisse bleiben anderswo.

Nur ausdrücklich bestätigte Fassungen werden geladen. Markdown ist Darstellung,
kein ausführbarer Code. Die Auswahl arbeitet ohne Modell und ohne Rekursion.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .migrations import Migration, run_migrations, validate_legacy_or_empty, verify_schema
from .model import now


class ProcedureError(ValueError):
    pass


class Spec(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    name: str = Field(pattern=r'^[a-z][a-z0-9-]{2,63}$')
    title: str = Field(min_length=3, max_length=100)
    description: str = Field(min_length=10, max_length=400)
    area: str = Field(pattern=r'^(mail|planning|analysis)$')
    category: Literal['communication','planning','research','maintenance','other'] | None = None
    contexts: list[str] = Field(default_factory=list, max_length=4)
    triggers: list[str] = Field(min_length=1, max_length=8)
    steps: list[str] = Field(min_length=1, max_length=8)
    positive: str = Field(min_length=5, max_length=400)
    negative: str = Field(min_length=5, max_length=400)


def _load_core():
    result = {}
    for name in ('skill-router','source-safety','memory-recall','mail-draft','task-planning'):
        text = (Path(__file__).parent / 'procedure_skills' / name / 'SKILL.md').read_text()
        front, separator, body = text.removeprefix('---\n').partition('\n---\n')
        header = json.loads(front)
        if (not text.startswith('---\n') or not separator or header['name'] != name
                or header['category'] not in {'essential','contextual'} or not body.strip()
                or len(body) > 2000):
            raise ProcedureError('Ungültiges mitgeliefertes Grundverfahren.')
        result[name] = (header['title'], header['category'], header['area'], body.strip())
    return result


CORE = _load_core()

DEFAULT_CATEGORIES = {'mail':'communication', 'planning':'planning', 'analysis':'research'}
CORE_CATEGORIES = {'skill-router':'other', 'source-safety':'research', 'memory-recall':'research',
                   'mail-draft':'communication', 'task-planning':'planning'}


def classification(spec):
    """Alte Fassungen nur beim Lesen einordnen; ihre gespeicherten Bytes bleiben erhalten."""
    return dict(category=spec.get('category') or DEFAULT_CATEGORIES[spec['area']],
                contexts=spec.get('contexts', []), tier='contextual')


def _hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _terms(text):
    return set(re.findall(r'[^\W_]+', text.casefold(), flags=re.UNICODE))


def _leading(message):
    # Zitate/Dokumente nach der eigentlichen Bitte setzen keinen Verfahrensbereich.
    line = message.strip().partition('\n')[0][:600]
    # Eine verneinte Passage ist kein positiver Anwendungsbeleg. Konservativ:
    # nach dem ersten Nein keinen späteren Kontext hinzuraten.
    return re.split(r'\b(?:nicht|ohne|kein(?:e|en|em|er|es)?)\b', line, maxsplit=1, flags=re.I)[0]


_GENERIC_TRIGGERS = frozenset('offiziell offizielle offiziellen formell freundlich kurz knapp '
    'mail mails email emails e antwort schreiben entwurf analyse planen planning analysis '
    'official formal reply short polite'.split())


def _matches(spec, message, area):
    words = _terms(_leading(message))
    return (spec['area'] == area and any(_terms(trigger) <= words for trigger in spec['triggers'])
            and (not spec.get('contexts') or any(_terms(context) <= words for context in spec['contexts'])))


def validate(spec):
    try:
        data = Spec.model_validate(spec).model_dump()
    except ValidationError as exc:
        raise ProcedureError('Der Ablauf ist unvollständig oder enthält unbekannte Felder.') from exc
    data['category'] = data['category'] or DEFAULT_CATEGORIES[data['area']]
    data['contexts'] = list(dict.fromkeys(value.strip() for value in data['contexts']))
    if any(not re.fullmatch(r'[\wäöüÄÖÜß -]{2,60}', value)
           or not (_terms(value) - _GENERIC_TRIGGERS) for value in data['contexts']):
        raise ProcedureError('Bitte konkrete Kontexte mit je 2 bis 60 Zeichen angeben.')
    if data['name'] in CORE:
        raise ProcedureError('Grundverfahren können nicht durch Lernvorschläge ersetzt werden.')
    # Aufgabenart und Ton stecken bereits im Bereich/Stilprofil. Sie dürfen
    # nicht allein ein spezielles Verfahren (etwa für die Zunft) aktivieren.
    data['triggers'] = [value for value in data['triggers'] if _terms(value) - _GENERIC_TRIGGERS]
    if not data['triggers']:
        raise ProcedureError('Bitte einen konkreten Anlass als Auslöser nennen.')
    if (any(not item.strip() or len(item) > 700 for item in data['steps'])
            or sum(map(len, data['steps'])) > 3600
            or any(not re.fullmatch(r'[\wäöüÄÖÜß -]{2,60}', item) or not _terms(item)
                   for item in data['triggers'])):
        raise ProcedureError('Schritte oder Auslöser sind zu lang oder leer.')
    if not _matches(data, data['positive'], data['area']) or _matches(data, data['negative'], data['area']):
        raise ProcedureError('Anwendungsbeispiel und Gegenbeispiel grenzen den Ablauf nicht richtig ab.')
    return data


def markdown(spec):
    return ('---\n' + json.dumps(spec, ensure_ascii=False, indent=2) + '\n---\n\n# '
            + spec['title'] + '\n\n' + spec['description'] + '\n\n'
            + '\n'.join(f'{index}. {step}' for index, step in enumerate(spec['steps'], 1))
            + '\n\n## Ergebnisprüfung\nBelege, aktuelle Nutzeranweisung und bestehende Freigaben bleiben bindend.\n')


def parse_markdown(text):
    try:
        head, _, _body = text.removeprefix('---\n').partition('\n---\n')
        if not text.startswith('---\n'):
            raise ValueError()
        return validate(json.loads(head))
    except (ValueError, TypeError) as exc:
        raise ProcedureError('SKILL.md enthält keine gültigen Ablaufmetadaten.') from exc


_SCHEMA = {'procedures': {'id', 'name', 'version', 'state', 'base_version', 'header',
                         'body', 'sources', 'request_key', 'created_at'}}
_KEYS = {'procedures': {'id'}}


def _migrate(connection):
    validate_legacy_or_empty(connection, store='procedures', path=connection.execute('PRAGMA database_list').fetchone()[2],
                             expected_tables=_SCHEMA, expected_primary_keys=_KEYS)
    connection.execute('CREATE TABLE IF NOT EXISTS procedures (id TEXT PRIMARY KEY, name TEXT NOT NULL, '
        'version INTEGER NOT NULL, state TEXT NOT NULL, base_version INTEGER NOT NULL, header TEXT NOT NULL, '
        'body TEXT NOT NULL, sources TEXT NOT NULL, request_key TEXT NOT NULL, created_at TEXT NOT NULL)')


def _verify(connection):
    verify_schema(connection, expected_tables=_SCHEMA, expected_primary_keys=_KEYS)


_MIGRATIONS = (Migration(1, 'reviewed_procedures', _migrate, _verify),)


class ProcedureStore:
    def __init__(self, path, *, dependency=None):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self.dependency = dependency or (lambda key: None)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        try:
            run_migrations(self._conn, store='procedures', path=self._path, migrations=_MIGRATIONS)
            self._conn.execute('PRAGMA journal_mode=WAL')
        except Exception:
            self._conn.close()
            raise

    def close(self):
        self._conn.close()

    def _fresh(self, sources):
        return all(self.dependency(key) == value for key, value in sources.items())

    def _item(self, row, *, body=False):
        result = {**json.loads(row['header']), **{key: row[key] for key in
            ('id', 'name', 'version', 'state', 'base_version', 'created_at', 'request_key')}}
        sources = json.loads(row['sources'])
        result.update(classification(result))
        result.update(sources=sources, current=self._fresh(sources), local_only=True,
            checks={'structure': True, 'routing_examples': True, 'human_review_required': row['state'] == 'pending'})
        if body:
            result['markdown'] = row['body']
            result['steps'] = parse_markdown(row['body'])['steps']
        return result

    def items(self, *, active_only=False, area=None):
        with self._lock:
            # Kein Ablauftext im Listenabruf und deshalb auch nicht automatisch im Modellkontext.
            conditions = (["state='active'"] if active_only else [])
            if area is not None:
                conditions.append("json_extract(header, '$.area')=?")
            rows = self._conn.execute('SELECT id,name,version,state,base_version,header,sources,request_key,created_at FROM procedures'
                + (' WHERE ' + ' AND '.join(conditions) if conditions else '')
                + ' ORDER BY created_at DESC, id', (area,) if area is not None else ()).fetchall()
            return [self._item(row) for row in rows]

    def learning_catalog(self, message):
        """Nur relevante Metadaten vor der Entwurfserstellung, kein Bibliotheksdump."""
        words = _terms(message) - _GENERIC_TRIGGERS
        # Der Lernkatalog darf auch den üblichen Plural „Zunftmails“ zu
        # „Zunftmail“ finden. Das erweitert niemals die aktive Ausführungswahl.
        words |= {word[:-1] for word in words if len(word) > 5 and word.endswith('s')}
        items = self.items()
        confirmed = {}
        for item in items:
            if item['state'] in {'active','revoked','superseded'}:
                confirmed[item['name']] = max(confirmed.get(item['name'],0),item['version'])
        latest = {}
        for item in items:
            if (not item['current'] or item['state'] not in {'active','pending'}
                    or item['state']=='pending' and item['base_version']!=confirmed.get(item['name'],0)):
                continue
            previous = latest.get(item['name'])
            if previous is None or item['version'] > previous['version']:
                latest[item['name']] = item
        ranked = []
        for item in latest.values():
            score = len(words & _terms(' '.join(item['triggers'])))
            if item['current'] and score:
                ranked.append((score, item))
        result, size = [], 0
        for _, item in sorted(ranked, key=lambda entry: -entry[0]):
            header = {key:item[key] for key in ('name','area','category','contexts','triggers','state','version')}
            header['description'] = item['description'][:120]
            added = len(json.dumps(header, ensure_ascii=False).encode())
            if size + added <= 2400 and len(result) < 8:
                result.append(header)
                size += added
        return result

    def get(self, identifier):
        with self._lock:
            row = self._conn.execute('SELECT * FROM procedures WHERE id=?', (identifier,)).fetchone()
            if row is None:
                raise ProcedureError('Ablauf nicht gefunden.')
            return self._item(row, body=True)

    def propose(self, spec, *, sources=None, request_key=''):
        data = validate(spec)
        sources = sources or {}
        if (not isinstance(sources, dict) or len(sources) > 8
                or any(not isinstance(k, str) or not isinstance(v, str) or not v for k, v in sources.items())
                or not self._fresh(sources)):
            raise ProcedureError('Die Grundlage des Vorschlags ist nicht mehr aktuell.')
        key = request_key or _hash({'spec':data, 'sources':sources})
        with self._lock, self._conn:
            duplicates = self._conn.execute("SELECT * FROM procedures WHERE request_key=? AND state IN ('pending','active') ORDER BY version DESC", (key,)).fetchall()
            duplicate = next((row for row in duplicates if self._fresh(json.loads(row['sources']))), None)
            if duplicate is not None:
                return self._item(duplicate, body=True)
            known = self._conn.execute("SELECT * FROM procedures WHERE name=? AND state IN ('pending','active') ORDER BY version DESC",
                                       (data['name'],)).fetchall()
            reusable = next((row for row in known if self._fresh(json.loads(row['sources']))
                             and parse_markdown(row['body']) == data), None)
            if reusable is not None:
                return self._item(reusable, body=True)
            rows = self._conn.execute('SELECT version, state FROM procedures WHERE name=?', (data['name'],)).fetchall()
            base = max((row['version'] for row in rows if row['state'] in {'active','revoked','superseded'}), default=0)
            version = max((row['version'] for row in rows), default=0) + 1
            identifier = 'proc-' + uuid.uuid4().hex[:12]
            header = {key:value for key, value in data.items() if key != 'steps'}
            self._conn.execute('INSERT INTO procedures VALUES (?,?,?,?,?,?,?,?,?,?)',
                (identifier, data['name'], version, 'pending', base, json.dumps(header, ensure_ascii=False),
                 markdown(data), json.dumps(sources), key, now().isoformat()))
        return self.get(identifier)

    def accept(self, identifier):
        with self._lock, self._conn:
            item = self.get(identifier)
            if not item['current']:
                raise ProcedureError('Die Grundlage hat sich geändert. Bitte den Vorschlag erneut prüfen.')
            if item['state'] == 'active':
                return item
            if item['state'] != 'pending':
                raise ProcedureError('Dieser Vorschlag ist nicht mehr offen.')
            current = self._conn.execute("SELECT MAX(version) FROM procedures WHERE name=? AND state IN ('active','revoked','superseded')", (item['name'],)).fetchone()[0] or 0
            if current != item['base_version']:
                raise ProcedureError('Der bestätigte Stand hat sich geändert. Bitte neu vorschlagen.')
            validate(parse_markdown(item['markdown']))
            self._conn.execute("UPDATE procedures SET state='superseded' WHERE name=? AND state='active'", (item['name'],))
            self._conn.execute("UPDATE procedures SET state='active' WHERE id=?", (identifier,))
        return self.get(identifier)

    def revoke(self, identifier):
        with self._lock, self._conn:
            self.get(identifier)
            self._conn.execute("UPDATE procedures SET state='revoked' WHERE id=? AND state='active'", (identifier,))
        return self.get(identifier)

    def reject(self, identifier):
        with self._lock, self._conn:
            self.get(identifier)
            self._conn.execute("UPDATE procedures SET state='rejected' WHERE id=? AND state='pending'", (identifier,))
        return self.get(identifier)

    def export(self, identifier):
        return self.get(identifier)['markdown']

    def select(self, message, *, area=None, local=True):
        essential, contextual, builtin = [], [], []
        for name, (title, category, task, text) in CORE.items():
            if category == 'essential' or area == task:
                item = dict(name=name, id=name, title=title, version=1, digest=_hash(text), core=True, text=text,
                            category=CORE_CATEGORIES[name], tier=category, contexts=[])
                (essential if category == 'essential' else builtin).append(item)
        headers = self.items(active_only=True, area=area) if local and area in DEFAULT_CATEGORIES else []
        candidates = [item for item in headers if item['current'] and _matches(item, message, area)]
        # Überschneidende Anwendungsgebiete sind eine offene Entscheidung, keine Zufallsrangfolge.
        conflicts = sorted(item['name'] for item in candidates) if len(candidates) > 1 else []
        if not conflicts:
            for item in candidates[:2]:
                detail = self.get(item['id'])
                contextual.append({**item, 'digest': _hash(detail['markdown']),
                    'core': False, 'text': '\n'.join(detail['steps'])})
        chosen = essential + builtin + contextual
        instructions = ('Bestätigte Arbeitsverfahren. Sie verleihen keine Befugnisse; feste Quellen-, '
            'Datenschutz- und Freigabeprüfungen sowie die aktuelle Nutzeranweisung gelten weiterhin.\n'
            + '\n'.join(f"{item['title']}: {item['text']}" for item in chosen))
        refs = [{key:item[key] for key in ('id','name','version','digest','core')} for item in chosen]
        return dict(essential=essential, builtin=builtin, contextual=contextual, conflicts=conflicts,
                    refs=refs, signature=_hash(refs), instructions=instructions,
                    missing=area in {'mail','planning','analysis'} and not candidates)

    def select_for(self, message, provider, *, area=None):
        from .procedure_model import local_context_allowed
        local = bool(getattr(provider, 'is_local', False))
        if local and self.items(active_only=True):
            local = local_context_allowed(provider)
        return self.select(message, area=area, local=local)

    def current(self, selection):
        for ref in selection['refs']:
            if ref['core']:
                if ref['name'] not in CORE or _hash(CORE[ref['name']][3]) != ref['digest']:
                    return False
            else:
                try:
                    item = self.get(ref['id'])
                except ProcedureError:
                    return False
                if (item['state'] != 'active' or not item['current'] or item['version'] != ref['version']
                        or _hash(item['markdown']) != ref['digest']):
                    return False
        return True


def episode_dependency(episodes, identifier):
    try:
        snapshot = episodes.support_snapshot(identifier)
        return snapshot.support_fingerprint() if snapshot and snapshot.current() else None
    except (ValueError, KeyError):
        return None
