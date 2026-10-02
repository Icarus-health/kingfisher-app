"""Verdrahtung der Wegezeit: Einstellung „Fahrzeiten berechnen“, Schlüssel, Mac-Helfer.

Die Regeln stehen in `wegezeit.py`. Hier steht nur, wie der Server sie mit Einstellungen,
Schlüsselbund und dem Mac-Arbeiter verbindet.

* `GET/PUT /api/v1/wegezeit/einstellungen`: Einwilligung, Heimatadresse, Verkehrsmittel, Dienst.
  Die Vorgabe ist **aus**; nur `aktiv: true` erlaubt, Adressen an einen Kartendienst zu schicken.
* `PUT/DELETE /api/v1/wegezeit/schluessel`: Schlüssel eines Kartendienstes im Schlüsselbund. Er kommt
  nie über die Schnittstelle zurück, nur „hinterlegt“ ja oder nein.
* `GET /api/v1/wegezeit/mac/anfragen`, `POST /api/v1/wegezeit/mac/antworten`: der Mac-Arbeiter
  (`scripts/mac_maps_worker.py`) holt offene Fragen ab und liefert Fahrzeiten aus Apple Karten.
"""
from __future__ import annotations

import os
from copy import deepcopy
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from . import config
from .wegezeit import (Briefkasten, Einstellung, GoogleRoutes, MacKarten, OpenRouteService, WegezeitDienst,
                       VERKEHRSMITTEL)

FEHLT_SATZ = {
    'startort': 'Für die Wegezeit fehlt noch dein Startort.',
    'dienst': 'Auf diesem Rechner gibt es keine Apple Karten. Ohne einen eigenen Kartendienst kann Kingfisher keine '
              'Wegezeit berechnen; den richtet ein Techniker einmal ein.',
}
"""Was fehlt, in einem Satz; so steht es auch auf der Karte."""

SCHLUESSEL = {'openrouteservice': 'ICARUS_ORS_KEY', 'google': 'ICARUS_GOOGLE_ROUTES_KEY'}
"""Dienst -> Name im Schlüsselbund (`secrets.KNOWN`)."""


class EinstellungIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    aktiv: bool | None = None
    heimat: str | None = Field(default=None, max_length=300)
    verkehrsmittel: Literal['auto', 'oepnv', 'fuss'] | None = None
    dienst: Literal['automatisch', 'apple', 'openrouteservice', 'google'] | None = None
    puffer_min: int | None = Field(default=None, ge=0, le=120)


class SchluesselIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    dienst: Literal['openrouteservice', 'google']
    schluessel: str = Field(min_length=8, max_length=300)


class AntwortIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=64)
    minuten: int | None = Field(default=None, ge=1, le=24 * 60)
    fehler: str = Field(default='', max_length=200)


def dienst(app) -> WegezeitDienst:
    """Der Fahrzeitdienst dieser App: einmal gebaut, liest die Einstellung bei jeder Auskunft neu."""
    vorhanden = getattr(app.state, 'wegezeit', None)
    if vorhanden is not None:
        return vorhanden
    app.state.wegezeit_briefkasten = Briefkasten()

    def schluessel(name: str):
        return lambda: os.environ.get(name) or None

    anbieter = {'apple': MacKarten(app.state.wegezeit_briefkasten),
                'openrouteservice': OpenRouteService(schluessel(SCHLUESSEL['openrouteservice'])),
                'google': GoogleRoutes(schluessel(SCHLUESSEL['google']))}
    app.state.wegezeit = WegezeitDienst(
        anbieter, einstellung=lambda: Einstellung.aus(getattr(getattr(app.state, 'settings', None), 'wegezeit', None)))
    return app.state.wegezeit


