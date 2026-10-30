"""Begrenzte Fristkonfliktprüfung für unbestätigte Aufgabenvorschläge.

Eine spätere Mail darf weder den Originalbeleg umschreiben noch allein eine neue
Aufgabe begründen. Exakte Adressen und ein ausdrücklicher Datumswechsel liefern
hier nur einen sichtbaren Prüfhinweis; Namen werden nie zusammengeführt.
"""
import re
import sqlite3

from .episodes import AUSGEBLENDETE_ZUSTAENDE, mail_address, sql_aktuell
from .mail_quote_history import _ranges
from .model import SourceType
from .satzpruefung import daten_in
from .task_review import current_task_context

MAX_MAILS = 200
MAX_BODY = 20000
MAX_DOCUMENT = 60000
MAX_QUERY_STEPS = 1_000_000
PROGRESS_OPCODES = 1000
REASON = ('Eine spätere Nachricht nennt eine mögliche Friständerung. Bitte beide Quellen prüfen. '
          'Diesen alten Vorschlag nicht übernehmen; die aktuelle Aufgabe bei Bedarf neu festhalten.')
LIMIT_REASON = ('Die Prüfung auf spätere Friständerungen ist unvollständig. '
                'Bitte die aktuelle Aufgabe anhand der Quellen neu festhalten.')
_CHANGE = re.compile(r'\b(?:Frist|Termin)\b.{0,120}\b(?:geändert|geaendert|verschoben|verlegt)\b', re.I | re.S)
_PROJECT = re.compile(r'^(?:(?:AW|RE|FW):\s*)*Projekt\s+([^:\n]+)(?::|$)', re.I)
_PROJECT_MENTION = re.compile(r'\bProjekt\s+([A-ZÄÖÜ][\w-]*(?:[ \t]+[A-ZÄÖÜ][\w-]*)*)')
_TOKEN = re.compile(r'[^\W\d_]{4,}', re.UNICODE)
_GENERIC = frozenset('bitte schicke schicken sende senden soll sollte werde werden wurde jetzt gilt '
                     'statt frist termin geändert geaendert verschoben projekt november oktober '
                     'januar februar märz april juni juli august september dezember hallo viele grüße '
                     'morgen heute montag dienstag mittwoch donnerstag freitag samstag sonntag'.split())


def _parties(source):
    senders = [c for c in source.contacts if c.get('rolle') == 'von']
    if len(senders) != 1:
        return None
    sender = mail_address(senders[0].get('adresse') or '')
    recipients = frozenset(mail_address(c.get('adresse') or '') for c in source.contacts
                           if c.get('rolle') in ('an', 'cc', 'bcc')) - {''}
    return (sender, recipients) if sender and recipients else None


def _account(source):
    # Nur die bereits gespeicherte Kontoherkunft, keine Ableitung aus Namen.
    match = re.fullmatch(r'(.+):(?:<[^<>\s]+>|imap:.+)', source.provenance.source_ref or '')
    return match[1] if match else None


def _current_text(body):
    characters = list(body)
    for start, end in _ranges(body):
        characters[start:end] = ' ' * (end-start)
    return '\n'.join(line for line in ''.join(characters).splitlines()
                     if not line.lstrip().startswith('>'))


def _topic(source, later, quote):
    if source.project_id and later.project_id and source.project_id != later.project_id:
        return False
    first, second = _PROJECT.match(source.title), _PROJECT.match(later.title)
    if first and second and first[1].strip().casefold() != second[1].strip().casefold():
        return False
    excluded = set(_GENERIC)
    for contact in source.contacts:
        excluded.update(w.casefold() for w in _TOKEN.findall(contact.get('name') or ''))
    for project in (first, second):
        if project:
            excluded.update(w.casefold() for w in _TOKEN.findall(project[1]))
    _, without_dates = daten_in(quote)
    words = {w.casefold() for w in _TOKEN.findall(without_dates)} - excluded
    same_project = bool((first and second) or (source.project_id and source.project_id == later.project_id))
    return words, 1 if same_project else 2


