"""Protect current-state selection from silently omitted change evidence.

This is a coverage guard, not a supersession or identity engine. Matching query
words can justify showing an original but never prove that it cancels another
source. Unresolved changes therefore stay quotes and require clarification.
"""
from datetime import datetime
import re

from .lexical import terms_v1

_CURRENT = re.compile(r'\b(?:aktuell\w*|derzeit|jetzt|noch|offen\w*)\b', re.I)
_HISTORY = re.compile(r'\b(?:ursprüng\w*|damals|früher|historisch\w*|hatte|vorher|gestern|vorgestern|letzte[nmrs]?|vergangene[nmrs]?)\b', re.I)
# These generic words cannot establish which task/event the question concerns.
_GENERIC = frozenset({'stand', 'hilfe', 'helfen', 'zusage', 'zusagen', 'zugesagt', 'verbindlich', 'heute', 'aufgabe', 'aufgaben',
    'frist', 'fristen', 'termin', 'termine', 'deadline', 'deadlines', 'gilt', 'gelten', 'beim',
    'meine', 'meiner', 'meinen', 'meinem', 'unser', 'unsere', 'unserer', 'was', 'welche', 'welchen',
    'welcher', 'wie', 'jetzt', 'aktuell', 'aktuelle', 'aktuellen', 'aktueller', 'derzeit', 'noch',
    'offen', 'offene', 'offenen', 'ich', 'mir', 'mich', 'ist', 'sind', 'der', 'die', 'das', 'für',
    'zum', 'zur', 'mit', 'habe', 'haben', 'muss', 'müssen'})
_CANCEL = re.compile(r'\b(?:abgesagt|absagen|absage|storniert|stornierung|entfällt|entfaellt|'
    r'findet\s+nicht\s+statt|fällt\s+aus|zurückgezogen|gestrichen|'
    r'(?:meine\s+)?zusage\b(?:(?!\bnicht\b)[^.;!?\n]){0,100}\b(?:streichen|zurückziehen)|'
    r'nicht\s+mehr\s+(?:nötig|notwendig|erforderlich)|'
    r'(?:kann|werde)\b[^.;!?\n]{0,100}\bnicht\b[^.;!?\n]{0,60}\b(?:helfen|übernehmen|teilnehmen))\b', re.I)
_ADDITIVE = r'(?!\s+(?:nur|bloß|bloss|allein)\b)'
_NEGATED = re.compile(r'\b(?:nicht|keine?|niemals)\b' + _ADDITIVE + r'[^.;!?\n]{0,45}$', re.I)
_FOLLOWING_NEGATION = re.compile(r'^\s+(?:(?:ist|wurde|wird|werden|war)\s+)?nicht\b' + _ADDITIVE, re.I)


def explicit_cancellation(text):
    """Detect explicit cancellation wording; a negated cancellation is not one.

    Only the trigger clause is inspected. This is deliberately not used to
    rewrite facts, delete commitments, or assert who cancelled whose promise.
    """
    for match in _CANCEL.finditer(text):
        start = max((text.rfind(c, 0, match.start()) for c in '.;!?\n'), default=-1) + 1
        before = text[start:match.start()]
        # Negation is part of these positive cancellation phrases themselves.
        intrinsic = bool(re.match(r'findet\s+nicht|nicht\s+mehr|(?:kann|werde)\b', match.group(), re.I))
        if (not intrinsic and _NEGATED.search(before)) or _FOLLOWING_NEGATION.match(text[match.end():]):
            continue
        return True
    return False


def _date(row):
    try:
        value = datetime.fromisoformat(row.get('occurred_at') or '')
        return value if value.tzinfo is not None else None
    except (TypeError, ValueError):
        return None


def omitted(question, rows, ids, status, *, historical=False):
    """IDs of query-matching changes omitted from a current source report.

    All concrete query words must occur in both the chosen original and the
    candidate. Known person and project exclusions remain exclusions. A source
    created earlier can still establish today's current state. Unknown source time can require clarification but cannot prove
    'later'. An older change does not challenge a newer selected report.
    """
    if historical or status != 'reports' or not _CURRENT.search(question) or _HISTORY.search(question):
        return []
    anchors = {word for word in terms_v1(question) if len(word) >= 3 and word not in _GENERIC}
    if not anchors:
        return []
    selected = [row for row in rows if row['id'] in ids and row['id'].startswith('S')
                and anchors <= set(terms_v1(row.get('context', '')))]
    if not selected:
        return []
    projects = {row.get('project_id') for row in selected if row.get('project_id')}
    changes = []
    for row in rows:
        if (row['id'] in ids or not row['id'].startswith('S') or row.get('andere_person')
                or row.get('kind') not in {'change', 'status'}
                or not anchors <= set(terms_v1(row.get('context', '')))):
            continue
        if projects and row.get('project_id') and row['project_id'] not in projects:
            continue
        if row['kind'] != 'change' and not explicit_cancellation(row.get('context', '')):
            continue
        date = _date(row)
        if date is not None and all(_date(chosen) is not None and _date(chosen) > date for chosen in selected):
            continue
        changes.append(row['id'])
    return changes
