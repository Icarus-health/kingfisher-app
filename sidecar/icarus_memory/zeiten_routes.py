"""Das Protokoll der Antwortzeiten: `GET /api/v1/antwortzeiten`.

Die Zahlen sind die, die jede Gedächtnisantwort beim Entstehen mitbekommt (`zeitmessung.py`,
`answer['zeiten']`) und die mit dem Gespräch gespeichert sind. Hier wird nur gelesen und zusammengefasst:
Median und 90-%-Wert je Abschnitt über die letzten 50 Antworten, dazu die Modelle der Rollen
`frage` und `antwort`, der Stand des Schalters für die Sätze und der des zweiten Tors (Prüfmodell). Es gibt keinen eigenen Speicher, und es
steht nie ein Fragetext oder Antworttext darin.
"""
from __future__ import annotations

from typing import Any

from . import zeitmessung
from .agent_verdrahtung import satzpruefung_stand
from .model_roles import anbieter_fuer_frage, rollen_von


def _modellname(anbieter: Any) -> str | None:
    name = getattr(anbieter, "model", None)
    return name if isinstance(name, str) and name else None


def protokoll(app, limit: int = zeitmessung.LETZTE_ANTWORTEN) -> dict[str, Any]:
    """Kennzahlen der jüngsten Antworten, Modelle der Rollen, Ziel und Schalter."""
    antworten = app.state.conversations.antwortzeiten(limit)
    rollen = rollen_von(app)
    einstellungen = getattr(app.state, "settings", None)
    return {
        "antworten": len(antworten),
        "ziel_s": zeitmessung.ZIEL_MEDIAN_S,
        "abschnitte": zeitmessung.kennzahlen([a["zeiten"] for a in antworten]),
        "modelle": {"frage": _modellname(anbieter_fuer_frage(rollen)),
                    "antwort": _modellname(rollen.provider("antwort"))},
        "saetze": "aus" if getattr(einstellungen, "antwort_saetze", "an") == "aus" else "an",
        "pruefung": satzpruefung_stand(app),
    }


def register(app, guard) -> None:
    @app.get("/api/v1/antwortzeiten", dependencies=guard)
    def antwortzeiten():
        return protokoll(app)
