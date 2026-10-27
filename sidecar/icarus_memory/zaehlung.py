"""Eine Zahl je Begriff (Persona-Prüfung, Paket Z1, 27.10.2026).

Heute sagte „Ein Punkt braucht dich“, Aufgaben „2 Aufgaben brauchen dich heute“; über einer leeren Liste stand „1“ am
Filter, und unter Zugänge „2 Kalender verbunden“ über drei Zeilen. Jede Stelle zählte mit eigener Regel. Hier steht die
eine Regel je Begriff; jede Anzeige rechnet mit ihr, und `test_eine_zahl.py` hält die Stellen gleich:

* **braucht dich heute** (`heute_dran`): offene Aufgaben, die bei dir liegen (nicht „wartet auf“), fällig heute oder
  früher, nach dem Kalendertag des Nutzers. Das Briefing auf Heute, die Zeile unter „Aufgaben“ und der Satz auf Heute
  zählen damit; das Briefing teilt sie nur in „überfällig“ (früherer Tag) und „heute fällig“.
* **offen, wartet, erledigt** im Bereichsfilter (`ids_im_bereich`): Der Filter „Arbeit · Privat“ filtert im Sidecar,
  vor dem Zählen und vor dem Blättern. So sind Zahl am Segment, Projektüberblick und Liste dieselbe Auswahl.
* **was Heute braucht** (`Briefing.zaehlung`): die Aufgaben von oben und die übrigen Punkte des Briefings (Termin,
  Entscheidung, Vorschlag …), auch die, die über die drei sichtbaren hinaus nicht mehr dastehen.

Nur Lesen; nichts hier ändert eine Aufgabe.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable

from .datumstext import iso_versuchen

ALLE = "alle"


def _feld(aufgabe: Any, name: str) -> Any:
    if isinstance(aufgabe, dict):
        return aufgabe.get(name)
    wert = getattr(aufgabe, name, None)
    return getattr(wert, "value", wert)


def bei_mir_offen(aufgabe: Any) -> bool:
    """Offen und nicht bei jemand anderem. Fehlt der Stand (ältere Briefingdaten), gilt die Aufgabe als offen."""
    return str(_feld(aufgabe, "status") or "open") == "open" and not _feld(aufgabe, "wartet_auf")


def faellig_am(aufgabe: Any, jetzt: datetime) -> date | None:
    """Der Kalendertag der Fälligkeit beim Nutzer. Ein Zeitpunkt mit Zone wird in die Zone von `jetzt` umgerechnet;
    ein Datum ohne Uhrzeit und ein Zeitpunkt ohne Zone behalten ihren geschriebenen Tag."""
    faellig = iso_versuchen(_feld(aufgabe, "due"))
    if faellig is None:
        return None
    if faellig.tzinfo is not None and jetzt.tzinfo is not None:
        faellig = faellig.astimezone(jetzt.tzinfo)
    return faellig.date()


def _heute(jetzt: datetime) -> date:
    return jetzt.date()


def heute_dran(aufgaben: Iterable[Any], jetzt: datetime) -> list[Any]:
    """Was dich heute braucht: offen bei dir, fällig heute oder früher. Reihenfolge wie übergeben."""
    heute = _heute(jetzt)
    treffer = []
    for aufgabe in aufgaben:
        if not bei_mir_offen(aufgabe):
            continue
        tag = faellig_am(aufgabe, jetzt)
        if tag is not None and tag <= heute:
            treffer.append(aufgabe)
    return treffer


def ist_ueberfaellig(aufgabe: Any, jetzt: datetime) -> bool:
    """Teil von `heute_dran`: fällig an einem früheren Tag."""
    tag = faellig_am(aufgabe, jetzt)
    return tag is not None and tag < _heute(jetzt) and bei_mir_offen(aufgabe)


def bereich_gewaehlt(bereich: str | None) -> str | None:
    """None für „kein Filter“ (leer oder „alle“), sonst die Kennung des Bereichs."""
    wert = (bereich or "").strip()
    return None if not wert or wert == ALLE else wert


def ids_im_bereich(app: Any, bereich: str | None, *, project_id: str | None = None) -> set[str] | None:
    """Die Kennungen aller Aufgaben (jeden Stands) im gewählten Bereich, mit derselben Herleitung wie in der Liste
    (`bereiche.aufgaben_anreichern`). None heißt: kein Filter."""
    gewaehlt = bereich_gewaehlt(bereich)
    if gewaehlt is None:
        return None
    from . import bereiche
    store = app.state.tasks
    aufgaben = store.by_project(project_id, include_closed=True) if project_id else store.all_tasks(limit=-1)
    daten = bereiche.aufgaben_anreichern(app, [t.to_dict() for t in aufgaben])
    return {d["id"] for d in daten if d.get("bereich") == gewaehlt}


def heute_dran_zahl(app: Any, jetzt: datetime, *, project_id: str | None = None, ids: set[str] | None = None) -> int:
    """„N Aufgaben brauchen dich heute“ unter Aufgaben: dieselbe Regel wie das Briefing, mit Projekt und Bereich der Liste."""
    offen = app.state.tasks.open_tasks(limit=None)
    if project_id:
        offen = [t for t in offen if t.project_id == project_id]
    if ids is not None:
        offen = [t for t in offen if t.id in ids]
    return len(heute_dran(offen, jetzt))


__all__ = ["ALLE", "bei_mir_offen", "bereich_gewaehlt", "faellig_am", "heute_dran", "heute_dran_zahl",
           "ids_im_bereich", "ist_ueberfaellig"]
