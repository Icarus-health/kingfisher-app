"""Conservative original-offset mail history guard, independent of model sections.

Only strong embedded mail headers establish history. This never resolves dates,
changes source text, or turns a model's irrelevant signature into useful evidence.
"""
import re

_DATE = re.compile(r'\b(?:19|20)\d{2}\b|\b\d{1,2}\.\d{1,2}\.\d{2}\b')
_FIELD = re.compile(r'^(von|gesendet|an|cc|betreff):\s*(\S.*)$', re.I)
_REPLY = re.compile(r'^(?:Am\s.+\bschrieb\b.*|On\s.+\bwrote)\s*:\s*$', re.I)
_PREFIX = re.compile(r'^[ \t]*(?:>[ \t]*)*')


def _ranges(body):
    lines, offset = [], 0
    for raw in body.splitlines(keepends=True):
        lines.append((offset, offset + len(raw), raw.rstrip('\r\n')))
        offset += len(raw)
    ranges = []
    tail = len(body)
    for index, (start, end, raw) in enumerate(lines):
        if start >= tail:
            break  # a proven Outlook tail already covers every later line
        text = _PREFIX.sub('', raw).strip()
        first = _FIELD.fullmatch(text)
        if first and first[1].lower() == 'von':
            # Exact ordered Outlook field sequence; blank lines and Cc are
            # allowed, prose or isolated From/Von words are insufficient.
            fields = ['gesendet', 'an', 'betreff']
            position = 0
            for _, _, following in lines[index + 1:index + 25]:
                following = _PREFIX.sub('', following).strip()
                if not following:
                    continue
                field = _FIELD.fullmatch(following)
                if field and field[1].lower() == 'cc' and position == 2:
                    continue
                if not field or field[1].lower() != fields[position]:
                    break
                if position == 0 and not _DATE.search(field[2]):
                    break
                position += 1
                if position == 3:
                    if raw.lstrip().startswith('>'):
                        # Explicit quote prefixes delimit inline replies too;
                        # an unquoted answer below them remains current.
                        ranges.extend((lower, upper) for lower, upper, line in lines[index:]
                                      if re.match(r'^[ \t]*>', line))
                    else:
                        tail = min(tail, start)
                    break
        if re.match(r'^(?:Am|On)\s', text, re.I):
            # Reply headers can wrap the sender address onto another line.
            # Require both an explicit date and the complete reply delimiter.
            header = text
            stop = index
            while len(header) <= 900 and stop < min(index + 3, len(lines)):
                if _DATE.search(header) and _REPLY.fullmatch(header):
                    quoted = []
                    for lower, upper, line in lines[stop + 1:]:
                        if re.match(r'^[ \t]*>', line):
                            quoted.append((lower, upper))
                    if quoted:
                        ranges.append((start, lines[stop][1]))
                        ranges.extend(quoted)
                    break
                stop += 1
                if stop < min(index + 3, len(lines)):
                    header += ' ' + _PREFIX.sub('', lines[stop][2]).strip()
    if tail < len(body):
        ranges.append((tail, len(body)))
    return sorted(set(ranges))


def guard(episode, items):
    """Downgrade proven quoted content; ambiguous mixed blocks stay uncertain."""
    kind = getattr(episode, 'kind', None)
    provenance = getattr(episode, 'provenance', None)
    if hasattr(provenance, 'to_dict'):
        provenance = provenance.to_dict()
    source = provenance.get('source_type') if isinstance(provenance, dict) else None
    if getattr(kind, 'value', kind) != 'message' or getattr(source, 'value', source) != 'email':
        return items
    body = episode.body
    ranges = _ranges(body)
    if not ranges:
        return items
    guarded = []
    for item in items:
        updated = dict(item)
        if item['kind'] != 'irrelevant':
            start, end = item['start'], item['end']
            overlaps = [(max(start, lower), min(end, upper)) for lower, upper in ranges
                        if lower < end and upper > start]
            if overlaps:
                cursor, uncovered = start, []
                for lower, upper in overlaps:
                    if lower > cursor:
                        uncovered.append(body[cursor:lower])
                    cursor = max(cursor, upper)
                uncovered.append(body[cursor:end])
                updated['kind'] = 'uncertain' if ''.join(uncovered).strip() else 'historical'
        guarded.append(updated)
    return guarded
