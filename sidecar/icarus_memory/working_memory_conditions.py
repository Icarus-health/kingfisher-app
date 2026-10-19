"""Preserve explicit source conditions without inferring task ownership.

This is a narrow downgrade after the mail-history guard, not a second
classifier. Clear leading clauses and postposed offer-acceptance conditions are
evidence; the grammatical "Wenn" of a polite request is not sufficient.
Only an immediately preceding voluntary list offer can qualify its enrollment
details; an offer elsewhere never makes an unrelated paragraph conditional.
Mixed blocks keep their complete source reference and become uncertain because
one block label cannot safely express both an independent action and a condition.
Impersonal registration-route information alone does not establish a request.
"""
import re


_STATEMENTS = re.compile(r"(?<=[.!?;])\s+")
_CONDITION_START = re.compile(r"^(?:wenn|falls|sofern|sollten?)\b", re.I)
_CONDITION = re.compile(r"^(?:wenn|falls|sofern|sollten?)\b[^,?;]+,", re.I)
# These two inversions have different meanings. Keep their evidence narrow:
# a reply contingent on accepting an offer, versus a conventional polite ask.
_OFFER_REPLY = re.compile(
    r"^(?:bitte\s+)?(?:melden\s+sie\s+sich|geben\s+sie\s+rückmeldung|antworten\s+sie)\b[^,;!?]*,"
    r"\s*(?:falls|sofern|wenn)\s+sie\b[^,.!?;]*\b(?:auftrag|angebot)\b"
    r"[^,.!?;]*\b(?:übernehmen|annehmen)\b[^,.!?;]*[.!]?$", re.I,
)
_POLITE_REQUEST = re.compile(
    r"^wenn\s+sie\s+(?:mir|uns)\s+bitte\b[^,?;]+,\s*(?:wäre\s+ich|wären\s+wir)"
    r"\s+ihnen\s+(?:sehr\s+)?dankbar[.!]?$", re.I,
)
_QUALIFIER = re.compile(r"^(?:nicht vorher|nur dann|erst dann)[.!?]?$", re.I)
_INDEPENDENT = re.compile(
    r"\b(?:unabhängig\s+(?:davon|von)|auf\s+jeden\s+fall|in\s+jedem\s+fall|so\s+oder\s+so|ohnehin)\b",
    re.I,
)
_PARAGRAPH = re.compile(r"\r?\n[ \t]*(?:\r?\n[ \t]*)+")
_ENROLLMENT = re.compile(r"^Für\s+die\s+Aufnahme\s+benötigen\s+wir\b", re.I)
_LIST = r"\b(?:mail[- ]?)?verteiler\b"
_VOLUNTARY_LIST = re.compile(
    r"(?:^|[.!?]\s+)(?:gerne\s+können\s+wir\s+Sie\b[^.!?]*" + _LIST + r"[^.!?]*\baufnehmen\b|"
    r"wenn\s+Sie\s+möchten\b[^.!?]*" + _LIST + r"[^.!?]*\bauf(?:nehmen)?\b|"
    r"Sie\s+können\b[^.!?]*\bselbst\s+entscheiden,\s*ob\b[^.!?]*" + _LIST + r")", re.I,
)
_MANDATORY = re.compile(r"\b(?:müssen|verpflichtend|vorgeschrieben|Pflichtregistrierung)\b", re.I)
_JOINED = re.compile(r"\bSie\s+haben\b[^.!?]*\b(?:angemeldet|zugestimmt|bestätigt)\b", re.I)
# Finite route grammar, never a wildcard across arbitrary clauses. Unknown
# channels stay with the model's classification rather than swallowing an ask.
_REGISTRATION_ROUTE = re.compile(
    r"^(?:(?:(?:die|eine)\s+)?(?:Anmeldung|Registrierung)\s+ist\s+"
    r"(?:(?:nur|ausschließlich|schriftlich|online|digital|elektronisch)\s+)*|"
    r"Es\s+ist\s+(?:(?:nur|ausschließlich)\s+)?(?:eine\s+)?"
    r"(?:(?:schriftliche|digitale|elektronische)\s+)?(?:Anmeldung|Registrierung)\s+)"
    r"(?:über|per)\s+(?:(?:den|das|die)\s+)?"
    r"(?:[\w-]*(?:portal|shop)|Formular|E-Mail|Post)"
    r"(?:\s+(?:unter\s+)?<?https?://[^\s<>;,!?]+>?)?\s+möglich[.!]?$", re.I,
)
_REGISTRATION_ACTION = re.compile(
    r"\b(?:bitte|Sie|Ihr\w*|wir|ich|müssen|muss|sollen|soll|verpflicht\w*|\w*pflicht\w*|"
    r"erforderlich|notwendig|bestätigt|gebucht|reserviert)\b", re.I,
)


