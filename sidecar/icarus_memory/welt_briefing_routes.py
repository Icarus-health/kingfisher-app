"""Verdrahtung der Weltmeldung im Briefing: Einstellungen, Feeds, Abbestellen.

Die Regeln stehen in `welt_meldungen.py` (Auswahl) und `welt_feeds.py` (Feeds lesen). Hier steht nur, wie der
Server sie mit Einstellungen, Bestand und Modellrolle verbindet.

* `GET  /api/v1/welt/briefing`: Schalter, Feeds mit Zustand, wählbare Quellen, Abbestelltes, Vorgaben zum Anklicken.
* `PUT  /api/v1/welt/briefing`: „Meldung aus der Welt im Briefing“ ein oder aus; gewählte öffentliche Quellen.
* `POST /api/v1/welt/feeds`: einen RSS- oder Atom-Feed hinzufügen (wird einmal gelesen und geprüft).
* `DELETE /api/v1/welt/feeds/{id}`, `POST /api/v1/welt/feeds/{id}/schalter`: entfernen, aus- und einschalten.
* `POST /api/v1/welt/abbestellen`: eine Quelle oder eine Sache abbestellen (ein Klick, sofort wirksam).
* `POST /api/v1/welt/zulassen`: eine abbestellte Sache wieder zulassen.

Das Modell der Rolle `hintergrund` darf einen Treffer nur ablehnen, und nur wenn es lokal ist und die
Modellprüfung im Zeitplan freigegeben wurde (dieselbe Freigabe wie für die Einordnung).
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from . import config
from .akten_routes import bausteine
from .welt_feeds import FeedFehler
from .welt_meldungen import WeltDienst
from .welt_vorgaben import ABGERUFEN, STAND, mit_zustand


class BriefingIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    aktiv: bool | None = None
    weltquellen: list[str] | None = Field(default=None, max_length=50)


class FeedIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    url: str = Field(min_length=8, max_length=2000)
    label: str = Field(default='', max_length=80)


class SchalterIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    an: bool


class AbbestellenIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    quelle_id: str | None = Field(default=None, max_length=64)
    sache: str | None = Field(default=None, max_length=300)


class ZulassenIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sache: str = Field(min_length=1, max_length=300)


def dienst(app, data_dir=None) -> WeltDienst:
    """Der Weltdienst dieser App, an den aktuellen Speicher gebunden (wie `akten_routes.bausteine`)."""
    vorhanden = getattr(app.state, 'welt_dienst', None)
    if vorhanden is not None and vorhanden[0] is app.state.episodes:
        return vorhanden[1]

    def speichern(daten: dict[str, Any]) -> None:
        vorher = app.state.settings.welt
        app.state.settings.welt = daten
        try:
            config.save(app.state.welt_datenordner(), app.state.settings)
        except Exception:
            app.state.settings.welt = vorher
            raise

    def anbieter():
        """Nur ein lokales Modell, nur mit der Freigabe der Modellprüfung im Zeitplan."""
        plan = app.state.settings.schedule
        if not (plan.enabled and plan.with_model):
            return None
        from .model_roles import rollen_von
        return rollen_von(app).provider('hintergrund')

    neu = WeltDienst(lesen=lambda: app.state.settings.welt, speichern=speichern,
                     bezuege=lambda: bausteine(app)[0], episodes=lambda: app.state.episodes,
                     weltquellen=lambda: list(app.state.settings.world_sources), anbieter=anbieter)
    app.state.welt_dienst = (app.state.episodes, neu)
    return neu


def register(app, guard, data_dir) -> None:
    app.state.welt_datenordner = data_dir

    def stand() -> dict[str, Any]:
        d = dienst(app)
        welt = d.welt()
        fehler = d.feedstand()
        namen: dict[str, str] = {}
        if welt.abbestellt_sachen:
            try:
                namen = bausteine(app)[0].beschriftungen(welt.abbestellt_sachen)
            except Exception:  # noqa: BLE001 - ein gelöschter Bestand ändert nichts an der Liste
                namen = {}
        return {
            'aktiv': welt.aktiv,
            'feeds': [{**f, 'fehler': fehler.get(f['id'], '')} for f in welt.feeds],
            'weltquellen': [{'id': q.get('id'), 'label': q.get('label') or q.get('url'),
                             'gewaehlt': q.get('id') in welt.weltquellen}
                            for q in app.state.settings.world_sources if q.get('enabled', True)],
            'abbestellt': [{'sache': s, 'name': namen.get(s) or s.split(':', 1)[-1]} for s in welt.abbestellt_sachen],
            # Alle Vorgaben, je mit `gewaehlt` und `feed_id`: ein Klick fügt hinzu, der zweite entfernt (welt_vorgaben.py).
            'vorschlaege': mit_zustand(welt.feeds),
            'vorschlaege_stand': {'stand': STAND, 'abgerufen': ABGERUFEN},
            'modell': bool(app.state.settings.schedule.enabled and app.state.settings.schedule.with_model),
        }

    @app.get('/api/v1/welt/briefing', dependencies=guard)
    def welt_stand() -> dict[str, Any]:
        return stand()

    @app.put('/api/v1/welt/briefing', dependencies=guard)
    def welt_setzen(body: BriefingIn) -> dict[str, Any]:
        d = dienst(app)
        if body.weltquellen is not None:
            d.weltquellen_waehlen(body.weltquellen)
        if body.aktiv is not None:
            d.einschalten(body.aktiv)
        return stand()

    @app.post('/api/v1/welt/feeds', dependencies=guard, status_code=201)
    def feed_neu(body: FeedIn) -> dict[str, Any]:
        try:
            dienst(app).feed_hinzufuegen(body.url, body.label)
        except FeedFehler as fehler:
            raise HTTPException(422, str(fehler)) from None
        return stand()

    @app.delete('/api/v1/welt/feeds/{feed_id}', dependencies=guard)
    def feed_weg(feed_id: str) -> dict[str, Any]:
        if not dienst(app).feed_entfernen(feed_id):
            raise HTTPException(404, 'Feed nicht gefunden.')
        return stand()

    @app.post('/api/v1/welt/feeds/{feed_id}/schalter', dependencies=guard)
    def feed_schalter(feed_id: str, body: SchalterIn) -> dict[str, Any]:
        if not dienst(app).feed_einschalten(feed_id, body.an):
            raise HTTPException(404, 'Feed nicht gefunden.')
        return stand()

    @app.post('/api/v1/welt/abbestellen', dependencies=guard)
    def abbestellen(body: AbbestellenIn) -> dict[str, Any]:
        if bool(body.quelle_id) == bool(body.sache):
            raise HTTPException(422, 'Bitte genau eine Quelle oder eine Sache angeben.')
        d = dienst(app)
        ok = d.quelle_abbestellen(body.quelle_id) if body.quelle_id else d.sache_abbestellen(body.sache or '')
        if not ok:
            raise HTTPException(404, 'Nichts zu abbestellen gefunden.')
        return stand()

    @app.post('/api/v1/welt/zulassen', dependencies=guard)
    def zulassen(body: ZulassenIn) -> dict[str, Any]:
        if not dienst(app).sache_zulassen(body.sache):
            raise HTTPException(404, 'Diese Sache war nicht abbestellt.')
        return stand()


__all__ = ['dienst', 'register']
