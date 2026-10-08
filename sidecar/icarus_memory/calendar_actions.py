"""Explicit, durable Google Calendar event actions.

No action is sent while preparing a draft. A confirmed draft is claimed in
SQLite before any network call; ambiguous edits and cancellations stay blocked.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import closing
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import httpx

from . import config
from .datumstext import iso_lesen_streng
from .google_oauth import CALENDAR_URL, SCOPES, GoogleError

UPDATES = {'all', 'externalOnly', 'none'}


class ActionError(ValueError):
    def __init__(self, message, status=422):
        super().__init__(message)
        self.status = status


class ProviderError(Exception):
    def __init__(self, status=None):
        self.status = status


class GoogleProvider:
    """Fixed Google endpoints only; provider bodies and bearer tokens stay private."""
    def __init__(self, oauth): self.oauth = oauth

    def _request(self, method, source, key, path, *, params=None, body=None, etag=None):
        try:
            token = self.oauth.access_token(key)
        except GoogleError:
            raise ProviderError(401) from None
        headers = {'Authorization': 'Bearer ' + token}
        if etag:
            headers['If-Match'] = etag
        url = CALENDAR_URL + path
        try:
            with httpx.Client(timeout=25, follow_redirects=False) as client:
                response = client.request(method, url, headers=headers, params=params, json=body)
                response.raise_for_status()
                return response.json() if response.content else None
        except httpx.HTTPStatusError as exc:
            raise ProviderError(exc.response.status_code) from None
        except (httpx.HTTPError, ValueError):
            raise ProviderError() from None

    @staticmethod
    def _calendar_path(source):
        return '/calendars/' + quote(source.url, safe='')

    def calendar(self, source, key):
        return self._request('GET', source, key, '/users/me/calendarList/' + quote(source.url, safe=''))

    def event(self, source, key, event_id):
        try:
            return self._request('GET', source, key, self._calendar_path(source) + '/events/' + quote(event_id, safe=''))
        except ProviderError as exc:
            if exc.status == 404:
                return None
            raise

    def create(self, source, key, body, updates):
        return self._request('POST', source, key, self._calendar_path(source) + '/events',
                             params={'sendUpdates': updates}, body=body)

    def patch(self, source, key, event_id, etag, body, updates):
        return self._request('PATCH', source, key,
            self._calendar_path(source) + '/events/' + quote(event_id, safe=''),
            params={'sendUpdates': updates}, body=body, etag=etag)

    def delete(self, source, key, event_id, etag, updates):
        return self._request('DELETE', source, key,
            self._calendar_path(source) + '/events/' + quote(event_id, safe=''),
            params={'sendUpdates': updates}, etag=etag)


def _event_time(value):
    if not isinstance(value, str):
        raise ActionError('Beginn und Ende müssen eine Zeitzone enthalten.')
    try:
        stamp = iso_lesen_streng(value)
    except ValueError:
        raise ActionError('Ungültige Terminzeit.') from None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ActionError('Beginn und Ende müssen eine Zeitzone enthalten.')
    return stamp


def _times(title, start, end):
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 500:
        raise ActionError('Bitte einen Termintitel angeben (höchstens 500 Zeichen).')
    if _event_time(end) <= _event_time(start):
        raise ActionError('Das Ende muss nach dem Beginn liegen.')
    return {'summary': title.strip(), 'start': {'dateTime': start}, 'end': {'dateTime': end}}


def _public(record):
    return {key: record[key] for key in ('id', 'status', 'kind', 'source_id', 'stand',
        'provider_event_id', 'preview') if key in record}


class CalendarActions:
    def __init__(self, path: Path, settings, oauth, provider=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.settings, self.oauth = settings, oauth
        self.provider = provider or GoogleProvider(oauth)
        with closing(self._db()) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS actions (id TEXT PRIMARY KEY, status TEXT NOT NULL, record TEXT NOT NULL)')

    def _db(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        return db

    def _source(self, source_id):
        source = next((s for s in self.settings().calendar_sources if s.id == source_id), None)
        if not source or source.kind != 'google' or not source.enabled or not source.configured:
            raise ActionError('Diese Google-Kalenderquelle ist nicht mehr verfügbar.', 409)
        key = config.integration_secret_name('calendar', source.id)
        raw = self.oauth.keychain.get(key)
        try:
            grant = json.loads(raw or '')
            scopes = set(grant['scope'].split())
            if grant.get('kind') != 'calendar_write' or not SCOPES['calendar_write'].issubset(scopes):
                raise ValueError()
            if not grant.get('refresh_token') or not grant.get('grant_id'):
                raise ValueError()
        except (ValueError, KeyError, TypeError, AttributeError):
            raise ActionError('Für diesen Kalender fehlt die ausdrücklich freigegebene Schreibberechtigung.', 409) from None
        # Grant ID survives refresh-token rotation but changes on reauthorization.
        # Never return this digest to clients.
        binding = hashlib.sha256(json.dumps([source.id, source.url, source.user,
            grant.get('client_id'), grant['grant_id'], sorted(scopes)], separators=(',', ':')).encode()).hexdigest()
        return source, key, binding

    def sources(self):
        result = []
        for source in self.settings().calendar_sources:
            if source.kind != 'google':
                continue
            try:
                self._source(source.id)
                writable, reason = True, None
            except ActionError as exc:
                writable, reason = False, str(exc)
            result.append({'id': source.id, 'label': source.label, 'user': source.user,
                'calendar_id': source.url, 'can_write': writable, 'reason': reason})
        return {'sources': result}

    def _role(self, source, key):
        try:
            remote = self.provider.calendar(source, key)
        except Exception:
            raise ActionError('Kalenderrechte konnten nicht geprüft werden.', 503) from None
        if not remote or remote.get('id') != source.url or remote.get('accessRole') not in {'writer', 'owner'}:
            raise ActionError('Für diesen Kalender fehlen aktuelle Schreibrechte.', 403)
        return remote['accessRole']

    def draft(self, *, kind, source_id, title=None, start=None, end=None, event_id=None, send_updates=None):
        if kind not in {'create', 'edit', 'cancel'} or send_updates not in UPDATES:
            raise ActionError('Aktion und Benachrichtigungsauswahl sind erforderlich.')
        source, key, binding = self._source(source_id)
        self._role(source, key)
        if kind in {'create', 'edit'}:
            body = _times(title, start, end)
        else:
            body = {}
        current = None
        if kind != 'create':
            if not isinstance(event_id, str) or not event_id or len(event_id) > 1024:
                raise ActionError('Bitte einen konkreten Termin auswählen.')
            try:
                current = self.provider.event(source, key, event_id)
            except Exception:
                raise ActionError('Der Termin konnte nicht geprüft werden.', 503) from None
            if not current or current.get('id') != event_id or current.get('status') == 'cancelled' or not current.get('etag'):
                raise ActionError('Dieser Termin ist nicht mehr bearbeitbar.', 409)
            if current.get('locked') or current.get('eventType', 'default') != 'default':
                raise ActionError('Dieser geschützte Kalendereintrag ist nicht bearbeitbar.', 422)
            if kind == 'cancel' and (current.get('organizer') or {}).get('self') is not True:
                raise ActionError('Eine Absage ist nur auf der bestätigten Organisator-Kopie möglich. Fremde Einladungen bitte direkt bei Google verwalten.', 422)
            if current.get('recurringEventId') or current.get('recurrence'):
                raise ActionError('Serientermine benötigen eine gesonderte Bearbeitung.', 422)
        action_id = uuid.uuid4().hex
        provider_id = 'kf' + action_id if kind == 'create' else event_id
        if kind == 'create':
            body['id'] = provider_id
            body['extendedProperties'] = {'private': {'kingfisherDraftId': action_id}}
        attendees = [a['email'] for a in (current or {}).get('attendees', []) if isinstance(a, dict) and a.get('email')]
        preview = {'kind': kind, 'source_id': source.id, 'calendar': source.label,
            'account': source.user, 'event_id': provider_id, 'title': body.get('summary'),
            'start': body.get('start'), 'end': body.get('end'), 'attendees': attendees,
            'send_updates': send_updates, 'etag': (current or {}).get('etag'),
            'current': {k: current.get(k) for k in ('summary', 'start', 'end', 'location', 'description', 'status') if k in current} if current else None}
        stand = hashlib.sha256(json.dumps(preview, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        record = {'id': action_id, 'status': 'draft', 'kind': kind, 'source_id': source_id,
            'binding': binding, 'stand': stand, 'provider_event_id': provider_id,
            'preview': preview, 'body': body, 'etag': (current or {}).get('etag')}
        with closing(self._db()) as db, db:
            db.execute('INSERT INTO actions VALUES (?,?,?)', (action_id, 'draft', json.dumps(record)))
        return _public(record)

    def get(self, action_id):
        with closing(self._db()) as db, db:
            row = db.execute('SELECT record, status FROM actions WHERE id=?', (action_id,)).fetchone()
        if not row:
            raise ActionError('Entwurf nicht gefunden.', 404)
        record = json.loads(row['record'])
        record['status'] = row['status']
        return _public(record)

    def _write(self, record, status):
        record['status'] = status
        with closing(self._db()) as db, db:
            db.execute('UPDATE actions SET status=?, record=? WHERE id=?',
                (status, json.dumps(record), record['id']))
        return _public(record)

    def _claim(self, action_id, stand):
        db = self._db()
        try:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT record, status FROM actions WHERE id=?', (action_id,)).fetchone()
            if not row:
                raise ActionError('Entwurf nicht gefunden.', 404)
            record = json.loads(row['record'])
            if record['stand'] != stand:
                raise ActionError('Die Vorschau hat sich geändert. Bitte erneut prüfen.', 409)
            if row['status'] == 'done':
                db.commit()
                return record, False
            if row['status'] == 'running':
                # A process may have stopped after claiming an action. The
                # provider timeout is 25s; allow only a stale create to be
                # reconciled after 120s. Edits/cancels cannot be retried.
                if time.time() - record.get('claimed_at', time.time()) < 120:
                    raise ActionError('Diese Aktion wird bereits ausgeführt.', 409)
                if record['kind'] != 'create':
                    db.execute('UPDATE actions SET status=? WHERE id=?', ('uncertain', action_id))
                    db.commit()
                    raise ActionError('Der Ausgang ist unklar. Bitte den Termin manuell prüfen.', 409)
            if row['status'] == 'uncertain' and record['kind'] != 'create':
                raise ActionError('Der Ausgang ist unklar. Bitte den Termin manuell prüfen.', 409)
            if row['status'] not in {'draft', 'uncertain', 'running'}:
                raise ActionError('Dieser Entwurf kann nicht ausgeführt werden.', 409)
            record['reconcile_only'] = row['status'] != 'draft'
            record['claimed_at'] = time.time()
            db.execute('UPDATE actions SET status=?, record=? WHERE id=?',
                       ('running', json.dumps(record), action_id))
            db.commit()
            return record, True
        finally:
            db.close()

    @staticmethod
    def _matches_fields(record, event):
        if not event or event.get('id') != record['provider_event_id']:
            return False
        if event.get('summary') != record['body']['summary']:
            return False
        try:
            return all(_event_time(event[part]['dateTime']) ==
                       _event_time(record['body'][part]['dateTime']) for part in ('start', 'end'))
        except (ActionError, KeyError, TypeError):
            return False

    @staticmethod
    def _matches_create(record, event):
        marker = (event.get('extendedProperties') or {}).get('private') or {} if event else {}
        return marker.get('kingfisherDraftId') == record['id'] and CalendarActions._matches_fields(record, event)

    def execute(self, action_id, *, confirmed=False, stand=None):
        if confirmed is not True or not isinstance(stand, str):
            raise ActionError('Bitte die angezeigte Vorschau ausdrücklich bestätigen.')
        record, claimed = self._claim(action_id, stand)
        if not claimed:
            return _public(record)
        try:
            source, key, binding = self._source(record['source_id'])
            if binding != record['binding']:
                raise ActionError('Kalenderzugang wurde geändert. Bitte einen neuen Entwurf erstellen.', 409)
            self._role(source, key)
            event_id, updates = record['provider_event_id'], record['preview']['send_updates']
            if record['kind'] == 'create':
                existing = self.provider.event(source, key, event_id)
                if existing:
                    if not self._matches_create(record, existing):
                        raise ActionError('Terminkennung ist bereits anders belegt. Bitte manuell prüfen.', 409)
                    return self._write(record, 'done')
                if record.get('reconcile_only'):
                    return self._write(record, 'uncertain')
                try:
                    created = self.provider.create(source, key, record['body'], updates)
                    if not self._matches_create(record, created):
                        raise ProviderError()
                except ProviderError as exc:
                    if exc.status == 409:
                        existing = self.provider.event(source, key, event_id)
                        if self._matches_create(record, existing):
                            return self._write(record, 'done')
                        if existing:
                            raise ActionError('Terminkennung ist bereits anders belegt. Bitte manuell prüfen.', 409) from None
                    raise
            elif record['kind'] == 'edit':
                updated = self.provider.patch(source, key, event_id, record['etag'], record['body'], updates)
                if not self._matches_fields(record, updated):
                    raise ProviderError()
            else:
                self.provider.delete(source, key, event_id, record['etag'], updates)
            return self._write(record, 'done')
        except ActionError:
            self._write(record, 'blocked')
            raise
        except ProviderError as exc:
            if exc.status in {401, 403, 404, 412}:
                self._write(record, 'blocked')
                raise ActionError('Kalender oder Termin hat sich geändert. Bitte neu prüfen.', 409) from None
            return self._write(record, 'uncertain')
        except Exception:
            return self._write(record, 'uncertain')
