"""Verdrahtung der Mitteilungen auf dem Mac (Regeln in `mitteilungen.py`).

* `GET  /api/v1/mitteilungen/faellig`: höchstens drei kleine Mitteilungen (`id`, `art`, `titel`, `satz`, `pfad`); leer,
  solange der Schalter aus ist. Die Mac-App fragt alle fünf Minuten.
* `POST /api/v1/mitteilungen/{kennung}/zugestellt`: die App hat sie gezeigt (Logbuch `mitteilung`).
* `POST /api/v1/mitteilungen/{kennung}/rueckmeldung` `{ueberfluessig: bool}`: „War überflüssig“ (Logbuch
  `mitteilung_ueberfluessig`). Unbekannte Kennungen: 404.
* `GET  /api/v1/mitteilungen/woche`: `{gesendet, ueberfluessig}` der letzten sieben Tage.
* `GET/PUT /api/v1/mitteilungen/einstellung`: `an` (Vorgabe aus) und `morgens` (`HH:MM`, Vorgabe 07:30), dazu die
  Erlaubnis des Systems und die Wochenzahl.
* `POST /api/v1/mitteilungen/erlaubnis` `{status}`: die App meldet, ob der Mac Mitteilungen erlaubt hat.

Alle Routen stehen hinter demselben Guard wie der Rest. Die Quellen sind die des Tagesbriefings (`tag_routes.py`),
die Fristen (`fristlage.py`) und die Wegezeit nur lesend (`wegezeit.py`).
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from . import config, fristlage, identitaet
from .mitteilungen import MAX_ID, Dienst, Einstellung, uhrzeit_gueltig
from .model import user_timezone

UHRZEIT_SATZ = 'Bitte eine Uhrzeit wie 07:30, vor 21:00 Uhr.'


class EinstellungIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    an: bool | None = None
    morgens: str | None = Field(default=None, max_length=5)


class RueckmeldungIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ueberfluessig: bool


class ErlaubnisIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['unbekannt', 'erlaubt', 'abgelehnt']


def _jetzt() -> datetime:
    zone = user_timezone()
    return datetime.now(zone) if zone else datetime.now().astimezone()


def dienst(app) -> Dienst:
    """Der Dienst dieser App: einmal gebaut; liest die Einstellung bei jedem Abruf neu."""
    vorhanden = getattr(app.state, 'mitteilungen_dienst', None)
    if vorhanden is not None:
        return vorhanden
    data_dir = app.state.mitteilungen_data_dir

    def einstellung() -> Einstellung:
        return Einstellung.aus(getattr(getattr(app.state, 'settings', None), 'mitteilungen', None))

    def briefing() -> dict[str, Any] | None:
        from .tag_routes import briefing as tag_briefing
        return tag_briefing(app, buchen=False)

    def termine(jetzt: datetime) -> list[dict[str, Any]]:
        from .tag_routes import termine as tag_termine
        return tag_termine(app, jetzt)

    def fristen(jetzt: datetime) -> list[fristlage.Frist]:
        from .akten_routes import bausteine, nachfuehren
        nachfuehren(app)
        bezuege, akten = bausteine(app)
        eigene = identitaet.eigene_adressen(getattr(app.state, 'settings', None))
        return fristlage.sammeln(akten, bezuege, jetzt=jetzt, eigene=eigene)

    def wegezeit(ort: str, beginn: datetime) -> dict[str, Any] | None:
        from .wegezeit_routes import dienst as wegezeit_dienst
        return wegezeit_dienst(app).auskunft(ort, beginn=beginn, nur_lesen=True).to_dict()

    neu = Dienst(data_dir() / 'mitteilungen.sqlite3', einstellung=einstellung, briefing=briefing, termine=termine,
                 fristen=fristen, wegezeit=wegezeit, uhr=_jetzt)
    app.state.mitteilungen_dienst = neu
    return neu


def register(app, guard, data_dir) -> None:
    app.state.mitteilungen_data_dir = data_dir

    def stand() -> dict[str, Any]:
        d = dienst(app)
        return {**Einstellung.aus(app.state.settings.mitteilungen).to_dict(), 'erlaubnis': d.erlaubnis(), 'woche': d.woche()}

    def kennung_pruefen(kennung: str) -> str:
        if not kennung or len(kennung) > MAX_ID:
            raise HTTPException(404, 'Diese Mitteilung kenne ich nicht.')
        return kennung

    @app.get('/api/v1/mitteilungen/faellig', dependencies=guard)
    def faellig() -> dict[str, Any]:
        return {'mitteilungen': dienst(app).faellig()}

    @app.post('/api/v1/mitteilungen/{kennung}/zugestellt', dependencies=guard)
    def zugestellt(kennung: str) -> dict[str, Any]:
        if not dienst(app).zugestellt(kennung_pruefen(kennung)):
            raise HTTPException(404, 'Diese Mitteilung kenne ich nicht.')
        return {'ok': True}

    @app.post('/api/v1/mitteilungen/{kennung}/rueckmeldung', dependencies=guard)
    def rueckmeldung(kennung: str, body: RueckmeldungIn) -> dict[str, Any]:
        if not dienst(app).rueckmeldung(kennung_pruefen(kennung), ueberfluessig=body.ueberfluessig):
            raise HTTPException(404, 'Diese Mitteilung kenne ich nicht.')
        return {'ok': True}

    @app.get('/api/v1/mitteilungen/woche', dependencies=guard)
    def woche() -> dict[str, int]:
        return dienst(app).woche()

    @app.get('/api/v1/mitteilungen/einstellung', dependencies=guard)
    def einstellung() -> dict[str, Any]:
        return stand()

    @app.put('/api/v1/mitteilungen/einstellung', dependencies=guard)
    def einstellung_setzen(body: EinstellungIn) -> dict[str, Any]:
        if body.morgens is not None and not uhrzeit_gueltig(body.morgens):
            raise HTTPException(422, UHRZEIT_SATZ)
        with app.state.conversation_lock:
            neu = Einstellung.aus(app.state.settings.mitteilungen).to_dict()
            if body.an is not None:
                neu['an'] = body.an
            if body.morgens is not None:
                neu['morgens'] = body.morgens
            vorher = app.state.settings.mitteilungen
            app.state.settings.mitteilungen = deepcopy(Einstellung.aus(neu).to_dict())
            try:
                config.save(data_dir(), app.state.settings)
            except Exception:
                app.state.settings.mitteilungen = vorher
                raise
        return stand()

    @app.post('/api/v1/mitteilungen/erlaubnis', dependencies=guard)
    def erlaubnis(body: ErlaubnisIn) -> dict[str, Any]:
        dienst(app).erlaubnis_setzen(body.status)
        return stand()


__all__ = ['dienst', 'register']
