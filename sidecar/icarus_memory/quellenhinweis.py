"""Der Quellenhinweis einer belegten Gedächtnisantwort, in Alltagssprache.

Früher stand unter einer Antwort `Quelle [1]: Gespräch · "conversation:c-…:message:m-…"`
und `Ereigniszeit: 2026-10-01T10:25:07.79…+00:00`. Ein Mensch sagt dazu „Gespräch vom
1. Oktober 2026, 12:25 Uhr“, „E-Mail „Angebot“ von Lena Probe vom …“ oder „Termin
„Abstimmung Atlas“ am …“. Diese Sätze entstehen hier, Zeiten in der Zeitzone des Nutzers
(`datumstext`). Die Kennungen bleiben ein Datenfeld (`daten`): Die Oberfläche öffnet damit
die Quelle mit einem Klick und zeigt sie nur hinter „Für Techniker“.

Gelesen wird nur, was gespeichert ist: Titel und Absender der Quelle, ihre Zeiten. Nichts
wird geraten; fehlt etwas, entfällt der Teil des Satzes.
"""
from __future__ import annotations

import re
from email.utils import parseaddr
from typing import Any

from .datumstext import zeitpunkt_text

#: Quellenart -> Wort im Satz. Unbekannte Arten heißen „Beleg“.
ART = {'email': 'E-Mail', 'calendar': 'Termin', 'document': 'Dokument', 'chat': 'Gespräch',
       'user_stated': 'Deine Angabe', 'manual_correction': 'Deine Berichtigung', 'web': 'Webseite'}

#: Titel, die nur die Art wiederholen (ein Gesprächsausschnitt heißt so), sagen nichts.
_LEERE_TITEL = {'gesprächsausschnitt', '(ohne titel)', ''}
_GESPRAECH = re.compile(r'^conversation:([^:\s]+):message:([^:\s]+)$')
TITEL_LAENGE = 120


def _einzeilig(text: Any, laenge: int = TITEL_LAENGE) -> str:
    """Gespeicherter Text als eine ruhige Zeile: Zeilenumbrüche und Steuerzeichen werden Leerzeichen."""
    zeile = ' '.join(str(text or '').split())
    return zeile if len(zeile) <= laenge else zeile[:laenge - 1].rstrip() + '…'


def gespraech(source_ref: Any) -> tuple[str, str] | None:
    """(Gespräch, Nachricht) aus einer Gesprächsquelle, sonst None."""
    treffer = _GESPRAECH.match(source_ref) if isinstance(source_ref, str) else None
    return (treffer.group(1), treffer.group(2)) if treffer else None


def _absender(episode: Any) -> str:
    for kontakt in getattr(episode, 'contacts', None) or []:
        if isinstance(kontakt, dict) and kontakt.get('rolle') == 'von':
            name = kontakt.get('name') or kontakt.get('adresse')
            if name:
                return _einzeilig(name, 80)
    beteiligte = getattr(episode, 'participants', None) or []
    if beteiligte:
        name, adresse = parseaddr(str(beteiligte[0]))
        return _einzeilig(name or adresse or beteiligte[0], 80)
    return ''


def angaben(episode: Any) -> dict[str, str]:
    """Was der Hinweis von der gespeicherten Quelle braucht: Titel und (bei Mails) Absender."""
    titel = _einzeilig(getattr(episode, 'title', ''))
    if titel.lower() in _LEERE_TITEL:
        titel = ''
    art = getattr(getattr(getattr(episode, 'provenance', None), 'source_type', None), 'value', '')
    return {'titel': titel, 'absender': _absender(episode) if art == 'email' else ''}


def text(beleg: dict[str, Any], gefunden: dict[str, str] | None = None) -> str:
    """Der Hinweis zu einem Beleg (`primary_evidence` einer Wissensprojektion) in einem Satzteil."""
    art = beleg.get('source_type')
    gefunden = gefunden or {}
    titel = gefunden.get('titel') or ''
    absender = gefunden.get('absender') or ''
    teile = [ART.get(art, 'Beleg')]
    if titel and art in ('email', 'calendar', 'document', 'web'):
        teile.append(f'„{titel}“')
    if absender:
        teile.append(f'von {absender}')
    satz = ' '.join(teile)
    wann = zeitpunkt_text(beleg.get('occurred_at'))
    if wann:
        return satz + (' am ' if art == 'calendar' else ' vom ') + wann
    erfasst = zeitpunkt_text(beleg.get('recorded_at'))
    return satz + (f', aufgenommen am {erfasst}' if erfasst else '')


def daten(nummer: int, row: dict[str, Any], hinweis: str) -> dict[str, Any]:
    """Das Datenfeld zu einem Hinweis: womit die Oberfläche die Quelle öffnet, und die Kennungen für Techniker."""
    beleg = row['primary_evidence']
    eintrag = {'nummer': nummer, 'text': hinweis, 'art': beleg['source_type'],
               'assertion_id': row['assertion_id'], 'episode_id': beleg['episode_id'],
               'source_ref': beleg['source_ref'], 'occurred_at': beleg['occurred_at'],
               'recorded_at': beleg['recorded_at']}
    ort = gespraech(beleg['source_ref']) if beleg['source_type'] == 'chat' else None
    if ort:
        eintrag['conversation_id'], eintrag['message_id'] = ort
    return eintrag
