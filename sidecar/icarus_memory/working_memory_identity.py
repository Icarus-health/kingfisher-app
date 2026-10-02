"""A narrow guard for same-display-name sender ambiguity in selected reports.

Mailboxes identify source senders, not humans. This helper neither creates a
person record nor treats a matching display name as proof of identity.
"""

from __future__ import annotations

import re
from typing import Any

from .lexical import terms_v1
from .people_quality import ist_sammelpostfach, lokalteil


_SENDER = re.compile(r"^([^<>\r\n@]+?)\s+<([^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+)>$")
_SINGULAR_OPENING = re.compile(r"^(?:wann|bis\s+wann|hat|ist|war|wird|was\s+hat|wie|wo)\b", re.I)
_PLURAL = re.compile(
    r"\b(?:alle|beide|mehrere|jeweils|zusammen|gemeinsam|personen|absender|"
    r"vergleich|gegenüber|bzw|vs|zwei|beiden)\b", re.I,
)
_STREET = re.compile(r"^.{2,100}?\s+\d+[a-zA-Z]?$", re.UNICODE)
_NEGATION = re.compile(r'\b(?:nicht|außer|ausser|statt|ohne|ausgenommen)\b', re.I)
_CAPITALIZED = re.compile(r"(?<![\w])([A-ZÄÖÜ][a-zäöüß]+(?:[-‐][A-ZÄÖÜ]?[a-zäöüß]+)*)")
_PROJECT_QUALIFIER = re.compile(
    r"\b(?:aus|im|in|für|fuer|vom|von)\s+(?:(?:dem|das|der)\s+)?Projekt\s+[A-ZÄÖÜ][\w-]*"
)


def _normal(text: str) -> str:
    return " ".join(text.split()).casefold()


def _sender(row: dict[str, Any]) -> tuple[str, str] | None:
    # Der Absender ist der Beteiligte mit Rolle `von`; Empfänger und Cc stehen
    # ebenfalls in `participants`, sind aber nicht gemeint. Ältere Zeilen ohne
    # `sender` tragen genau einen Beteiligten: den Absender.
    participants = row.get("participants")
    text = row.get("sender")
    if not (isinstance(text, str) and text.strip()):
        if not isinstance(participants, list) or len(participants) != 1 or not isinstance(participants[0], str):
            return None
        text = participants[0]
    match = _SENDER.fullmatch(text.strip())
    if match is None:
        return None
    display = match[1].strip()
    if len(display) >= 2 and display.startswith('"') and display.endswith('"'):
        display = display[1:-1]
    name, mailbox = _normal(display), match[2].casefold()
    if not name or ist_sammelpostfach(lokalteil(mailbox)):
        return None
    return name, mailbox


def _original_street(row: dict[str, Any], sender: tuple[str, str]) -> str | None:
    """Use only a matching, unquoted From/Adresse preamble in the original body."""
    context = row.get("context")
    if not isinstance(context, str):
        return None
    lines = context.splitlines()
    if len(lines) < 2:
        return None
    from_line = re.fullmatch(r"(?:Von|From):\s*(.+)", lines[0].strip(), re.I)
    address_line = re.fullmatch(r"Adresse:\s*(.+)", lines[1].strip(), re.I)
    if from_line is None or address_line is None:
        return None
    header_sender = _sender({"participants": [from_line[1]]})
    if header_sender != sender:
        return None
    street = _normal(address_line[1].split(",", 1)[0])
    return street if _STREET.fullmatch(street) else None


def _explicit_mailboxes(question: str, senders: list[tuple[str, str]]) -> set[str]:
    return {mailbox for _, mailbox in senders
            if re.search(r'(?<![\w.+@-])' + re.escape(mailbox) + r'(?![\w.+@-])', question)}


def _explicit_streets(question: str, rows: list[dict[str, Any]],
                      senders: list[tuple[str, str] | None]) -> set[str]:
    matches = set()
    for row, sender in zip(rows, senders):
        if sender is None:
            continue
        street = _original_street(row, sender)
        if street is None:
            continue
        # A street merely mentioned in the question is not an identity cue.
        selector = r"(?<!\w)(?:von\s+(?:der|dem)|aus\s+(?:der|dem)|adresse\s*:)\s+" + re.escape(street) + r"(?!\w)"
        if re.search(selector, question):
            matches.add(sender[1])
    return matches


def _topic_terms(question: str, name: str) -> set[str]:
    person_terms = terms_v1(name)
    terms = set()
    for match in _CAPITALIZED.finditer(question):
        # A capital letter at the start of the question is sentence casing,
        # not evidence that the word is a named subject.
        if match.start() == 0:
            continue
        terms.update(terms_v1(match.group(1)))
    return terms - person_terms


