"""Mappe, Ebene 2: Einzelheiten zu einem Projekt oder einer Person, ohne Modell.

Ein Stabschef hat zu jedem Vorgang die offenen Punkte parat, bevor jemand
fragt. Diese Ebene stellt sie aus der Struktur zusammen, die schon da ist:

- Bitten und Zusagen aus den eingeordneten Quellen, wörtlich zitiert,
- letzte Entwicklungen (Änderungen und Statusmeldungen),
- offene Aufgaben mit Fälligkeit und worauf gewartet wird,
- anstehende Termine, deren Titel oder Ort den Namen trägt.

Regeln (siehe docs/25-gedaechtnis-konzeptpruefung.md, „Mappen“):

- **Abgeleitet, nie Quelle.** Nichts hiervon wird gespeichert oder als
  Material an ein Modell gegeben. Jede Zeile verweist auf ihre Quelle.
- **Wörtlich.** Zitate sind genau der eingeordnete Abschnitt der Quelle;
  gekürzt wird nur sichtbar mit „…“.
- **Keine stillen Grenzen.** Jede Liste nennt, wie viele es insgesamt gibt.
- **Ob eine Bitte erledigt ist, weiß die Mappe nicht.** Sie zeigt, was die
  Quellen sagen, mit Datum; erledigt ist, was als Aufgabe abgeschlossen ist.
"""
from __future__ import annotations

import re
from email.utils import parseaddr
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from .datumstext import iso_versuchen_utc as _zeit
from .model import readable_time
from .working_memory_store import WorkingMemoryStore

JE_LISTE = 5
KURZ = 3
ALLE = 50
ZITAT = 400
TERMIN_FENSTER = timedelta(days=30)
ARTEN = {'request': 'Bitte', 'commitment': 'Zusage', 'conditional': 'Bedingte Aussage',
         'change': 'Änderung', 'status': 'Statusmeldung', 'fact': 'Angabe'}


def _zitat(text: str) -> tuple[str, bool]:
    text = text.strip()
    if len(text) <= ZITAT:
        return text, False
    return text[:ZITAT].rstrip() + ' …', True


MAX_GEPRUEFT = 500


def lesen(store: WorkingMemoryStore, ref: dict[str, Any], claims: Any) -> tuple[Any, str] | None:
    """(Episode, voller Text) eines Abschnitts, sofern er noch gilt; sonst None.

    Eine Referenz gilt nur, wenn `resolve` sie bestätigt (Fingerabdruck, aktuelle
    Fassung) und die Quelle nicht in bestätigtes oder zurückgezogenes Wissen
    eingegangen ist: Wie bei jeder Antwort wird sie nicht roh wiederbelebt.
    Mappe und Akte (`akten.py`) prüfen an dieser einen Stelle.
    """
    snapshot = store.resolve(ref)
    if (snapshot is None or snapshot.episode.produced
            or (claims is not None and not claims.source_is_unclaimed(ref['episode_id']))):
        return None
    return snapshot.episode, snapshot.episode.body[ref['start']:ref['end']]


def eintrag(ref: dict[str, Any], episode: Any, voll: str) -> dict[str, Any] | None:
    """Die Zeile für die Anzeige: Art, wörtliches Zitat (sichtbar gekürzt), Quelle, Zeiten."""
    text, gekuerzt = _zitat(voll)
    if not text:
        return None
    return {'art': ARTEN.get(ref['kind'], ref['kind']), 'text': text, 'gekuerzt': gekuerzt,
            'titel': episode.title[:200], 'episode_id': episode.id,
            'participants': list(episode.participants)[:3],
            'occurred_at': episode.occurred_at.isoformat() if episode.occurred_at else None,
            'recorded_at': episode.recorded_at.isoformat()}


def _abschnitte(episode_ids: list[str], arten: Iterable[str], *, episodes: Any, claims: Any,
                anzahl: int = JE_LISTE) -> dict[str, Any]:
    """Die neuesten gültigen Abschnitte, dazu eine ehrliche Gesamtzahl.

    Was nur hier geprüft werden kann (bestätigte Aussage aus der Quelle,
    geänderte Fassung), wird seitenweise übersprungen, bis genug gültige
    Einträge da sind. Ist dann noch nicht alles geprüft, heißt die Zahl
    „bis zu“, denn unter den ungeprüften können weitere ausfallen.
    """
    store = WorkingMemoryStore(episodes)
    eintraege, gesehen = [], set()
    gueltig = geprueft = offset = 0
    gesamt = archiviert = 0
    seite = min(64, max(anzahl * 3, 15))
    while True:
        found = store.items_for(episode_ids, list(arten), limit=seite, offset=offset)
        gesamt, archiviert = found['total'], found['archived']
        if not found['refs']:
            break
        offset += len(found['refs'])
        for ref in found['refs']:
            geprueft += 1
            gelesen = lesen(store, ref, claims)
            if gelesen is None:
                continue
            zeile = eintrag(ref, *gelesen)
            if zeile is None or (zeile['episode_id'], zeile['text']) in gesehen:
                continue
            gesehen.add((zeile['episode_id'], zeile['text']))
            gueltig += 1
            if len(eintraege) < anzahl:
                eintraege.append(zeile)
        if (len(eintraege) >= anzahl and geprueft >= anzahl * 3) or geprueft >= MAX_GEPRUEFT \
                or offset >= gesamt:
            break
    vollstaendig = offset >= gesamt
    return {'eintraege': eintraege,
            'gesamt': gueltig if vollstaendig else gueltig + (gesamt - offset),
            'ungefaehr': not vollstaendig, 'archiviert': archiviert}


