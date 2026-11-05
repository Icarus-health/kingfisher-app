"""Local task decisions, distinct from historical source reports.

Proofs contain references only. They use the existing task lifetime/event boundary;
no copied owner, source text, identity inference or second truth store is persisted.
"""
import copy
import re
import sqlite3

from .task_responsibility import ResponsibilityLookupIncomplete
from .tasks import effective_responsibility, is_task_id, responsibility_label

KIND = 'responsibility'
CONTEXT = 'task_responsibility_context'
CLARIFY = 'Welche gespeicherte Aufgabe meinst du? Bitte nenne ihre Kennung oder den vollständigen Titel in Anführungszeichen.'
WITHHELD = 'Die Zuständigkeit oder ihre Aufgabengrundlage hat sich geändert oder ist nicht verfügbar. Bitte frage erneut.'
MAX_SOURCES = 32
MAX_TASKS = 8
# Deliberately bounded everyday owner intents. This is not semantic understanding.
_INTENT = re.compile(r'^wer\s+(?:ist\b.*\b(?:zuständig|verantwortlich)|kümmert sich\b|übernimmt\b|macht\b)', re.I | re.S)
_OPERANDS = (
    re.compile(r'Wer ist (?:für )?(?:die Aufgabe )?(.+?) (?:zuständig|verantwortlich)\??', re.I),
    re.compile(r'Wer kümmert sich um (?:die Aufgabe )?(.+?)\??', re.I),
    re.compile(r'Wer (?:übernimmt|macht) (?:die Aufgabe )?(.+?)\??', re.I),
)


def _proof(snapshot):
    return {'version': 1, 'kind': KIND, 'task_id': snapshot['task'].id,
            'task_revision': snapshot['revision'],
            'responsibility_event_sequence': snapshot['responsibility_event_sequence']}


def valid(record):
    return (isinstance(record, dict) and set(record) == {
        'version', 'kind', 'task_id', 'task_revision', 'responsibility_event_sequence'}
        and type(record['version']) is int and record['version'] == 1 and record['kind'] == KIND
        and is_task_id(record['task_id']) and type(record['task_revision']) is int
        and 1 <= record['task_revision'] <= 2**63 - 1
        and (record['responsibility_event_sequence'] is None or
             type(record['responsibility_event_sequence']) is int
             and 1 <= record['responsibility_event_sequence'] <= record['task_revision']))


def _snapshot(tasks, record):
    if not valid(record):
        return None
    try:
        snapshot = tasks.responsibility_snapshot(record['task_id'])
        if _proof(snapshot) != record:
            return None
        # An unbound old/restored explicit document must never acquire event proof.
        if snapshot['task'].responsibility is not None and snapshot['responsibility_event_sequence'] is None:
            return None
        return snapshot
    except (KeyError, ValueError, sqlite3.Error, ResponsibilityLookupIncomplete):
        return None


def answer(question, tasks):
    from . import task_status_answers as status
    if not _INTENT.match(question.strip()):
        return None
    operand, quoted = None, False
    for pattern in _OPERANDS:
        if match := pattern.fullmatch(question.strip()):
            operand = match[1].strip()
            if len(operand) > 1 and (operand[0], operand[-1]) in {('"', '"'), ('„', '“')}:
                operand, quoted = operand[1:-1], True
            break
    if not operand or '\n' in operand or '\r' in operand:
        return status.generic('owner_clarify')
    try:
        if is_task_id(operand):
            snapshot = tasks.responsibility_snapshot(operand)
        else:
            lookup = tasks.status_for_recall(operand, quoted=quoted)
            if lookup.proof is None:
                return status.generic('owner_clarify')
            snapshot = tasks.responsibility_snapshot(lookup.proof.task_id)
            # The title match and owner snapshot are separate transactions.
            # A rename or new lifetime must not answer the earlier title.
            if snapshot['revision'] != lookup.proof.task_revision:
                return status.generic('owner_clarify')
        proof = _proof(snapshot)
        return {**status.base_context(), status.KEY: proof}
    except (KeyError, ValueError, sqlite3.Error, ResponsibilityLookupIncomplete):
        return status.generic('owner_clarify')


def _text(snapshot):
    task = snapshot['task']
    decision = effective_responsibility(task)
    if decision == 'self':
        owner = 'Du selbst (ausdrücklich bestätigt)'
    elif decision == 'person':
        owner = responsibility_label(task) + ' (ausdrücklich bestätigt)'
    elif decision == 'unknown':
        owner = 'ausdrücklich ungeklärt'
    else:
        owner = 'nicht bestätigt; aus der Quelle wird keine aktuelle Zuständigkeit abgeleitet'
    title = task.title[:400] + ('…' if len(task.title) > 400 else '')
    return f'Aktuelle Zuständigkeit für „{title}“: {owner}. Die bestätigende Person ist nicht aufgezeichnet.'


def project_message(value, tasks, *, resolve):
    from . import task_status_answers as status
    record = value['metadata']['context'][status.KEY]
    value['content'] = WITHHELD if resolve else status.NEUTRAL
    context = {**status.base_context(), 'task_status_view': True}
    value['metadata'] = {**value['metadata'], 'context': context}
    if resolve and (snapshot := _snapshot(tasks, record)):
        value['content'] = _text(snapshot)
        sequence = snapshot['responsibility_event_sequence']
        if sequence is not None:
            context['task_link'] = {'id': snapshot['task'].id, 'status': snapshot['task'].status.value,
                                    'sequence': str(sequence)}
    return value


