"""Zeitraum in einer Frage: welche Quellen zuerst berücksichtigt werden.

Nur Angaben, die sich eindeutig auf die Vergangenheit bis heute beziehen
(„gestern“, „letzte Woche“, „in den letzten 3 Tagen“, „letztes Jahr“, „dieses Jahr“,
„in den letzten drei Monaten“, „vor zwei Wochen“). Monatsnamen und
künftige Angaben bleiben außen vor: „Wann ist die Abnahme im Oktober?“ fragt
nach dem Inhalt, nicht nach dem Eingang der Mail.

Der Zeitraum ordnet nur um, er schließt nichts aus. Eine Quelle außerhalb
bleibt Kandidat, wenn Platz ist.
"""
import calendar
from datetime import datetime, timedelta, timezone
import re

from .model import user_timezone

NUMBERS = {'zwei': 2, 'drei': 3, 'vier': 4, 'fünf': 5, 'sechs': 6, 'sieben': 7, 'acht': 8,
           'neun': 9, 'zehn': 10, 'vierzehn': 14}
_NUMBER = r'(\d{1,3}|' + '|'.join(NUMBERS) + r')'
# „vor einer Woche“, „vor einem Monat“: auch der unbestimmte Artikel als Zahl.
_NUMBER_EIN = r'(\d{1,3}|ein|eine|einer|einem|einen|' + '|'.join(NUMBERS) + r')'
# Unbestimmter Artikel als Zahl: „in einer Woche“, „in einem Monat“, „innerhalb eines Monats“ (nur für künftige Angaben).
_EINS = frozenset({'ein', 'eine', 'einer', 'einem', 'einen', 'eines'})
PATTERNS = [
    ('days', re.compile(r'\b(?:in\s+den\s+)?(?:letzten|vergangenen)\s+' + _NUMBER + r'\s+(tagen?|wochen)\b', re.I)),
    ('days', re.compile(r'\bseit\s+' + _NUMBER + r'\s+(tagen|wochen)\b', re.I)),
    ('last_week', re.compile(r'\b(?:letzte[rn]?|vorige[rn]?|vergangene[rn]?)\s+woche\b', re.I)),
    ('this_week', re.compile(r'\b(?:diese[rn]?)\s+woche\b', re.I)),
    ('months', re.compile(r'\b(?:in\s+den\s+)?(?:letzten|vergangenen)\s+' + _NUMBER + r'\s+monaten?\b', re.I)),
    ('ago', re.compile(r'\bvor\s+' + _NUMBER_EIN + r'\s+(tag(?:en)?|wochen?|monat(?:en)?)\b', re.I)),
    ('last_year', re.compile(r'\b(?:(?:letzte[sn]?|vorige[sn]?|vergangene[sn]?)\s+jahr(?:es)?|im\s+vorjahr)\b', re.I)),
    ('this_year', re.compile(r'\bdiese[sm]?\s+jahr(?:es)?\b', re.I)),
    ('last_month', re.compile(r'\b(?:letzte[nm]?|vorige[nm]?|vergangene[nm]?)\s+monat\b', re.I)),
    ('this_month', re.compile(r'\b(?:diese[nm]?)\s+monat\b', re.I)),
    ('day_before', re.compile(r'\bvorgestern\b', re.I)),
    ('yesterday', re.compile(r'\bgestern\b', re.I)),
    ('today', re.compile(r'\bheute\b', re.I)),
]
# Only immediate negation of a recognized period, not an unrelated "nicht" elsewhere.
_ZEIT_VORWORTE = r'(?:(?:von|vom|aus|in|im|am|der|den|dem)\s+)*'
_NEGIERTE_ZEIT = re.compile(r'\bnicht\s+' + _ZEIT_VORWORTE + r'$', re.I)
_NICHT_NUR_ZEIT = re.compile(r'\bnicht\s+(?:nur|bloß|bloss|allein|ausschließlich|ausschliesslich)\s+'
                            + _ZEIT_VORWORTE + r'$', re.I)
_RELATIVES_WORT = r'(?:heute|gestern|vorgestern|morgen|nächste[nmr]?\s+(?:montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag))\b'
_WORTANFANG = r'(?:(?:das\s+)?(?:wort|ausdruck)\s+)?[\u201e"\']?'
_QUELLENWORT = re.compile(r'\b(?:original(?:notiz|mail|nachricht|quelle|text)|notiz|mail|nachricht)\b', re.I)
_ZEITWORTBEZUG = re.compile(
    r'\b(?:bezog|bezieht)\s+sich\s+' + _WORTANFANG + _RELATIVES_WORT + r'|'
    r'\b(?:bedeutet|bedeutete|meint|meinte)\s+' + _WORTANFANG + _RELATIVES_WORT + r'|'
    r'\b(?:datum|tag|zeitpunkt)\b[^.!?\n]{0,80}\bmit\s+' + _WORTANFANG + _RELATIVES_WORT
    + r'[^.!?\n]{0,120}\bgemeint\b', re.I)


