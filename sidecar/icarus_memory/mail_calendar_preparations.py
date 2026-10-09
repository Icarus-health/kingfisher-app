"""Persistent, non-executable calendar preparations derived from bounded mail context."""
from __future__ import annotations

from contextlib import closing
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from .calendar_actions import ActionError

_VERSION = 1
_TIME = re.compile(r'(?<![\w])\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)(?![\w])')
_CLOCK = r'(?:[01]?\d|2[0-3]):[0-5]\d'
_ZONE = r'(?:MESZ|MEZ|UTC(?:[+-](?:[01]\d|2[0-3]):[0-5]\d)?(?![+-]))'
_ZONE_SUFFIX = rf'(?:\(\s*(?P<zone_paren>{_ZONE})\s*\)|(?P<zone_plain>{_ZONE}))'
_GERMAN_LONG = re.compile(rf'(?<![\w.])(?P<day>\d{{1,2}})\.\s+(?P<month_name>Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+(?P<year>\d{{4}})\s+von\s+(?P<start>{_CLOCK})\s+bis\s+(?P<end>{_CLOCK})(?:\s+Uhr)?\s+{_ZONE_SUFFIX}(?![\w])', re.I)
_GERMAN_NUMERIC = re.compile(rf'(?<![\w.])(?P<day>\d{{1,2}})\.(?P<month_num>\d{{1,2}})\.(?P<year>\d{{4}})\s*,?\s*(?P<start>{_CLOCK})\s*(?:–|—|-|\bbis\b)\s*(?P<end>{_CLOCK})(?:\s+Uhr)?\s+{_ZONE_SUFFIX}(?![\w])', re.I)
_OTHER_CLOCK = re.compile(rf'(?<![\d:]){_CLOCK}(?![\d:])')
_OTHER_HOUR = re.compile(r'(?<!\d)(?:[01]?\d|2[0-3])\s*Uhr\b', re.I)
_ALT = re.compile(r'\b(?:alternativ(?:e|en)?|stattdessen|ersatzweise|wahlweise|andernfalls)\b|\boder\b', re.I)
_CANCEL = re.compile(r'\b(?:abgesagt|absage|entfällt|faellt aus|fällt aus|findet nicht statt|gestrichen|cancelled|canceled)\b', re.I)
_HISTORY_WARNING = 'Zeitvorschläge sind unbestätigt. Der angezeigte Mailverlauf ist begrenzt; außerhalb davon können weitere Nachrichten oder Absagen vorliegen.'
_MONTHS = {'januar': 1, 'februar': 2, 'märz': 3, 'maerz': 3, 'april': 4,
    'mai': 5, 'juni': 6, 'juli': 7, 'august': 8, 'september': 9,
    'oktober': 10, 'november': 11, 'dezember': 12}


def _json_copy(value):
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError, OverflowError):
        raise ActionError('Der Mailkontext ist nicht lesbar.') from None


