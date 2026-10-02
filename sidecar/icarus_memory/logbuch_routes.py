"""Verdrahtung des Logbuchs (`logbuch.py`): die Datei, die Route, die Zeilen fürs Briefing.

* `GET /api/v1/logbuch?seit=…`: die Chronik als ruhige Ansicht, nach Tagen gruppiert (jüngster zuerst),
  dazu die Zusammenfassung des Zeitraums. `seit` ist ein Zeitpunkt (ISO); ohne Angabe gelten sieben Tage.
  Die Route liest nur und zählt **nicht** als Blick: Wer den Verlauf öffnet, verschiebt den Bezugspunkt
  der drei Briefingzeilen nicht.
* `zeilen(app, jetzt)`: die drei Zeilen fürs Tagesbriefing und fürs Morgenbriefing. Der Aufruf gilt als der
  letzte Blick (`Logbuch.bezugspunkt`). Er wirft nie: Geht etwas schief, fehlen die Zeilen, das Briefing bleibt.

Das Logbuch bekommt seine Einträge von den schreibenden Stellen (`logbuch.vermerke`), nicht von dieser Datei.
Lint (`lint.zusammenfassung()`) hängt sich über `befunde_lieferant_setzen` ein oder setzt
`app.state.logbuch.befunde_lieferant` selbst.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, Query

from . import logbuch
from .datumstext import iso_versuchen
from .logbuch import Logbuch, drei_zeilen

logger = logging.getLogger(__name__)

#: So weit schaut die Chronik-Ansicht ohne Angabe zurück.
STANDARD_TAGE = 7
MAX_TAGE = 366


def _zone_des_nutzers():
    from .model import user_timezone
    zone = user_timezone()
    return zone or datetime.now().astimezone().tzinfo


def verbinden(app, data_dir: Callable[[], Any]) -> Logbuch:
    """Öffnet das Logbuch dieser App und macht es zum aktiven (auch nach einer Wiederherstellung)."""
    alt = getattr(app.state, 'logbuch', None)
    lieferant = getattr(alt, 'befunde_lieferant', None)
    neu = Logbuch(data_dir() / 'logbuch.sqlite3', befunde_lieferant=lieferant)
    app.state.logbuch = neu
    logbuch.verbinde(neu)
    return neu


def befunde_lieferant_setzen(app, lieferant: Callable[[], dict] | None) -> None:
    """Bindet `lint.zusammenfassung` (oder etwas Gleichwertiges) ein; `None` löst es wieder."""
    app.state.logbuch.befunde_lieferant = lieferant


def zeilen(app, jetzt: datetime, *, buchen: bool = True) -> list[str]:
    """Die drei Zeilen seit dem letzten Blick; dieser Aufruf ist der neue Blick (außer mit `buchen=False`).

    Die Oberfläche fragt bei offenem Tab jede Minute nach. Dieses Nachladen bucht keinen Blick: Sonst bliebe der
    Bezugspunkt bei einem Tab, der über Nacht offen steht, für immer auf dem Stand vom Vortag oder spränge nie vor.
    Leer, wenn etwas schiefgeht."""
    try:
        buch: Logbuch | None = getattr(app.state, 'logbuch', None)
        if buch is None:
            return []
        bezug = buch.bezugspunkt(jetzt, buchen=buchen)
        return drei_zeilen(buch.seit(bezug, jetzt))
    except Exception:  # noqa: BLE001 - das Logbuch ist Beiwerk; das Briefing darf nie daran scheitern
        logger.exception('Logbuch: Zeilen fürs Briefing nicht bestimmbar')
        return []


def ansicht(buch: Logbuch, von: datetime, bis: datetime) -> dict[str, Any]:
    z = buch.seit(von, bis)
    return {'seit': von.isoformat(timespec='seconds'), 'bis': bis.isoformat(timespec='seconds'),
            'zeilen': drei_zeilen(z), 'leer': z.leer, 'zusammenfassung': z.to_dict(),
            'tage': buch.tage(von, bis, bis.tzinfo)}


def register(app, guard, data_dir) -> None:
    verbinden(app, data_dir)

    @app.get('/api/v1/logbuch', dependencies=guard)
    def logbuch_ansicht(seit: str | None = Query(None, max_length=64)) -> dict[str, Any]:
        """Was Kingfisher getan hat, nach Tagen; ohne `seit` die letzten sieben Tage. Verändert nichts."""
        zone = _zone_des_nutzers()
        jetzt = datetime.now(zone)
        if seit:
            von = iso_versuchen(seit)
            if von is None:
                raise HTTPException(status_code=422, detail='Der Zeitpunkt ist kein Datum mit Uhrzeit.')
            von = von.astimezone(zone) if von.tzinfo else von.replace(tzinfo=zone)
        else:
            von = jetzt - timedelta(days=STANDARD_TAGE)
        von = max(von, jetzt - timedelta(days=MAX_TAGE))
        if von > jetzt:
            von = jetzt
        return ansicht(app.state.logbuch, von, jetzt)


__all__ = ['ansicht', 'befunde_lieferant_setzen', 'register', 'verbinden', 'zeilen']
