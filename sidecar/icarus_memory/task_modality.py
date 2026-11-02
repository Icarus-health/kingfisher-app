"""Narrow German optional-attribute check; it never rewrites source evidence."""
import html
import re

_CUE = re.compile(r'\b(?:idealerweise|vorzugsweise|nach\s+möglichkeit|wenn\s+möglich)\b')
_END = re.compile(r'[.!?;]|\n[ \t]*\n')
_TRAILING_DETAIL = re.compile(r'\b(?:als|im|in|bis|am|um)\s+[^,;.!?()]+[, (]*$')
_WORD = re.compile(r'[^\W_]+', re.UNICODE)
_FUNCTION = frozenset(('als an am auf aus bei bis das dass dem den der des die ein eine einer einem einen '
    'für im in mit nach oder ohne sie du ihr wir so und von vom vor zu zum zur bitte '
    'idealerweise vorzugsweise möglich möglichkeit wenn '
    'senden schicken einreichen übermitteln mitsenden abgeben erhalten').split())


def _qualified_spans(text):
    spans = []
    for cue in _CUE.finditer(text):
        ending = _END.search(text, cue.end())
        end = ending.start() if ending else len(text)
        start = cue.start()
        # A postposed cue can qualify the preceding attribute: "als PDF,
        # wenn möglich". Without a bounded attribute, retain the whole clause
        # conservatively rather than manufacture an unconditional short title.
        tail = [word.group() for word in _WORD.finditer(text, cue.end(), end)
                if word.group() not in _FUNCTION]
        if not tail:
            previous = list(_END.finditer(text, 0, cue.start()))
            clause_start = previous[-1].end() if previous else 0
            prefix = text[clause_start:cue.start()]
            attribute = _TRAILING_DETAIL.search(prefix)
            start = clause_start + attribute.start() if attribute else clause_start
        spans.append((start, end))
    return spans


def _inside(position, spans):
    return any(start <= position < end for start, end in spans)


def optional_details_supported(title, quote):
    """An optional source attribute repeated in a title must remain qualified.

    Each title occurrence is checked against its own clause, so an unrelated
    `idealerweise` later in the title cannot qualify an earlier mandatory PDF.
    Omission of an optional attribute remains allowed. Ambiguous simplifications
    fall back to the existing exact original quote at the extraction boundary.
    This complements, and does not replace, whole-source semantic review.
    """
    source = html.unescape(quote).casefold().replace('\r\n', '\n').replace('\r', '\n')
    source_spans = _qualified_spans(source)
    if not source_spans:
        return True
    optional = {word.group() for word in _WORD.finditer(source)
                if _inside(word.start(), source_spans) and word.group() not in _FUNCTION}
    summary = html.unescape(title).casefold().replace('\r\n', '\n').replace('\r', '\n')
    title_spans = _qualified_spans(summary)
    return not any(word.group() in optional and not _inside(word.start(), title_spans)
                   for word in _WORD.finditer(summary))
