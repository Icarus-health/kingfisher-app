"""Verdrahtung von „In die Akte übernehmen“ (`uebernehmen.py`).

* `GET  /api/v1/antworten/uebernehmen?conversation_id=…&message_id=…`: die Rückfrage vor dem Vorschlagen. Die Sätze der
  Antwort mit Hinweisen und Vorgabe, die Akten, in die sie passen (die Sachen der Frage, sonst aus den Belegen), und
  was diese Antwort schon vorgeschlagen hat, mit dem Zustand der Vorschläge.
* `POST /api/v1/antworten/uebernehmen`: erzeugt je gewähltem Satz einen **Vorschlag**. Die Oberfläche schickt nur
  Gespräch, Nachricht, gewählte Satznummern, Ziel-Sache und Notiz; die Antwort, ihre Sätze und Belege liest der Server
  selbst aus der Gesprächsansicht und prüft sie erneut (wie beim Rückkanal, `rueckmeldung_routes.py`).

Nichts davon legt einen Claim an oder nimmt einen Vorschlag an: Die Annahme bleibt der vorhandenen Vorschlagskarte
(`/api/v1/memory/candidates/{id}/accept`) und damit dem Menschen. Nichts davon ist außenwirksam.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from . import uebernehmen
from .akten_routes import bausteine, nachfuehren
from .uebernehmen import UebernehmenFehler


class UebernehmenIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    conversation_id: str = Field(min_length=1, max_length=200)
    message_id: str = Field(min_length=1, max_length=200)
    saetze: list[int] = Field(min_length=1, max_length=20)
    sache: str | None = Field(default=None, max_length=300)
    notiz: str = Field(default='', max_length=1000)


def register(app, guard) -> None:
    def antwort(gespraech_id: str, nachricht_id: str):
        """(Nachricht, Frage, Dargestellt) der Antwort; 404 ohne die Antwort, 409 ohne übernehmbare Sätze."""
        nachrichten = app.state.gespraech_ansicht(gespraech_id)['messages']
        stelle = next((i for i, m in enumerate(nachrichten) if m['id'] == nachricht_id and m['role'] == 'assistant'), None)
        if stelle is None:
            raise HTTPException(status_code=404, detail='Diese Antwort gibt es nicht mehr.')
        try:
            dargestellt = uebernehmen.antwort_lesen(nachrichten[stelle], app.state.episodes, app.state.claims)
        except UebernehmenFehler as fehler:
            raise HTTPException(status_code=409, detail=str(fehler)) from None
        return nachrichten[stelle], uebernehmen.frage_der_antwort(nachrichten, stelle), dargestellt

    @app.get('/api/v1/antworten/uebernehmen', dependencies=guard)
    def vorschau(conversation_id: str = Query(..., min_length=1, max_length=200),
                 message_id: str = Query(..., min_length=1, max_length=200)) -> dict[str, Any]:
        """Die Rückfrage: Sätze, Ziele und der bisherige Stand der Vorschläge dieser Antwort."""
        nachricht, _, dargestellt = antwort(conversation_id, message_id)
        nachfuehren(app)
        bezuege, _ = bausteine(app)
        ziele = uebernehmen.ziele_der_antwort(nachricht, dargestellt, bezuege)
        vorgabe = ziele[0]['sache'] if ziele else None
        return {'saetze': [s.als_dict() for s in uebernehmen.saetze_info(dargestellt, vorgabe, app.state.claims)],
                'ziele': ziele, 'sache': vorgabe,
                'bisher': uebernehmen.bisherige(app.state.proposals, conversation_id, message_id)}

    @app.post('/api/v1/antworten/uebernehmen', dependencies=guard, status_code=201)
    def vorschlagen(body: UebernehmenIn) -> dict[str, Any]:
        """Legt je gewähltem Satz einen Vorschlag an (nie eine Aussage). Die Annahme geschieht auf der Vorschlagskarte."""
        nachricht, frage, dargestellt = antwort(body.conversation_id, body.message_id)
        nachfuehren(app)
        bezuege, _ = bausteine(app)
        ziele = uebernehmen.ziele_der_antwort(nachricht, dargestellt, bezuege)
        if not ziele:
            raise HTTPException(status_code=409, detail='Zu dieser Antwort gibt es keine Akte, in die sie passt.')
        sache = body.sache or ziele[0]['sache']
        if sache not in {z['sache'] for z in ziele}:
            raise HTTPException(status_code=422, detail='Diese Akte gehört nicht zu der Antwort.')
        try:
            with app.state.conversation_lock:
                ergebnisse = uebernehmen.vorschlagen(
                    dargestellt=dargestellt, nummern=body.saetze, sache=sache, notiz=body.notiz, frage=frage,
                    gespraech_id=body.conversation_id, nachricht_id=body.message_id, episodes=app.state.episodes,
                    claims=app.state.claims, service=app.state.knowledge_service)
        except UebernehmenFehler as fehler:
            raise HTTPException(status_code=422, detail=str(fehler)) from None
        name = next(z['name'] for z in ziele if z['sache'] == sache)
        return {'sache': sache, 'name': name, 'ergebnisse': ergebnisse}
