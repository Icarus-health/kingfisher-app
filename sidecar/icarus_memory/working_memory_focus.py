"""Bounded checks on selected original reports, not a general relevance model.

Reject an explicitly different travel record; ask about ambiguous full names in
singular delivery questions. Neither check creates person identities or facts.
"""
import re

# An untyped reservation is left to the selector. Only an explicitly competing
# category is rejected, preserving paraphrases and generic ticket references.
_TRAVEL = {
    'rail': re.compile(r'\b(?:zug(?:buchung(?:en)?|fahrt(?:en)?|ticket\w*)?|bahn(?:buchung\w*|fahrkarte\w*|ticket\w*|fahrt\w*)?|fahrkarte\w*|ice|intercity)\b', re.I),
    'hotel': re.compile(r'\b(?:hotel\w*|unterkunft\w*|übernachtung\w*)\b', re.I),
    'flight': re.compile(r'\b(?:flug\w*|flieger|flight\w*)\b', re.I),
}
_RECORD_QUERY = re.compile(r'\b(?:zug|bahn|hotel|flug)buchung(?:en)?\b', re.I)
_DELIVERY_PERSON = re.compile(
    r'^(?:wann|bis wann)\s+(?P<verb>liefert|schickt|sendet|verschickt|versendet)\s+'
    r'(?P<name>[A-ZÄÖÜ][a-zäöüß]+)\s+(?:die|den|das|seine|ihre)\s+(?P<object>[A-ZÄÖÜ][\w-]+)\b')


def adjust(question, rows, ids, status):
    """Keep unknown vocabulary with the model; guard only explicit mismatches."""
    by_id = {row['id']: row for row in rows}
    selected = list(ids)
    if _RECORD_QUERY.search(question):
        asked = {key for key, pattern in _TRAVEL.items() if pattern.search(question)}
        if len(asked) == 1:
            topic = next(iter(asked))
            kept = []
            for identifier in selected:
                row = by_id[identifier]
                # Confirmed claims have their own conflict/lineage handling.
                text = row.get('context', '')
                domains = {key for key, pattern in _TRAVEL.items() if pattern.search(text)}
                if not identifier.startswith('S') or not domains or topic in domains:
                    kept.append(identifier)
            selected = kept
            if not selected:
                return [], 'unknown'
    person = _DELIVERY_PERSON.match(question[:1].lower() + question[1:])
    if person and status in {'reports', 'person', 'conflict'}:
        # Only literal full-name subjects followed by the same asked action.
        # A season, address, adjacent noun or project label cannot establish a
        # person here. This is a clarification guard, never an identity merge.
        pattern = re.compile(r'(?<!\w)' + re.escape(person['name'])
                             + r'\s+([A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)?)\s+'
                             + re.escape(person['verb']) + r'\s+(?:die|den|das|seine|ihre)\s+'
                             + re.escape(person['object']) + r'\b')
        names = set()
        for identifier in selected:
            if identifier.startswith('S'):
                names.update(pattern.findall(by_id[identifier].get('text', '')))
        if len(names) > 1:
            return selected, 'person'
    return selected, status
