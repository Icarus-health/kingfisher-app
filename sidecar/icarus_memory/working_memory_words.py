"""Conservative character-suffix candidates for German source search.

A suffix hit is only a retrieval hint, never a lemma, synonym or identity
equivalence. The answer selector still receives and checks the original text.
Short fragments, arbitrary substrings and sender metadata are excluded.
"""
import hashlib

from .episodes import sql_nicht_ignoriert
from .lexical import terms_v1

MIN_HEAD = 6
MAX_HEAD = 24
MIN_PREFIX = 3
MAX_WORD = 64
PREFIX = 'working-suffix-v1:'


def candidate_words(text):
    result = set()
    for word in terms_v1(text):
        if not word.isalpha() or not MIN_HEAD + MIN_PREFIX <= len(word) <= MAX_WORD:
            continue
        for length in range(MIN_HEAD, min(MAX_HEAD, len(word) - MIN_PREFIX) + 1):
            result.add(PREFIX + word[-length:])
    return result


def query_words(words):
    return {PREFIX + word for word in words
            if word.isalpha() and MIN_HEAD <= len(word) <= MAX_HEAD}


def backfill(connection):
    """Rebuild only derived search hashes; no model or source/state mutation.

    One bounded source item is decoded at a time. Invalid and oversized rows
    remain unavailable under the existing source-reference validation rules.
    """
    import json
    cursor = connection.execute(
        'SELECT i.id,i.start,i.end,e.document FROM working_memory_items i '
        'JOIN episodes e ON e.id=i.episode_id '
        'JOIN working_memory_sources s ON s.episode_id=i.episode_id '
        "WHERE s.status='complete' AND s.fingerprint=i.fingerprint "
        f"AND {sql_nicht_ignoriert('e')} "
        'AND length(CAST(e.document AS BLOB))<=64000')
    changed = False
    for identifier, start, end, document in cursor:
        try:
            value = json.loads(document)
            body, title = value['body'], value['title']
            if (not isinstance(body, str) or not isinstance(title, str)
                    or len(body) > 12000 or not 0 <= start < end <= len(body)):
                continue
        except (ValueError, KeyError, TypeError):
            continue
        words = candidate_words(title[:300] + ' ' + body[start:end])
        before = connection.total_changes
        connection.executemany(
            'INSERT OR IGNORE INTO working_memory_tokens(item_id,token_hash) VALUES(?,?)',
            ((identifier, hashlib.sha256(word.encode('utf-8')).hexdigest()) for word in words))
        changed = changed or connection.total_changes > before
    if changed:
        connection.execute('UPDATE working_memory_scan SET revision=revision+1 WHERE id=1')
