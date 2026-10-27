"""Verdrahtung „Aufgaben von selbst“ (Regeln in `aufgaben_von_selbst.py`).

* `GET/PUT /api/v1/aufgaben-von-selbst/einstellung` `{an}`: der Schalter „Aufgaben aus Mails selbst anlegen“ (Vorgabe an).
* `GET  /api/v1/aufgaben-von-selbst/heute`: was Kingfisher heute selbst angelegt hat (`anzahl`, `satz`, `aufgaben`).
* `POST /api/v1/aufgaben-von-selbst/{task_id}/rueckgaengig`: nimmt eine selbst angelegte Aufgabe zurück (404, 409).
* `POST /api/v1/aufgaben-von-selbst/{task_id}/wiederherstellen`: „Rückgängig“ des Zurücknehmens (404, 409).
* `POST /api/v1/aufgaben-von-selbst/rueckgaengig` `{task_ids}` und `/wiederherstellen` `{task_ids}`: dasselbe für den
  Hinweis auf Heute, der alle von heute zusammenfasst.
* `POST /api/v1/task-candidates/alle-uebernehmen` `{ids}`: „Alle übernehmen“ mit vorbefülltem Projekt, Person und
  Frist; `POST /api/v1/task-candidates/gruppe/{gruppe}/rueckgaengig` nimmt die ganze Gruppe zurück.
* `POST /api/v1/aufgaben-von-selbst/durchlauf`: ein Durchlauf sofort (für Proben; sonst nach jeder Mailaufnahme).
* `GET  /api/v1/aufgaben-von-selbst/zurueckgenommen`: was du zurückgenommen hast, dauerhaft wiederherstellbar (unter
  „Erledigt“ in der Aufgabenliste; Paket Z2).
* `POST /api/v1/task-candidates/aufgabe/{task_id}/zurueck`: ein übernommener Vorschlag zurück zur Prüfung, jederzeit
  (404, 409 mit Satz; Paket Z2, Z4).
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from .aufgaben_von_selbst import ALLE_HOECHSTENS, durchlauf_fuer, schritt_fuer


class EinstellungIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    an: bool


class KennungenIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    task_ids: list[str] = Field(min_length=1, max_length=200)


class AlleIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ids: list[str] = Field(min_length=1, max_length=ALLE_HOECHSTENS)


def register(app, guard) -> None:
    def candidates():
        from .task_candidates import TaskCandidates
        return TaskCandidates(app.state.episodes, app.state.proposals, app.state.tasks, app.state.workspace,
                              app.state.conversation_lock)

    def eigene():
        from . import identitaet
        return identitaet.eigene_adressen(getattr(app.state, 'settings', None))

    @app.get('/api/v1/aufgaben-von-selbst/einstellung', dependencies=guard)
    def einstellung() -> dict[str, Any]:
        return {'an': app.state.tasks.auto_an()}

    @app.put('/api/v1/aufgaben-von-selbst/einstellung', dependencies=guard)
    def einstellung_setzen(body: EinstellungIn) -> dict[str, Any]:
        return {'an': app.state.tasks.auto_setzen(body.an)}

    @app.post('/api/v1/aufgaben-von-selbst/durchlauf', dependencies=guard)
    def durchlauf() -> dict[str, Any]:
        return schritt_fuer(app)

    @app.get('/api/v1/aufgaben-von-selbst/heute', dependencies=guard)
    def heute() -> dict[str, Any]:
        with app.state.conversation_lock:
            return durchlauf_fuer(app).heute()

    def zurueck(task_id: str) -> dict[str, Any]:
        try:
            return durchlauf_fuer(app).zuruecknehmen(task_id).to_dict()
        except KeyError as exc:
            raise HTTPException(404, 'Aufgabe nicht gefunden.') from exc
        except LookupError as exc:
            raise HTTPException(409, str(exc)) from exc

    def wieder(task_id: str) -> dict[str, Any]:
        try:
            return durchlauf_fuer(app).wiederherstellen(task_id).to_dict()
        except KeyError as exc:
            raise HTTPException(404, 'Hier gibt es nichts wiederherzustellen.') from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post('/api/v1/aufgaben-von-selbst/rueckgaengig', dependencies=guard)
    def alle_zurueck(body: KennungenIn) -> dict[str, Any]:
        with app.state.conversation_lock:
            ergebnis = [zurueck(task_id) for task_id in dict.fromkeys(body.task_ids)]
        n = len(ergebnis)
        return {'aufgaben': ergebnis,
                'satz': '1 Aufgabe zurückgenommen.' if n == 1 else f'{n} Aufgaben zurückgenommen.'}

    @app.post('/api/v1/aufgaben-von-selbst/wiederherstellen', dependencies=guard)
    def alle_wieder(body: KennungenIn) -> dict[str, Any]:
        with app.state.conversation_lock:
            return {'aufgaben': [wieder(task_id) for task_id in dict.fromkeys(body.task_ids)]}

    @app.post('/api/v1/aufgaben-von-selbst/{task_id}/rueckgaengig', dependencies=guard)
    def eine_zurueck(task_id: str) -> dict[str, Any]:
        with app.state.conversation_lock:
            return zurueck(task_id)

    @app.post('/api/v1/aufgaben-von-selbst/{task_id}/wiederherstellen', dependencies=guard)
    def eine_wieder(task_id: str) -> dict[str, Any]:
        with app.state.conversation_lock:
            return wieder(task_id)

    @app.post('/api/v1/task-candidates/alle-uebernehmen', dependencies=guard)
    def alle_uebernehmen(body: AlleIn) -> dict[str, Any]:
        dienst = candidates()
        adressen = eigene()

        def annehmen(proposal_id: str, **daten: Any):
            return dienst.accept(proposal_id, eigene=adressen, **daten)
        # `TaskCandidates.accept` nimmt die Sperre je Vorschlag selbst; der Durchlauf liest nur.
        return durchlauf_fuer(app).alle_uebernehmen(body.ids, annehmen=annehmen)

    @app.get('/api/v1/aufgaben-von-selbst/zurueckgenommen', dependencies=guard)
    def zurueckgenommen(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
        return {'aufgaben': app.state.tasks.anlage_zurueckgenommen(limit)}

    @app.post('/api/v1/task-candidates/aufgabe/{task_id}/zurueck', dependencies=guard)
    def zur_pruefung(task_id: str) -> dict[str, Any]:
        with app.state.conversation_lock:
            try:
                return durchlauf_fuer(app).zur_pruefung(task_id)
            except KeyError as exc:
                raise HTTPException(404, 'Aufgabe nicht gefunden.') from exc
            except LookupError as exc:
                raise HTTPException(409, str(exc)) from exc

    @app.post('/api/v1/task-candidates/gruppe/{gruppe}/rueckgaengig', dependencies=guard)
    def gruppe_zurueck(gruppe: str) -> dict[str, Any]:
        with app.state.conversation_lock:
            ergebnis = durchlauf_fuer(app).gruppe_zuruecknehmen(gruppe)
        if not ergebnis['zurueckgenommen'] and not ergebnis['geblieben']:
            raise HTTPException(404, 'Diese Übernahme gibt es nicht (mehr).')
        return ergebnis


__all__ = ['register']
