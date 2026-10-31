"""Interner, quellengebundener Nachweis ganzer skalarer DOCX-Feldzeilen."""
import hashlib
import json
import re

TAG = 'docx-native-rows:'
_DRAFT = re.compile(r'\b(?:entwurf\w*|vorläufig\w*|vorlaeufig\w*|unverbindlich\w*|verworfen\w*|ungültig\w*|ungueltig\w*|nicht\s+freigegeben|noch\s+offen)\b', re.I)
_LABEL = re.compile(r'[\wäöüÄÖÜß ()/\-]+:?')
_VALUE = re.compile(r'[0-9][0-9.,:/+\-]*')


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def capture(body, main, rows, source, parent):
    marker = 'Word-Haupttext\n' + main
    if not rows or body.count(marker) != 1:
        return []
    start = body.index(marker) + len('Word-Haupttext\n')
    data = {'v': 1, 'body': digest(body), 'data': [start, start + len(main), digest(main)],
            'rows': [[start + a, start + b] for a, b in rows], 'source': source, 'parent': parent}
    return [TAG + json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'))]


def _record(row):
    pending, value_seen = False, False
    for cell in row.split('\t'):
        bits = cell.split('\n')
        label = bits[0].strip()
        scalar = lambda s: bool(_VALUE.fullmatch(re.sub(r'[ \t]+', '', s)))
        if len(bits) == 1 and scalar(label):
            if not pending:
                return False
            pending, value_seen = False, True
            continue
        if not label and len(bits) == 1:
            pending = False
            continue
        if len(bits) > 2 or not _LABEL.fullmatch(label) or not any(c.isalpha() for c in label):
            return False
        pending = len(bits) == 1
        if len(bits) == 2 and bits[1].strip(' \t'):
            if not scalar(bits[1]):
                return False
            value_seen = True
    return value_seen


def read(snapshot, fingerprint, visible, persons=()):
    """None: ungültiger Proof; (): gültig, keine geeignete sichtbare Row; sonst Raw-Zeilen."""
    from .working_memory_store import source_fingerprint
    from .working_memory_analysis import _unique_object
    from . import satzpruefung as sp
    from .episodes import EpisodeKind
    from .model import SourceType
    from .anhaenge import _DOCX_KOPF, _DOCX_UMFANG
    try:
        if not snapshot or not snapshot.current() or source_fingerprint(snapshot) != fingerprint:
            return None
        ep = snapshot.episode
        if (ep.kind is not EpisodeKind.DOCUMENT or ep.provenance.source_type is not SourceType.EMAIL
                or not snapshot.mail_parent_valid or not snapshot.mail_parent_fingerprint):
            return None
        tags = [t[len(TAG):] for t in ep.tags if t.startswith(TAG)]
        parents = [t[len('mail-parent:'):] for t in ep.tags if t.startswith('mail-parent:')]
        if (len(tags) != 1 or len(tags[0]) > 6000 or len(parents) != 1
                or 'anhang:gelesen' not in ep.tags or 'source:truncated' in ep.tags):
            return None
        data = json.loads(tags[0], object_pairs_hook=_unique_object)
        if (type(data) is not dict or set(data) != {'v', 'body', 'data', 'rows', 'source', 'parent'}
                or type(data['v']) is not int or data['v'] != 1 or data['body'] != digest(ep.body)
                or any(type(data[k]) is not str for k in ('body', 'source', 'parent'))
                or data['source'] != snapshot.source_key or data['parent'] != parents[0]
                or not re.fullmatch(r'mail:[a-f0-9]{64}:anhang:[1-9][0-9]*', snapshot.source_key)
                or type(data['data']) is not list or len(data['data']) != 3):
            return None
        start, end, sha = data['data']
        if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(ep.body)
                or type(sha) is not str or sha != digest(ep.body[start:end]) or type(data['rows']) is not list
                or not 1 <= len(data['rows']) <= 64):
            return None
        head, _, rest = ep.body.partition('\n\n')
        if (start != len(head) + 2 + len(_DOCX_KOPF) or not rest.startswith(_DOCX_KOPF)
                or ep.body.count(_DOCX_KOPF) != 1 or ep.body[end:] != '\n\n' + _DOCX_UMFANG):
            return None
        main = ep.body[start:end]
        spans, previous = [], start
        for pair in data['rows']:
            if type(pair) is not list or len(pair) != 2:
                return None
            a, b = pair
            if (type(a) is not int or type(b) is not int
                    or not previous <= a < b <= end or a < start):
                return None
            previous = b
            row = ep.body[a:b]
            if (row != row.strip() or ep.body.count(row) != 1 or (a > start and ep.body[a - 2:a] != '\n\n')
                    or (b < end and ep.body[b:b + 2] != '\n\n')):
                return None
            spans.append((a, b, row))
        if sp._ZITATZEICHEN.search(main) or _DRAFT.search(main):
            return ()
        atomic = (*sp.originalregelabsatz_einheiten(main), *(t for t in sp.originalabschnitt_stellen(main)
            if sp.originalregeln(t[2])))
        result = []
        for a, b, row in spans:
            if len(row) > 400 or not _record(row):
                continue
            if (sp.originalregeln(row) or sp._PERSONENBEZUG.search(row) or sp._PERSONENROLLE.search(row)
                    or sp._ENDLICH.search(row)
                    or any(a - start < y and b - start > x for x, y, _ in atomic)
                    or any(re.search(r'(?<!\w)' + re.escape(n) + r'(?!\w)', row, re.I)
                           for name in persons for n in (name, name.split()[0]) if n)):
                continue
            if row in visible and '[…]' not in row and '[gekürzt,' not in row:
                result.append(row)
        return tuple(result)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return None


def review_key(question, row, refs, model):
    return digest(json.dumps(['native-question-v1', question, row, refs, model], sort_keys=True, ensure_ascii=False))
