"""A local saved-task status view; the conversation stores proof, not its rendering."""

from dataclasses import dataclass
import re
import sqlite3

from .datumstext import iso_versuchen, zeitpunkt_text
from .source_answers import MAX_DOCUMENT_BYTES
from .tasks import TaskCompletionChanged, TaskRecallProof, is_task_id


KEY = 'task_status_answer'
USER_FLAG = 'task_status_lookup'
NEUTRAL = 'Aufgabenstatus — beim Öffnen erneut geprüft.'
WITHHELD = 'Dieser Aufgabenstatus ist nicht verfügbar. Bitte frage bei Bedarf erneut.'
_GENERIC = {
    'not_found': 'Ich finde keine gespeicherte Aufgabe mit dieser Kennung oder diesem vollständigen Titel.',
    'ambiguous': 'Die Aufgabe ist nicht eindeutig. Bitte nenne ihre Kennung oder setze den vollständigen Titel in Anführungszeichen.',
    'coverage_limited': 'Ich konnte die Aufgaben nicht vollständig prüfen. Bitte nenne die Kennung der Aufgabe.',
    'history_limited': 'Ich konnte den gespeicherten Aufgabenverlauf nicht vollständig prüfen.',
    'withheld': WITHHELD,
}
_FLAGS = re.IGNORECASE
_PATTERNS = (
    (True, re.compile(r'Wie ist der Status der Aufgabe (?P<operand>.+)\?', _FLAGS)),
    (False, re.compile(r'(?:Ist|Wurde) (?P<operand>.+?) (?:schon |bereits )?(?:erledigt|abgeschlossen)\?', _FLAGS)),
    (False, re.compile(r'Habe ich (?P<operand>.+?) (?:schon |bereits )?(?:erledigt|abgeschlossen)\?', _FLAGS)),
)
_MARKER = re.compile(r'die Aufgabe\s+', _FLAGS)
_QUOTED = re.compile(r'(?:"([^"\r\n]+)"|„([^“\r\n]+)“)')
_UNSUPPORTED = re.compile(
    r'\b(?:nicht|niemals|heute|gestern|morgen|damals|letzte[nrms]?|vorgestern|inzwischen|mittlerweile)\b'
    r'|^(?:das|es|sie|er|diese|jene|diese Aufgabe)$|[?;!"]|[„“]'
    r'|\b(?:seit|bis|am|um)\s+(?:\d|Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag)'
    r'|,\s*(?:und|oder|weil|obwohl|sobald|aber|wenn)\b'
    r'|\b(?:erledigt|abgeschlossen)\s+(?:und|oder|aber)\b'
    r'|\b(?:laut\s+(?:(?:der|dem|einer|einem)\s+)?(?:Mail|Nachricht|Bericht)|in\s+(?:den|meinen)\s+Quellen)\b', _FLAGS)
_EPISODE_ID = re.compile(r'e-[a-f0-9]{12}')
_FINGERPRINT = re.compile(r'[a-f0-9]{64}')
_INT64_MAX = 2**63 - 1


@dataclass(frozen=True)
class Reference:
    operand: str
    explicit: bool
    quoted: bool
    by_id: bool


def parse(question: str) -> Reference | None:
    question = question.strip()
    if '\n' in question or '\r' in question:
        return None
    for explicit, pattern in _PATTERNS:
        match = pattern.fullmatch(question)
        if match is None:
            continue
        operand = match['operand'].strip()
        marker = None if explicit else _MARKER.match(operand)
        if marker:
            explicit, operand = True, operand[marker.end():]
        quoted = _QUOTED.fullmatch(operand)
        if quoted:
            operand = next(group for group in quoted.groups() if group is not None)
        elif _UNSUPPORTED.search(operand):
            return None
        by_id = not quoted and is_task_id(operand)
        # A malformed explicit ID remains a local no-match, never a model prompt.
        explicit = explicit or bool(quoted) or by_id
        if not operand:
            return None
        return Reference(operand, explicit, bool(quoted), by_id)
    return None


def _seq(value):
    return type(value) is int and 1 <= value <= _INT64_MAX


def _episode_id(value):
    return isinstance(value, str) and _EPISODE_ID.fullmatch(value) is not None


def _stamps(proof: TaskRecallProof, episodes):
    ids = set()
    if not proof.manual_creation:
        if not _episode_id(proof.creation_episode):
            return None
        ids.add(proof.creation_episode)
    if proof.mail_completion:
        if not _episode_id(proof.completion_episode):
            return None
        ids.add(proof.completion_episode)
    refs = []
    for identifier in sorted(ids):
        try:
            snapshot = episodes.belegbarer_snapshot(identifier, max_bytes=MAX_DOCUMENT_BYTES,
                                                    require_unarchived=True)
            if snapshot is None:
                return None
            refs.append({'episode_id': identifier, 'fingerprint': snapshot.support_fingerprint()})
        except (ValueError, KeyError, TypeError, sqlite3.Error, UnicodeError):
            return None
    return refs


def _reference(proof, tasks, episodes):
    refs = _stamps(proof, episodes)
    if refs is None:
        return None
    try:
        # Re-read the task revision after cross-store source checks. In-process
        # source changes already use the caller's conversation lock.
        latest, _, _ = tasks.completion_snapshot(proof.task_id)
    except (TaskCompletionChanged, sqlite3.Error):
        return None
    if latest.sequence != proof.task_revision:
        return None
    return {'version': 1, 'task_id': proof.task_id, 'task_revision': proof.task_revision,
            'state_event_sequence': proof.state_event_sequence,
            'confirmation_event_sequence': proof.confirmation_event_sequence, 'source_refs': refs}