def _aufgaben(tasks: Iterable[Any], jetzt: datetime, anzahl: int = JE_LISTE) -> dict[str, Any]:
    offen = [task for task in tasks if getattr(task.status, 'value', task.status) == 'open']
    # Überfällige und bald fällige zuerst, dann die ohne Termin nach Alter.
    offen.sort(key=lambda task: (task.due is None, task.due or task.created_at))
    # Auch wo auf jemanden gewartet wird, ist ein verstrichenes Datum verstrichen.
    return {'eintraege': [{
        'id': task.id, 'title': task.title,
        'due': task.due.isoformat() if task.due else None,
        'overdue': bool(task.due and task.due < jetzt),
        'wartet_auf': task.wartet_auf,
    } for task in offen[:anzahl]], 'gesamt': len(offen)}


def _termine(termine: list[dict] | None, namen: list[str], adressen: list[str], jetzt: datetime,
             anzahl: int = KURZ) -> dict[str, Any]:
    """Termine der nächsten 30 Tage, deren Titel oder Ort einen Namen trägt
    oder zu deren Gästen eine der Adressen gehört. Namen werden nie gegen
    Adressen geprüft: „Mainz“ ist nicht mainz@example.org."""
    if termine is None:
        return {'eintraege': [], 'gesamt': 0, 'kalender': 'nicht_erreichbar'}
    muster = [re.compile(r'(?<!\w)' + re.escape(name) + r'(?!\w)', re.I) for name in namen if name.strip()]
    gesucht = {adresse.casefold() for adresse in adressen if adresse}
    heute = jetzt.date()
    passend = []
    for termin in termine:
        beginn = _zeit(termin.get('start'))
        titel = str(termin.get('summary') or termin.get('title') or '')
        ort = str(termin.get('location') or '')
        gaeste = {parseaddr(str(value))[1].casefold() for value in termin.get('attendees') or ()}
        ganztags = bool(termin.get('all_day'))
        if beginn is None:
            continue
        # Ein Ganztagstermin gilt den ganzen Tag, auch wenn „jetzt“ schon später ist.
        if ganztags:
            if not heute <= beginn.date() <= (jetzt + TERMIN_FENSTER).date():
                continue
        elif not jetzt <= beginn <= jetzt + TERMIN_FENSTER:
            continue
        if any(m.search(titel) or m.search(ort) for m in muster) or (gesucht & gaeste):
            passend.append({'uid': termin.get('uid'), 'titel': titel, 'ort': ort, 'start': beginn.isoformat(),
                            'ganztags': ganztags})
    passend.sort(key=lambda termin: termin['start'])
    return {'eintraege': passend[:anzahl], 'gesamt': len(passend), 'kalender': 'ok'}


def einzelheiten(episode_ids: list[str], *, episodes: Any, claims: Any, tasks: Iterable[Any] = (),
                 termine: list[dict] | None = (), namen: list[str] = (), adressen: list[str] = (),
                 jetzt: datetime | None = None, alle: bool = False) -> dict[str, Any]:
    """Ebene 2 der Mappe. `termine` None heißt: Kalender gerade nicht lesbar.

    `alle` zeigt je Liste bis zu 50 Einträge statt der kurzen Übersicht.
    """
    jetzt = jetzt or datetime.now(timezone.utc)
    lang, kurz = (ALLE, ALLE) if alle else (JE_LISTE, KURZ)
    return {
        'stand': jetzt.isoformat(),
        'bitten_und_zusagen': _abschnitte(episode_ids, ('request', 'commitment', 'conditional'),
                                          episodes=episodes, claims=claims, anzahl=lang),
        'entwicklungen': _abschnitte(episode_ids, ('change', 'status'), episodes=episodes, claims=claims,
                                     anzahl=kurz),
        'angaben': _abschnitte(episode_ids, ('fact',), episodes=episodes, claims=claims, anzahl=kurz),
        'einordnung': WorkingMemoryStore(episodes).classification_state(episode_ids),
        'aufgaben': _aufgaben(tasks, jetzt, lang),
        'termine': _termine(list(termine) if termine is not None else None, list(namen), list(adressen),
                            jetzt, kurz),
    }


def _datum(value: str | None) -> str:
    moment = _zeit(value)
    return f'{moment.day}.{moment.month}.{moment.year}' if moment else ''


