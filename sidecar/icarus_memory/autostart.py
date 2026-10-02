"""Autostart beim Anmelden: eine Frage, keine stille Vorgabe.

Der Sidecar läuft im Container und kann auf dem Rechner selbst nichts
einrichten. Er merkt sich nur die Antwort des Menschen (`autostart.json` im
Datenordner); ein Helfer auf dem Rechner setzt sie um. Auf dem Mac ist das
`scripts/mac_autostart.py` (Launch Agent unter `~/Library/LaunchAgents`), auf
anderen Systemen gibt es noch keinen Helfer, und die Oberfläche sagt „noch
nicht verfügbar“.

Die Trennung ist Absicht und eine Sicherheitszusage: Über die API kommt nur
ein Ja oder Nein, nie ein Pfad oder Befehl. Was beim Anmelden startet, bestimmt
der Helfer selbst aus seinem eigenen Aufruf.

* `GET  /api/v1/autostart`: `gewuenscht` (`None`, solange niemand gefragt
  wurde), `verfuegbar` (ein Helfer hat sich in der letzten Minute gemeldet),
  `eingerichtet` (was der Helfer vorfand), `plattform`.
* `PUT  /api/v1/autostart` mit `{"an": true|false}`: nur auf Klick.
* `POST /api/v1/autostart/helfer` mit `{"plattform", "eingerichtet"}`: der
  Helfer meldet sich und bekommt die Antwort zurück.

Vorgabe ist `None`: Ohne Antwort schreibt der Helfer nichts und entfernt nichts.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any, Callable, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict

#: So lange gilt die Meldung eines Helfers; danach heißt es wieder „noch nicht verfügbar“.
HELFER_GILT_S = 60.0


class AutostartIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    an: bool


class HelferIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    plattform: Literal['macos']
    eingerichtet: bool


def wunsch_lesen(pfad) -> bool | None:
    try:
        roh = json.loads(pfad.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    wert = roh.get('gewuenscht') if isinstance(roh, dict) else None
    return wert if isinstance(wert, bool) else None


def register(app, guard, data_dir: Callable[[], Any], uhr: Callable[[], float] = time.monotonic) -> None:
    datei = lambda: data_dir() / 'autostart.json'  # noqa: E731
    helfer: dict[str, Any] = {}

    def stand() -> dict[str, Any]:
        gemeldet = helfer.get('zeit')
        verfuegbar = gemeldet is not None and uhr() - gemeldet < HELFER_GILT_S
        return {'gewuenscht': wunsch_lesen(datei()), 'verfuegbar': verfuegbar,
                'eingerichtet': bool(helfer.get('eingerichtet')) if verfuegbar else None,
                'plattform': helfer.get('plattform') if verfuegbar else None}

    # Die Einrichtung fragt danach, ob sie den Schritt „Beim Anmelden“ überhaupt zeigt (Fremdprobe, Befund 26).
    app.state.autostart_stand = stand

    @app.get('/api/v1/autostart', dependencies=guard)
    def autostart() -> dict[str, Any]:
        return stand()

    @app.put('/api/v1/autostart', dependencies=guard)
    def autostart_setzen(body: AutostartIn) -> dict[str, Any]:
        from .atomic import write_text_atomic
        try:
            write_text_atomic(datei(), json.dumps({'gewuenscht': body.an,
                                                   'entschieden_am': datetime.now().astimezone().isoformat()}))
        except OSError:
            raise HTTPException(500, 'Die Wahl konnte nicht gespeichert werden.') from None
        return stand()

    @app.post('/api/v1/autostart/helfer', dependencies=guard)
    def autostart_helfer(body: HelferIn) -> dict[str, Any]:
        helfer.update(zeit=uhr(), plattform=body.plattform, eingerichtet=body.eingerichtet)
        return {'gewuenscht': wunsch_lesen(datei())}


__all__ = ['HELFER_GILT_S', 'register', 'wunsch_lesen']
