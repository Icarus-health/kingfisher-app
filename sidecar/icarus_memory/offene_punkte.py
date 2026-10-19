"""„Worauf warte ich noch?“ und „Was habe ich zugesagt?“: aus den Akten, ohne Modell.

Ein Stabschef weiß das auswendig. Die Akten wissen es auch (`akten.py`): Jeder vermutlich offene Punkt trägt seine
Richtung (`von_mir` oder `an_mich`, nur bei Mails) und die Entscheidungen des Nutzers (`akten_entscheidungen.py`).

* **Worauf warte ich?** Zusagen anderer an dich und deine eigenen Bitten, zu denen keine spätere Erledigung oder
  Absage vorliegt und die du nicht als erledigt abgelegt hast.
* **Was habe ich zugesagt?** Deine eigenen Zusagen, ebenso.

Wie die Mappe im Gespräch ist die Antwort eine Ansicht: Gespeichert wird nur die Frage, nie ein Zitat; beim Öffnen
des Gesprächs wird sie neu aus den Akten zusammengestellt (`conversations.py`, `server.py`). Jede Zeile nennt ihre
Quelle. Die Antwort behauptet nicht, dass etwas offen ist: Es heißt „vermutlich“.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .datumstext import tag_text

WARTET_AUF = re.compile(
    r'\b(?:worauf|auf\s+was)\s+(?:warte|warten)\s+(?:ich|wir)\b'
    r'|\bwer\s+(?:schuldet|schulden)\s+(?:mir|uns)\b'
    r'|\bwas\s+(?:schuldet|schulden)\s+(?:man\s+)?(?:mir|uns)\b'
    r'|\bwas\s+(?:steht|ist)\s+(?:bei\s+anderen|von\s+anderen)\s+(?:noch\s+)?(?:aus|offen)\b', re.I)
ZUGESAGT = re.compile(
    r'\bwas\s+(?:habe|hab|haben)\s+(?:ich|wir)\s+(?:noch\s+|eigentlich\s+|alles\s+)*(?:zugesagt|versprochen)\b'
    r'|\bwelche\s+zusagen\s+(?:habe|hab|haben)\s+(?:ich|wir)\b'
    r'|\bwas\s+(?:muss|müssen)\s+(?:ich|wir)\s+noch\s+(?:liefern|schicken|erledigen)\b', re.I)
ARTEN = ('wartet_auf', 'zugesagt')
#: Höchstens so viele Akten je Art werden gelesen (wie im Briefing, `fristlage.sammeln`).
JE_ART = 60
MAX_PUNKTE = 12


def art_der_frage(frage: str) -> str | None:
    """`wartet_auf`, `zugesagt` oder None: eine feste Frageform, kein Modell."""
    if not isinstance(frage, str) or len(frage) > 300:
        return None
    if WARTET_AUF.search(frage):
        return 'wartet_auf'
    if ZUGESAGT.search(frage):
        return 'zugesagt'
    return None


def _passt(art: str, eintrag: dict[str, Any]) -> bool:
    richtung, was = eintrag.get('richtung'), eintrag.get('art')
    if art == 'wartet_auf':
        return (richtung == 'an_mich' and was == 'Zusage') or (richtung == 'von_mir' and was == 'Bitte')
    return richtung == 'von_mir' and was == 'Zusage'


def sammeln(akten: Any, bezuege: Any, art: str, *, jetzt: datetime | None = None) -> dict[str, Any]:
    """Die passenden offenen Punkte aus den zuletzt aktiven Akten, jüngste zuerst, je Textstelle einmal."""
    if art not in ARTEN:
        raise ValueError('Unbekannte Art der Frage.')
    jetzt = jetzt or datetime.now(timezone.utc)
    punkte: dict[str, dict[str, Any]] = {}
    for sachen_art in ('person', 'organisation', 'projekt'):
        for eintrag in bezuege.sachen(art=sachen_art, limit=JE_ART)['sachen']:
            akte = akten.akte(eintrag['sache'], jetzt=jetzt, alle=True)
            if akte is None:
                continue
            for e in akte['offen']['eintraege']:
                ziel = e.get('ziel')
                if not ziel or not _passt(art, e):
                    continue
                # Die persönlichste Akte gibt den Namen: Person vor Organisation vor Projekt.
                punkte.setdefault(ziel, {**e, 'sache': akte['sache'], 'sache_name': akte['name']})
    geordnet = sorted(punkte.values(), key=lambda p: (p.get('occurred_at') or p.get('recorded_at') or ''),
                      reverse=True)
    return {'punkte': geordnet[:MAX_PUNKTE], 'gesamt': len(geordnet)}


def _wer(punkt: dict[str, Any]) -> str:
    """„Silke Vogt (Akademie Taunus), Zusage“ oder „Deine Bitte an Silke Vogt“."""
    from .episodes import mail_address
    from .kontakte import anzeigename
    akte = punkt.get('sache_name') or ''
    if punkt.get('richtung') == 'an_mich':
        absender = (punkt.get('participants') or [''])[0]
        name = anzeigename(absender) or mail_address(absender) or akte
        return f'{name if not akte or akte == name else f"{name} ({akte})"}, {punkt["art"]}'
    return f'Deine {punkt["art"]}' + (f' an {akte}' if akte else '')


def als_text(gesammelt: dict[str, Any], art: str) -> tuple[str, list[dict[str, Any]]]:
    """Die Antwort als Text mit nummerierten Quellen."""
    punkte, gesamt = gesammelt['punkte'], gesammelt['gesamt']
    links: list[dict[str, Any]] = []
    if not punkte:
        if art == 'wartet_auf':
            return ('In deinen Akten finde ich nichts, worauf du noch wartest: keine Zusage an dich und keine Bitte '
                    'von dir ohne spätere Erledigung.', links)
        return ('In deinen Akten finde ich keine eigene Zusage ohne spätere Erledigung.', links)
    if art == 'wartet_auf':
        kopf = (f'Du wartest vermutlich noch auf {"eine Sache" if gesamt == 1 else f"{gesamt} Dinge"} '
                '(aus deinen Akten; keine spätere Erledigung gefunden):')
    else:
        kopf = (f'Du hast vermutlich noch {"eine Zusage" if gesamt == 1 else f"{gesamt} Zusagen"} offen '
                '(aus deinen Akten; keine spätere Erledigung gefunden):')
    zeilen = [kopf]
    for nummer, punkt in enumerate(punkte, 1):
        wann = tag_text(punkt.get('occurred_at') or punkt.get('recorded_at'))
        zeilen.append(f'{nummer}. {_wer(punkt)}{f" vom {wann}" if wann else ""}: „{punkt["text"]}“ [Quelle {nummer}]')
        links.append({'episode_id': punkt['episode_id'], 'label': f'Quelle {nummer} öffnen', 'automatic_memory': True})
    if gesamt > len(punkte):
        zeilen.append(f'Die jüngsten {len(punkte)} von {gesamt}; die übrigen stehen in den Akten.')
    zeilen.append('Ob es wirklich noch offen ist, steht in den Quellen nicht. In der Akte legst du einen Punkt mit '
                  'einem Klick als erledigt ab.')
    return '\n'.join(zeilen), links


__all__ = ['ARTEN', 'als_text', 'art_der_frage', 'sammeln']