def _stand(binding, fields, reviewed):
    raw = json.dumps([_VERSION, binding, fields, reviewed], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()


def _valid_time(value):
    if value == '':
        return None
    if not isinstance(value, str) or len(value) > 64 or not _TIME.fullmatch(value):
        raise ActionError('Bitte vollständige ISO-Zeiten mit ausdrücklich angegebener Zeitzone verwenden.')
    try:
        parsed = datetime.fromisoformat(value[:-1] + '+00:00' if value.endswith('Z') else value)
    except ValueError:
        raise ActionError('Bitte gültige ISO-Zeiten mit ausdrücklich angegebener Zeitzone verwenden.') from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ActionError('Bitte eine Zeitzone ausdrücklich angeben.')
    return parsed


def _german_time(match):
    try:
        month_name = match.groupdict().get('month_name')
        month_num = match.groupdict().get('month_num')
        month = _MONTHS[month_name.casefold()] if month_name else int(month_num)
        day, year = int(match.group('day')), int(match.group('year'))
        event_date = date(year, month, day)
        zone = (match.group('zone_paren') or match.group('zone_plain')).upper()
        if zone == 'MESZ': offset = timedelta(hours=2)
        elif zone == 'MEZ': offset = timedelta(hours=1)
        elif zone == 'UTC': offset = timedelta()
        else:
            sign = 1 if zone[3] == '+' else -1
            hours, minutes = map(int, zone[4:].split(':'))
            offset = sign * timedelta(hours=hours, minutes=minutes)
        tz = timezone(offset)
        start = datetime.combine(event_date, time.fromisoformat(match.group('start')), tz)
        end = datetime.combine(event_date, time.fromisoformat(match.group('end')), tz)
        if end <= start:
            return None
        return start.isoformat(timespec='seconds'), end.isoformat(timespec='seconds')
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def _time_ranges(text):
    ranges = []
    cursor = 0
    for paragraph in re.split(r'(?:\r?\n\s*){2,}', text):
        offset = text.find(paragraph, cursor)
        cursor = offset + len(paragraph)
        for pattern in (_GERMAN_LONG, _GERMAN_NUMERIC):
            for match in pattern.finditer(paragraph):
                values = _german_time(match)
                if values:
                    ranges.append((values[0], values[1], paragraph,
                        offset + match.start(), offset + match.end()))
        matches = list(_TIME.finditer(paragraph))
        for index in range(0, len(matches) - 1, 2):
            first, second = matches[index:index + 2]
            if not re.search(r'\bbis\b', paragraph[first.end():second.start()], re.I):
                continue
            try:
                start, end = first.group(0), second.group(0)
                if _valid_time(end) > _valid_time(start):
                    ranges.append((start, end, paragraph,
                        offset + first.start(), offset + second.end()))
            except (ActionError, TypeError, ValueError):
                continue
    return ranges


def _other_time_text(text, span):
    remaining = text[:span[0]] + ' ' + text[span[1]:]
    return bool(_TIME.search(remaining) or _OTHER_CLOCK.search(remaining) or _OTHER_HOUR.search(remaining))


def _suggest(context):
    warnings = [_HISTORY_WARNING]
    items = context.get('items') if isinstance(context, dict) else None
    if not isinstance(items, list):
        return '', '', '', '', warnings + ['Die geöffnete Nachricht fehlt im Verlauf; Zeiten bitte im Original prüfen.']
    currents = [item for item in items if isinstance(item, dict) and item.get('current') is True]
    if len(currents) != 1:
        return '', '', '', '', warnings + ['Die geöffnete Nachricht ist im Verlauf nicht eindeutig; Zeiten bitte im Original prüfen.']
    current = currents[0]
    text = current.get('text')
    if not isinstance(text, str):
        return '', '', '', '', warnings + ['Der Originaltext ist nicht verfügbar; Zeiten bitte im Original prüfen.']
    if context.get('limited') is True:
        return '', '', '', '', warnings + ['Der Verlauf ist unvollständig; Zeiten wurden nicht automatisch übernommen.']
    if any(item.get('truncated') is True for item in items if isinstance(item, dict)):
        return '', '', '', '', warnings + ['Eine Nachricht im Verlauf ist gekürzt; Zeiten wurden nicht automatisch übernommen.']
    all_text = '\n'.join(' '.join(value for value in (item.get('title', ''), item.get('text', '')) if isinstance(value, str))
        for item in items if isinstance(item, dict))
    if _CANCEL.search(all_text):
        return '', '', '', '', warnings + ['Im Verlauf steht eine Absage oder Aufhebung; bitte die Zeit im Original prüfen.']
    current_ranges = _time_ranges(text)
    if len(current_ranges) != 1:
        return '', '', '', '', warnings + ['Es gibt keine eindeutige vollständige Zeitangabe in einem Absatz; bitte Zeiten im Original prüfen.']
    start, end, paragraph, range_start, range_end = current_ranges[0]
    if _other_time_text(text, (range_start, range_end)):
        return '', '', '', '', warnings + ['Im Absatz stehen weitere Zeitangaben; bitte die Zeit im Original prüfen.']
    if _ALT.search(paragraph) or _ALT.search(all_text.replace(paragraph, '')):
        return '', '', '', '', warnings + ['Der Verlauf enthält Alternativen; es wurde keine Zeit ausgewählt.']
    try:
        start_time, end_time = _valid_time(start), _valid_time(end)
        if end_time <= start_time:
            raise ValueError()
    except (ActionError, TypeError, ValueError):
        return '', '', '', '', warnings + ['Die Zeitangaben sind nicht eindeutig geordnet; bitte im Original prüfen.']
    for item in items:
        if not isinstance(item, dict) or item is current:
            continue
        other_text = item.get('text')
        if not isinstance(other_text, str):
            continue
        for other_start, other_end, _, _, _ in _time_ranges(other_text):
            try:
                if (_valid_time(other_start), _valid_time(other_end)) != (start_time, end_time):
                    return '', '', '', '', warnings + ['Im bekannten Verlauf stehen abweichende vollständige Zeitangaben; bitte Verlauf und Original prüfen.']
            except (ActionError, TypeError, ValueError):
                continue
    return start, end, paragraph, paragraph, warnings


class MailCalendarPreparations:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._db()) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS actions (id TEXT PRIMARY KEY, status TEXT NOT NULL, record TEXT NOT NULL)')

    def _db(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _binding(binding):
        if not isinstance(binding, str) or len(binding) != 64 or not re.fullmatch(r'[0-9a-fA-F]{64}', binding):
            raise ActionError('Die Quellenbindung ist ungültig.')

    def prepare(self, uid: str, binding: str, context: dict, subject: str) -> dict:
        if not isinstance(uid, str) or not uid or len(uid) > 2048:
            raise ActionError('Die Mailkennung ist ungültig.')
        self._binding(binding)
        if not isinstance(subject, str) or len(subject) > 500:
            raise ActionError('Der Betreff ist zu lang oder ungültig.')
        copied = _json_copy(context)
        if not isinstance(copied, dict) or (copied.get('uid') is not None and copied['uid'] != uid):
            raise ActionError('Mail und Verlauf passen nicht zusammen.', 409)
        start, end, time_quote, end_quote, warnings = _suggest(copied)
        copied['unverified_limited_history'] = True
        existing_warnings = copied.get('warnings', [])
        if not isinstance(existing_warnings, list):
            existing_warnings = []
        copied['warnings'] = list(dict.fromkeys([*(w for w in existing_warnings if isinstance(w, str)), *warnings]))
        title = subject if subject.strip() else ''
        fields = {'title': title, 'start': start, 'end': end}
        origins = {
            'title': {'kind': 'source' if title else 'missing', 'quote': title},
            'start': {'kind': 'source' if start else 'missing', 'quote': time_quote if start else ''},
            'end': {'kind': 'source' if end else 'missing', 'quote': end_quote if end else ''},
        }
        record = {'id': 'mp' + hashlib.sha256((uid + binding).encode()).hexdigest(),
            'status': 'preparation', 'kind': 'mail_preparation', 'source_id': '', 'uid': uid,
            'binding': binding, 'stand': _stand(binding, fields, False), 'fields': fields,
            'origins': origins, 'context': copied, 'reviewed': False}
        raw = json.dumps(record, ensure_ascii=False, separators=(',', ':'))
        with closing(self._db()) as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                db.execute('INSERT OR IGNORE INTO actions (id,status,record) VALUES (?,?,?)',
                           (record['id'], 'preparation', raw))
                row = db.execute('SELECT status,record FROM actions WHERE id=?', (record['id'],)).fetchone()
                if row is None or row['status'] != 'preparation':
                    raise ActionError('Diese Kennung gehört bereits zu einer anderen Kalenderaktion.', 409)
                saved = json.loads(row['record'])
                if not isinstance(saved, dict) or saved.get('kind') != 'mail_preparation' or saved.get('uid') != uid or saved.get('binding') != binding:
                    raise ActionError('Diese Kennung gehört bereits zu einer anderen Kalenderaktion.', 409)
                db.commit()
                return saved
            except BaseException:
                db.rollback()
                raise

    def get(self, preparation_id: str) -> dict:
        with closing(self._db()) as db:
            row = db.execute('SELECT status,record FROM actions WHERE id=?', (preparation_id,)).fetchone()
        if row is None or row['status'] != 'preparation':
            raise ActionError('Vorbereitung nicht gefunden.', 404)
        try:
            record = json.loads(row['record'])
        except (TypeError, ValueError):
            raise ActionError('Vorbereitung kann nicht gelesen werden.', 409) from None
        if not isinstance(record, dict) or record.get('kind') != 'mail_preparation':
            raise ActionError('Vorbereitung nicht gefunden.', 404)
        return record

    def update(self, preparation_id: str, stand: str, fields: dict, reviewed: bool) -> dict:
        if type(reviewed) is not bool or not isinstance(fields, dict) or set(fields) != {'title', 'start', 'end'}:
            raise ActionError('Alle drei Felder und die ausdrückliche Prüfentscheidung sind erforderlich.')
        cleaned = {}
        for key, limit in (('title', 500), ('start', 64), ('end', 64)):
            value = fields[key]
            if not isinstance(value, str) or len(value) > limit:
                raise ActionError('Ein Feld ist zu lang oder ungültig.')
            cleaned[key] = value.strip()
        start, end = _valid_time(cleaned['start']), _valid_time(cleaned['end'])
        if start is not None and end is not None and end <= start:
            raise ActionError('Das Ende muss nach dem Beginn liegen.')
        with closing(self._db()) as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                row = db.execute('SELECT status,record FROM actions WHERE id=?', (preparation_id,)).fetchone()
                if row is None or row['status'] != 'preparation':
                    raise ActionError('Vorbereitung nicht gefunden.', 404)
                record = json.loads(row['record'])
                if not isinstance(record, dict) or record.get('kind') != 'mail_preparation':
                    raise ActionError('Vorbereitung nicht gefunden.', 404)
                if not isinstance(stand, str) or stand != record.get('stand'):
                    raise ActionError('Die Vorbereitung wurde inzwischen geändert. Bitte neu laden.', 409)
                for key, value in cleaned.items():
                    if value == '':
                        record['origins'][key] = {'kind': 'missing', 'quote': ''}
                    elif value != record['fields'][key]:
                        record['origins'][key] = {'kind': 'user', 'quote': ''}
                record['fields'] = cleaned
                record['reviewed'] = reviewed
                record['stand'] = _stand(record['binding'], cleaned, reviewed)
                db.execute('UPDATE actions SET record=? WHERE id=? AND status=?',
                           (json.dumps(record, ensure_ascii=False, separators=(',', ':')), preparation_id, 'preparation'))
                db.commit()
                return record
            except BaseException:
                db.rollback()
                raise
