"""Termine nachbereiten: Was ist herausgekommen?

Nach einem Termin mit Externen fragt das Briefing einmal nach, ruhig und
abweisbar („Nichts festzuhalten“), höchstens für drei Termine zugleich, und nur,
wenn keine Mitschrift vorliegt (`transkript_zuordnung.py`). Die Antwort,
getippt oder als Mitschrift (SRT/VTT), wird eine Quelle wie jede andere:
mit den Teilnehmern, dem Projekt des Termins und dem Ende des Termins als
Zeitpunkt. Die Einordnung liest daraus Bitten und Zusagen, die Aufgaben-
erkennung schlägt vor. Ein Fakt wird daraus erst, wenn ein Mensch annimmt;
dieses Modul legt nur die Quelle ab.

Ein Termin ist über Kennung *und* Beginn bestimmt: Eine Serie teilt sich im
Kalender eine Kennung, und die Nachbereitung vom letzten Dienstag gilt nicht
für diesen. Siehe docs/24-weg-zum-jarvis.md, Etappe 2.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable

from .bezuege import org_aus_adresse
from .datumstext import iso_versuchen as _zeit
from .episodes import mail_address
from .identitaet import domaene
from .kontakte import anzeigename
from .transcript_import import parse_transcript

# So lange fragt das Briefing nach. Was länger zurückliegt, ist aus dem Kopf,
# und die Frage wäre nur noch ein Vorwurf. Nachbereiten geht im Kalender
# trotzdem jederzeit.
FENSTER = timedelta(hours=48)

# So viele Karten „Wie war das Gespräch mit …?“ stehen höchstens zugleich offen. Mehr wäre
# ein Vorwurf: Wer nach einem vollen Tag fünf Fragen sieht, beantwortet keine.
MAX_KARTEN = 3


def schluessel(uid: str, start: Any) -> str | None:
    """„uid|Beginn in UTC“ — oder nichts, wenn der Beginn fehlt."""
    beginn = _zeit(start)
    if not uid or beginn is None or beginn.tzinfo is None:
        return None
    return f'{uid}|{beginn.astimezone(timezone.utc).isoformat()}'


def gleicher_beginn(a: Any, b: Any) -> bool:
    erster, zweiter = _zeit(a), _zeit(b)
    if erster is None or zweiter is None or erster.tzinfo is None or zweiter.tzinfo is None:
        return False
    return erster == zweiter


def andere_teilnehmer(attendees: Iterable[str], eigene: Iterable[str]) -> list[str]:
    """Die Teilnehmer ohne einen selbst, jeder einmal."""
    selbst = {mail_address(a) for a in eigene if mail_address(a)}
    ergebnis, gesehen = [], set()
    for eingabe in attendees or ():
        text = str(eingabe).strip()
        adresse = mail_address(text)
        kennung = adresse or text.casefold()
        if not kennung or kennung in gesehen or (adresse and adresse in selbst):
            continue
        gesehen.add(kennung)
        ergebnis.append(text)
    return ergebnis


def externe(attendees: Iterable[str], eigene: Iterable[str]) -> list[str]:
    """Die Teilnehmer von außerhalb: ohne Adresse, oder mit einer Adresse fremder Domäne.

    Eine eigene Firmendomäne macht Kollegen zu Internen. Ein privater Anbieter
    (gmail, gmx, icloud …) tut das nicht: Wer dort schreibt, ist nicht dieselbe
    Organisation, nur derselbe Anbieter.
    """
    interne = {domaene(mail_address(a)) for a in eigene if mail_address(a) and org_aus_adresse(mail_address(a))}
    ergebnis = []
    for text in andere_teilnehmer(attendees, eigene):
        adresse = mail_address(text)
        if not adresse or domaene(adresse) not in interne:
            ergebnis.append(text)
    return ergebnis


def _anzeige(teilnehmer: str) -> str:
    return anzeigename(teilnehmer) or mail_address(teilnehmer) or str(teilnehmer).strip()


def frage_zu(summary: str, mit: list[str]) -> str:
    """Die Frage der Karte, kurz: „Wie war das Gespräch mit Anna Keller?“"""
    namen = [_anzeige(text) for text in mit if _anzeige(text)]
    if not namen:
        return f'Wie war „{summary}“?'
    if len(namen) == 1:
        wer = namen[0]
    elif len(namen) == 2:
        wer = f'{namen[0]} und {namen[1]}'
    else:
        wer = f'{namen[0]} und {len(namen) - 1} weiteren'
    return f'Wie war das Gespräch mit {wer}?'


def offene(items: list[dict[str, Any]], *, jetzt: datetime, eigene: Iterable[str],
           erledigt: dict[str, str | None],
           hat_mitschrift: Callable[[str], bool] = lambda schluessel: False) -> list[dict[str, Any]]:
    """Vergangene Termine der letzten 48 Stunden, nach denen Kingfisher fragt.

    Gefragt wird nur nach Terminen mit Externen (`externe`), nie nach einem
    Termin, der schon beantwortet oder mit „Nichts festzuhalten“ abgewiesen ist
    (`erledigt`), und nicht, wenn eine Mitschrift zugeordnet ist
    (`hat_mitschrift(Schlüssel)`). Höchstens `MAX_KARTEN`, neueste zuerst. Ein
    gewähltes Projekt allein macht keine Frage mehr nötig.
    """
    eigene = list(eigene)
    ergebnis = []
    for item in items:
        if item.get('all_day'):
            continue
        beginn, ende = _zeit(item.get('start')), _zeit(item.get('end'))
        if beginn is None or ende is None or beginn.tzinfo is None or ende.tzinfo is None:
            continue
        if not (jetzt - FENSTER <= ende <= jetzt):
            continue
        key = schluessel(str(item.get('uid') or ''), beginn)
        if key is None or key in erledigt or hat_mitschrift(key):
            continue
        mit = externe(item.get('attendees') or (), eigene)
        if not mit:
            continue
        summary = item.get('summary') or 'Termin'
        ergebnis.append({'uid': item.get('uid'), 'start': item.get('start'), 'end': item.get('end'),
                         'summary': summary, 'teilnehmer': len(andere_teilnehmer(item.get('attendees') or (), eigene)),
                         'mit': [_anzeige(text) for text in mit[:3]], 'frage': frage_zu(summary, mit)})
    ergebnis.sort(key=lambda eintrag: _zeit(eintrag['end']), reverse=True)
    return ergebnis[:MAX_KARTEN]


def text_aus_mitschrift(text: str, format: str) -> str:
    """Eine SRT- oder VTT-Mitschrift als lesbarer Text, ohne Zeitmarken.

    Zeitmarken helfen beim Abspielen, nicht beim Lesen; die Einordnung
    würde sie nur als Rauschen sehen. Wer spricht, bleibt stehen.
    """
    segmente = parse_transcript(text, format)
    if not segmente:
        raise ValueError('Die Mitschrift enthält keine Abschnitte.')
    zeilen, zuletzt = [], None
    for segment in segmente:
        sprecher = segment.get('speaker')
        inhalt = str(segment.get('text') or '').strip()
        if not inhalt:
            continue
        if sprecher and sprecher == zuletzt and zeilen:
            zeilen[-1] += ' ' + inhalt
            continue
        zeilen.append(f'{sprecher}: {inhalt}' if sprecher else inhalt)
        zuletzt = sprecher
    if not zeilen:
        raise ValueError('Die Mitschrift enthält keinen Text.')
    return '\n'.join(zeilen)


__all__ = ['FENSTER', 'MAX_KARTEN', 'andere_teilnehmer', 'externe', 'frage_zu', 'gleicher_beginn', 'offene',
           'schluessel', 'text_aus_mitschrift']
