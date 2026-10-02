"""Verdrahtung des Agenten mit der Anwendung: an einer Stelle statt an mehreren.

Der Agent bekommt außer seinen Speichern einige spät gebundene Zusatzobjekte
(Projektverzeichnis, Terminsuche, Projektmappe, eigene Adressen, Anbieter der Rolle
`frage`). Sie wurden beim Start, beim Neuaufbau der Speicher und bei einem
eingesetzten Agenten jeweils einzeln gesetzt; eine Stelle vergessen hieß: dieser
Weg sah einen anderen Stand als die anderen. Jetzt rufen alle diese Funktionen.

Anbieter kommen nur über `model_roles` (`rollen_von(app).provider(rolle)`): Gespräch
bekommt die Rolle `antwort`, jede Hintergrundarbeit (Verdichtung, Zusammenfassung,
Einordnung) die Rolle `hintergrund`, und die ist immer lokal.
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from . import identitaet, satzpruefung_modell
from .consolidation import Consolidator
from .model_roles import anbieter_fuer_frage, anbieter_fuer_pruefung, rollen_von
from .self_model_support import EpisodeSupportResolver
from .summaries import Summarizer
from .workspace import WorkspaceError

if TYPE_CHECKING:  # pragma: no cover
    from fastapi import FastAPI

    from .agent import Agent


def _project_directory(app: FastAPI):
    """Projektnamen für das Gedächtnis, spät gebunden an den aktuellen Arbeitsbereich."""
    return lambda: [(project.id, project.name)
                    for project in app.state.workspace.projects(include_closed=True)]


TERMINE_CACHE = timedelta(minutes=5)
TERMINE_WARTEN = 3.0
TERMINE_FEHLER_CACHE = timedelta(minutes=1)


def _search_calendar(app: FastAPI):
    """Termine ±30 Tage für die erste Suchstufe, kurz zwischengespeichert.

    Ein entfernter Kalender darf eine Frage nicht aufhalten: Nach drei
    Sekunden geht es ohne Termine weiter, und die Antwort sagt das (None).
    Es läuft höchstens ein Abruf zugleich; er füllt im Hintergrund den
    Zwischenspeicher für die nächste Frage. Das Fenster bleibt im laufenden
    Jahr, weil der Mac-Kalender nur dieses abgleicht.
    """
    state = {'lock': threading.Lock(), 'running': None, 'calendar': None,
             'source_generation': None, 'revision': 0}

    def source_revision(calendar):
        marker = getattr(calendar, 'cache_revision', None)
        return marker() if callable(marker) else None

    def abrufen(calendar, generation, revision, source_generation, start, days):
        try:
            events = [event.to_dict() for event in calendar.events(days=days, at=start)]
        except Exception:  # noqa: BLE001 - nicht erreichbar: eine Minute lang nicht erneut fragen
            events = None
        with state['lock']:
            if (app.state.calendar is calendar
                    and getattr(app.state, '_calendar_search_generation', 0) == generation
                    and state['revision'] == revision
                    and source_revision(calendar) == source_generation):
                app.state.search_calendar_cache = (calendar, generation, revision, source_generation,
                                                   datetime.now(timezone.utc), events)

    def lesen():
        calendar = getattr(app.state, 'calendar', None)
        if calendar is None:
            with state['lock']:
                state['calendar'] = None
                state['source_generation'] = None
                state['revision'] += 1
                app.state.search_calendar_cache = None
            return []
        generation = getattr(app.state, '_calendar_search_generation', 0)
        source_generation = source_revision(calendar)
        with state['lock']:
            if state['calendar'] is not calendar or state['source_generation'] != source_generation:
                state['calendar'] = calendar
                state['source_generation'] = source_generation
                state['revision'] += 1
                app.state.search_calendar_cache = None
            revision = state['revision']
        current = datetime.now(timezone.utc)
        cached = getattr(app.state, 'search_calendar_cache', None)
        token = (calendar, generation, revision, source_generation)
        if (cached is not None and cached[:4] == token
                and current - cached[4] < (TERMINE_CACHE if cached[5] is not None else TERMINE_FEHLER_CACHE)
                and source_revision(calendar) == source_generation):
            return cached[5]
        with state['lock']:
            worker = state['running']
            if worker is not None and worker[1:] == token and worker[0].is_alive():
                # Ein hängender Kalender hält nicht jede weitere Frage auf.
                return None
            start = max(current - timedelta(days=30), current.replace(month=1, day=1, hour=0, minute=0,
                                                                     second=0, microsecond=0))
            end = min(current + timedelta(days=30), current.replace(month=12, day=31, hour=23, minute=59,
                                                                   second=0, microsecond=0))
            thread = threading.Thread(target=abrufen,
                                      args=(calendar, generation, revision, source_generation,
                                            start, max(1, (end - start).days)),
                                      daemon=True)
            state['running'] = (thread, *token)
            thread.start()
        thread.join(TERMINE_WARTEN)
        cached = getattr(app.state, 'search_calendar_cache', None)
        if (thread.is_alive() or cached is None or cached[:4] != token
                or app.state.calendar is not calendar
                or getattr(app.state, '_calendar_search_generation', 0) != generation
                or source_revision(calendar) != source_generation):
            return None
        return cached[5]
    return lesen


def _projekt_mappe(app: FastAPI, project_id: str, *, alle: bool = False):
    """Ebene 2 der Projektmappe, für Profil und Gespräch dieselbe. None ohne Projekt."""
    from .mappe import einzelheiten
    try:
        project = app.state.workspace.project(project_id)
    except WorkspaceError:
        return None
    agent = getattr(app.state, 'agent', None)
    entries = getattr(agent, '_calendar_entries', None)
    ids = [row['id'] for row in app.state.episodes.project_heads(project_id)]
    daten = einzelheiten(ids, episodes=app.state.episodes, claims=app.state.claims,
                         tasks=app.state.tasks.by_project(project_id),
                         termine=entries() if callable(entries) else [], namen=[project.name], alle=alle)
    daten['name'] = project.name
    return daten


def verdrahte_zusaetze(app: FastAPI, agent: Agent) -> None:
    """Die spät gebundenen Zusatzobjekte des Agenten, alle aus dem aktuellen Stand der Anwendung."""
    agent._runtime_boundary = app.state.runtime_boundary
    agent._projects = _project_directory(app)
    agent._termine = _search_calendar(app)
    agent._mappe = lambda project_id: _projekt_mappe(app, project_id)
    agent._eigene = lambda: identitaet.eigene_adressen(getattr(app.state, "settings", None))
    agent._frage_anbieter = lambda: anbieter_fuer_frage(rollen_von(app))
    # Sätze an oder aus: dieselbe Stelle wie `Agent._saetze_an`; eine Änderung baut den Agenten neu.
    agent._saetze = getattr(getattr(app.state, "settings", None), "antwort_saetze", "an") != "aus"
    # Zweites Tor der Satzprüfung: Einstellung und Modell der Rolle `pruefung`, je Antwort frisch gelesen.
    agent._pruefung = lambda: pruef_tor(app)
    # Solange das Sprachmodell im Hintergrund lädt, sagt eine Antwort ohne Modell das ehrlich (Fremdprobe 2, Befund 6).
    agent._modell_laedt = lambda: modell_laedt_satz(app)


def modell_laedt_satz(app: FastAPI) -> str:
    """„Kingfisher lädt noch sein Sprachmodell (60 %).“, solange das Laden läuft; sonst leer."""
    manager = getattr(app.state, "pull_manager", None)
    stand = manager.reihe_stand() if manager is not None else None
    return stand["satz"] if stand and stand.get("laeuft") else ""


def pruef_tor(app: FastAPI) -> satzpruefung_modell.Tor:
    """Das zweite Tor zum aktuellen Stand: an nur mit Einstellung `an` und einem lokalen Modell der Rolle `pruefung`."""
    einstellung = getattr(getattr(app.state, "settings", None), "satzpruefung_modell", "an")
    return satzpruefung_modell.tor(einstellung, anbieter_fuer_pruefung(rollen_von(app)))


def verdrahte_speicher(app: FastAPI, agent: Agent) -> None:
    """Die Speicher der Anwendung an einen bestehenden Agenten hängen (Neuaufbau, eingesetzter Agent)."""
    agent._store = app.state.store
    agent._episodes = app.state.episodes
    agent._knowledge = app.state.claims
    agent._knowledge_conflicts = app.state.knowledge_service.answer_conflict_status
    agent._snapshot_provider = app.state.episodes.support_snapshot
    agent._support_resolver = EpisodeSupportResolver(app.state.proposals, app.state.episodes)


def baue_hintergrund(app: FastAPI) -> None:
    """Verdichter und Zusammenfasser auf den aktuellen Speichern und dem Anbieter der Rolle `hintergrund`.

    Ohne Neubau würde der Verdichter nach einem Wechsel weiter das alte Modell oder den alten
    Speicher benutzen. Der Anbieter ist der der Rolle `hintergrund`, nie der des Gesprächs.
    """
    anbieter = rollen_von(app).provider("hintergrund")
    app.state.consolidator = Consolidator(
        store=app.state.store,
        episodes=app.state.episodes,
        proposals=app.state.proposals,
        provider=anbieter,
    )
    app.state.summarizer = Summarizer(episodes=app.state.episodes, provider=anbieter)


def satzpruefung_stand(app: FastAPI) -> dict[str, str | None]:
    """Für Einstellungen und Protokoll: Schalter (`an`/`aus`), Zustand des Tors und das Prüfmodell (oder None)."""
    tor = pruef_tor(app)
    einstellung = getattr(getattr(app.state, "settings", None), "satzpruefung_modell", "an")
    return {"schalter": "aus" if einstellung == "aus" else "an", "zustand": tor.zustand,
            "modell": getattr(anbieter_fuer_pruefung(rollen_von(app)), "model", None) or None}


__all__ = ["baue_hintergrund", "pruef_tor", "satzpruefung_stand", "verdrahte_speicher", "verdrahte_zusaetze"]
