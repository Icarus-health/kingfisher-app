"""Conservative German conversation routing; no model, permission or identity inference.

Supported factual question forms use original evidence. Other conversation and
explicit actions keep the existing chat path. An explicit API mode overrides this.
"""
import re

_MEMORY_QUESTION = re.compile(
    r'^(?:was (?:weißt du|wissen wir|hast du dir gemerkt|haben wir festgehalten) (?:über|zu)\b'
    r'|welche (?:adresse|e-mail-adresse|mailadresse|telefonnummer|frist|entscheidung)\b'
    r'|(?:was|wie) ist (?:der (?:aktuelle )?stand|es um)\b'
    r'|was steht (?:in (?:der|dem|den)|zu|über)\b'
    r'|wann (?:ist|war|findet|beginnt|endet)\b'
    r'|wurde .+ (?:versendet|verschickt|bestätigt|erledigt|abgesagt)\s*\??$)', re.I)
# Bounded questions about the existence of a business record. Route even if
# search is empty: absence of a retrieved record is not proof of nonexistence.
# The first noun must be a record, so geography, science and capability/advice
# questions do not become personal-memory lookups merely because of the verb.
_RECORD_EXISTENCE = re.compile(
    r'^(?:liegt|liegen|gibt\s+es|besteht|bestehen)\s+'
    r'(?:(?:mir|uns|jetzt|schon|bereits|noch|hier|dazu|dafür)\s+)*'
    r'(?:(?:eine?|die|der|das|meine?|unsere?)\s+)?'
    r'(?:(?:hotel|zug|flug)?buchung(?:en)?|buchungsbestätigung(?:en)?|'
    r'reservierung(?:en)?|freigabe[n]?|zusage[n]?)\b'
    r'[^.!?\n]*\??$', re.I)
_NEW_TURN = re.compile(
    r'\b(?:schreib\w*|sende\w*|schick\w*|merke\w*|speicher\w*|lösche\w*|loesche\w*|'
    r'vergiss|öffne\w*|oeffne\w*|erstelle\w*|buche\w*|kaufe\w*|suche\w*|erkläre\w*|erklaere\w*)\b', re.I)
_QUESTION_START = re.compile(r'^(?:was|wie|wer|wo|wann|warum|wieso|welch\w*|kann\w*|hast|ist|sind)\b', re.I)
_PERSONAL_RECALL = re.compile(
    r'^(?:'
    r'(?:was|wann|wie|wo|welch\w*)\s+(?:hast du(?: dir)?|habe ich dir|haben wir|hatten wir)\b'
    r'.*\b(?:gesagt|erzählt|erzaehlt|gemerkt|festgehalten|notiert|gespeichert|erwähnt|erwaehnt)\b'
    r'|(?:erinnerst du dich|kannst du dich (?:noch )?erinnern|wei(?:ß|ss)t du noch|kennst du)\b'
    r'.*\b(?:ich|mich|mir|mein\w*|wir|uns|unser\w*)\b'
    r')', re.I)
# Direkte Fragen nach eigenen Angaben bleiben auch ohne Suchtreffer im
# beleggebundenen Weg. „Wie kann ich …?“ und allgemeine Erklärungen sind
# nicht gemeint; ausdrückliche Aktionen werden weiterhin vorher erkannt.
_PERSONAL_FACT = re.compile(
    r'^(?:welch\w*\s+[^.!?\n]{1,160}\s+(?:habe|haben|hatte|hatten)\s+(?:ich|wir)\b[^.!?\n]{0,160}\??$'
    r'|(?:was|wer|wo|welch\w*|wie(?:\s+(?:hoch|groß|gross|teuer|alt|lang))?)\s+'
    r'(?:ist|sind|war|waren|lautet|lauten|heißt|heisst|heißen|heissen|hat|haben)\b'
    r'[^.!?\n]{0,160}\b(?:mein(?:e|en|er|es|em)?|unser(?:e|en|er|es|em)?)\b)', re.I)
_DELIVERY_QUESTION = re.compile(
    r'^(?:wann|bis wann|wer|was) (?:schickt|sendet|verschickt|versendet|liefert)\b'
    r'(?P<rest>[^.!?\n]*)\??$', re.I)
_PREPARATION_TIME = re.compile(
    r'^(?:(?:bitte\s+)?bereite\s+mich|wie\s+bereite\s+ich\s+mich)'
    r'\s+auf\s+[^.!?\n]{1,200}\s+vor[.!?]\s*'
    r'(?:wann|bis\s+wann|an\s+welchem\s+datum|um\s+wie\s+viel\s+uhr)\b[^.!?\n]*\??$', re.I)
