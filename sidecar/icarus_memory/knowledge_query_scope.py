"""Positive evidence preference for an explicit contact question.

A matching named context may move evidence forward. Different qualifiers
are not proof of different people: employer, location and department can
coexist. This module never excludes evidence or assigns identities.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .personenfrage import namensfolgen
from .word_forms import umschrift_gleich

_QUALIFIER = re.compile(
    r'\s+(?:aus|im|in|bei|beim|vom|von|an|am)\s+'
    r'(?:(?:der|dem|den|des|das|einer|einem)\s+)?'
    r'(?P<context>[A-ZÄÖÜ][\w-]*(?:\s+[A-ZÄÖÜ][\w-]*){0,3})(?![\w-])')
# Recognize a positive request, not an ever-growing blacklist of clauses.
# Other question forms keep their normal lexical/semantic ordering.
_CONTACT_REQUEST = re.compile(r'\s*(?:wo|wie)\s+(?:erreiche|kontaktiere)\s+ich\s+', re.I)


def _words(match):
    return tuple(umschrift_gleich(w) for w in match['context'].split())


@dataclass(frozen=True)
class ExplicitContext:
    name: re.Pattern
    context: tuple[str, ...]

    def matches(self, statement):
        occurrences = list(self.name.finditer(statement))
        if len(occurrences) != 1 or statement[:occurrences[0].start()].strip():
            return False
        context = _QUALIFIER.match(statement[occurrences[0].end():])
        return context is not None and _words(context) == self.context


def explicit_context(query):
    """Prefer a literal named contact context, without choosing a person.

    Full request matching leaves disputed affiliations, multiple alternatives,
    negation and unsupported syntax at their normal retrieval order.
    """
    if len(query) > 1200:
        return None
    for name in namensfolgen(query):
        if len(name.split()) < 2:
            continue
        pattern = re.compile(r'(?<![\w-])' + r'\s+'.join(map(re.escape, name.split())) + r'(?![\w-])', re.I)
        occurrences = list(pattern.finditer(query))
        if len(occurrences) != 1:
            continue
        occurrence = occurrences[0]
        if not _CONTACT_REQUEST.fullmatch(query[:occurrence.start()]):
            continue
        tail = query[occurrence.end():]
        context = _QUALIFIER.match(tail)
        if context is None or not re.fullmatch(r'\s*[?.]?\s*', tail[context.end():]):
            continue
        return ExplicitContext(pattern, _words(context))
    return None
