"""Verdrahtung von Geburtstagen und Wiederkehrendem (`wiederkehrendes.py`).

* `GET  /api/v1/wiederkehrendes?sache=…`: offene Vorschläge und angenommene Aussagen (Geburtstag, Wiederkehrendes)
  einer Akte, für die Karte in der Akte. Liest nur.
* `GET  /api/v1/geburtstag?sache=person:…`: der angenommene Geburtstag einer Person mit „steht an“-Satz, sonst `null`.
* `POST /api/v1/wiederkehrendes/vorschlagen`: Anstoß (Prüfung und Messung); legt nur Wissenskandidaten an. Im Betrieb
  läuft dieselbe Suche im Faden der Bezüge (`akten_routes.nachlauf_anmelden`), höchstens alle `ABSTAND_S` Sekunden
  und nur nach einer Änderung.

Angenommen oder abgelehnt wird über den vorhandenen Weg des Gedächtnisses (`/api/v1/memory/candidates/{id}/accept`
und `/reject`); erst die Annahme legt eine Aussage an.
"""
from __future__ import annotations

import threading
import time
from dataclasses import asdict
from typing import Any

from fastapi import HTTPException, Query

from . import identitaet
from .bezuege import zerlegen
from .wiederkehrendes import Lauf, geburtstage_vorlegen, stand, wiederkehrendes_vorlegen

ABSTAND_S = 600.0
_SPERRE = threading.Lock()


def suchen(app) -> dict[str, Any]:
    """Ein Lauf: Geburtstage im inneren Kreis, Wiederkehrendes aus privaten Akten und Serien im Kalender."""
    if not _SPERRE.acquire(blocking=False):
        return {'laeuft': True}
    try:
        from .akten_routes import bausteine
        bezuege, _ = bausteine(app)
        lauf = Lauf()
        geburtstage_vorlegen(bezuege, app.state.knowledge_service, app.state.proposals, app.state.claims,
                             identitaet.eigene_adressen(getattr(app.state, 'settings', None)), lauf=lauf)
        wiederkehrendes_vorlegen(bezuege, app.state.knowledge_service, app.state.proposals, lauf=lauf)
        app.state.wiederkehrendes_letzter = (time.monotonic(), bezuege.aenderungsstand())
        return {'laeuft': False, **asdict(lauf)}
    finally:
        _SPERRE.release()


def _faellig(app) -> bool:
    letzter = getattr(app.state, 'wiederkehrendes_letzter', None)
    if letzter is not None and time.monotonic() - letzter[0] < ABSTAND_S:
        return False
    from .akten_routes import bausteine
    return letzter is None or letzter[1] != bausteine(app)[0].aenderungsstand()


def register(app, guard) -> None:
    from .akten_routes import nachfuehren, nachlauf_anmelden

    app.state.wiederkehrendes_letzter = (time.monotonic(), None)
    nachlauf_anmelden(app, lambda: _faellig(app), lambda: suchen(app))

    @app.get('/api/v1/wiederkehrendes', dependencies=guard)
    def wiederkehrendes_stand(sache: str = Query(..., min_length=3, max_length=300)) -> dict[str, Any]:
        """Was die Karte „Geburtstag und Wiederkehrendes“ einer Akte zeigt. Schreibt nichts."""
        if zerlegen(sache) is None:
            raise HTTPException(status_code=422, detail='Unbekannte Akte.')
        return stand(sache, app.state.proposals, app.state.claims)

    @app.get('/api/v1/geburtstag', dependencies=guard)
    def geburtstag_einer_person(sache: str = Query(..., min_length=3, max_length=300)) -> dict[str, Any]:
        """Der bestätigte Geburtstag einer Person als „steht an“ für die Akte (Fremdprobe 2, Befund 20); ohne
        angenommene Aussage `null`. Schreibt nichts."""
        from datetime import datetime
        from .model import user_timezone
        from .wiederkehrendes import anstehend_text, bestaetigter_geburtstag
        teile = zerlegen(sache)
        if teile is None or teile[0] != 'person':
            raise HTTPException(status_code=422, detail='Einen Geburtstag haben nur Personen.')
        gefunden = bestaetigter_geburtstag(app.state.claims, sache)
        if gefunden is None:
            return {'geburtstag': None}
        heute = datetime.now(user_timezone()).date()
        return {'geburtstag': {**gefunden, 'text': anstehend_text(gefunden['wert'], heute)}}

    @app.post('/api/v1/wiederkehrendes/vorschlagen', dependencies=guard)
    def wiederkehrendes_vorschlagen() -> dict[str, Any]:
        """Geburtstage und Wiederkehrendes als Wissenskandidaten vorlegen; nie eine Aussage selbst."""
        nachfuehren(app, warten=True)
        return suchen(app)


__all__ = ['register', 'suchen']
