"""Necessary literal case binding, never proof that a source answers the question.

Only explicitly typed references in the user's question activate this guard.
Unparsed scopes and independently scoped subquestions stay with the selector.
No model expansion, arbitrary word overlap, or persistent identity is trusted.
"""
import re

_DASHES = str.maketrans({'‐': '-', '‑': '-', '–': '-'})
_CODE = r'[a-zäöü]{1,16}(?:[-/][a-zäöü]{1,16})?[-/]?\d[\w/-]*'
_TYPED = re.compile(r'\b(?:auftrag|aufträge[n]?|vorgang|vorgänge[n]?|tickets?|projekt(?:e|en)?|fall|fälle[n]?|rechnung(?:en)?)'
                    r'\s+(?:(?:nr\.?|nummer)\s*)?(?P<code>' + _CODE + r')(?![\w/-])', re.I)
_CODES = re.compile(r'(?<![\w/-])' + _CODE + r'(?![\w/-])', re.I)
_COORDINATED = re.compile(r'\s*(?:,|und|oder|sowie|&)\s*(?P<code>' + _CODE + r')(?![\w/-])', re.I)
_OTHER_TOPIC = re.compile(r'\b(?:und|oder|sowie|außerdem|zusätzlich)\b|&', re.I)
_SCOPED_JOIN = re.compile(r'\x00\s*(?:,|und|oder|sowie|&)\s*\x00', re.I)
_SUBQUESTION = re.compile(r'\b(?:und|oder|sowie|außerdem|zusätzlich)\s+(?:auch\s+)?'
                          r'(?:wer|was|wann|wo|wie|welch\w*|ist|sind|hat|haben|gibt)\b', re.I)
_NEGATIVE = re.compile(r'\b(?:nicht|kein\w*|außer|ausser|statt|ohne|ausgenommen)\b', re.I)


def wanted(question):
    text = question.translate(_DASHES)
    # A global constraint would erase legitimate evidence for another question.
    # Negated scopes also need language interpretation, not a positive ID set.
    if (_SUBQUESTION.search(text) or _NEGATIVE.search(text)
            or re.search(r'[?;]\s*\S', text) or not _TYPED.search(text)):
        return frozenset()
    # Union permits comparisons; unrelated untyped mail numbers are not scopes.
    found, spans = set(), []
    for match in _TYPED.finditer(text):
        found.add(match['code'].casefold())
        end = match.end()
        while peer := _COORDINATED.match(text, end):
            found.add(peer['code'].casefold())
            end = peer.end()
        spans.append((match.start(), end))
    masked = text
    for start, end in reversed(spans):
        masked = masked[:start] + '\x00' + masked[end:]
    while _SCOPED_JOIN.search(masked):
        masked = _SCOPED_JOIN.sub('\x00', masked)
    # Without a language parser, remaining coordination may introduce an
    # independent topic even without a repeated interrogative ("... und Urlaub").
    if _OTHER_TOPIC.search(masked):
        return frozenset()
    return frozenset(found)


def permits(row, references):
    if not references or not row['id'].startswith('S'):
        return True
    text = '\n'.join(row.get(key, '') for key in ('context', 'title', 'project'))
    found = {match[0].casefold() for match in _CODES.finditer(text.translate(_DASHES))}
    return bool(found & references)
