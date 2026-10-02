"""Closed German noun inflections for query-time candidates, version 1.

No persisted token contract, identity alias or general stemmer changes.
Compound heads preserve their entire prefix; arbitrary endings are not
stripped. NOUN_SYNONYMS_V1 below is a separate, explicitly closed set of
query-time noun synonyms (distinct words, not inflections) -- not a
general or auto-generated synonym mechanism.
"""

NOUN_FORMS_V1 = (
    ('bericht', 'berichts', 'berichtes', 'berichte', 'berichten'),
    ('dokument', 'dokuments', 'dokumentes', 'dokumente', 'dokumenten'),
    ('vertrag', 'vertrags', 'vertrages', 'verträge', 'verträgen'),
    ('entwurf', 'entwurfs', 'entwurfes', 'entwürfe', 'entwürfen'),
    ('termin', 'termins', 'termine', 'terminen'),
    ('projekt', 'projekts', 'projekte', 'projekten'),
    ('server', 'servers', 'servern'),
    ('kontakt', 'kontakts', 'kontakte', 'kontakten'),
    ('schlüssel', 'schlüssels', 'schlüsseln'),
    ('plan', 'plans', 'planes', 'pläne', 'plänen'),
    ('ziel', 'ziels', 'zieles', 'ziele', 'zielen'),
    ('adresse', 'adressen'),
    ('rechnung', 'rechnungen'),
    ('aufgabe', 'aufgaben'),
    ('notiz', 'notizen'),
    ('datei', 'dateien'),
    ('quelle', 'quellen'),
    ('entscheidung', 'entscheidungen'),
    ('anmeldung', 'anmeldungen'),
    ('wartung', 'wartungen'),
    ('lieferung', 'lieferungen'),
    ('lizenz', 'lizenzen'),
    ('vorliebe', 'vorlieben'),
)
_FORMS = {form: group for group in NOUN_FORMS_V1 for form in group}
_HEADS = sorted(_FORMS, key=lambda form: (-len(form), form))


def alternatives(term: str) -> frozenset[str]:
    if term in _FORMS:
        return frozenset(_FORMS[term])
    for head in _HEADS:
        if term.endswith(head):
            prefix = term[:-len(head)]
            if len(prefix) >= 3 and prefix.isalpha():
                return frozenset(prefix + form for form in _FORMS[head])
    return frozenset((term,))


def matching_terms(query_terms, document_terms):
    """Return original query terms matched by a literal or listed noun form."""
    return {term for term in query_terms if alternatives(term) & document_terms}


# Explicit, closed, query-time-only noun synonyms: distinct German/English
# words for the same everyday thing, never forms of one lemma -- so this
# stays separate from NOUN_FORMS_V1 and never touches alternatives()'s
# compound-suffix matching. Each entry pairs full inflection sets for both
# words. Kept deliberately small; add a pair here by hand only after the
# same reproduce-then-fix review this first pair went through, never as an
# auto-generated or general synonym/stemming mechanism.
NOUN_SYNONYMS_V1 = (
    ('bericht', 'berichts', 'berichtes', 'berichte', 'berichten',
     'report', 'reports'),
)
_SYNONYM_FORMS = {form: group for group in NOUN_SYNONYMS_V1 for form in group}


def synonym_alternatives(term: str) -> frozenset[str]:
    """Exact-form synonym alternation only -- never suffix/compound matching.

    'Reisebericht', 'Geschäftsbericht' and 'Reporter' are therefore never
    touched: none of them equals a listed form, and unlike alternatives()
    this function never strips or matches a prefix.
    """
    if term in _SYNONYM_FORMS:
        return frozenset(_SYNONYM_FORMS[term])
    return frozenset((term,))


def synonym_matching_terms(query_terms, document_terms):
    """Query terms matched only via the closed noun-synonym classes above.

    Distinct from matching_terms(): a synonym is not a word form, and a
    caller must never describe a match reached only through this function
    as one (see agent.py's reason text).
    """
    return {term for term in query_terms if synonym_alternatives(term) & document_terms}