_PREPARATION_ADVICE = re.compile(r'^wie\s+bereite\s+ich\s+mich\b', re.I)
_WORKING_FOLLOWUP = re.compile(
    r'^(?:(?:und|bitte)\s+)?(?:'
    r'(?:welche|was\s+für\s+eine)\s+(?:bedingung|voraussetzung)\s+'
    r'(?:gilt(?:\s+denn)?|besteht)\s+(?:dabei|dafür|hier)|'
    r'(?:erklär(?:e)?|erklaer(?:e)?|erläutere|erlaeutere|beschreib(?:e)?)\s+'
    r'(?:mir\s+)?(?:das|dazu|dabei)(?:\s+(?:bitte|genauer|kurz))*|'
    r'(?:kannst\s+du|könntest\s+du|koenntest\s+du)\s+(?:mir\s+)?'
    r'(?:das|dazu|dabei)\s+(?:erklären|erklaeren|erläutern|erlaeutern)(?:\s+bitte)?|'
    r'was\s+bedeutet\s+(?:das|dazu|dabei))\??[.!]?$', re.I)


def is_working_followup(message, previous_context):
    """Recognize bounded immediate condition and explanation follow-ups."""
    if not isinstance(message, str) or not _WORKING_FOLLOWUP.fullmatch(message.strip()):
        return False
    if not isinstance(previous_context, dict) or previous_context.get('answer_mode') != 'memory_evidence':
        return False
    mappe = previous_context.get('mappe_answer')
    if isinstance(mappe, dict):
        # Nach dem Stand der Dinge bleibt die Nachfrage im Projekt.
        query = mappe.get('query')
        return (isinstance(query, str) and bool(query.strip())
                and len(query) + len(message) + len('\nNachfrage des Nutzers: ') <= 20000
                and isinstance(mappe.get('id'), str))
    answer = previous_context.get('working_answer')
    contract = previous_context.get('answer_contract')
    from .working_memory_answers import lookup_of
    retrieval_query = lookup_of(answer)
    return (isinstance(answer, dict) and answer.get('status') == 'reports'
            and isinstance(retrieval_query, str) and bool(retrieval_query.strip())
            and len(retrieval_query) + len(message) + len('\nNachfrage des Nutzers: ') <= 20000
            and isinstance(contract, dict) and contract.get('status') in {'reports', 'working_reports'})


_ICH_BEZUG = re.compile(r'\b(?:ich|mich|mir|mein\w*|wir|uns|unser\w*)\b', re.I)


def _gedaechtnisfrage(text, anfrage):
    """Will die Frage etwas aus dem eigenen Bestand? Entscheidet die Anfrage, nicht ein Einzelmuster.

    Ohne Anfrage gilt der Rückfall aus `frage.py`. Hält das Modell eine Frage für
    allgemein, bleibt sie nur dann im Bestand, wenn sie eine Sache nennt oder von
    „ich“ und „wir“ spricht; ein Fehlurteil des kleinen Modells schickt eine
    Gedächtnisfrage so nie in den freien Chat.
    """
    from .frage import rueckfall
    from .working_memory_answers import is_question
    if anfrage is None:
        anfrage = rueckfall(text)
    if getattr(anfrage, 'herkunft', '') == 'modell' and not anfrage.gedaechtnisfrage:
        return bool(anfrage.sachen) or bool(_ICH_BEZUG.search(text))
    return anfrage.gedaechtnisfrage or is_question(text)


def route(message, previous_context=None, *, new_question=False, working_available=False, anfrage=None):
    text = message.strip()
    from .source_answers import literal_query
    if (re.match(r'^(?:was steht\b|(?:bitte\s+)?(?:suche?|zeige?|finde)\b)', text, re.I)
            and literal_query(text) is not None):
        return 'memory_evidence'
    previous = previous_context if isinstance(previous_context, dict) else {}
    if not new_question and is_working_followup(text, previous):
        return 'memory_followup'
    delivery = _DELIVERY_QUESTION.fullmatch(text)
    # A question about somebody else's delivery is not an instruction to
    # send. Keep a second command in the same sentence on the action path.
    if delivery and not _NEW_TURN.search(delivery['rest']):
        return 'memory_evidence'
    if _NEW_TURN.search(text):
        return 'chat'
    # A preparation request followed by a concrete time question must use
    # current evidence. Bare preparation requests keep the tool-enabled path.
    if working_available and _PREPARATION_TIME.fullmatch(text):
        return 'memory_evidence'
    if _PREPARATION_ADVICE.match(text):
        return 'chat'
    # Explicit recall of the user's own statements stays evidence-bound even
    # when retrieval currently has no candidate; a free chat answer could invent
    # a personal fact. General explanations without a recall/self-reference cue
    # continue through the ordinary chat route.
    if _RECORD_EXISTENCE.fullmatch(text):
        return 'memory_evidence'
    if _PERSONAL_RECALL.search(text) or _PERSONAL_FACT.search(text):
        return 'memory_evidence'
    if working_available and _gedaechtnisfrage(text, anfrage):
        return 'memory_evidence'
    if _MEMORY_QUESTION.search(text):
        return 'memory_evidence'
    contract = previous.get('answer_contract')
    if (not new_question and previous.get('answer_mode') == 'memory_evidence'
            and isinstance(contract, dict) and contract.get('status') in {'clarify', 'working_unclear'}
            and len(text) <= 200 and '?' not in text and not _QUESTION_START.search(text)):
        return 'memory_followup'
    return 'chat'