def _has_shared_topic_anchor(question: str, name: str,
                             first: dict[str, Any], second: dict[str, Any]) -> bool:
    """Require a non-person query term in each indexed candidate span.

    `context` is intentionally excluded: it can contain quoted or adjacent
    material that did not make this source a candidate for the asked topic.
    The only generated form is the regular German -e/-en noun plural.
    """
    first_text, second_text = first.get("text"), second.get("text")
    if not isinstance(first_text, str) or not isinstance(second_text, str):
        return False
    first_terms, second_terms = terms_v1(first_text), terms_v1(second_text)
    for term in _topic_terms(question, name):
        forms = {term}
        if term.endswith("e") and len(term) > 3:
            forms.add(term + "n")
        if forms & first_terms and forms & second_terms:
            return True
    return False


def adjust_selection(question: str, source_rows: list[dict[str, Any]],
                     selected_ids: list[str], *, candidate_ids: list[str] | None = None
                     ) -> tuple[list[str], str | None, str | None]:
    """Return (selected IDs, forced status, clarification hint).

    The selected IDs remain the starting point. A competing retrieved source is
    added only when it has the same source display name, a different mailbox,
    and a shared non-person query anchor in both indexed spans. An explicit
    sender/address selector and list questions keep their existing behavior.
    """
    original = list(selected_ids)
    unchanged = (original, None, None)
    if (not isinstance(question, str) or not isinstance(source_rows, list)
            or not isinstance(selected_ids, list) or not original
            or any(not isinstance(identifier, str) for identifier in original)
            or len(set(original)) != len(original)):
        return unchanged
    normalized_question = _normal(question)
    if (not _SINGULAR_OPENING.match(normalized_question)
            or _PLURAL.search(normalized_question) or _NEGATION.search(normalized_question)):
        return unchanged
    by_id = {row.get("id"): row for row in source_rows if isinstance(row, dict) and isinstance(row.get("id"), str)}
    if any(identifier not in by_id for identifier in original):
        return unchanged
    candidates = list(original) if candidate_ids is None else list(candidate_ids)
    if (not candidates or any(not isinstance(identifier, str) for identifier in candidates)
            or len(set(candidates)) != len(candidates) or any(identifier not in by_id for identifier in candidates)):
        return unchanged

    # A single model-selected source can still have a relevant omitted peer in
    # the bounded retrieval set. Use participant metadata for the source name;
    # a name mentioned in body text never establishes sender identity.
    selected_rows = [by_id[identifier] for identifier in original]
    selected_senders = [_sender(row) for row in selected_rows]
    if all(sender is not None for sender in selected_senders):
        names = {sender[0] for sender in selected_senders}
        if len(names) == 1:
            name = next(iter(names))
            name_mentions = len(re.findall(r"(?<!\w)" + re.escape(name) + r"(?!\w)", normalized_question))
            candidate_rows = [by_id[identifier] for identifier in candidates]
            candidate_senders = [_sender(row) for row in candidate_rows]
            if (name_mentions == 1 and not _PROJECT_QUALIFIER.search(question)
                    and "@" not in normalized_question
                    and not _explicit_mailboxes(normalized_question, [s for s in candidate_senders if s is not None])
                    and not _explicit_streets(normalized_question, candidate_rows, candidate_senders)):
                additions = []
                selected_mailboxes = {sender[1] for sender in selected_senders if sender is not None}
                for identifier, row, sender in zip(candidates, candidate_rows, candidate_senders):
                    if (identifier in original or sender is None or sender[0] != name
                            or sender[1] in selected_mailboxes):
                        continue
                    if any(_has_shared_topic_anchor(question, name, selected_row, row)
                           for selected_row, selected_sender in zip(selected_rows, selected_senders)
                           if selected_sender is not None and selected_sender[0] == name):
                        additions.append(identifier)
                if additions:
                    return (original + additions, "person",
                            "Welche der genannten Personen meinst du? Die Quellen nennen verschiedene Absenderadressen.")

    if len(original) < 2:
        return unchanged
    rows = [by_id[identifier] for identifier in original]
    senders = [_sender(row) for row in rows]
    if any(sender is None for sender in senders):
        return unchanged
    # The same exact display name must be the single person named in the query.
    names = {sender[0] for sender in senders}
    if len(names) != 1:
        return unchanged
    name = next(iter(names))
    if len(re.findall(r"(?<!\w)" + re.escape(name) + r"(?!\w)", normalized_question)) != 1:
        return unchanged
    if len({sender[1] for sender in senders}) < 2:
        return unchanged

    email_matches = _explicit_mailboxes(normalized_question, senders)
    street_matches = _explicit_streets(normalized_question, rows, senders)
    # Multiple or disagreeing explicit selectors are not a singular target.
    if len(email_matches | street_matches) > 1:
        return unchanged
    matches = email_matches | street_matches
    if matches:
        mailbox = next(iter(matches))
        narrowed = [identifier for identifier, sender in zip(original, senders) if sender[1] == mailbox]
        return narrowed, "reports" if len(narrowed) == 1 else None, None
    # An email selector outside these selected sources cannot be resolved here.
    if "@" in normalized_question:
        return unchanged
    return original, "person", "Welche der genannten Personen meinst du? Die Quellen nennen verschiedene Absenderadressen."
