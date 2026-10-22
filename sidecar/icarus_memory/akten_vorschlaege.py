"""Vorschlag „Neue Akte?“: ein Projekt, das sich in den Mails bildet, erkennen und mit einem Klick anlegen.

Projekt-Akten entstehen bisher nur über eine Zuordnung des Nutzers (`episode.project_id`) oder als Akte einer
bloßen Erwähnung (`projekt:n:<Name>`, `bezuege.py`). Ein Projekt, das sich erst in den Mails bildet, bemerkt
niemand. Dieses Modul sieht die erwähnten, noch nicht angelegten Projekte durch und schlägt vor, daraus eine
Akte zu machen, mit Begründung in einem Satz und den Textstellen.

Regeln (`docs/30-akten.md`, Abschnitt „Neue Akte?“):

* **Verdichtung schlägt vor, sie schreibt nicht.** Ein Projekt ist Ablage, kein Fakt; es entsteht nur durch den
  Klick des Nutzers (`annehmen`). Der Vorschlag selbst speichert nichts, und das Annehmen legt keine Aussage an.
* **Ohne Modell**, deterministisch und nachprüfbar: Ein Name wird vorgeschlagen, wenn mindestens eine Schwelle
  erreicht ist: `MIN_QUELLEN` geltende Quellen, oder `MIN_BETEILIGTE` verschiedene Personen über mindestens zwei
  Quellen, oder Quellen über `MIN_TAGE` Tage verteilt.
* **Nie vorgeschlagen** werden Namen, die ein vorhandenes Projekt tragen (ohne Groß- und Kleinschreibung, in
  Umschrift wie „Mueller“ und „Müller“), Namen mit weniger als `MIN_ZEICHEN` Zeichen und reine Zahlen. Zwei
  gleichnamige Projekte ordnet `bezuege.projekte_aus` bewusst nicht zu; das bleibt so.
* **Reversibel.** Annehmen lässt sich zurücknehmen (Zuordnungen lösen, Projekt entfernen, wenn nichts anderes
  daran hängt). „Nein danke“ wird gemerkt und nicht wiederholt, bis der Nutzer es unter der Akte zurücknimmt.
* **Nur Verweise.** Die Tabelle `akten_vorschlag_entscheidungen` (Migration 24) hält je Vorschlag die Entscheidung,
  den Zeitpunkt, die Sache, das angelegte Projekt und die zugeordneten Quellen-IDs. Kein Text.

Die Kennung eines Vorschlags ist ein Hash des normalisierten Namens (`kennung_von`); die Projekt-ID ist daraus
abgeleitet (`projekt_id`), damit ein unterbrochenes Annehmen beim zweiten Versuch nur ergänzt.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .bezuege import projekt_kennung, sache_id, zerlegen
from .datumstext import iso_versuchen, tag_und_monat
from .word_forms import umschrift_gleich

#: Schwellen: eine davon genügt.
MIN_QUELLEN = 3
MIN_BETEILIGTE = 2
MIN_TAGE = 14
#: Kürzere Namen und reine Zahlen sind kein Projekt („X1“, „2026“).
MIN_ZEICHEN = 3
#: So viele erwähnte Projekte werden höchstens durchgesehen (jüngste zuerst).
MAX_SACHEN = 500
#: So viele Quellen zeigt ein Vorschlag mit Textstelle; zugeordnet werden beim Annehmen alle.
QUELLEN_GEZEIGT = 5
MAX_NAMEN = 3

ENTSCHEIDUNGEN = ('angenommen', 'abgelehnt')
TABLES = {'akten_vorschlag_entscheidungen': {'kennung', 'entscheidung', 'zeit', 'sache', 'projekt_id', 'quellen'}}
PRIMARY_KEYS = {'akten_vorschlag_entscheidungen': {'kennung'}}

_KENNUNG = re.compile(r'^[0-9a-f]{16}$')
_QUELLEN_WORT = {'message': 'Mails', 'document': 'Notizen', 'event': 'Terminen'}


def migrate(connection: sqlite3.Connection) -> None:
    """Migration 24 der Episoden: die Entscheidungen zu Vorschlägen „Neue Akte?“ (nur Verweise)."""
    connection.execute("""CREATE TABLE akten_vorschlag_entscheidungen (
        kennung TEXT PRIMARY KEY,
        entscheidung TEXT NOT NULL CHECK(entscheidung IN ('angenommen','abgelehnt')),
        zeit REAL NOT NULL,
        sache TEXT NOT NULL DEFAULT '',
        projekt_id TEXT NOT NULL DEFAULT '',
        quellen TEXT NOT NULL DEFAULT '[]')""")


# -- Kennungen ---------------------------------------------------------------------------------


def kennung_von(name: str) -> str:
    """Die stabile Kennung eines Vorschlags: Hash des normalisierten Namens („Projekt Atlas“, „atlas“ sind eins)."""
    return hashlib.sha256(projekt_kennung(name).encode()).hexdigest()[:16]


def projekt_id(kennung: str) -> str:
    """Die Projekt-ID zu einer Kennung; deterministisch, damit Annehmen idempotent bleibt."""
    return 'p-akte-' + hashlib.sha256(kennung.encode()).hexdigest()[:24]


def gueltige_kennung(kennung: str) -> bool:
    return isinstance(kennung, str) and bool(_KENNUNG.match(kennung))


def _vergleichsform(name_kennung: str) -> str:
    return umschrift_gleich(projekt_kennung(name_kennung))


def vorhandene_projekte(workspace: Any) -> set[str]:
    """Vergleichsformen aller Projektnamen des Arbeitsbereichs, auch abgeschlossener."""
    if workspace is None:
        return set()
    try:
        projekte = workspace.projects(include_closed=True)
    except Exception:  # noqa: BLE001 - ohne Arbeitsbereich gibt es keine vorhandenen Projekte
        return set()
    return {_vergleichsform(p.name) for p in projekte if projekt_kennung(p.name)}


# -- Der Vorschlag -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Vorschlag:
    """Ein erwähntes, noch nicht angelegtes Projekt mit Begründung und Textstellen. Nichts davon ist gespeichert."""

    kennung: str
    sache: str
    """`projekt:n:<Name>`, die Akte der bloßen Erwähnung."""
    name: str
    grund: str
    """Ein Satzteil ohne Punkt: „In 4 Mails seit 3. Oktober mit Anna Keller und Ben Braun“."""
    anzahl: int
    tage: int
    erste: str
    """Zeitpunkt der ältesten Quelle (ISO), für die Reihenfolge im Briefing."""
    quellen: tuple[dict[str, Any], ...]
    """Jüngste zuerst, höchstens `QUELLEN_GEZEIGT`: `episode_id`, `titel`, `datum`, `zitat`."""
    beteiligte: tuple[dict[str, Any], ...]
    """Personen in denselben Quellen: `sache`, `name`, `anzahl`."""
    quellen_ids: tuple[str, ...]
    """Alle geltenden Quellen; sie werden beim Annehmen zugeordnet."""

    def als_dict(self) -> dict[str, Any]:
        return {'kennung': self.kennung, 'sache': self.sache, 'name': self.name, 'grund': self.grund,
                'anzahl': self.anzahl, 'tage': self.tage, 'erste': self.erste, 'quellen': list(self.quellen),
                'beteiligte': list(self.beteiligte)}


def _zeit(text: str | None) -> datetime | None:
    return iso_versuchen(text) if text else None


def _aufzaehlung(namen: list[str]) -> str:
    if len(namen) <= MAX_NAMEN:
        return namen[0] if len(namen) == 1 else ', '.join(namen[:-1]) + ' und ' + namen[-1]
    rest = len(namen) - MAX_NAMEN
    return ', '.join(namen[:MAX_NAMEN]) + (' und einer weiteren Person' if rest == 1 else f' und {rest} weiteren')


def grund_satz(anzahl: int, arten: set[str], erste: datetime | None, namen: list[str]) -> str:
    """„In 4 Mails seit 3. Oktober mit Anna Keller und Ben Braun“: Zahl, Zeit und Menschen, nachprüfbar."""
    wort = _QUELLEN_WORT[next(iter(arten))] if len(arten) == 1 and next(iter(arten)) in _QUELLEN_WORT else 'Quellen'
    teile = [f'In {anzahl} {wort}']
    if erste is not None:
        teile.append(f'seit {tag_und_monat(erste.astimezone())}')
    if namen:
        teile.append('mit ' + _aufzaehlung(namen))
    return ' '.join(teile)


def _schwelle_erreicht(anzahl: int, beteiligte: int, tage: int) -> bool:
    return anzahl >= MIN_QUELLEN or (beteiligte >= MIN_BETEILIGTE and anzahl >= 2) or (tage >= MIN_TAGE and anzahl >= 2)


def _bauen(bezuege: Any, sache: str, kennung: str, *, pruefen: bool = True) -> Vorschlag | None:
    quellen = bezuege.quellen_von(sache)
    if not quellen:
        return None
    ids = [q['episode_id'] for q in quellen]
    zeiten = [z for z in (_zeit(q['zeit']) for q in quellen) if z is not None]
    tage = (max(zeiten) - min(zeiten)).days if len(zeiten) > 1 else 0
    gemeinsame = bezuege.gemeinsame(sache, ids)
    personen = sorted((s for s in gemeinsame if s.startswith('person:')), key=lambda s: (-gemeinsame[s], s))
    if pruefen and not _schwelle_erreicht(len(quellen), len(personen), tage):
        return None
    namen = bezuege.beschriftungen(personen[:MAX_NAMEN + 1]) if personen else {}
    beteiligte = tuple({'sache': s, 'name': namen.get(s, s), 'anzahl': gemeinsame[s]} for s in personen[:MAX_NAMEN + 1])
    gezeigt = []
    for q in quellen[:QUELLEN_GEZEIGT]:
        try:
            titel = bezuege.episodes.get(q['episode_id']).title
        except Exception:  # noqa: BLE001 - eine unlesbare Quelle fehlt nur in der Anzeige
            titel = ''
        zitat = next((z for z in (bezuege.zitat(q['episode_id'], s, e) for s, e in q.get('stellen', [])) if z), '')
        gezeigt.append({'episode_id': q['episode_id'], 'titel': titel, 'datum': q['zeit'], 'zitat': zitat})
    erste = min(zeiten) if zeiten else None
    return Vorschlag(
        kennung=kennung, sache=sache, name=bezuege.beschriftung(sache, quellen=quellen),
        grund=grund_satz(len(quellen), {str(q.get('art') or '') for q in quellen}, erste,
                         [b['name'] for b in beteiligte]),
        anzahl=len(quellen), tage=tage, erste=erste.isoformat() if erste else '', quellen=tuple(gezeigt),
        beteiligte=beteiligte, quellen_ids=tuple(ids))


def _erwaehnte(bezuege: Any, workspace: Any) -> list[tuple[str, str]]:
    """(Sache, Kennung) der erwähnten, noch nicht angelegten Projekte, die überhaupt in Frage kommen."""
    vorhanden = vorhandene_projekte(workspace)
    ergebnis = []
    for eintrag in bezuege.sachen(art='projekt', limit=MAX_SACHEN)['sachen']:
        teile = zerlegen(eintrag['sache'])
        if teile is None or not teile[1].startswith('n:'):
            continue
        name_kennung = teile[1][2:]
        if len(name_kennung) < MIN_ZEICHEN or name_kennung.isdigit() or _vergleichsform(name_kennung) in vorhanden:
            continue
        ergebnis.append((eintrag['sache'], kennung_von(name_kennung)))
    return ergebnis


def kandidaten(bezuege: Any, workspace: Any) -> list[Vorschlag]:
    """Alle Vorschläge, die eine Schwelle erreichen und nicht entschieden sind; die meisten Quellen zuerst,
    bei gleicher Zahl der älteste."""
    gemerkt = Entscheidungen(bezuege.episodes).alle()
    ergebnis = []
    for sache, kennung in _erwaehnte(bezuege, workspace):
        if kennung in gemerkt:
            continue
        vorschlag = _bauen(bezuege, sache, kennung)
        if vorschlag is not None:
            ergebnis.append(vorschlag)
    ergebnis.sort(key=lambda v: (-v.anzahl, v.erste or '9', v.sache))
    return ergebnis


def vorschlag_zu(bezuege: Any, workspace: Any, kennung: str) -> Vorschlag | None:
    """Der Vorschlag zu einer Kennung, auch unter der Schwelle und auch nach „Nein danke“ (der Nutzer darf es
    sich anders überlegen). None, wenn kein erwähntes Projekt diese Kennung trägt.

    Wurde das Projekt schon angelegt, aber die Entscheidung nicht gemerkt (Unterbrechung), hängen die Erwähnungen
    bereits am Projekt: Dann gilt dessen Akte als Vorschlag, damit der zweite Versuch nur ergänzt.
    """
    for sache, k in _erwaehnte(bezuege, workspace):
        if k == kennung:
            return _bauen(bezuege, sache, kennung, pruefen=False)
    if workspace is not None:
        from .workspace import WorkspaceError
        try:
            projekt = workspace.project(projekt_id(kennung))
        except WorkspaceError:
            return None
        if projekt.is_open():
            return _bauen(bezuege, sache_id('projekt', projekt.id), kennung, pruefen=False)
    return None


# -- Ablage der Entscheidungen -------------------------------------------------------------------


class Entscheidungen:
    """Was ein Mensch zu einem Vorschlag gesagt hat. Schreibt nur auf ausdrücklichen Wunsch (`merken`, `loeschen`)."""

    def __init__(self, episodes: Any) -> None:
        self.episodes = episodes

    @staticmethod
    def _dict(zeile: Any) -> dict[str, Any]:
        try:
            quellen = json.loads(zeile['quellen'] or '[]')
        except ValueError:
            quellen = []
        return {'kennung': zeile['kennung'], 'entscheidung': zeile['entscheidung'], 'zeit': zeile['zeit'],
                'sache': zeile['sache'], 'projekt_id': zeile['projekt_id'],
                'quellen': [str(q) for q in quellen if isinstance(q, str)]}

    def alle(self) -> dict[str, str]:
        with self.episodes._lock:
            return {z['kennung']: z['entscheidung'] for z in self.episodes._conn.execute(
                'SELECT kennung, entscheidung FROM akten_vorschlag_entscheidungen')}

    def zu(self, kennung: str) -> dict[str, Any] | None:
        with self.episodes._lock:
            zeile = self.episodes._conn.execute(
                'SELECT * FROM akten_vorschlag_entscheidungen WHERE kennung = ?', (kennung,)).fetchone()
        return self._dict(zeile) if zeile else None

    def nach_projekt(self, projekt_id: str) -> dict[str, Any] | None:
        if not projekt_id:
            return None
        with self.episodes._lock:
            zeile = self.episodes._conn.execute(
                "SELECT * FROM akten_vorschlag_entscheidungen WHERE projekt_id = ? AND entscheidung = 'angenommen'",
                (projekt_id,)).fetchone()
        return self._dict(zeile) if zeile else None

    def merken(self, kennung: str, entscheidung: str, *, sache: str = '', projekt_id: str = '',
               quellen: tuple[str, ...] | list[str] = ()) -> dict[str, Any]:
        if not gueltige_kennung(kennung) or entscheidung not in ENTSCHEIDUNGEN:
            raise ValueError('Unbekannter Vorschlag oder unbekannte Entscheidung.')
        with self.episodes.transaction():
            self.episodes._conn.execute(
                'INSERT INTO akten_vorschlag_entscheidungen VALUES (?,?,?,?,?,?) ON CONFLICT(kennung) DO UPDATE SET '
                'entscheidung=excluded.entscheidung, zeit=excluded.zeit, sache=excluded.sache, '
                'projekt_id=excluded.projekt_id, quellen=excluded.quellen',
                (kennung, entscheidung, time.time(), sache, projekt_id, json.dumps(list(quellen))))
        return self.zu(kennung) or {}

    def loeschen(self, kennung: str) -> bool:
        with self.episodes.transaction():
            return self.episodes._conn.execute(
                'DELETE FROM akten_vorschlag_entscheidungen WHERE kennung = ?', (kennung,)).rowcount > 0


def oeffentlich(gemerkt: dict[str, Any]) -> dict[str, Any]:
    """Die Entscheidung für die Anzeige: ohne die Liste der Quellen-IDs, nur ihre Zahl."""
    return {'kennung': gemerkt['kennung'], 'entscheidung': gemerkt['entscheidung'], 'zeit': gemerkt['zeit'],
            'projekt_id': gemerkt['projekt_id'], 'quellen': len(gemerkt['quellen'])}


# -- Annehmen, Ablehnen, Zurücknehmen -------------------------------------------------------------


class SchonEntschieden(Exception):
    """Der Vorschlag ist schon angenommen (oder abgelehnt): nichts wird doppelt getan."""


class Unbekannt(Exception):
    """Zu dieser Kennung gibt es keinen Vorschlag und keine Entscheidung."""


def _zahl_quellen(n: int, verb: str) -> str:
    return f'keine Quelle {verb}' if n == 0 else f'eine Quelle {verb}' if n == 1 else f'{n} Quellen {verb}'


def link_zur_akte(sache: str) -> str:
    return f'/memory/akte/{sache}'


def annehmen(bezuege: Any, workspace: Any, vorschlag: Vorschlag, *, audit: Any = None) -> dict[str, Any]:
    """Legt das Projekt idempotent an und ordnet die Quellen des Vorschlags zu, die noch kein Projekt haben.

    Ablage, kein Fakt: Es entsteht keine Aussage, nur `project_id` an den Quellen (wie `PUT /episodes/projects`).
    """
    from .model import Provenance, SourceType, now
    from .workspace import WorkspaceError
    episodes = bezuege.episodes
    ablage = Entscheidungen(episodes)
    gemerkt = ablage.zu(vorschlag.kennung)
    if gemerkt is not None and gemerkt['entscheidung'] == 'angenommen':
        raise SchonEntschieden('Diese Akte ist schon angelegt.')
    pid = projekt_id(vorschlag.kennung)
    try:
        projekt = workspace.project(pid)
    except WorkspaceError:
        projekt = None
    if projekt is None:
        projekt = workspace.add_project(
            vorschlag.name, Provenance(source_type=SourceType.USER_STATED, source_ref=f'akte-vorschlag:{vorschlag.kennung}',
                                       captured_at=now()), _identifier=pid)
    elif not projekt.is_open():
        raise SchonEntschieden('Zu diesem Vorschlag gibt es schon ein abgeschlossenes Projekt. Bitte dort nachsehen.')
    zugeordnet: list[str] = []
    for episode_id in vorschlag.quellen_ids:
        try:
            episode = episodes.get(episode_id)
        except Exception:  # noqa: BLE001 - eine inzwischen entzogene Quelle wird nicht zugeordnet
            continue
        if episode.project_id is None:
            episodes.link_project(episode_id, pid)
            zugeordnet.append(episode_id)
        elif episode.project_id == pid:
            zugeordnet.append(episode_id)   # nach einer Unterbrechung schon zugeordnet
    if audit is not None and zugeordnet:
        try:
            audit.record('quellen_projekt_zuordnen', 'write_local', 'auto', 'executed',
                         {'episode_ids': zugeordnet, 'project_id': pid})
        except Exception:  # noqa: BLE001 - das Protokoll darf die Ablage nicht aufhalten
            pass
    ablage.merken(vorschlag.kennung, 'angenommen', sache=vorschlag.sache, projekt_id=pid, quellen=zugeordnet)
    sache = sache_id('projekt', pid)
    return {'kennung': vorschlag.kennung, 'sache': sache, 'link': link_zur_akte(sache),
            'projekt': {'id': pid, 'name': projekt.name}, 'zugeordnet': len(zugeordnet),
            'satz': f'Akte „{projekt.name}“ angelegt, {_zahl_quellen(len(zugeordnet), "zugeordnet")}.'}


def ablehnen(bezuege: Any, vorschlag: Vorschlag) -> dict[str, Any]:
    """„Nein danke“: merken, nie wieder vorschlagen (bis der Nutzer es unter der Akte zurücknimmt)."""
    ablage = Entscheidungen(bezuege.episodes)
    if ablage.zu(vorschlag.kennung) is not None:
        raise SchonEntschieden('Dazu gibt es schon eine Entscheidung von dir.')
    ablage.merken(vorschlag.kennung, 'abgelehnt', sache=vorschlag.sache)
    return {'kennung': vorschlag.kennung, 'sache': vorschlag.sache, 'link': link_zur_akte(vorschlag.sache),
            'satz': f'Gemerkt: „{vorschlag.name}“ wird nicht mehr vorgeschlagen.'}


def zuruecknehmen(bezuege: Any, workspace: Any, kennung: str, *, tasks: Any = None, audit: Any = None) -> dict[str, Any]:
    """Stellt den Stand vor der Entscheidung her: Zuordnungen lösen, Projekt entfernen, wenn nichts anderes daran
    hängt (andere Quellen, Aufgaben, Notizen); eine Ablehnung wird einfach vergessen."""
    from .workspace import WorkspaceError
    episodes = bezuege.episodes
    ablage = Entscheidungen(episodes)
    gemerkt = ablage.zu(kennung)
    if gemerkt is None:
        raise Unbekannt('Dazu gibt es keine Entscheidung von dir.')
    sache = gemerkt['sache']
    if gemerkt['entscheidung'] == 'abgelehnt':
        ablage.loeschen(kennung)
        name = bezuege.beschriftung(sache) if zerlegen(sache) else 'das Projekt'
        return {'kennung': kennung, 'sache': sache, 'link': link_zur_akte(sache),
                'satz': f'Zurückgenommen: „{name}“ kann wieder vorgeschlagen werden.'}
    pid = gemerkt['projekt_id']
    try:
        projekt = workspace.project(pid)
    except WorkspaceError:
        projekt = None
    name = projekt.name if projekt else (bezuege.beschriftung(sache) if zerlegen(sache) else 'das Projekt')
    geloest: list[str] = []
    for episode_id in gemerkt['quellen']:
        try:
            episode = episodes.get(episode_id)
        except Exception:  # noqa: BLE001
            continue
        if episode.project_id == pid:
            episodes.link_project(episode_id, None)
            geloest.append(episode_id)
    if audit is not None and geloest:
        try:
            audit.record('quellen_projekt_zuordnen', 'write_local', 'auto', 'executed',
                         {'episode_ids': geloest, 'project_id': None})
        except Exception:  # noqa: BLE001
            pass
    andere = len(episodes.by_project(pid, limit=100)) if pid else 0
    gebunden = False
    if projekt is not None and not andere:
        try:
            gebunden = bool(tasks is not None and tasks.by_project(pid, include_closed=True)) or bool(
                workspace.notes(project_id=pid, limit=1))
        except Exception:  # noqa: BLE001 - im Zweifel bleibt das Projekt stehen (fail closed)
            gebunden = True
    entfernt = False
    if projekt is not None and not andere and not gebunden:
        try:
            entfernt = workspace.remove_project(pid)
        except WorkspaceError:
            entfernt = False
    ablage.loeschen(kennung)
    satz = f'Zurückgenommen: {_zahl_quellen(len(geloest), "gelöst")}'
    if entfernt:
        satz += f', Projekt „{name}“ entfernt.'
    elif projekt is None:
        satz += '.'
    elif andere:
        satz += (f'. Das Projekt „{name}“ bleibt, weil noch eine andere Quelle dazugehört.' if andere == 1
                 else f'. Das Projekt „{name}“ bleibt, weil noch {andere} andere Quellen dazugehören.')
    else:
        satz += f'. Das Projekt „{name}“ bleibt, weil noch Aufgaben oder Notizen dazugehören.'
    return {'kennung': kennung, 'sache': sache, 'link': link_zur_akte(sache), 'geloest': len(geloest),
            'projekt_entfernt': entfernt, 'satz': satz}


__all__ = ['ENTSCHEIDUNGEN', 'Entscheidungen', 'MAX_SACHEN', 'MIN_BETEILIGTE', 'MIN_QUELLEN', 'MIN_TAGE', 'MIN_ZEICHEN',
           'SchonEntschieden', 'Unbekannt', 'Vorschlag', 'ablehnen', 'annehmen', 'grund_satz', 'gueltige_kennung',
           'kandidaten', 'kennung_von', 'oeffentlich', 'projekt_id', 'vorschlag_zu', 'zuruecknehmen']