def _registration_info(text):
    """A complete impersonal route statement, without an action or obligation."""
    text = ' '.join(text.split())
    text = re.sub(r"^\*{0,2}(?:Anmeldung|Registrierung):\*{0,2}\s*", '', text, flags=re.I)
    return bool(_REGISTRATION_ROUTE.fullmatch(text) and not _REGISTRATION_ACTION.search(text))


def _enrollment_kind(episode, item, items):
    """Only literal adjacent list context can qualify the enrollment details."""
    body = episode.body
    text = body[item['start']:item['end']]
    if not _ENROLLMENT.match(text):
        return None
    boundaries = list(_PARAGRAPH.finditer(body, 0, item['start']))
    if not boundaries or body[boundaries[-1].end():item['start']].strip():
        return None  # The referenced block must start this physical paragraph.
    lower = boundaries[-2].end() if len(boundaries) > 1 else 0
    upper = boundaries[-1].start()
    previous = body[lower:upper].strip()
    if not re.search(_LIST, previous, re.I) or any(line.lstrip().startswith('>') for line in previous.splitlines()):
        return None
    if any(row['kind'] == 'historical' and row['start'] < upper and row['end'] > lower for row in items):
        return None
    from .mail_quote_history import guard as history_guard
    probe = {'start': lower, 'end': upper, 'kind': 'fact'}
    if history_guard(episode, [probe])[0]['kind'] != 'fact':
        return None
    joined = _JOINED.search(previous)
    if joined and not re.search(r"\b(?:nicht|keine?)\b", joined[0], re.I):
        return None  # A completed opt-in is not an outstanding optional offer.
    voluntary = bool(_VOLUNTARY_LIST.search(previous))
    if _MANDATORY.search(previous):
        return 'uncertain' if voluntary else None
    if (not voluntary or _INDEPENDENT.search(text)
            or len(_STATEMENTS.split(text.strip())) > 1):
        return 'uncertain'
    return 'conditional'


def _condition_kind(text):
    statements, start = [], 0
    for boundary in _STATEMENTS.finditer(text):
        part = text[start:boundary.start()].strip()
        # An ordinal date before the first clause comma is not a sentence end
        # ("Wenn Sie am 12. November Zeit haben, ..."). After that comma,
        # preserve boundaries so an independent following request is visible.
        if (_CONDITION_START.match(part) and "," not in part
                and re.search(r"\d\.$", part)):
            continue
        if part:
            statements.append(part)
        start = boundary.end()
    if text[start:].strip():
        statements.append(text[start:].strip())
    conditional = [not _POLITE_REQUEST.fullmatch(part)
                   and bool(_CONDITION.match(part) or _OFFER_REPLY.fullmatch(part))
                   for part in statements]
    if not any(conditional):
        return None
    if not conditional[0] or _INDEPENDENT.search(text):
        return "uncertain"
    # A following independent sentence may contain another personal request.
    # Do not silently discard it by labelling the whole block conditional.
    if any(not condition and not _QUALIFIER.fullmatch(part)
           for part, condition in zip(statements, conditional)):
        return "uncertain"
    return "conditional"


def guard(episode, items):
    """Downgrade requests/commitments; keep original offsets and history labels.

Call after ``mail_quote_history.guard`` so proven history stays authoritative.
No source text, item, ownership annotation, or surrounding paragraph is modified.
"""
    body = getattr(episode, "body", None)
    if not isinstance(body, str):
        return items
    guarded = []
    for item in items:
        updated = dict(item)
        if item["kind"] in {"request", "commitment"}:
            kind = _condition_kind(body[item["start"]:item["end"]])
            if kind is None:
                kind = _enrollment_kind(episode, item, items)
            if kind is None and item['kind'] == 'request' and _registration_info(body[item['start']:item['end']]):
                kind = 'fact'
            if kind is not None:
                updated["kind"] = kind
        guarded.append(updated)
    return guarded
