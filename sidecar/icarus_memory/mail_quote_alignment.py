"""Eindeutige Maildarstellung auf einen unveränderten Originalspan zurückführen.

Keine Ähnlichkeitssuche: Großschreibung, Wörter, Zahlen und Operatoren bleiben
gleich. Nur vollständige HTML-Entities, Whitespace und Präfixe vollständig
markierter mehrzeiliger Mail-Zitatabsätze werden zum Vergleich dargestellt.
"""
import html
import re
from html.entities import html5


_ENTITY = re.compile(r'&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]+);')
_LINE_PREFIX = re.compile(r'(?m)^[ \t]*>[ \t]+')
_CODE_FENCE = re.compile(r'(?m)^[ \t]*(?:>[ \t]*)*(?:```|~~~)')


def _decoded(text):
    """Einmalige Entitydarstellung mit Originalspan für jedes Ausgabezeichen."""
    chars, spans, index = [], [], 0
    while index < len(text):
        match = _ENTITY.match(text, index)
        token = match[0] if match else ''
        known = bool(token) and token[1:] in html5
        if token.startswith('&#'):
            digits = token[2:-1]
            try:
                number = int(digits[1:], 16) if digits[:1].lower() == 'x' else int(digits)
                known = 0 < number <= 0x10FFFF and not 0xD800 <= number <= 0xDFFF
            except ValueError:
                known = False
        decoded = html.unescape(token) if known else ''
        if match and decoded and decoded != token:
            chars.extend(decoded)
            spans.extend([(index, match.end())] * len(decoded))
            index = match.end()
        else:
            chars.append(text[index])
            spans.append((index, index + 1))
            index += 1
    return ''.join(chars), spans


def _quote_prefix_mask(text):
    """Nur ganze physische Absätze mit mindestens zwei markierten Inhaltszeilen.

    Eine einzelne oder gemischt markierte Zeile kann ein Vergleichsoperator
    sein. Entity-decodierte Zeichen begründen ausdrücklich kein Mail-Markup.
    """
    mask, paragraph = set(), []

    def finish():
        prefixes = [_LINE_PREFIX.match(line) for _, line in paragraph]
        if (paragraph and all(prefixes)
                and sum(bool(line[prefix.end():].strip())
                        for (_, line), prefix in zip(paragraph, prefixes)) >= 2):
            for (offset, _), prefix in zip(paragraph, prefixes):
                mask.update(range(offset, offset + prefix.end()))
        paragraph.clear()

    offset = 0
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip('\r\n')
        if line.strip():
            paragraph.append((offset, line))
        else:
            finish()
        offset += len(raw)
    finish()
    return mask


def _canonical(text, skipped=()):
    decoded, positions = _decoded(text)
    chars, spans = [], []
    for index, char in enumerate(decoded):
        start, end = positions[index]
        if start in skipped:
            continue
        if char.isspace():
            if chars and chars[-1] == ' ':
                spans[-1] = (spans[-1][0], end)
            else:
                chars.append(' ')
                spans.append((start, end))
        else:
            chars.append(char)
            spans.append((start, end))
    if chars and chars[-1] == ' ':
        chars.pop()
        spans.pop()
    if chars and chars[0] == ' ':
        chars.pop(0)
        spans.pop(0)
    return ''.join(chars), spans


def _word(char):
    return char.isalnum() or char == '_'


def align(body, quote):
    """(Originalzitat, Start, Ende) nur bei genau einem vollständigen Treffer.

    Aufrufer müssen zuerst den unveränderten Literalpfad und die Quellenart
    prüfen. Codeblöcke und nicht eindeutig belegte Darstellungen bleiben außen.
    """
    if _CODE_FENCE.search(body) or _CODE_FENCE.search(quote):
        return None
    source_mask = _quote_prefix_mask(body)
    source, spans = _canonical(body, source_mask)
    needle, _ = _canonical(quote, _quote_prefix_mask(quote))
    if not needle:
        return None
    start = source.find(needle)
    if start < 0 or source.find(needle, start + 1) >= 0:
        return None
    end = start + len(needle)
    # Kein Teil eines mehrzeichigen Entity-Ergebnisses oder eines Wortes/einer Zahl.
    if (start and (spans[start - 1] == spans[start]
                   or (_word(source[start - 1]) and _word(source[start])))):
        return None
    if (end < len(source) and (spans[end - 1] == spans[end]
                             or (_word(source[end - 1]) and _word(source[end])))):
        return None
    lower, upper = spans[start][0], spans[end - 1][1]
    line_start = body.rfind('\n', 0, lower) + 1
    prefix = _LINE_PREFIX.match(body, line_start)
    if prefix and line_start not in source_mask:
        return None  # Auch ein Start nach einem ungeklärten Präfix ist kein Beweis für dessen Bedeutung.
    raw = body[lower:upper]
    # Der Ausschnitt kann mitten in einer markierten Zeile beginnen. Seine
    # Präfixbeweise stammen ausschließlich aus dem vollständigen Original.
    raw_mask = {position - lower for position in source_mask if lower <= position < upper}
    if _canonical(raw, raw_mask)[0] != needle:
        return None
    return raw, lower, upper