def capture(tasks, episode_ids, episodes=None):
    """Bound source linkage scans and materialized task documents, fail closed."""
    ids = sorted(set(episode_ids))
    if len(ids) > MAX_SOURCES:
        return None
    if tasks is None:
        return {'version': 1, 'sources': [{'episode_id': identifier, 'tasks': []} for identifier in ids]}
    sources, task_count = [], 0
    try:
        for identifier in ids:
            linked = tasks.mit_quelle('episode:' + identifier, limit=MAX_TASKS + 1)
            task_count += len(linked)
            if task_count > MAX_TASKS:
                return None
            refs = [_proof(tasks.responsibility_snapshot(task.id)) for task in linked]
            if any(_snapshot(tasks, ref) is None for ref in refs):
                return None
            entry = {'episode_id': identifier, 'tasks': sorted(refs, key=lambda ref: ref['task_id'])}
            if refs and episodes is not None:
                from .source_answers import MAX_DOCUMENT_BYTES
                support = episodes.belegbarer_snapshot(identifier, max_bytes=MAX_DOCUMENT_BYTES,
                                                        require_unarchived=True)
                if support is None:
                    return None
                entry['support_fingerprint'] = support.support_fingerprint()
            sources.append(entry)
    except (KeyError, ValueError, sqlite3.Error, ResponsibilityLookupIncomplete):
        return None
    return {'version': 1, 'sources': sources}


def episode_ids(context):
    """Read only known reference shapes, never a recursive scan of arbitrary text."""
    working = context.get('working_answer')
    source = context.get('source_answer')
    if isinstance(working, dict):
        refs = list(working.get('basis') or [])
        # Confirmed knowledge entries are a separate source path within working memory.
        refs += [{'episode_id': row.get('primary_episode_id')} for row in
                 (working.get('claim_basis') or {}).values() if isinstance(row, dict)]
    elif isinstance(source, dict):
        refs = source.get('refs') or []
    else:
        refs = [item.get('knowledge_projection', {}).get('primary_evidence', {})
                for item in context.get('items', []) if isinstance(item, dict)]
    return sorted({ref['episode_id'] for ref in refs if isinstance(ref, dict)
                   and isinstance(ref.get('episode_id'), str)})


def binding(context):
    working = context.get('working_answer')
    return working.get(CONTEXT) if isinstance(working, dict) else context.get(CONTEXT)


def describe(record, tasks):
    """Current local display/input only. Never persist or forward this to cloud."""
    if not isinstance(record, dict) or record.get('version') != 1 or not isinstance(record.get('sources'), list):
        return None, False
    lines, ambiguous = [], False
    for source in record['sources']:
        refs = source['tasks']
        snapshots = [_snapshot(tasks, ref) for ref in refs]
        if any(snapshot is None for snapshot in snapshots):
            return None, False
        explicit = [snapshot for snapshot in snapshots if snapshot['task'].responsibility is not None]
        if explicit and len(refs) > 1:
            ambiguous = True
        lines.extend(_text(snapshot) for snapshot in explicit)
    return list(dict.fromkeys(lines)), ambiguous


def project_sources(value, original_context, tasks, episodes, *, resolve):
    """Shared initial/retry/reopen view, after normal source availability checks."""
    ids = episode_ids(original_context)
    if not ids:
        return value
    result = copy.deepcopy(value)
    current = capture(tasks, ids, episodes) if resolve else None
    saved = binding(original_context)
    lines, ambiguous = describe(current, tasks) if current is not None else (None, False)
    # Old metadata can render only if no explicit task decision could be contradicted.
    stale = lines is None or current is None or (saved != current if saved is not None else bool(lines))
    if stale:
        return _withhold(result)
    shown = value.get('metadata', {}).get('context', {})
    shown_ids = {ref.get('episode_id') for key in ('source_links', 'quellen')
                 for ref in shown.get(key, []) if isinstance(ref, dict)}
    displayed = {**current, 'sources': [source for source in current['sources'] if source['episode_id'] in shown_ids]}
    lines, ambiguous = describe(displayed, tasks)
    if lines is None or capture(tasks, ids, episodes) != current:
        return _withhold(result)
    if lines:
        if ambiguous:
            lines.append('Diese Quelle ist mit mehreren Aufgaben verknüpft. Für eine einzelne Zuständigkeit: ' + CLARIFY)
        result['content'] = '\n'.join(lines) + '\n\nHistorische Quellenangabe — keine aktuelle Zuständigkeitsbestätigung:\n' + result['content']
        context = result['metadata']['context']
        context.pop('satzantwort', None)
        context.pop('original_fallback', None)
    return result


def _withhold(result):
    from . import task_status_answers as status
    prior = result['metadata'].get('context', {})
    context = {**status.base_context(), 'memory_answer_withheld': True, 'task_status_view': True}
    # Invalidating local display does not undo the source-only cloud call that
    # already happened. Preserve its existing receipt, never source/task text.
    if (isinstance(prior.get('gedaechtnis_cloud'), dict)
            and (prior.get('answer_contract') or {}).get('model_egress') == 'external'):
        context.update(gedaechtnis_cloud=copy.deepcopy(prior['gedaechtnis_cloud']), model_called=True,
                       answer_contract={'version': 1, 'status': 'invalidated', 'model_called': True,
                                        'model_egress': 'external', 'semantic_validation': False,
                                        'selected_assertion_ids': []})
    result['content'] = WITHHELD
    result['metadata']['context'] = context
    return result
