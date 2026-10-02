"""Conservative project guard over original source text, never an identity linker.

Explicit project labels are evidence of what a source discusses, not proof of
truth or a persistent workspace assignment. Unlabelled prose stays with the
existing selection path. No additional model call or index mutation is needed.
"""
import re
from .lexical import terms_v1

_NAME = r'[A-ZÄÖÜ][\w-]*(?:[ \t]+[A-ZÄÖÜ][\w-]*){0,3}'
_PROJECT = re.compile(r'\b[Pp]rojekt[ \t]+(' + _NAME + r')(?=\s|[,:;.?!]|$)')
_QUALIFIER = re.compile(r'\b(?:für|zu|im|in|zum)[ \t]+(?:[Pp]rojekt[ \t]+)?(' + _NAME + r')[?!.\s]*$')
_SINGULAR = re.compile(r'^(?:wann|bis wann|wer|wo|wie|was|hat|ist|wird|unter welch\w*)\b', re.I)
_PLURAL = re.compile(r'\b(?:alle|beide\w*|jeweils|mehrere|vergleiche?|übersicht|zusammen|gegenüber)\b', re.I)
_NEGATIVE = re.compile(r'\b(?:nicht|kein\w*|außer|ausser|statt|ohne|ausgenommen)\b', re.I)
_NOUN = re.compile(r'\b[A-ZÄÖÜ][\w-]*\b')
_TOPIC = re.compile(r'\b(?:die|der|das|den|dem|des|zur|zum)\s+([A-ZÄÖÜ][\w-]*)\b')


def labels(row):
    """Only a directory label or an explicit, unnegated project mention.

    Quoted lines and negative/multiple-project sentences cannot establish a
    single source scope. Keep all labels when a source discusses several.
    """
    if row.get('project'):
        return {row['project'].strip().casefold()}
    found = set()
    for line in row.get('context', '').splitlines():
        if line.lstrip().startswith(('>', '"', '„')):
            continue
        for sentence in re.split(r'[.!?]\s+', line):
            if _NEGATIVE.search(sentence):
                continue
            for match in _PROJECT.finditer(sentence):
                # A coordinated label must not silently become one project.
                if re.match(r'\s+(?:und|oder|bzw\.?|&)\s', sentence[match.end():]):
                    return set()
                found.add(match[1].casefold())
    return found


def source_label(context):
    """A choice caption quoted from the same unambiguous original project name."""
    found = labels({'context': context})
    if len(found) != 1:
        return ''
    name = next(iter(found))
    for match in _PROJECT.finditer(context):
        if match[1].casefold() == name:
            return 'Projekt ' + match[1]
    return ''


def adjust(question, rows, selected, status):
    """Filter explicit mismatches; restore an omitted, same-topic scope peer.

    Names alone do not merge projects or people. The guard never changes
    confirmed K-claims and never promotes a model's unknown to an answer.
    """
    automatic = [row for row in rows if row['id'].startswith('S')]
    by_id = {row['id']: row for row in automatic}
    scopes = {row['id']: labels(row) for row in automatic}
    selected = list(selected)
    if not selected:
        return selected, status
    # Negated/compound query scopes require linguistic interpretation. Do not
    # turn a name merely mentioned there into a positive scope selector.
    if _NEGATIVE.search(question):
        return selected, status
    known = set().union(*scopes.values()) if scopes else set()
    wanted = {label for label in known
              if re.search(r'(?<!\w)' + re.escape(label) + r'(?!\w)', question, re.I)}
    qualifier = _QUALIFIER.search(question)
    if qualifier and not wanted:
        # An unknown qualifier may be a recipient or object, not a project.
        # Its occurrence in original text is enough to leave interpretation
        # to the existing selector instead of rejecting a legitimate report.
        mention = re.compile(r'(?<!\w)' + re.escape(qualifier[1]) + r'(?!\w)', re.I)
        if not any(mention.search(row.get('context', '')) for row in automatic):
            wanted = {qualifier[1].casefold()}
    if wanted:
        selected = [identifier for identifier in selected
                    if not scopes.get(identifier) or scopes[identifier] & wanted]
        return selected, status if selected else 'unknown'
    # A model's person label must not suppress a project clarification for
    # documents without sender identities. Preserve actual identity ambiguity.
    scope_status = status in {'reports', 'scope', 'conflict'} or (
        status == 'person' and all(not by_id.get(i, {}).get('participants') for i in selected))
    if (not scope_status or not _SINGULAR.match(question.strip())
            or _PLURAL.search(question) or any(i.startswith('K') for i in selected)):
        return selected, status
    # A capitalized content word in the question must occur in both indexed
    # spans. Shared verbs/person metadata alone must not introduce a peer.
    # Without an explicit noun phrase we cannot distinguish a person's name
    # from the subject being asked about; do not invent a shared topic.
    if not _TOPIC.search(question):
        return selected, status
    anchors = set().union(*(terms_v1(m[0]) for m in _NOUN.finditer(question) if m.start() > 0))
    anchors -= set().union(*(terms_v1(label) for label in known)) if known else set()
    additions = []
    for identifier in selected:
        scope = scopes.get(identifier, set())
        if len(scope) != 1:
            continue
        own_terms = terms_v1(by_id[identifier].get('text', ''))
        for row in automatic:
            other = scopes[row['id']]
            if (len(other) == 1 and not scope & other
                    and anchors and anchors <= own_terms & terms_v1(row.get('text', ''))):
                additions.append(row['id'])
    if additions:
        return list(dict.fromkeys(selected + additions)), 'scope'
    return selected, status