def original_time_reference(question):
    """A question about a relative word's meaning in a source, not its arrival time.

    A source mention alone is insufficient: the question must explicitly ask
    what its relative word meant or referred to. No date is inferred here.
    """
    return isinstance(question, str) and bool(_QUELLENWORT.search(question) and _ZEITWORTBEZUG.search(question))


def _negation(question, match):
    prefix = question[:match.start()]
    return ('offen' if _NICHT_NUR_ZEIT.search(prefix) else
            'negiert' if _NEGIERTE_ZEIT.search(prefix) else None)


def has_negated_period(question):
    """A recognized period is excluded or explicitly nonexclusive: model suggestions must not restore it."""
    return isinstance(question, str) and any(_negation(question, match)
        for _, pattern in PATTERNS for match in pattern.finditer(question))


def zahl(wort):
    """Ziffern oder ausgeschriebene Zahl („zwei“, „14“, „einer“) als int, sonst None.

    Die eine Stelle für Zahlwörter: `mentioned_period` (Vergangenheit) und
    `fristen.py` (Zukunft) lesen sie gleich.
    """
    wort = str(wort or '').strip().lower()
    if wort.isdigit():
        return int(wort)
    return 1 if wort in _EINS else NUMBERS.get(wort)


def _midnight(value):
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


def _month_start(value):
    return _midnight(value).replace(day=1)