def register(app, guard, data_dir) -> None:
    def speichern(neu: dict[str, Any]) -> None:
        vorher = app.state.settings.wegezeit
        app.state.settings.wegezeit = neu
        try:
            config.save(data_dir(), app.state.settings)
        except Exception:
            app.state.settings.wegezeit = vorher
            raise

    def was_fehlt(einstellung: Einstellung) -> str | None:
        """Was zum Rechnen fehlt: `startort`, `dienst` oder nichts (Fremdprobe, Befund 19).

        Apple Karten zählt, sobald sich der Mac-Arbeiter gemeldet hat, auch vor der Einwilligung; ein eigener
        Kartendienst, sobald sein Schlüssel hinterlegt ist. Ohne beides kann das Einschalten nichts berechnen.
        """
        if not einstellung.heimat:
            return 'startort'
        anbieter_je_name = dienst(app)._anbieter  # legt auch den Briefkasten an
        briefkasten = app.state.wegezeit_briefkasten
        moeglich = {name for name, anbieter in anbieter_je_name.items() if anbieter.verfuegbar()}
        if briefkasten.angeklopft() or briefkasten.online():
            moeglich.add('apple')
        gewollt = {einstellung.dienst} if einstellung.dienst in ('apple', 'openrouteservice', 'google') else None
        return None if (moeglich & gewollt if gewollt else moeglich) else 'dienst'

    def stand() -> dict[str, Any]:
        gesetzt = {name: bool(os.environ.get(var)) for name, var in SCHLUESSEL.items()}
        fehlt = was_fehlt(Einstellung.aus(app.state.settings.wegezeit))
        return {**dienst(app).stand(), 'schluessel_hinterlegt': gesetzt,
                'verkehrsmittel_moeglich': list(VERKEHRSMITTEL),
                'kann_rechnen': fehlt is None, 'fehlt': fehlt, 'fehlt_satz': FEHLT_SATZ.get(fehlt or '', '')}

    @app.get('/api/v1/wegezeit/einstellungen', dependencies=guard)
    def einstellungen() -> dict[str, Any]:
        return stand()

    @app.put('/api/v1/wegezeit/einstellungen', dependencies=guard)
    def einstellungen_setzen(body: EinstellungIn) -> dict[str, Any]:
        with app.state.conversation_lock:
            neu = Einstellung.aus(app.state.settings.wegezeit).to_dict()
            neu.update({k: v.strip() if isinstance(v, str) else v for k, v in body.model_dump().items()
                        if v is not None})
            # Einschalten nur, wenn es auch rechnen kann; sonst hieße „An“ nur, dass nichts kommt (Befund 19).
            fehlt = was_fehlt(Einstellung.aus(neu)) if body.aktiv is True else None
            if fehlt is not None:
                raise HTTPException(409, FEHLT_SATZ[fehlt])
            speichern(deepcopy(Einstellung.aus(neu).to_dict()))
        return stand()

    @app.put('/api/v1/wegezeit/schluessel', dependencies=guard)
    def schluessel_setzen(body: SchluesselIn) -> dict[str, Any]:
        keychain = getattr(app.state, 'keychain', None)
        if keychain is None:
            raise HTTPException(503, 'Der Schlüsselspeicher ist nicht bereit.')
        config.store_secret(keychain, SCHLUESSEL[body.dienst], body.schluessel.strip())
        return stand()

    @app.delete('/api/v1/wegezeit/schluessel', dependencies=guard)
    def schluessel_loeschen(dienst_name: Literal['openrouteservice', 'google'] = 'openrouteservice') -> dict[str, Any]:
        keychain = getattr(app.state, 'keychain', None)
        if keychain is not None:
            config.clear_secret(keychain, SCHLUESSEL[dienst_name])
        return stand()

    @app.get('/api/v1/wegezeit/mac/anfragen', dependencies=guard)
    def mac_anfragen() -> dict[str, Any]:
        """Für den Mac-Arbeiter: offene Fragen. Nur bei Einwilligung; sonst gibt es nichts zu berechnen."""
        dienst(app)
        app.state.wegezeit_briefkasten.klopfen()  # Apple Karten ist da; zählt erst mit Einwilligung als online
        if not Einstellung.aus(app.state.settings.wegezeit).aktiv:
            return {'anfragen': [], 'aktiv': False}
        return {'anfragen': app.state.wegezeit_briefkasten.offene(), 'aktiv': True}

    @app.post('/api/v1/wegezeit/mac/antworten', dependencies=guard)
    def mac_antworten(body: AntwortIn) -> dict[str, bool]:
        dienst(app)
        if not Einstellung.aus(app.state.settings.wegezeit).aktiv:
            return {'angenommen': False}   # ohne Einwilligung gibt es nichts zu beantworten
        return {'angenommen': app.state.wegezeit_briefkasten.beantworten(body.id, minuten=body.minuten,
                                                                         fehler=body.fehler)}
