"""Verdrahtung des Wetters: Einstellung „Wetter im Briefing“, Ortssuche.

Die Regeln stehen in `wetter.py`. Hier steht nur, wie der Server sie mit den Einstellungen verbindet.

* `GET /api/v1/wetter/einstellungen`: an oder aus, der gewählte Ort, und ein Vorschlag für den Ort aus dem
  Startort der Fahrzeiten (nur der Ortsname; gefragt wird der Dienst erst, wenn der Nutzer den Vorschlag anklickt).
* `PUT /api/v1/wetter/einstellungen`: ein- und ausschalten, Ort wählen. Ohne Ort lässt sich das Wetter nicht
  einschalten. Koordinaten tippt niemand: Der Ort kommt aus einem Treffer der Suche.
* `GET /api/v1/wetter/orte?suche=…`: Orte zu einem Namen (Open-Meteo-Geocoding). Es geht nur der Name hinaus. Antwortet
  der Ortsdienst nicht (erwartbar, etwa ohne Netz), ist das kein Fehler des Sidecars: 200 mit leerer Liste, `grund` und
  einem Satz (`satz`), damit die Browserkonsole nicht rot wird (Fremdprobe, Befund 32).
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from . import config
from .wegezeit import Einstellung as WegEinstellung
from .wetter import Einstellung, WetterDienst, WetterFehler, ortsname


class OrtIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=80)
    ort: str = Field(default='', max_length=160)
    breite: float = Field(ge=-90, le=90)
    laenge: float = Field(ge=-180, le=180)


class EinstellungIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    aktiv: bool | None = None
    ort: OrtIn | None = None


def dienst(app) -> WetterDienst:
    """Der Wetterdienst dieser App: einmal gebaut, liest die Einstellung bei jeder Auskunft neu."""
    vorhanden = getattr(app.state, 'wetter_dienst', None)
    if vorhanden is None:
        vorhanden = WetterDienst(lambda: Einstellung.aus(getattr(getattr(app.state, 'settings', None), 'wetter', None)))
        app.state.wetter_dienst = vorhanden
    return vorhanden


def register(app, guard, data_dir) -> None:
    def stand() -> dict[str, Any]:
        einst = Einstellung.aus(app.state.settings.wetter)
        heimat = WegEinstellung.aus(app.state.settings.wegezeit).heimat
        vorschlag = ortsname(heimat) if not einst.name else ''
        return {'aktiv': einst.aktiv, 'ort': einst.ort, 'name': einst.name, 'vorschlag': vorschlag,
                'aus_umgebung': not app.state.settings.wetter and einst.aktiv}

    @app.get('/api/v1/wetter/einstellungen', dependencies=guard)
    def einstellungen() -> dict[str, Any]:
        return stand()

    @app.put('/api/v1/wetter/einstellungen', dependencies=guard)
    def einstellungen_setzen(body: EinstellungIn) -> dict[str, Any]:
        with app.state.conversation_lock:
            neu = Einstellung.aus(app.state.settings.wetter).to_dict()
            if body.ort is not None:
                neu.update({'ort': body.ort.ort or body.ort.name, 'name': body.ort.name.strip(),
                            'breite': round(body.ort.breite, 4), 'laenge': round(body.ort.laenge, 4)})
            if body.aktiv is not None:
                neu['aktiv'] = body.aktiv
            if neu['aktiv'] and not (neu['name'] and neu['breite'] is not None and neu['laenge'] is not None):
                raise HTTPException(422, 'Bitte zuerst einen Ort wählen.')
            vorher = app.state.settings.wetter
            app.state.settings.wetter = deepcopy(Einstellung.aus({**neu, 'aktiv': neu['aktiv'] is True}).to_dict())
            try:
                config.save(data_dir(), app.state.settings)
            except Exception:
                app.state.settings.wetter = vorher
                raise
            app.state.tag_wetter = None  # die Zeile im Briefing soll sofort den neuen Stand zeigen
        return stand()

    @app.get('/api/v1/wetter/orte', dependencies=guard)
    def orte(suche: str = Query('', max_length=80)) -> dict[str, Any]:
        try:
            return {'orte': dienst(app).suche(suche)}
        except WetterFehler:
            return {'orte': [], 'grund': 'ortsdienst_stumm',
                    'satz': 'Der Ortsdienst antwortet gerade nicht. Bitte später erneut versuchen.'}
