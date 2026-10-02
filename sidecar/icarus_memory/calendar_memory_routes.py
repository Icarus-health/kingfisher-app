"""Verdrahtung der Termine im Gedächtnis: Zeitplanlauf, Freigabe, Auskunft.

Die Regeln stehen in `calendar_memory`; hier steht nur, wie der Server sie mit
seinen Kalenderquellen verbindet. Der Mac-Kalender liefert seine Abschnitte selbst
(`mac_calendar.install_routes`, Route `/memory`); alle anderen Quellen liest der
Zeitplan (`abgleichen`) oder ein Klick auf „Jetzt abgleichen“.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from .calendar_memory import MAC_QUELLE, VERGANGENHEIT_TAGE, ZUKUNFT_TAGE, kalender_job
from .connectors.calendar import CalendarConnector
from .connectors.collections import CalendarCollection, NamedCalendar


def lesequellen(app) -> list[NamedCalendar]:
    """Die Quellen, die der Zeitplan liest: alle eingerichteten außer dem Mac-Kalender."""
    kalender = getattr(app.state, "calendar", None)
    if isinstance(kalender, CalendarCollection):
        return [quelle for quelle in kalender.sources if quelle.id != "mac-calendar"]
    if isinstance(kalender, CalendarConnector):
        return [NamedCalendar(id="legacy-calendar", label="Bestehender Kalender", reader=kalender)]
    return []


def freigegeben(app) -> Callable[[str], bool]:
    """Ob eine Gedächtnisquelle jetzt freigegeben ist: eingerichtet, beim Mac zusätzlich ausgewählt."""
    mac = app.state.mac_calendar
    ids = {quelle.id for quelle in lesequellen(app)}

    def frei(quelle: str) -> bool:
        return mac.freigegeben(quelle) if quelle.startswith(MAC_QUELLE) else quelle in ids
    return frei


def abgleichen(app, *, at: datetime | None = None, erlaubt: Callable[[], bool] = lambda: True) -> dict[str, Any]:
    """Liest alle Nicht-Mac-Quellen im Gedächtnisfenster, gleicht ab und entzieht Getrenntes."""
    gedaechtnis = app.state.calendar_memory
    frei = freigegeben(app)
    ergebnisse = kalender_job(gedaechtnis, lesequellen(app), at=at, erlaubt=lambda quelle: erlaubt() and frei(quelle))
    entzogen = gedaechtnis.entziehen_ohne_freigabe(frei)
    ergebnis = {"quellen": {quelle: r.to_dict() for quelle, r in ergebnisse.items()}, "entzogen_getrennt": entzogen,
                "abgeglichen_am": (at or datetime.now().astimezone()).isoformat()}
    app.state.calendar_memory_letzter = ergebnis
    return ergebnis


def install_routes(app, guard) -> None:
    @app.get("/api/v1/calendar-memory", dependencies=guard)
    def auskunft() -> dict[str, Any]:
        """Wie viele Termine im Gedächtnis liegen, je Quelle, und was der letzte Abgleich tat."""
        gedaechtnis = app.state.calendar_memory
        quellen = [{"id": q.id, "label": q.label, "termine": gedaechtnis.anzahl(q.id)} for q in lesequellen(app)]
        return {"fenster": {"tage_zurueck": VERGANGENHEIT_TAGE, "tage_voraus": ZUKUNFT_TAGE},
                "mac_termine": gedaechtnis.anzahl(MAC_QUELLE), "quellen": quellen,
                "letzter_abgleich": getattr(app.state, "calendar_memory_letzter", None)}

    @app.post("/api/v1/calendar-memory/sync", dependencies=guard)
    def jetzt_abgleichen() -> dict[str, Any]:
        """Stößt den Abgleich der Nicht-Mac-Quellen an; der Mac-Arbeiter liefert seine Abschnitte selbst."""
        return abgleichen(app)
