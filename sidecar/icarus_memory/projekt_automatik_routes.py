"""Verdrahtung von „Projekte von selbst“ (`projekt_automatik.py`): Heute-Hinweis und „Rückgängig“ je Mail.

* `GET  /api/v1/projekte/automatik`: was Kingfisher in den letzten Tagen selbst angelegt hat (Name, Akte, Grund);
  für die eine ruhige Zeile auf Heute, nie eine Liste.
* `POST /api/v1/projekte/automatik/zuordnung/{episode_id}/zuruecknehmen`: eine automatische Zuordnung lösen und die
  Mail für die Absenderregel sperren. 404, wenn Kingfisher sie nicht selbst zugeordnet hat; 409, wenn sie inzwischen
  woanders liegt (dann gilt, was der Nutzer gesetzt hat).

Ein ganzes Projekt nimmt weiter `POST /api/v1/akten/vorschlaege/{kennung}/zuruecknehmen` zurück
(`akten_vorschlaege_routes.py`); für eine Anlage durch Kingfisher löst es nur dessen eigene Zuordnungen und merkt sich das.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from . import projekt_automatik as automatik


def register(app, guard) -> None:
    from .akten_routes import bausteine

    @app.get('/api/v1/projekte/automatik', dependencies=guard)
    def projekte_automatik() -> dict[str, Any]:
        """Neue Projekte von Kingfisher, jüngste zuerst (höchstens `MAX_JE_TAG` je Tag, `SICHTBAR_TAGE` lang)."""
        bezuege, _ = bausteine(app)
        return {'neu': automatik.neue_projekte(bezuege, getattr(app.state, 'workspace', None))}

    @app.post('/api/v1/projekte/automatik/zuordnung/{episode_id}/zuruecknehmen', dependencies=guard)
    def projekt_zuordnung_zuruecknehmen(episode_id: str) -> dict[str, Any]:
        from .episodes import EpisodeError
        ablage = automatik.Ablage(app.state.episodes)
        if ablage.zuordnung(episode_id) is None:
            raise HTTPException(status_code=404, detail='Diese Mail hat Kingfisher nicht selbst zugeordnet.')
        try:
            return automatik.zuordnung_zuruecknehmen(app.state.episodes, episode_id,
                                                     audit=getattr(app.state, 'audit', None))
        except automatik.NichtAutomatisch as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except EpisodeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


__all__ = ['register']
