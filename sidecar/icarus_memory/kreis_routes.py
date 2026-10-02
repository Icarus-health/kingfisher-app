"""Verdrahtung des Kreises je Person (`kreis.py`): Karte in der Akte, Bestätigung, Übersicht.

* `GET    /api/v1/kreis?sache=person:a:…`: bestätigter Kreis, Vorschlag mit Begründung, die drei Wahlen.
* `PUT    /api/v1/kreis` `{sache, kreis}`: der Klick eines Menschen legt den Kreis fest.
* `DELETE /api/v1/kreis?sache=…`: zurück auf „noch offen“ (der Vorschlag wirkt dann wieder nicht).
* `GET    /api/v1/kreis/uebersicht`: wie viele Personen bestätigt, wie viele Vorschläge offen, welche.
* `POST   /api/v1/kreis/sammel` `{kreis: "kollegen", anzahl}`: alle offenen Vorschläge „Kollegen“ mit einem Klick
  bestätigen, nachdem der Mensch die Rückfrage in einem Satz beantwortet hat („21 Personen als Kollegen festlegen?“).
  Nie für den inneren Kreis. Stimmt `anzahl` nicht mehr, wird nichts gespeichert (409).
* `DELETE /api/v1/kreis/sammel?sammlung=…`: die Liste zurücknehmen; die Personen sind wieder offen.

Ohne Bestätigung schreibt keine dieser Routen etwas. Die Sachen-ID steht nie im Pfad (`akten_routes.py`).
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from . import identitaet
from .bezuege import zerlegen
from .kreis import Kreise, SammelVeraltet


class KreisIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sache: str = Field(min_length=3, max_length=300)
    kreis: Literal['innerer_kreis', 'kollegen', 'kontakte']


class SammelIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kreis: Literal['innerer_kreis', 'kollegen', 'kontakte']
    anzahl: int = Field(ge=0, le=100_000)


def kreise(app) -> Kreise:
    """Die Kreise dieser App, an die aktuellen Bezüge und die eigenen Adressen gebunden."""
    from .akten_routes import bausteine
    bezuege, _ = bausteine(app)
    return Kreise(bezuege, identitaet.eigene_adressen(getattr(app.state, 'settings', None)))


def _person(sache: str) -> str:
    teile = zerlegen(sache)
    if teile is None or teile[0] != 'person':
        raise HTTPException(status_code=422, detail='Einen Kreis haben nur Personen.')
    return sache


def register(app, guard) -> None:
    from .akten_routes import nachfuehren

    @app.get('/api/v1/kreis', dependencies=guard)
    def kreis_stand(sache: str = Query(..., min_length=3, max_length=300)) -> dict[str, Any]:
        """Die Karte „Kreis“ einer Person: was gilt, was Kingfisher vorschlägt und warum."""
        nachfuehren(app)
        return kreise(app).stand(_person(sache))

    @app.put('/api/v1/kreis', dependencies=guard)
    def kreis_bestaetigen(body: KreisIn) -> dict[str, Any]:
        """Legt den Kreis fest. Erst dieser Klick macht aus dem Vorschlag einen Fakt."""
        try:
            return kreise(app).bestaetigen(_person(body.sache), body.kreis)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.delete('/api/v1/kreis', dependencies=guard)
    def kreis_zuruecknehmen(sache: str = Query(..., min_length=3, max_length=300)) -> dict[str, Any]:
        """Nimmt die Bestätigung zurück; danach ist der Kreis wieder offen."""
        kreis = kreise(app)
        if not kreis.zuruecknehmen(_person(sache)):
            raise HTTPException(status_code=404, detail='Für diese Person ist kein Kreis bestätigt.')
        return kreis.stand(sache)

    @app.get('/api/v1/kreis/uebersicht', dependencies=guard)
    def kreis_uebersicht(liste: int = Query(20, ge=0, le=200)) -> dict[str, Any]:
        """Für „Kingfisher und du“: bestätigt, offen, welche offen sind.

        Läuft der Abgleich der Bezüge noch im Hintergrund, ist die Zählung vorläufig; `zaehlt_noch` sagt das, damit
        die Oberfläche nicht eine zu kleine Zahl als Stand ausgibt, sondern gleich noch einmal fragt.
        """
        stand = nachfuehren(app)
        uebersicht = kreise(app).uebersicht(liste=liste)
        uebersicht['zaehlt_noch'] = bool(stand.get('offen'))
        return uebersicht

    @app.post('/api/v1/kreis/sammel', dependencies=guard)
    def kreis_sammel(body: SammelIn) -> dict[str, Any]:
        """Alle offenen Vorschläge „Kollegen“ auf einmal; nie der innere Kreis. Antwort mit einem Satz."""
        nachfuehren(app, warten=True)
        try:
            ergebnis = kreise(app).sammel_bestaetigen(body.kreis, body.anzahl)
        except SammelVeraltet as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        n = ergebnis['anzahl']
        satz = ('Es gab keinen offenen Vorschlag.' if n == 0 else 'Eine Person als Kollegen festgelegt.' if n == 1
                else f'{n} Personen als Kollegen festgelegt.')
        return {**ergebnis, 'satz': satz}

    @app.delete('/api/v1/kreis/sammel', dependencies=guard)
    def kreis_sammel_zurueck(sammlung: float = Query(...)) -> dict[str, Any]:
        """Nimmt eine Sammelbestätigung zurück; wer seitdem einzeln geändert wurde, bleibt, wie er ist."""
        n = kreise(app).sammlung_zuruecknehmen(sammlung)
        if not n:
            raise HTTPException(status_code=404, detail='Diese Liste gibt es nicht mehr.')
        return {'anzahl': n, 'satz': 'Zurückgenommen: ' + ('eine Person ist' if n == 1 else f'{n} Personen sind')
                + ' wieder offen.'}


__all__ = ['kreise', 'register']