def deadline_review(episodes, proposal, source):
    """Frisch lesen; nur Prüfmetadaten zurückgeben, nie Titel oder Frist ersetzen.

    Die enge Regel erfasst ausdrücklich benannte alte und neue Kalenderdaten in
    derselben aktuellen Passage. Andere Formulierungen sind damit nicht geprüft.
    """
    if (source.provenance.source_type is not SourceType.EMAIL or source.occurred_at is None
            or source.occurred_at.tzinfo is None or len(proposal.evidence) != 1):
        return None
    parties = _parties(source)
    dates, _ = daten_in(proposal.evidence[0].quote)
    if parties is None or not dates:
        return None
    remaining_steps = MAX_QUERY_STEPS

    def progress():
        nonlocal remaining_steps
        remaining_steps -= PROGRESS_OPCODES
        return int(remaining_steps < 0)

    with episodes._lock:
        episodes._conn.set_progress_handler(progress, PROGRESS_OPCODES)
        try:
            rows = episodes._conn.execute(
                'SELECT CASE WHEN length(CAST(e.document AS BLOB))<=? THEN e.document END AS document '
                'FROM episodes e WHERE ' + sql_aktuell('e') +
                " AND e.kind='message' AND json_extract(e.document,'$.provenance.source_type')='email' "
                'AND julianday(e.occurred_at)>julianday(?) AND EXISTS '
                "(SELECT 1 FROM json_each(e.document,'$.contacts') c "
                "WHERE json_extract(c.value,'$.rolle')='von' "
                "AND lower(trim(json_extract(c.value,'$.adresse')))=?) "
                'ORDER BY julianday(e.occurred_at) DESC,e.id LIMIT ?',
                (MAX_DOCUMENT, source.occurred_at.isoformat(), parties[0], MAX_MAILS+1)).fetchall()
        except sqlite3.OperationalError as exc:
            if 'interrupted' not in str(exc).lower():
                raise
            return {'temporal_status': 'context_limit', 'temporal_reason': LIMIT_REASON,
                    'followup_episode_id': None, 'review_required': True}
        finally:
            episodes._conn.set_progress_handler(None, 0)
    limited = len(rows) > MAX_MAILS
    for row in rows[:MAX_MAILS]:
        if row['document'] is None:
            limited = True
            continue
        later = episodes._from_row(row)
        if (later.state in AUSGEBLENDETE_ZUSTAENDE or _parties(later) != parties
                or _account(later) != _account(source) or current_task_context(episodes, later.id) is None):
            continue
        topic = _topic(source, later, proposal.evidence[0].quote)
        if topic is False:
            continue
        words, minimum = topic
        if len(later.body) > MAX_BODY:
            limited = True
            continue
        for paragraph in re.split(r'\n\s*\n', _current_text(later.body)):
            if not _CHANGE.search(paragraph):
                continue
            project = _PROJECT.match(source.title)
            mentions = _PROJECT_MENTION.findall(paragraph)
            if project and any(name.casefold() != project[1].strip().casefold() for name in mentions):
                continue
            found = {w.casefold() for w in _TOKEN.findall(paragraph)}
            if len(words & found) < minimum:
                continue
            newer, _ = daten_in(paragraph)
            def old_matches(d):
                return any((d.tag, d.monat) == (old.tag, old.monat)
                           and (d.jahr is None or old.jahr is None or d.jahr == old.jahr) for old in dates)
            if any(old_matches(d) for d in newer) and any(not old_matches(d) for d in newer):
                return {'temporal_status': 'followup', 'temporal_reason': REASON,
                        'followup_episode_id': later.id, 'review_required': True}
    if limited:
        return {'temporal_status': 'context_limit', 'temporal_reason': LIMIT_REASON,
                'followup_episode_id': None, 'review_required': True}
    return None
