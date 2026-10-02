"""Verdrahtung der Fassungsprüfung (`fassung.py`): Routen und der Haken im Zeitplan.

* `GET  /api/v1/fassung`: laufende Fassung, neuestes Manifest, ob ein Update da ist und ob es eine neuere App braucht,
  wann zuletzt nachgesehen wurde und ob die tägliche Prüfung an ist. Fragt nicht nach außen.
* `POST /api/v1/fassung/pruefen`: sieht sofort nach (ein Klick auf „Jetzt nachsehen“), auch wenn die tägliche
  Prüfung aus ist. Die Antwort ist der Stand und `erreicht` (kam ein gültiges Manifest?).
* `PUT  /api/v1/fassung` `{pruefen}`: schaltet die tägliche Prüfung.

Die tägliche Prüfung läuft im Faden des Zeitplans (`Scheduler.nebenbei_setzen`). Der Faden läuft deshalb auch dann,
wenn der Zeitplan selbst aus ist, solange die Prüfung an ist; er tut dann nichts anderes.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from .fassung import DATEI, Fassungspruefung, manifest_url


class FassungIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    pruefen: bool


def pruefung_von(app, data_dir: Callable[[], Path]) -> Fassungspruefung:
    """Die Prüfung dieser App; einmal angelegt. Die Datei folgt dem Datenordner (auch nach einer Wiederherstellung)."""
    pruefung = getattr(app.state, 'fassung', None)
    if pruefung is None:
        pruefung = app.state.fassung = Fassungspruefung(lambda: data_dir() / DATEI)
    return pruefung


def zeitplan_anschliessen(app, scheduler, data_dir: Callable[[], Path]) -> bool:
    """Hängt die tägliche Prüfung an den Zeitplan. True, wenn der Faden ihretwegen laufen soll."""
    pruefung = pruefung_von(app, data_dir)
    setzen = getattr(scheduler, 'nebenbei_setzen', None)
    if setzen is None:  # ein Ersatz-Zeitplan (etwa in Tests) ohne leichte Aufgabe
        return False
    if not manifest_url():
        setzen(None)
        return False
    setzen(pruefung.im_takt)
    return pruefung.an


def register(app, guard, data_dir: Callable[[], Path]) -> None:
    pruefung_von(app, data_dir)

    @app.get('/api/v1/fassung', dependencies=guard)
    def fassung_lesen() -> dict[str, Any]:
        return app.state.fassung.stand()

    @app.post('/api/v1/fassung/pruefen', dependencies=guard)
    def fassung_pruefen() -> dict[str, Any]:
        erreicht = app.state.fassung.jetzt_pruefen()
        return {**app.state.fassung.stand(), 'erreicht': erreicht}

    @app.put('/api/v1/fassung', dependencies=guard)
    def fassung_schalten(body: FassungIn) -> dict[str, Any]:
        stand = app.state.fassung.schalten(body.pruefen)
        scheduler = getattr(app.state, 'scheduler', None)
        if scheduler is not None:
            if zeitplan_anschliessen(app, scheduler, data_dir):
                scheduler.start()
            elif not app.state.settings.schedule.enabled:
                scheduler.stop()
        return stand


__all__ = ['FassungIn', 'pruefung_von', 'register', 'zeitplan_anschliessen']
