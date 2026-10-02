"""Verdrahtung der Einstellung „Wortteile für die letzten N Jahre“ des Suchindex.

Die Regeln stehen in `source_index.py`, der Umbau am `EpisodeStore`. Hier steht nur, wie der Server sie mit den
Einstellungen verbindet.

* `GET /api/v1/suchindex`: die Einstellung, wie viele Quellen Wortteile haben und wie viele nur Wörter, und der
  belegte Platz des Index in MB (`null`, wenn diese SQLite ihn nicht nennen kann).
* `PUT /api/v1/suchindex`: `{"wortteile_jahre": N}` (0 = alle, Vorgabe). Speichert die Einstellung und baut den
  Index um: Quellen, die älter sind als N Jahre, wandern in den kleineren Wortindex, die übrigen bleiben im
  Trigramm-Index. Die Antwort nennt, wie viele Quellen umgezogen sind. Das kann bei großem Bestand dauern.

Beim Start gleicht `anwenden` die gespeicherte Einstellung mit dem Index ab (nach einer Wiederherstellung kann der
Index aus einer Sicherung anders stehen als die Einstellungen).
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from . import config

log = logging.getLogger(__name__)

#: Obergrenze, damit ein Tippfehler nicht „Jahr 3000“ bedeutet; 100 Jahre ist praktisch „alle“.
MAX_JAHRE = 100


class SuchindexIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    wortteile_jahre: int = Field(ge=0, le=MAX_JAHRE)


def jahre_aus(settings) -> int:
    """Die gespeicherte Einstellung als ganze Zahl von 0 bis 100; Unbrauchbares heißt 0 (alle)."""
    roh = getattr(settings, 'suchindex', None)
    wert = roh.get('wortteile_jahre') if isinstance(roh, dict) else 0
    return wert if type(wert) is int and 0 <= wert <= MAX_JAHRE else 0


def anwenden(app) -> None:
    """Den Index auf die gespeicherte Einstellung bringen. Ein Fehler hält den Start nicht auf."""
    jahre = jahre_aus(app.state.settings)
    try:
        if app.state.episodes.suchindex_jahre() != jahre:
            app.state.episodes.suchindex_einstellen(jahre)
    except Exception:  # noqa: BLE001 - der Abgleich beim nächsten Start holt es nach; die Suche bleibt vollständig
        log.exception('Der Suchindex konnte nicht auf die Einstellung gebracht werden.')


def register(app, guard, data_dir) -> None:
    def stand(zusatz: dict[str, Any] | None = None) -> dict[str, Any]:
        roh = app.state.episodes.suchindex_stand()
        platz = roh['bytes']
        return {'wortteile_jahre': roh['wortteile_jahre'], 'quellen': roh['quellen'],
                'mit_wortteilen': roh['mit_wortteilen'], 'nur_woerter': roh['nur_woerter'],
                'groesse_mb': None if platz is None else round(platz / (1024 * 1024), 1), **(zusatz or {})}

    @app.get('/api/v1/suchindex', dependencies=guard)
    def suchindex() -> dict[str, Any]:
        return stand()

    @app.put('/api/v1/suchindex', dependencies=guard)
    def suchindex_setzen(body: SuchindexIn) -> dict[str, Any]:
        try:
            umbau = app.state.episodes.suchindex_einstellen(body.wortteile_jahre)
        except Exception:  # noqa: BLE001
            log.exception('Der Suchindex konnte nicht umgebaut werden.')
            raise HTTPException(500, 'Der Suchindex konnte nicht umgebaut werden. Die Suche funktioniert weiter; '
                                     'bitte erneut versuchen.') from None
        with app.state.conversation_lock:
            vorher = app.state.settings.suchindex
            app.state.settings.suchindex = {'wortteile_jahre': body.wortteile_jahre}
            try:
                config.save(data_dir(), app.state.settings)
            except Exception:
                app.state.settings.suchindex = vorher
                raise HTTPException(500, 'Die Einstellung konnte nicht gespeichert werden.') from None
        return stand({'umgestuft': umbau['umgestuft'], 'verdichtet': umbau['verdichtet']})