def als_text(daten: dict[str, Any], titel: str) -> tuple[str, list[dict[str, Any]]]:
    """Die Mappe als Gesprächsantwort: dieselben Zeilen wie im Profil.

    Jede zitierte Zeile bekommt einen Link auf ihre Quelle. Die Zahlen
    stehen wie im Profil da; nichts wird still weggelassen.
    """
    lines = [f'{titel} · Stand der Dinge',
             'Aus den eingeordneten Quellen zusammengestellt, ohne neuen Modellaufruf.']
    links: list[dict[str, Any]] = []

    def mehr(liste: dict[str, Any]) -> None:
        gezeigt = len(liste['eintraege'])
        if liste['gesamt'] > gezeigt:
            if gezeigt:
                lines.append(f"{gezeigt} von {'bis zu ' if liste.get('ungefaehr') else ''}{liste['gesamt']}; "
                             "die übrigen stehen in der Mappe im Gedächtnis.")
            else:
                lines.append(f"Bis zu {liste['gesamt']} weitere sind noch nicht geprüft; sie stehen in der Mappe "
                             "im Gedächtnis.")
        archiv = liste.get('archiviert') or 0
        if archiv:
            lines.append('Ein Eintrag stammt aus verdichteten Monaten und wird hier nicht aufgeführt.' if archiv == 1
                         else f'{archiv} Einträge stammen aus verdichteten Monaten und werden hier nicht aufgeführt.')

    aufgaben = daten['aufgaben']
    if aufgaben['eintraege']:
        lines += ['', 'Aufgaben']
        for aufgabe in aufgaben['eintraege']:
            wann = (f"{'überfällig seit' if aufgabe['overdue'] else 'fällig'} {_datum(aufgabe['due'])}"
                    if aufgabe['due'] else 'ohne Termin')
            warten = f", wartet auf {aufgabe['wartet_auf']}" if aufgabe.get('wartet_auf') else ''
            lines.append(f"· {aufgabe['title']} ({wann}{warten})")
        mehr(aufgaben)
    termine = daten['termine']
    if termine['eintraege']:
        lines += ['', 'Nächste Termine']
        for termin in termine['eintraege']:
            ort = f" · {termin['ort']}" if termin.get('ort') else ''
            beginn = _zeit(termin['start'])
            # Ganztägiges steht als Tag da, wie es im Kalender steht; sonst mit
            # Uhrzeit in der Zeitzone des Nutzers.
            wann = (f"am {beginn.day}.{beginn.month}.{beginn.year} (ganztägig)" if termin.get('ganztags') and beginn
                    else readable_time(beginn, joiner=' um ') if beginn else termin['start'])
            lines.append(f"· {termin['titel']} {wann if termin.get('ganztags') else 'am ' + wann}{ort}")
        mehr(termine)
    if termine.get('kalender') == 'nicht_erreichbar':
        lines += ['', 'Der Kalender hat gerade nicht rechtzeitig geantwortet; Termine fehlen hier.']
    for schluessel, ueberschrift in (('bitten_und_zusagen', 'Bitten und Zusagen'),
                                     ('entwicklungen', 'Letzte Entwicklungen'),
                                     ('angaben', 'Neueste Angaben')):
        liste = daten[schluessel]
        if not liste['eintraege'] and not liste.get('archiviert') and not liste['gesamt']:
            continue
        lines += ['', ueberschrift]
        for eintrag in liste['eintraege']:
            nummer = len(links) + 1
            wann = _datum(eintrag['occurred_at']) or f"erfasst {_datum(eintrag['recorded_at'])}"
            name, adresse = parseaddr(eintrag['participants'][0]) if eintrag['participants'] else ('', '')
            von = f", {name or adresse or eintrag['participants'][0]}" if eintrag['participants'] else ''
            lines.append(f"· {eintrag['art']} ({wann}{von}): „{eintrag['text']}“ [Quelle {nummer}]")
            links.append({'episode_id': eintrag['episode_id'], 'label': f'Quelle {nummer} öffnen',
                          'automatic_memory': True})
        mehr(liste)
    if len(lines) == 2:
        lines += ['', 'In den Quellen noch keine Bitten, Zusagen, Angaben, Aufgaben oder Termine.']
    einordnung = daten.get('einordnung') or {}
    offen, aus = einordnung.get('offen', 0), einordnung.get('ausgeschlossen', 0)
    # Was nicht eingeordnet ist, kann hier nicht stehen; das wird gesagt.
    if offen == 1:
        lines += ['', 'Eine Quelle wird noch eingeordnet und ist hier noch nicht berücksichtigt.']
    elif offen:
        lines += ['', f'{offen} Quellen werden noch eingeordnet und sind hier noch nicht berücksichtigt.']
    if aus == 1:
        lines += ['', 'Eine Quelle wird nicht eingeordnet (zu groß oder von dir ausgenommen).']
    elif aus:
        lines += ['', f'{aus} Quellen werden nicht eingeordnet (zu groß oder von dir ausgenommen).']
    if daten['bitten_und_zusagen']['eintraege']:
        lines += ['', 'Ob eine Bitte inzwischen erledigt ist, steht in der Quelle nicht; das Datum hilft beim Einschätzen.']
    return '\n'.join(lines), links


__all__ = ['als_text', 'einzelheiten']
