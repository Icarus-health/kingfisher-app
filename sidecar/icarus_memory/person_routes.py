"""Wege zu „Alles zu einer Person“ (Persona-Prüfung, Paket P, D7): Auskunft, Löschen, Sperrvermerke.

* `GET  /api/v1/memory/people/{name}/auskunft` – ein ZIP (`Auskunft.html`, `Auskunft.json`) als Download. Es entsteht im
  Speicher und geht nur an den Browser auf diesem Rechner; Kingfisher legt keine Kopie ab und sendet nichts hinaus.
* `GET  /api/v1/memory/people/{name}/loeschen` – was gelöscht würde und was bleibt (Zahlen für die Rückfrage).
* `POST /api/v1/memory/people/{name}/loeschen` – löscht alles zu ihr und legt den Sperrvermerk an.
* `GET  /api/v1/personen/sperre` und `DELETE /api/v1/personen/sperre/{kennung}` – Sperrvermerke ansehen und aufheben.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Response

from . import person_daten, personen


def _fehler(fehler: Exception) -> HTTPException:
    if isinstance(fehler, personen.Mehrdeutig):
        wer = '; '.join(f'{p.name} <{p.adressen[0]}>' if p.adressen else p.name for p in fehler.kandidaten)
        return HTTPException(status_code=409,
                             detail=f'„{fehler.name}“ gehört mehreren Menschen: {wer}. Bitte die Adresse angeben.')
    if isinstance(fehler, person_daten.PersonNichtGefunden):
        return HTTPException(status_code=404, detail=str(fehler))
    raise fehler


def install_routes(app: FastAPI, guard: list[Any]) -> None:

    @app.get('/api/v1/memory/people/{name}/auskunft', dependencies=guard)
    def person_auskunft(name: str) -> Response:
        try:
            daten = person_daten.auskunft(app, name)
        except (personen.Mehrdeutig, person_daten.PersonNichtGefunden) as fehler:
            raise _fehler(fehler) from fehler
        datei = person_daten.dateiname(daten['person']['name'])
        return Response(person_daten.auskunft_zip(daten), media_type='application/zip', headers={
            'Content-Disposition': f"attachment; filename=\"Auskunft.zip\"; filename*=UTF-8''{quote(datei)}",
            'Cache-Control': 'no-store', 'X-Kingfisher-Datei': quote(datei)})

    @app.get('/api/v1/memory/people/{name}/loeschen', dependencies=guard)
    def person_loeschen_vorschau(name: str) -> dict[str, Any]:
        try:
            return person_daten.vorschau(app, name)
        except (personen.Mehrdeutig, person_daten.PersonNichtGefunden) as fehler:
            raise _fehler(fehler) from fehler

    @app.post('/api/v1/memory/people/{name}/loeschen', dependencies=guard)
    def person_loeschen(name: str) -> dict[str, Any]:
        sperre = getattr(app.state, 'conversation_lock', None)
        try:
            if sperre is not None:
                with sperre:
                    return person_daten.loeschen(app, name)
            return person_daten.loeschen(app, name)
        except (personen.Mehrdeutig, person_daten.PersonNichtGefunden) as fehler:
            raise _fehler(fehler) from fehler

    @app.get('/api/v1/personen/sperre', dependencies=guard)
    def sperren() -> dict[str, Any]:
        from .person_sperre import fuer
        return {'sperren': fuer(app.state.episodes).liste()}

    @app.delete('/api/v1/personen/sperre/{kennung}', dependencies=guard)
    def sperre_aufheben(kennung: str) -> dict[str, Any]:
        from .person_sperre import fuer
        eintrag = fuer(app.state.episodes).aufheben(kennung)
        if eintrag is None:
            raise HTTPException(status_code=404, detail='Diesen Vermerk gibt es nicht mehr.')
        return {'aufgehoben': eintrag}
