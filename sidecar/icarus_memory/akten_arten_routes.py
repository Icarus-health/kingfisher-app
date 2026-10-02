"""Verdrahtung der privaten Akten-Arten (`akten_arten.py`): Karte in der Akte, Bestätigung, Fristen.

* `GET    /api/v1/akten/art?sache=organisation:…`: bestätigte Art, Vorschlag mit Begründung, die Wahlen.
* `PUT    /api/v1/akten/art` `{sache, art}`: der Klick eines Menschen legt die Art fest („keine“ ist auch eine Wahl).
* `DELETE /api/v1/akten/art?sache=…`: zurück auf den Vorschlag.
* `POST   /api/v1/akten/arten/fristen`: Kündigungs- und Zahlungsfristen aus Akten mit privater Art als
  Aufgabenvorschläge anlegen (Anstoß für Prüfung und Messung; im Betrieb läuft es nach dem Abgleich der Bezüge).

Im Hintergrund läuft die Fristensuche im Faden der Bezüge (`akten_routes.nachlauf_anmelden`), höchstens alle
`ABSTAND_S` Sekunden und nur nach einer Änderung. Sie legt nur Vorschläge an, nie Aufgaben.
"""
from __future__ import annotations

import threading
import time
from dataclasses import asdict
from typing import Any, Literal

from fastapi import HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from .akten_arten import ArtAblage, fristen_vorlegen, stand
from .bezuege import zerlegen

#: Mindestabstand zweier Fristensuchen im Hintergrund (Sekunden).
ABSTAND_S = 600.0
_SPERRE = threading.Lock()


class ArtIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sache: str = Field(min_length=3, max_length=300)
    art: Literal['haushalt', 'familie', 'gesundheit', 'vertraege', 'keine']


def _organisation(sache: str) -> str:
    teile = zerlegen(sache)
    if teile is None or teile[0] != 'organisation':
        raise HTTPException(status_code=422, detail='Eine private Art haben nur Akten von Organisationen.')
    return sache


def fristen_suchen(app) -> dict[str, Any]:
    """Ein Lauf der Fristensuche; läuft schon einer, sagt die Antwort das, statt zu warten."""
    if not _SPERRE.acquire(blocking=False):
        return {'laeuft': True}
    try:
        from .akten_routes import bausteine
        bezuege, _ = bausteine(app)
        lauf = fristen_vorlegen(bezuege, app.state.proposals)
        app.state.privat_fristen_letzter = (time.monotonic(), bezuege.aenderungsstand())
        return {'laeuft': False, **asdict(lauf)}
    finally:
        _SPERRE.release()


def _faellig(app) -> bool:
    letzter = getattr(app.state, 'privat_fristen_letzter', None)
    if letzter is not None and time.monotonic() - letzter[0] < ABSTAND_S:
        return False
    from .akten_routes import bausteine
    return letzter is None or letzter[1] != bausteine(app)[0].aenderungsstand()


def register(app, guard) -> None:
    from .akten_routes import bausteine, nachfuehren, nachlauf_anmelden

    # Wie der Lint: der erste Lauf im Hintergrund frühestens nach dem Mindestabstand.
    app.state.privat_fristen_letzter = (time.monotonic(), None)
    nachlauf_anmelden(app, lambda: _faellig(app), lambda: fristen_suchen(app))

    @app.get('/api/v1/akten/art', dependencies=guard)
    def akten_art(sache: str = Query(..., min_length=3, max_length=300)) -> dict[str, Any]:
        """Die Karte „Art der Akte“: was gilt, was Kingfisher vorschlägt und warum."""
        nachfuehren(app)
        bezuege, _ = bausteine(app)
        return stand(bezuege, _organisation(sache))

    @app.put('/api/v1/akten/art', dependencies=guard)
    def akten_art_bestaetigen(body: ArtIn) -> dict[str, Any]:
        """Legt die Art fest. Erst dieser Klick macht aus dem Vorschlag einen Fakt."""
        bezuege, _ = bausteine(app)
        sache = _organisation(body.sache)
        vorschlag = stand(bezuege, sache)['vorschlag']['art'] or ''
        ArtAblage(bezuege.episodes).bestaetigen(sache, body.art, vorschlag)
        return stand(bezuege, sache)

    @app.delete('/api/v1/akten/art', dependencies=guard)
    def akten_art_zuruecknehmen(sache: str = Query(..., min_length=3, max_length=300)) -> dict[str, Any]:
        bezuege, _ = bausteine(app)
        if not ArtAblage(bezuege.episodes).zuruecknehmen(_organisation(sache)):
            raise HTTPException(status_code=404, detail='Für diese Akte ist keine Art bestätigt.')
        return stand(bezuege, sache)

    @app.post('/api/v1/akten/arten/fristen', dependencies=guard)
    def akten_arten_fristen() -> dict[str, Any]:
        """Fristen aus privaten Akten als Aufgabenvorschläge anlegen; nie eine Aufgabe selbst."""
        nachfuehren(app, warten=True)
        return fristen_suchen(app)


__all__ = ['fristen_suchen', 'register']
