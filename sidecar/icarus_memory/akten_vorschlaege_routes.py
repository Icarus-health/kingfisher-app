"""Verdrahtung der Vorschläge „Neue Akte?“ (`akten_vorschlaege.py`): Zeile in der Akte, Satz im Briefing, drei Klicks.

* `GET  /api/v1/akten/vorschlaege`: alle offenen Vorschläge (Prüfung und Diagnose; die Oberfläche zeigt nie eine Liste).
* `POST /api/v1/akten/vorschlaege/{kennung}/annehmen`: legt das Projekt an, ordnet die Quellen ohne Projekt zu,
  merkt „angenommen“. Antwort: die Akte (Link) und ein Satz. 404 bei unbekannter Kennung, 409 wenn schon angenommen.
* `POST /api/v1/akten/vorschlaege/{kennung}/ablehnen`: „Nein danke“, wird gemerkt und nicht wiederholt.
* `POST /api/v1/akten/vorschlaege/{kennung}/zuruecknehmen`: stellt den Stand vor der Entscheidung her.

Jeder Klick steht im Logbuch (Art `akte_vorschlag`, nur Kennung, Entscheidung, Sache und Name, kein Text). Seit
Paket P (`docs/66-automatik.md`) legt Kingfisher **klare** Vorschläge vor dem Briefing selbst an
(`projekt_automatik.py`, mit Grund und „Rückgängig“); das Briefing fragt dann nur noch nach den unklaren, einer nach
dem anderen. Das Zurücknehmen einer solchen Anlage löst nur Kingfishers eigene Zuordnungen und wird gemerkt.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Path

from . import akten_vorschlaege as modul
from .bezuege import zerlegen

logger = logging.getLogger(__name__)

_KENNUNG = Path(..., pattern=r'^[0-9a-f]{16}$')


def _ins_logbuch(app, entscheidung: str, sache: str, name: str, kennung: str) -> None:
    buch = getattr(app.state, 'logbuch', None)
    if buch is not None:
        buch.vermerke('akte_vorschlag', entscheidung=entscheidung, sache=sache, name=name, kennung=kennung)


def fuer_briefing(app) -> dict[str, Any]:
    """Höchstens ein Vorschlag für Briefing und Heute: der mit den meisten Quellen, bei gleicher Zahl der älteste.

    Vorher legt Kingfisher die klaren selbst an und ordnet neue Mails nach Absender zu (`projekt_automatik`): Was
    dann noch übrig ist, ist unklar und bleibt Frage, einer nach dem anderen."""
    from . import projekt_automatik
    from .akten_routes import bausteine, nachfuehren
    projekt_automatik.schritt_fuer(app)
    nachfuehren(app)
    bezuege, _ = bausteine(app)
    alle = modul.kandidaten(bezuege, getattr(app.state, 'workspace', None))
    return {'anzahl': len(alle), 'vorschlag': alle[0].als_dict() if alle else None}


def fuer_akte(app, sache: str) -> dict[str, Any] | None:
    """Die Zeile „Daraus eine Akte machen?“ einer Akte `projekt:n:<Name>`, oder die gemerkte Entscheidung
    (abgelehnt dort, angenommen in der Akte des angelegten Projekts). None bei allen anderen Sachen."""
    from .akten_routes import bausteine
    from .projekt_automatik import ergaenzen
    teile = zerlegen(sache)
    if teile is None or teile[0] != 'projekt':
        return None
    bezuege, _ = bausteine(app)
    ablage = modul.Entscheidungen(bezuege.episodes)
    if teile[1].startswith('n:'):
        kennung = modul.kennung_von(teile[1][2:])
        gemerkt = ablage.zu(kennung)
        if gemerkt is not None:
            return {'vorschlag': None, 'entscheidung': ergaenzen(bezuege.episodes, bezuege, modul.oeffentlich(gemerkt))}
        vorschlag = next((v for v in modul.kandidaten(bezuege, getattr(app.state, 'workspace', None))
                          if v.kennung == kennung), None)
        return {'vorschlag': vorschlag.als_dict() if vorschlag else None, 'entscheidung': None}
    gemerkt = ablage.nach_projekt(teile[1])
    return ({'vorschlag': None, 'entscheidung': ergaenzen(bezuege.episodes, bezuege, modul.oeffentlich(gemerkt))}
            if gemerkt else None)


def _vorschlag(app, kennung: str) -> modul.Vorschlag:
    """Der Vorschlag zur Kennung; 409, wenn die Akte schon angelegt ist (die Erwähnungen hängen dann am Projekt,
    der Vorschlag selbst ist weg), 404, wenn kein erwähntes Projekt die Kennung trägt."""
    from .akten_routes import bausteine, nachfuehren
    nachfuehren(app)
    bezuege, _ = bausteine(app)
    gemerkt = modul.Entscheidungen(bezuege.episodes).zu(kennung)
    if gemerkt is not None and gemerkt['entscheidung'] == 'angenommen':
        raise HTTPException(status_code=409, detail='Diese Akte ist schon angelegt.')
    vorschlag = modul.vorschlag_zu(bezuege, getattr(app.state, 'workspace', None), kennung)
    if vorschlag is None:
        raise HTTPException(status_code=404, detail='Diesen Vorschlag gibt es nicht (mehr). Bitte neu laden.')
    return vorschlag


def register(app, guard) -> None:
    from . import projekt_automatik, projekt_automatik_routes
    from .akten_routes import bausteine, nachfuehren
    # Projekte von selbst (Paket P): Heute-Hinweis und „Rückgängig“ je Mail, in eigener Datei.
    projekt_automatik_routes.register(app, guard)

    @app.get('/api/v1/akten/vorschlaege', dependencies=guard)
    def akten_vorschlaege() -> dict[str, Any]:
        """Alle offenen Vorschläge mit Grund und Textstellen (Prüfung und Diagnose)."""
        nachfuehren(app)
        bezuege, _ = bausteine(app)
        alle = modul.kandidaten(bezuege, getattr(app.state, 'workspace', None))
        return {'anzahl': len(alle), 'vorschlaege': [v.als_dict() for v in alle]}

    @app.post('/api/v1/akten/vorschlaege/{kennung}/annehmen', dependencies=guard)
    def akten_vorschlag_annehmen(kennung: str = _KENNUNG) -> dict[str, Any]:
        """Erst dieser Klick legt das Projekt an. Ablage, kein Fakt; umkehrbar mit `zuruecknehmen`."""
        vorschlag = _vorschlag(app, kennung)
        bezuege, _ = bausteine(app)
        try:
            ergebnis = modul.annehmen(bezuege, app.state.workspace, vorschlag, audit=getattr(app.state, 'audit', None))
        except modul.SchonEntschieden as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        _ins_logbuch(app, 'angenommen', ergebnis['sache'], ergebnis['projekt']['name'], kennung)
        # Die Erwähnungen hängen jetzt am Projekt (Register-Token); die Akte des Projekts soll gleich vollständig sein.
        nachfuehren(app)
        return ergebnis

    @app.post('/api/v1/akten/vorschlaege/{kennung}/ablehnen', dependencies=guard)
    def akten_vorschlag_ablehnen(kennung: str = _KENNUNG) -> dict[str, Any]:
        """„Nein danke“: gemerkt, nie wiederholt, bis der Nutzer es unter der Akte zurücknimmt."""
        vorschlag = _vorschlag(app, kennung)
        bezuege, _ = bausteine(app)
        try:
            ergebnis = modul.ablehnen(bezuege, vorschlag)
        except modul.SchonEntschieden as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        _ins_logbuch(app, 'abgelehnt', vorschlag.sache, vorschlag.name, kennung)
        return ergebnis

    @app.post('/api/v1/akten/vorschlaege/{kennung}/zuruecknehmen', dependencies=guard)
    def akten_vorschlag_zuruecknehmen(kennung: str = _KENNUNG) -> dict[str, Any]:
        """Stellt den Stand vor der Entscheidung her; 404 ohne Entscheidung. Eine Anlage durch Kingfisher wird nur in
        ihren eigenen Zuordnungen gelöst und als abgelehnt gemerkt (`projekt_automatik.zuruecknehmen`)."""
        bezuege, _ = bausteine(app)
        try:
            ergebnis = projekt_automatik.zuruecknehmen(bezuege, app.state.workspace, kennung,
                                                       tasks=getattr(app.state, 'tasks', None),
                                                       audit=getattr(app.state, 'audit', None))
        except modul.Unbekannt as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        _ins_logbuch(app, 'zurueckgenommen', ergebnis['sache'], '', kennung)
        nachfuehren(app)
        return ergebnis


__all__ = ['fuer_akte', 'fuer_briefing', 'register']
