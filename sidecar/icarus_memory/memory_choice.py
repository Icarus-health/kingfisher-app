"""Conservative literal selection among already displayed evidence records.

This is not entity resolution: no aliases, registry labels, fuzzy matching,
identity links, or new facts are inferred. Unsupported language asks again.
"""
import re


_CONNECTIVES = frozenset('der die das den dem des im in am an aus vom von'.split())
_UNCERTAIN = frozenset(('nicht kein keine keinen keinem keiner keines ohne weder noch '
    'oder und aber außer ausser statt niemals nie not no neither nor or and '
    'vielleicht eventuell vermutlich angeblich falls wenn möglicherweise').split())


def select(message, rows):
    """Return aliases and method; [] means that a fresh clarification is needed."""
    text = message.strip().casefold()
    number = re.fullmatch(r'(?:\[([1-5])\]|(?:nummer |eintrag )?([1-5]))', text)
    if number:
        alias = 'E' + (number[1] or number[2])
        return ([alias], 'number') if alias in rows else ([], 'unresolved')
    # Closed syntax: short words only. Punctuation, addresses, identifiers,
    # negation, alternatives and commands cannot masquerade as a row number.
    if not re.fullmatch(r'[^\W\d_]+(?:\s+[^\W\d_]+){0,11}', text):
        return [], 'unresolved'
    words = text.split()
    if _UNCERTAIN.intersection(words):
        return [], 'unresolved'
    clues = [word for word in words if word not in _CONNECTIVES]
    if not clues:
        return [], 'unresolved'
    matches = []
    for alias, row in rows.items():
        words = re.findall(r'[^\W\d_]+', row['statement'].casefold())
        if _UNCERTAIN.intersection(words):
            continue
        # Preserve clue order, allowing intervening names and connective words.
        remaining = iter(words)
        if all(any(word == clue for word in remaining) for clue in clues):
            matches.append(alias)
    contexts = {(rows[alias]['subject_ref'], rows[alias]['target_ref'], rows[alias]['scope_ref'])
                for alias in matches}
    return (matches, 'literal') if len(contexts) == 1 else ([], 'unresolved')
