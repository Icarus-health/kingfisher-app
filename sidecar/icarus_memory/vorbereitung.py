"""Termine von selbst vorbereiten: wer kommt, und worum geht es?

Die Teilnehmer stehen im Kalender. Wer von ihnen im Bestand vorkommt, lässt
sich an der Mailadresse genau feststellen; das Programm muss niemanden danach
fragen. Das Projekt wird vorgeschlagen, nie festgelegt: aus dem Titel, oder
wenn die Nachrichten mit den Teilnehmern überwiegend einem Projekt zugeordnet
sind. Jeder Vorschlag nennt seinen Grund, und eine Berichtigung gilt dauerhaft
(`WorkspaceStore.set_event_project`).

Bewusst ohne Modell und ohne Namensraten: Eine Adresse ist eine Identität,
ein Name im Titel ist es nicht. Siehe docs/24-weg-zum-jarvis.md, Etappe 2.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

from .episodes import mail_address
from .connectors.collections import event_uids

ANTEIL = 0.6
MINDESTENS = 2


def teilnehmer(attendees: Iterable[str], *, index: dict[str, dict[str, Any]],
               eigene: Iterable[str] = ()) -> list[dict[str, Any]]:
    """Die Teilnehmer eines Termins, soweit sie im Bestand vorkommen.

    `index` stammt aus `EpisodeStore.participants_for_addresses`. Die eigenen
    Adressen fallen weg: Man bereitet sich nicht auf sich selbst vor. Ohne
    Adresse bleibt ein Teilnehmer unzuordenbar, statt über den Namen geraten
    zu werden.
    """
    selbst = {mail_address(adresse) for adresse in eigene if mail_address(adresse)}
    ergebnis, gesehen = [], set()
    for eingabe in attendees or ():
        adresse = mail_address(eingabe)
        schluessel = adresse or str(eingabe).strip().casefold()
        if not schluessel or schluessel in gesehen or (adresse and adresse in selbst):
            continue
        gesehen.add(schluessel)
        eintrag = index.get(adresse) if adresse else None
        namen = sorted((eintrag or {}).get('namen', {}).items(), key=lambda item: (-item[1], item[0]))
        person = namen[0][0] if namen else None
        angezeigt = _anzeigename(str(eingabe)) or (_anzeigename(person) if person else '') or adresse or str(eingabe)
        ergebnis.append({
            'eingabe': str(eingabe), 'adresse': adresse or None, 'name': angezeigt, 'person': person,
            'kontakte': len((eintrag or {}).get('quellen', {})),
            'zuletzt': (eintrag or {}).get('zuletzt'),
            'quellen': dict((eintrag or {}).get('quellen', {})),
        })
    return ergebnis


def _anzeigename(wert: str) -> str:
    """„Anna Keller“ aus „Anna Keller <anna@x.de>“ oder „Keller, Anna <…>“."""
    text = re.sub(r'<[^<>]*>\s*$', '', str(wert or '')).strip().strip('"').strip()
    return '' if '@' in text else text


def _im_titel(summary: str, projects: list[tuple[str, str]]) -> list[str]:
    """Projekte, deren Name im Titel steht, verschachtelte nur einmal.

    Kurze Namen (bis drei Zeichen, etwa „IT“) nur in genau dieser
    Schreibweise, sonst wäre jedes „it“ ein Projekt. Liegt ein Treffer in
    einem längeren („Mainz“ in „Mainz Messe“), gilt der längere.
    """
    treffer = []
    for pid, name in projects:
        name = name.strip()
        if not name:
            continue
        muster = re.compile(r'(?<!\w)' + re.escape(name) + r'(?!\w)', 0 if len(name) <= 3 else re.I)
        for m in muster.finditer(summary or ''):
            treffer.append((m.start(), m.end(), pid))
    uebrig = {pid for start, ende, pid in treffer
              if not any(s2 <= start and ende <= e2 and (e2 - s2) > (ende - start) for s2, e2, _ in treffer)}
    return sorted(uebrig)


def projekt_vorschlag(summary: str, personen: list[dict[str, Any]], offene: list[tuple[str, str]],
                      alle: Iterable[str] = ()) -> dict[str, Any] | None:
    """Ein Projekt mit Grund, oder nichts, wenn es nicht klar ist.

    Grundlage sind die Quellen mit den Teilnehmern, jede einmal gezählt,
    auch wenn mehrere Teilnehmer darin stehen. Geschlossene Projekte zählen
    im Nenner mit, werden aber nie vorgeschlagen.

    1. Der Titel nennt genau ein offenes Projekt, und die Quellen sprechen
       nicht klar für ein anderes.
    2. Sonst: Die Quellen gehören überwiegend (mindestens 60 %, mindestens
       zwei) zu einem offenen Projekt.
    """
    namen = {pid: name for pid, name in offene if isinstance(name, str) and name.strip()}
    quellen: dict[str, str | None] = {}
    for person in personen:
        quellen.update(person.get('quellen') or {})
    zaehler: dict[str, int] = {}
    for projekt in quellen.values():
        if projekt:
            zaehler[projekt] = zaehler.get(projekt, 0) + 1
    gesamt = sum(zaehler.values())
    fuehrend = max(zaehler.items(), key=lambda item: (item[1], item[0])) if zaehler else None
    klar = (fuehrend if fuehrend and fuehrend[1] >= MINDESTENS and fuehrend[1] / gesamt >= ANTEIL else None)

    im_titel = _im_titel(summary, list(namen.items()))
    if len(im_titel) > 1:
        return None
    if im_titel:
        pid = im_titel[0]
        if klar and klar[0] != pid:
            return None
        return {'id': pid, 'name': namen[pid], 'grund': f'Der Termin nennt „{namen[pid]}“.'}
    if not klar or klar[0] not in namen:
        return None
    pid, anzahl = klar
    beteiligt = [p['name'] for p in personen if pid in (p.get('quellen') or {}).values()]
    wer = beteiligt[0] if len(beteiligt) == 1 else f'{beteiligt[0]} und weiteren'
    return {'id': pid, 'name': namen[pid],
            'grund': f'{anzahl} von {gesamt} zugeordneten Quellen mit {wer} gehören zu „{namen[pid]}“.'}


def zuordnung(event: dict[str, Any], *, episodes: Any, workspace: Any, eigene: Iterable[str] = (),
              index: dict[str, dict[str, Any]] | None = None, projekte: list[Any] | None = None) -> dict[str, Any]:
    """Teilnehmer, Vorschlag und das geltende Projekt eines Termins.

    `projekt.herkunft` ist `gewaehlt`, wenn der Nutzer festgelegt hat, sonst
    `vorschlag`. Eine Festlegung auf „kein Projekt“ schlägt jeden Vorschlag.
    `index` und `projekte` darf reichen, wer mehrere Termine auf einmal
    vorbereitet: Dann läuft der Bestand nur einmal durch.
    """
    attendees = list(event.get('attendees') or ())
    if index is None:
        index = episodes.participants_for_addresses(attendees)
    if projekte is None:
        projekte = workspace.projects(include_closed=True)
    personen = teilnehmer(attendees, index=index, eigene=eigene)
    offene = [(p.id, p.name) for p in projekte if p.is_open()]
    vorschlag = projekt_vorschlag(str(event.get('summary') or ''), personen, offene, [p.id for p in projekte])
    choices = {pid for uid in event_uids(event) for chosen, pid in [workspace.event_project(uid)] if chosen}
    konflikt = len(choices) > 1
    festgelegt = bool(choices)
    pid = next(iter(choices)) if len(choices) == 1 else None
    projekt = None
    if festgelegt and pid:
        name = next((p.name for p in projekte if p.id == pid), None)
        projekt = {'id': pid, 'name': name, 'herkunft': 'gewaehlt'} if name else None
    elif not festgelegt and vorschlag:
        projekt = {**vorschlag, 'herkunft': 'vorschlag'}
    for person in personen:
        person.pop('quellen', None)
    return {'teilnehmer': personen, 'vorschlag': vorschlag, 'festgelegt': festgelegt, 'projekt': projekt,
            'anzahl_teilnehmer': len(personen), 'zuordnungskonflikt': konflikt}


__all__ = ['projekt_vorschlag', 'teilnehmer', 'zuordnung']