def _monate_zurueck(erster, monate):
    """Der Monatserste `monate` Monate vor `erster` (ebenfalls ein Monatserster)."""
    index = erster.year * 12 + erster.month - 1 - monate
    return erster.replace(year=index // 12, month=index % 12 + 1)


def ohne_zeitraum(text):
    """Die Frage ohne erkannte Zeitangaben, für die Wortsuche: „letztes“ und „Jahr“ sind keine Suchwörter.

    Bleibt danach kein Wort übrig („Was war letzte Woche?“), gilt die Frage unverändert: Dann sucht die
    Wortsuche wie bisher, und der Zeitraum ordnet.
    """
    if not isinstance(text, str):
        return text
    rest = text
    for _, pattern in PATTERNS:
        rest = pattern.sub(' ', rest)
    rest = re.sub(r'\b(?:in|im|aus|von|vom|seit)\s+(?=[?.!,]|\s*$)', ' ', rest)
    from .lexical import terms_v1
    from .source_index import funktionswort
    return rest if any(not funktionswort(wort) for wort in terms_v1(rest)) else text


def mentioned_period(question, now=None):
    """(Beginn, Ende, Beschriftung) des ersten positiven Zeitraums, sonst None.

    „Nicht heute, sondern gestern“ berücksichtigt gestern. „Nicht nur heute“ nennt
    ausdrücklich keinen einzelnen Bereich; es wird kein enger Zeitraum geraten.
    """
    if not isinstance(question, str) or original_time_reference(question):
        return None
    now = now or datetime.now(user_timezone() or timezone.utc)
    matches = [(match.start(), kind, match) for kind, pattern in PATTERNS for match in pattern.finditer(question)]
    if any(_negation(question, match) == 'offen' for _, _, match in matches):
        return None
    found = min((item for item in matches if _negation(question, item[2]) is None),
                default=None, key=lambda item: item[0])
    if found is None:
        return None
    _, kind, match = found
    today = _midnight(now)
    if kind == 'days':
        raw = match.group(1).lower()
        count = zahl(raw)
        days = count * (7 if match.group(2).lower().startswith('woche') else 1)
        if not 1 <= days <= 366:
            return None
        return today - timedelta(days=days - 1), today + timedelta(days=1), f'der letzten {days} Tage'
    if kind == 'months':
        count = zahl(match.group(1))
        if not count or not 1 <= count <= 24:
            return None
        erster = _monate_zurueck(_month_start(now), count)
        # Derselbe Tag vor `count` Monaten (am Monatsende der letzte Tag des kürzeren Monats).
        tag = min(today.day, calendar.monthrange(erster.year, erster.month)[1])
        return erster.replace(day=tag) + timedelta(days=1), today + timedelta(days=1), f'der letzten {count} Monate'
    if kind == 'ago':
        count = zahl(match.group(1))
        einheit = match.group(2).lower()
        if not count or not 1 <= count <= 120:
            return None
        # Beschriftungen ohne Datum: Eine gespeicherte Antwort bleibt am nächsten Tag gleich beschriftet.
        if einheit.startswith('tag'):
            tag = today - timedelta(days=count)
            return tag, tag + timedelta(days=1), 'von vor einem Tag' if count == 1 else f'von vor {count} Tagen'
        if einheit.startswith('woche'):
            montag = today - timedelta(days=7 * count + today.weekday())
            return montag, montag + timedelta(days=7), 'von vor einer Woche' if count == 1 else f'von vor {count} Wochen'
        erster = _monate_zurueck(_month_start(now), count)
        return erster, _monate_spaeter(erster, 1), 'von vor einem Monat' if count == 1 else f'von vor {count} Monaten'
    if kind == 'last_year':
        anfang = today.replace(month=1, day=1)
        return anfang.replace(year=anfang.year - 1), anfang, 'des letzten Jahres'
    if kind == 'this_year':
        anfang = today.replace(month=1, day=1)
        return anfang, today + timedelta(days=1), 'dieses Jahres'
    if kind == 'today':
        return today, today + timedelta(days=1), 'von heute'
    if kind == 'yesterday':
        return today - timedelta(days=1), today, 'von gestern'
    if kind == 'day_before':
        return today - timedelta(days=2), today - timedelta(days=1), 'von vorgestern'
    monday = today - timedelta(days=today.weekday())
    if kind == 'this_week':
        return monday, monday + timedelta(days=7), 'dieser Woche'
    if kind == 'last_week':
        return monday - timedelta(days=7), monday, 'der letzten Woche'
    first = _month_start(now)
    if kind == 'this_month':
        following = (first + timedelta(days=32)).replace(day=1)
        return first, following, 'dieses Monats'
    previous = (first - timedelta(days=1)).replace(day=1)
    return previous, first, 'des letzten Monats'


# -- Rückblick auf einen Kalenderzeitraum (nur zum Kennzeichnen, nie zum Ordnen) ------------------------

_MONATE = ('januar', 'februar', 'märz', 'april', 'mai', 'juni', 'juli', 'august', 'september', 'oktober',
           'november', 'dezember')
#: Jahreszeit -> Monat, in dem sie beginnt (drei Monate lang).
_JAHRESZEITEN = {'frühjahr': 3, 'frühling': 3, 'sommer': 6, 'herbst': 9, 'winter': 12}
_KALENDER = re.compile(
    r'\b(?:im|in|seit|während)\s+(?:dem\s+)?(?:(?P<zeit>frühjahr|frühling|sommer|herbst|winter)|'
    r'(?P<monat>' + '|'.join(_MONATE) + r'))(?:\s+(?P<jahr>20\d\d))?\b', re.I)
#: Nur Fragen im Rückblick: „im Oktober“ in „Wann ist die Abnahme im Oktober?“ meint den Inhalt, nicht den Eingang.
_VERGANGEN = re.compile(
    r'\b(?:passiert|geschehen|gelaufen|lief|war|waren|wurde|wurden|hat|hatte|haben|habe|gab|gesagt|besprochen|'
    r'zugesagt|geschrieben|vereinbart|beschlossen|eingegangen|geschickt|versprochen|angemerkt|gekostet)\b', re.I)


def _monate_spaeter(erster, monate):
    index = erster.month - 1 + monate
    return erster.replace(year=erster.year + index // 12, month=index % 12 + 1)


def kalenderzeitraum(question, now=None):
    """(Beginn, Ende, Beschriftung) eines genannten Monats oder einer Jahreszeit im Rückblick, sonst None.

    Nur zum Kennzeichnen von Quellen außerhalb (`kennzeichnung.py`); `mentioned_period` ordnet die Suche und
    kennt Monatsnamen bewusst nicht. Die Frage muss in der Vergangenheit stehen („was wurde im Juli besprochen“),
    und der Zeitraum muss begonnen haben: Ein Monat ohne Jahr, der noch kommt („im Oktober“, heute ist der
    30. September), ist mehrdeutig und ergibt keinen Zeitraum; geraten wird nicht. Es gilt die erste Nennung.
    """
    if not isinstance(question, str) or not _VERGANGEN.search(question):
        return None
    treffer = _KALENDER.search(question)
    if treffer is None:
        return None
    today = _midnight(now or datetime.now(user_timezone() or timezone.utc))
    jahreszeit = treffer.group('zeit')
    name = (jahreszeit or treffer.group('monat')).lower()
    beginn_monat = _JAHRESZEITEN[name] if jahreszeit else _MONATE.index(name) + 1
    jahr = int(treffer.group('jahr')) if treffer.group('jahr') else today.year
    if not treffer.group('jahr') and today < today.replace(year=jahr, month=beginn_monat, day=1):
        if not jahreszeit:
            return None
        jahr -= 1  # die zuletzt begonnene Jahreszeit
    beginn = today.replace(year=jahr, month=beginn_monat, day=1)
    return beginn, _monate_spaeter(beginn, 3 if jahreszeit else 1), f'im {name.capitalize()} {jahr}'


# -- Kommender Zeitraum („Was steht morgen an?“; nie zum Ordnen der Suche) ------------------------------

_WOCHENTAG_NUMMER = {'montag': 0, 'dienstag': 1, 'mittwoch': 2, 'donnerstag': 3, 'freitag': 4, 'samstag': 5,
                     'sonnabend': 5, 'sonntag': 6}
WOCHENTAGE = ('Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag')
_NAECHSTE = r'(?:nächste|naechste|kommende)'
_KOMMEND = [
    # „am 24.10.“, „am 24. Oktober“, „bis zum 24.10.2026“: ein konkretes Datum, das noch kommt.
    ('datum', re.compile(
        r'\b(?P<vor>am|bis(?:\s+zum)?|zum)\s+(?P<tag>\d{1,2})\.\s?(?:(?P<monat>\d{1,2})\.?(?:\s?(?P<jahr>20\d\d))?'
        r'|(?P<monatname>' + '|'.join(_MONATE) + r')(?:\s+(?P<jahr2>20\d\d))?)(?![\d.])', re.I)),
    ('uebermorgen', re.compile(r'\b(?P<vor>bis\s+)?(?:übermorgen|uebermorgen)\b', re.I)),
    # „am Morgen“ ist die Tageszeit, nicht der nächste Tag.
    ('morgen', re.compile(r'(?<!\bam\s)(?<!\bden\s)(?<!\bjeden\s)(?<!\bguten\s)\b(?P<vor>bis\s+)?morgen\b', re.I)),
    ('heute', re.compile(r'\bheute\b', re.I)),
    ('in', re.compile(r'\bin\s+' + _NUMBER_EIN + r'\s+(tag(?:en)?|wochen?|monat(?:en)?)\b', re.I)),
    ('naechste_woche', re.compile(r'\b' + _NAECHSTE + r'[nr]?\s+woche\b', re.I)),
    ('naechster_monat', re.compile(r'\b' + _NAECHSTE + r'[nmr]?\s+monat\b', re.I)),
    ('diese_woche', re.compile(r'\bdiese[rn]?\s+woche\b', re.I)),
    ('wochentag', re.compile(
        r'\b(?:(?P<vor>am\s+' + _NAECHSTE + r'n|am\s+kommenden|am|bis(?:\s+zum)?|zum|' + _NAECHSTE + r'n|diesen)\s+)?'
        r'(?P<tag>' + '|'.join(_WOCHENTAG_NUMMER) + r')\b', re.I)),
]


def _tag_beginn(tag, zone):
    from datetime import time
    return datetime.combine(tag, time.min, zone)


def kommender_zeitraum(question, now=None):
    """(Beginn, Ende, Beschriftung) eines kommenden Zeitraums in der Frage, sonst None.

    Nur für Fragen nach dem, was ansteht (`kommendes.py`): „morgen“, „übermorgen“, „heute“ (der Rest des
    Tages), „diese Woche“ (der Rest), „nächste Woche“ (Montag bis Sonntag), „nächsten Monat“, „in N
    Tagen/Wochen/Monaten“ (der Tag), „am Freitag“ (der nächste kommende; der gleiche Wochentag wie heute ist
    mehrdeutig: `mehrdeutig=True` und die Rückfrage stehen in der Beschriftung), „am 24.10.“ (ein Jahr ohne
    Angabe ist das nächste, an dem der Tag noch kommt). Vergangenes („letzte Woche“, „gestern“) bleibt Sache
    von `mentioned_period`. Das Ende ist ausschließlich. Tage gelten in der Zeitzone des Nutzers.

    Die Beschriftung: `text` (für die Antwort), `ausdruck`, `start`, `ende` (die Stelle in der Frage),
    `mehrdeutig` und bei Mehrdeutigkeit `rueckfrage`.
    """
    if not isinstance(question, str) or len(question) > 2000:
        return None
    zone = user_timezone() or timezone.utc
    now = (now or datetime.now(zone)).astimezone(zone)
    heute = now.date()
    treffer = [(kind, m) for kind, pattern in _KOMMEND for m in pattern.finditer(question)]
    if not treffer:
        return None
    # Ein konkretes Datum ist genauer als alles andere („am Freitag, den 24.10.“); sonst die erste Nennung.
    kind, match = next(((k, m) for k, m in treffer if k == 'datum'), min(treffer, key=lambda item: item[1].start()))
    vor = (match.groupdict().get('vor') or '').lower().strip()
    ab_jetzt = vor.startswith('bis')  # „bis Freitag“: von jetzt an bis einschließlich

    def ergebnis(von_tag, bis_tag, text, **mehr):
        von = now if ab_jetzt or von_tag is None else _tag_beginn(von_tag, zone)
        if von < now and von_tag is not None and von_tag == heute:
            von = now
        beschriftung = {'text': (f'bis {text}' if ab_jetzt and not text.startswith('bis ') else text),
                        'ausdruck': match.group(0), 'start': match.start(), 'ende': match.end(),
                        'mehrdeutig': False, **mehr}
        return von, _tag_beginn(bis_tag, zone), beschriftung

    if kind == 'datum':
        tag = int(match.group('tag'))
        monat = int(match.group('monat')) if match.group('monat') else _MONATE.index(match.group('monatname').lower()) + 1
        jahr_roh = match.group('jahr') or match.group('jahr2')
        try:
            if jahr_roh:
                datum = heute.replace(year=int(jahr_roh), month=monat, day=tag)
            else:
                datum = heute.replace(month=monat, day=tag)
                if datum < heute:
                    datum = datum.replace(year=heute.year + 1)
        except ValueError:
            return None
        if datum < heute:
            return None
        from .datumstext import tag_und_monat
        return ergebnis(datum, datum + timedelta(days=1), f'am {tag_und_monat(datum)} {datum.year}')
    if kind == 'uebermorgen':
        return ergebnis(heute + timedelta(days=2), heute + timedelta(days=3), 'übermorgen')
    if kind == 'morgen':
        return ergebnis(heute + timedelta(days=1), heute + timedelta(days=2), 'morgen')
    if kind == 'heute':
        return ergebnis(None, heute + timedelta(days=1), 'heute')
    if kind == 'in':
        anzahl = zahl(match.group(1))
        einheit = match.group(2).lower()
        if not anzahl or not 1 <= anzahl <= 999:
            return None
        if einheit.startswith('tag'):
            tag = heute + timedelta(days=anzahl)
        elif einheit.startswith('woche'):
            tag = heute + timedelta(weeks=anzahl)
        else:
            erster = _monate_spaeter(heute.replace(day=1), anzahl)
            tag = erster.replace(day=min(heute.day, calendar.monthrange(erster.year, erster.month)[1]))
        return ergebnis(tag, tag + timedelta(days=1), ' '.join(match.group(0).split()))
    montag = heute - timedelta(days=heute.weekday())
    if kind == 'naechste_woche':
        return ergebnis(montag + timedelta(days=7), montag + timedelta(days=14), 'nächste Woche')
    if kind == 'naechster_monat':
        erster = _monate_spaeter(heute.replace(day=1), 1)
        return ergebnis(erster, _monate_spaeter(erster, 1), 'nächsten Monat')
    if kind == 'diese_woche':
        return ergebnis(None, montag + timedelta(days=7), 'diese Woche')
    ziel = _WOCHENTAG_NUMMER[match.group('tag').lower()]
    name = WOCHENTAGE[ziel]
    abstand = (ziel - heute.weekday()) % 7
    # „nächsten Freitag“ am Freitag meint die kommende Woche; „am Freitag“ am Freitag ist mehrdeutig.
    if abstand == 0 and any(wort in vor for wort in ('nächste', 'naechste', 'kommende')):
        abstand = 7
    tag = heute + timedelta(days=abstand)
    if abstand == 0:
        return ergebnis(tag, tag + timedelta(days=1), f'am {name}', mehrdeutig=True,
                        rueckfrage=f'Meinst du heute oder nächsten {name}?')
    return ergebnis(tag, tag + timedelta(days=1), f'am {name}')
