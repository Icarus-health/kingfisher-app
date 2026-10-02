"""Owner-only original-source display. No model input, fact inference or writes.

Persist references only. Every display resolves them afresh; source texts never
become conversation memory. Sources already used for knowledge are deferred so
this narrow fallback cannot silently revive a corrected/retracted interpretation.
"""
import copy
import hashlib
import json
import re
import sqlite3
import unicodedata

from .model import readable_time

NEUTRAL = 'Quellensuche gespeichert. Originalstellen werden beim Öffnen erneut geprüft.'
UNAVAILABLE = 'Die damaligen Quellenstellen sind nicht mehr unverändert verwendbar. Bitte erneut suchen.'
MAX_DOCUMENT_BYTES = 768 * 1024
MAX_EXCERPT = 800
MAX_REFS = 3


def literal_query(question):
    if not isinstance(question, str) or not re.search(r'\b(?:quellen|originaltext|dokumenten)\b', question, re.I):
        return None
    matches = re.findall(r'"([^"\n]+)"|„([^“\n]+)“', question)
    if len(matches) != 1:
        return None
    literal = next(value for value in matches[0] if value)
    if not 3 <= len(literal) <= 120 or any(unicodedata.category(c) == 'Cc' for c in literal):
        return None
    return literal


def _snapshot(episodes, identifier):
    try:
        snapshot = episodes.belegbarer_snapshot(identifier, max_bytes=MAX_DOCUMENT_BYTES)
        if snapshot is None:
            return None
        return snapshot
    except (ValueError, TypeError, KeyError, sqlite3.Error, UnicodeError):
        return None


def _projection(snapshot):
    episode = snapshot.episode
    return {
        'episode_id': episode.id, 'digest': episode.digest, 'title': episode.title,
        'source_type': episode.provenance.source_type.value,
        'source_ref': episode.provenance.source_ref,
        'occurred_at': episode.occurred_at.isoformat() if episode.occurred_at else None,
        'recorded_at': episode.recorded_at.isoformat(),
        'ingestion_truncated': 'source:truncated' in episode.tags,
        'source_key': snapshot.source_key, 'head_id': snapshot.head_id,
        'generation': snapshot.generation,
    }


def _origin(episode):
    """Herkunft als Satz. Technische Kennungen (Message-ID, Konto-ID) bleiben
    in den Metadaten; sichtbar ist, was ein Mensch dazu sagen würde."""
    kind = episode.provenance.source_type.value
    ref = episode.provenance.source_ref or ''
    name = ref.split(':', 1)[1] if ':' in ref else ref
    if kind == 'email':
        sender = episode.participants[0] if episode.participants else ''
        return f'E-Mail von {sender[:200]}' if sender else 'E-Mail'
    if kind == 'chat':
        return 'Dein Gesprächsbeitrag'
    if kind == 'calendar':
        return 'Kalendereintrag'
    if kind == 'manual_correction':
        return 'Deine Berichtigung'
    prefixes = {'upload': 'Hochgeladenes Dokument', 'mac-folder': 'Datei aus freigegebenem Ordner',
                'datei': 'Datei', 'vault': 'Notiz', 'notion': 'Notion-Seite'}
    label = prefixes.get(ref.split(':', 1)[0]) if ':' in ref else None
    if label:
        return f'{label} „{name[:200]}“'
    return 'Dokument' if kind == 'document' else ''


