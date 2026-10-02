"""Deterministic, narrowly scoped calendar answers; no model authority.

This handles explicit overview questions and title-based clarification only.
It does not infer projects, execute instructions, or promise global free time.
"""
import re
import unicodedata

from .calendar_context import _timestamp


def _display(value):
    text = ''.join(' ' if unicodedata.category(c).startswith('C') else c for c in str(value))
    text = ' '.join(text.split())
    return re.sub(r'([\\`*_{}\[\]<>()#+.!|~\-])', r'\\\1', text)


def _event_line(event):
    start = _timestamp(event.get('start'))
    if start is None:
        return None
    offset = start.strftime('%z')
    when = start.strftime('%d.%m.%Y, %H:%M') + f' (UTC{offset[:3]}:{offset[3:]})'
    if event.get('all_day'):
        when = 'Ganztägiger Eintrag; Beginn laut Quelle: ' + when
    title = _display(event.get('summary') or 'Ohne Titel')
    source = _display(event.get('source_label') or 'ausgewählter Mac-Kalender')
    return f'- {when}: „{title}“ — Quelle: {source}'


OVERVIEW_QUESTIONS = {
        'welche termine habe ich als nächstes', 'was steht als nächstes an',
        'was steht als nächstes im kalender', 'zeige meine nächsten termine',
        'zeig mir meine nächsten termine', 'meine nächsten termine',
        'welche termine stehen an',
    }
AVAILABILITY_QUESTIONS = {'bin ich diese woche komplett frei', 'bin ich diese woche frei',
                        'habe ich diese woche frei'}


def is_overview_question(question):
    """Recognize only explicit overview/availability questions, never topic lookup."""
    q = ' '.join(question.casefold().split()).rstrip('?.!')
    return q in OVERVIEW_QUESTIONS or q in AVAILABILITY_QUESTIONS


def answer(question, calendar):
    q = ' '.join(question.casefold().split()).rstrip('?.!')
    overview = q in OVERVIEW_QUESTIONS
    availability = q in AVAILABILITY_QUESTIONS
    match = re.fullmatch(r'was ist (?:eigentlich )?mit ([\w ]{2,80})', q)
    events = calendar.get('events') or []
    matching = []
    if match and calendar.get('status') == 'available':
        terms = set(match[1].split())
        matching = [event for event in events
                    if terms <= set(re.findall(r'\w+', event.get('summary', '').casefold()))]
    if not (overview or availability or matching):
        return None
    status = calendar.get('status')
    if status != 'available':
        reason = {'stale': 'Der Kalenderstand ist veraltet oder zeitlich nicht verlässlich.',
                  'disabled': 'Es ist kein Mac-Kalender für diesen Überblick freigegeben.'}.get(
                      status, 'Der Mac-Kalender ist gerade nicht zuverlässig verfügbar.')
        return reason + ' Deshalb kann ich deine Termine oder freie Zeit nicht bestätigen. Bitte prüfe die Kalendersynchronisation.'
    chosen = matching[:3] if matching else events
    lines = [line for event in chosen if (line := _event_line(event)) is not None]
    if matching:
        intro = 'Meinst du diesen bevorstehenden oder laufenden Termin?' if len(matching) == 1 else 'Meinst du einen dieser bevorstehenden oder laufenden Termine?'
    elif availability:
        intro = 'Dass du diese Woche komplett frei bist, kann ich aus diesem begrenzten Kalenderüberblick nicht bestätigen.'
    else:
        intro = 'Im aktuellen Ausschnitt der ausgewählten Mac-Kalender stehen diese laufenden oder bevorstehenden Termine:'
    if not lines:
        intro += '\nIm vorliegenden Ausschnitt sind keine auswertbaren Einträge enthalten. Das belegt keine freie Woche.'
    elif lines:
        intro += '\n\n' + '\n'.join(lines)
    lower, upper = _timestamp(calendar.get('window_from')), _timestamp(calendar.get('window_to'))
    if lower and upper:
        intro += '\n\nAusschnitt: ' + lower.isoformat(timespec='minutes') + ' bis ' + upper.isoformat(timespec='minutes') + '. Zeiten mit dem jeweiligen UTC-Offset der Quelle.'
    if (calendar.get('coverage') != 'covered' or calendar.get('truncated')
            or calendar.get('invalid_count') or len(matching) > 3):
        intro += '\nDie Übersicht ist begrenzt oder nicht vollständig abgedeckt; weitere Termine sind möglich.'
    return intro