def base_context():
    return {'items': [], 'answer_mode': 'memory_evidence', 'history_egress': 'local_only', 'model_called': False}


def answer(question, tasks, episodes, *, retry=False):
    reference = parse(question)
    if reference is None:
        return generic('not_found') if retry else None
    try:
        lookup = (tasks.status_for_recall_id(reference.operand) if reference.by_id else
                  tasks.status_for_recall(reference.operand, quoted=reference.quoted))
    except (ValueError, sqlite3.Error):
        return generic('coverage_limited')
    if lookup.status == 'not_found' and not (reference.explicit or retry):
        return None
    proof = lookup.proof
    if proof is None:
        return generic(lookup.status)
    if not is_task_id(proof.task_id):
        return generic('withheld')
    if proof.state_event_sequence is None:
        return generic('history_limited')
    payload = _reference(proof, tasks, episodes)
    return generic('withheld') if payload is None else {**base_context(), KEY: payload}


def generic(outcome):
    return {**base_context(), KEY: {'version': 1, 'outcome': outcome}}


def hidden_from_history(item):
    def protected(fields):
        context = fields.get('context')
        return (fields.get(USER_FLAG) is True
                or isinstance(context, dict) and (KEY in context or 'task_link' in context
                                                  or context.get('task_status_view') is True))
    metadata = item.get('metadata')
    return protected(item) or isinstance(metadata, dict) and protected(metadata)


def _valid_record(record):
    if not isinstance(record, dict) or type(record.get('version')) is not int or record['version'] != 1:
        return False
    if set(record) != {'version', 'task_id', 'task_revision', 'state_event_sequence',
                       'confirmation_event_sequence', 'source_refs'}:
        return False
    revision = record['task_revision']
    if not is_task_id(record['task_id']) or not _seq(revision):
        return False
    for key in ('state_event_sequence', 'confirmation_event_sequence'):
        value = record[key]
        if value is not None and (not _seq(value) or value > revision):
            return False
    state, confirmed = record['state_event_sequence'], record['confirmation_event_sequence']
    if confirmed is not None and (state is None or confirmed < state):
        return False
    refs = record['source_refs']
    return (isinstance(refs, list) and len(refs) <= 2
            and all(isinstance(ref, dict) and set(ref) == {'episode_id', 'fingerprint'}
                    and _episode_id(ref['episode_id']) and isinstance(ref['fingerprint'], str)
                    and _FINGERPRINT.fullmatch(ref['fingerprint']) for ref in refs)
            and len({ref['episode_id'] for ref in refs}) == len(refs))


def _generic_outcome(record):
    if (isinstance(record, dict) and set(record) == {'version', 'outcome'}
            and type(record['version']) is int and record['version'] == 1
            and isinstance(record['outcome'], str) and record['outcome'] in _GENERIC):
        return record['outcome']
    return None


def storage_context(context):
    record = context[KEY]
    if _valid_record(record) or _generic_outcome(record):
        return {**base_context(), KEY: record}
    return generic('withheld')


def _render(proof):
    title = f'„{proof.title}“'
    if proof.state.value == 'open':
        result = f'Die gespeicherte Aufgabe {title} ist offen.'
    elif proof.state.value == 'dropped':
        result = f'Die gespeicherte Aufgabe {title} wurde verworfen.'
    else:
        result = f'Kingfisher führt die Aufgabe {title} als erledigt.'
        done_at = zeitpunkt_text(proof.done_at)
        confirmed_at = zeitpunkt_text(proof.confirmed_at)
        if done_at:
            result += f' Gespeicherter Erledigungszeitpunkt: {done_at}.'
        if proof.mail_completion:
            result += ' Der gespeicherte Erledigungsstand stützt sich auf eine Mail.'
        if proof.confirmation_event_sequence is not None:
            result += ' Die Erledigung wurde ausdrücklich bestätigt; die Person ist nicht aufgezeichnet.'
            if confirmed_at and iso_versuchen(proof.confirmed_at) != iso_versuchen(proof.done_at):
                result += f' Bestätigung aufgezeichnet: {confirmed_at}.'
        elif not proof.mail_completion:
            result += ' Wer die Erledigung veranlasst hat, ist nicht bekannt.'
    if proof.history_incomplete:
        result += ' Die frühere Aufgabengeschichte ist nicht vollständig belegbar.'
    return result


def project_message(value, tasks, episodes, *, resolve):
    """Never surface internal IDs, sequences or stamps unless proof validates."""
    record = value['metadata']['context'].get(KEY)
    value['content'] = NEUTRAL if not resolve else WITHHELD
    context = {**base_context(), 'task_status_view': True}
    value['metadata'] = {**value['metadata'], 'context': context}
    if not resolve:
        return value
    if outcome := _generic_outcome(record):
        value['content'] = _GENERIC[outcome]
        return value
    if not _valid_record(record):
        return value
    try:
        proof = tasks.status_for_recall_id(record['task_id']).proof
    except (ValueError, sqlite3.Error):
        return value
    if (proof is None or proof.state_event_sequence is None
            or proof.task_revision != record['task_revision']):
        return value
    if _reference(proof, tasks, episodes) != record:
        return value
    value['content'] = _render(proof)
    context['task_link'] = {'id': proof.task_id, 'status': proof.state.value,
                            'sequence': str(proof.confirmation_event_sequence or proof.state_event_sequence or proof.task_revision)}
    return value