def _fingerprint(snapshot):
    return hashlib.sha256(json.dumps(_projection(snapshot), ensure_ascii=False,
                                    sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _match_span(body, literal):
    """Casefold matching, but original Python character offsets (e.g. ß -> ss)."""
    start = body.casefold().find(literal.casefold())
    if start < 0:
        return None
    end = start + len(literal.casefold())
    offset, original_start = 0, None
    for index, char in enumerate(body):
        next_offset = offset + len(char.casefold())
        if original_start is None and next_offset > start:
            original_start = index
        if next_offset >= end:
            return original_start, index + 1
        offset = next_offset
    return None


def prepare(question, episodes, claims):
    literal = literal_query(question)
    if literal is None or episodes is None or claims is None:
        return None
    from .source_search import search
    result = search(episodes, literal)
    coverage = {key: value for key, value in result.items() if key != 'ids'}
    coverage.update(scope='stored_current_message_document_bodies', candidate_count=len(result['ids']),
                    checked_count=0, deferred_count=0, display_limited=False)
    refs = []
    for identifier in result['ids']:
        if len(refs) == MAX_REFS:
            coverage['display_limited'] = True
            break
        coverage['checked_count'] += 1
        snapshot = _snapshot(episodes, identifier)
        if snapshot is None or not claims.source_is_unclaimed(identifier):
            coverage['deferred_count'] += 1
            continue
        span = _match_span(snapshot.episode.body, literal)
        if span is None:
            coverage['deferred_count'] += 1
            continue
        start = max(0, span[0] - 200)
        refs.append({'episode_id': identifier, 'fingerprint': _fingerprint(snapshot),
                     'start': start, 'end': min(len(snapshot.episode.body), start + MAX_EXCERPT)})
    return {'version': 1, 'refs': refs, 'coverage': coverage}


def _resolve(ref, episodes, claims):
    if (not isinstance(ref, dict) or set(ref) != {'episode_id', 'fingerprint', 'start', 'end'}
            or not isinstance(ref['episode_id'], str) or not isinstance(ref['fingerprint'], str)
            or len(ref['fingerprint']) != 64 or type(ref['start']) is not int or type(ref['end']) is not int
            or not 0 <= ref['start'] < ref['end'] or ref['end'] - ref['start'] > MAX_EXCERPT):
        return None
    snapshot = _snapshot(episodes, ref['episode_id'])
    if (snapshot is None or _fingerprint(snapshot) != ref['fingerprint']
            or ref['end'] > len(snapshot.episode.body)
            or claims is None or not claims.source_is_unclaimed(ref['episode_id'])):
        return None
    return snapshot


def render(answer, episodes, claims):
    if (not isinstance(answer, dict) or answer.get('version') != 1
            or not isinstance(answer.get('refs'), list) or len(answer['refs']) > MAX_REFS
            or not isinstance(answer.get('coverage'), dict)):
        return UNAVAILABLE, [], 'source_unavailable'
    coverage = answer['coverage']
    rows = []
    for ref in answer['refs']:
        snapshot = _resolve(ref, episodes, claims)
        if snapshot is not None:
            rows.append((ref, snapshot))
    # Fresh final validation after collection, also for direct store mutations.
    rows = [(ref, snapshot) for ref, snapshot in rows if _resolve(ref, episodes, claims) is not None]
    invalid = len(rows) != len(answer['refs'])
    limited = any(coverage.get(key) for key in
                  ('truncated', 'budget_exhausted', 'oversize_skipped', 'display_limited', 'deferred_count'))
    links, lines = [], []
    if rows:
        lines = ['Quelle berichtet · nicht bestätigt',
                 'Gefundene Originalstellen; keine Feststellung, welche Angabe zutrifft oder aktuell gilt.']
        for number, (ref, snapshot) in enumerate(rows, 1):
            p, body = _projection(snapshot), snapshot.episode.body
            lines.extend(['', f"Quelle {number}: {p['title'][:200]}",
                          f"Quellenzeit: {readable_time(p['occurred_at'])} · Erfasst: {readable_time(p['recorded_at'])}"])
            origin = _origin(snapshot.episode)
            if origin:
                lines.append('Herkunft: ' + origin)
            if ref['start'] or ref['end'] < len(body):
                lines.append('Ausschnitt; Text davor oder danach ist hier nicht dargestellt.')
            lines.append(body[ref['start']:ref['end']])
            if p['ingestion_truncated']:
                lines.append('Schon bei der Aufnahme gekürzt; Originalteile fehlen.')
            links.append({'episode_id': p['episode_id'], 'label': f'Originalquelle {number} öffnen'})
        status = 'source_report'
    elif answer['refs']:
        lines, status = [UNAVAILABLE], 'source_unavailable'
    else:
        lines = ['Im durchsuchten gespeicherten Text wurde keine verwendbare Originalstelle gefunden.']
        status = 'source_search_incomplete' if limited else 'no_match_in_searched_text'
    lines.extend(['', 'Suchumfang: gespeicherte, zugelassene aktuelle Nachrichten- und Dokumenttexte. '
                  'Andere Kanäle, fehlende Anlagen und nicht aufgenommene Teile sind damit nicht geprüft.'])
    if limited or invalid:
        lines.append('Die Suche oder Anzeige ist unvollständig: Grenzen wurden erreicht oder Quellen zurückgestellt.')
    if coverage.get('deferred_count'):
        lines.append('Zurückgestellt: nicht prüfbare Quellen oder Quellen mit bestehenden Wissensableitungen. '
                     'Deren Korrekturstatus wird hier nicht umgangen.')
    return '\n'.join(lines), links, status


def project_message(message, episodes, claims, *, resolve=True):
    """Fresh API projection; never save its resolved text/links to the transcript."""
    context = message.get('metadata', {}).get('context')
    if message.get('role') != 'assistant' or not isinstance(context, dict) or 'source_answer' not in context:
        return message
    result = copy.deepcopy(message)
    text, links, status = render(context['source_answer'], episodes, claims) if resolve else (
        'Ältere Quellenantwort: Die Anzeige ist begrenzt. Bitte erneut nach der Originalstelle fragen.',
        [], 'source_not_resolved')
    result['content'] = text
    context = result['metadata']['context']
    context['source_links'] = links
    context.setdefault('answer_contract', {})['status'] = status
    return result
