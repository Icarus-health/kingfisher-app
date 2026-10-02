"""Eine frische Kingfisher-Instanz für eine Messung, gebaut wie das Produkt sie baut.

Gleiche Bausteine wie `server.create_app` im Betrieb und wie die bestehende
Diagnostik `scripts/probe_cos_workweek.py`: echte Speicher (SQLite in einem
temporären Verzeichnis), echter Agent, echte API über den TestClient. Anders als
im Betrieb wird der Agent hier mit dem gewünschten Anbieter **übergeben**, statt
ihn aus Schlüsselbund und Umgebung zu bauen: So kann keine echte Zugangsdaten-
Quelle des Rechners in die Messung geraten (siehe `umgebung.py`).

Innerhalb des Blocks gilt die eingefrorene Uhr der Welt (`uhr.py`); sie wird erst
nach dem Bau der App gesetzt.
"""
from __future__ import annotations

import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from .umgebung import isolierte_umgebung
from .uhr import eingefrorene_zeit, ist_eingefroren

TOKEN = 'messlatte'


@dataclass
class Instanz:
    verzeichnis: Path
    app: Any
    client: Any
    agent: Any
    episodes: Any
    claims: Any
    eigene: tuple = ()
    """Die Adressen des Nutzers der Welt. Im Betrieb kennt das Produkt sie aus den Konten."""

    @contextmanager
    def anbieter(self, provider) -> Iterator[None]:
        """Setzt für die Dauer des Blocks einen anderen Modellanbieter am Agenten."""
        vorher = self.agent._provider
        self.agent._provider = provider
        try:
            yield
        finally:
            self.agent._provider = vorher

    def anfrage(self, methode: str, pfad: str, daten: dict | None = None) -> Any:
        antwort = self.client.request(methode, pfad, **({'json': daten} if daten is not None else {}))
        antwort.raise_for_status()
        return antwort.json()

    def kalender_neu_lesen(self) -> None:
        """Wie `_build_agent`, nachdem der Mac-Kalender freigegeben wurde: Kalenderquelle neu bestimmen."""
        from icarus_memory import server
        self.app.state._calendar_search_generation = getattr(self.app.state, '_calendar_search_generation', 0) + 1
        self.app.state.search_calendar_cache = None
        self.app.state.calendar = server._configured_calendar(self.app)


@contextmanager
def instanz_starten(*, stichtag: datetime, zeitzone: str, provider=None,
                    verzeichnis: Path | None = None, eigene: tuple = (), frage_provider=None,
                    pruef_provider=None, wortteile_jahre: int = 0) -> Iterator[Instanz]:
    """Baut die Instanz, friert die Uhr ein und räumt beides am Ende auf.

    Höchstens eine Instanz je Prozess: Uhr, Umgebung und Postfach-Attrappe gelten prozessweit.
    """
    if ist_eingefroren():
        raise RuntimeError('In diesem Prozess läuft schon eine Messinstanz; sie muss zuerst beendet werden.')
    with tempfile.TemporaryDirectory(prefix='messlatte-') as temp:
        wurzel = Path(verzeichnis) if verzeichnis is not None else Path(temp)
        daten = wurzel / 'daten'
        daten.mkdir(parents=True, exist_ok=True)
        umgebung = {'ICARUS_DATA_DIR': str(daten), 'ICARUS_SIDECAR_TOKEN': TOKEN,
                    'ICARUS_MEMORY_SEMANTIC': '', 'KINGFISHER_TIMEZONE': zeitzone,
                    # Die Messinstanz fragt nie die Download-Seite nach einer neuen Fassung (fassung.py).
                    'KINGFISHER_UPDATE_URL': ''}
        with isolierte_umgebung(umgebung):
            from fastapi.testclient import TestClient
            from icarus_memory import MemoryBackend, SelfModelStore
            from icarus_memory.agent import Agent
            from icarus_memory.audit import AuditLog
            from icarus_memory.calendar_context import local_snapshot
            from icarus_memory.claims import ClaimStore
            from icarus_memory.episodes import EpisodeStore
            from icarus_memory.memory_routes import coverage as memory_coverage
            from icarus_memory.policy import Policy
            from icarus_memory.proposals import ProposalStore
            from icarus_memory.server import create_app, _wire_scheduler, Summarizer
            from icarus_memory.tools import build_registry

            episodes = EpisodeStore(daten / 'episodes.sqlite3')
            claims = ClaimStore(daten / 'knowledge.sqlite3')
            proposals = ProposalStore(daten / 'proposals.sqlite3')
            audit = AuditLog(daten / 'audit.sqlite3')
            agent = Agent(store=SelfModelStore(MemoryBackend(), subject_id='messlatte'), policy=Policy(),
                          audit=audit, tools={}, provider=provider, knowledge=claims, episodes=episodes,
                          max_rounds=4)
            app = create_app(agent._store, agent=agent, audit=audit, proposals=proposals,
                             episodes=episodes, knowledge=claims)
            # Einstellung `suchindex.wortteile_jahre` wie im Betrieb: in den Einstellungen, der Start gleicht den Index ab.
            # Der Bestand ist noch leer, es zieht nichts um.
            from icarus_memory import suchindex_routes
            app.state.settings.suchindex = {'wortteile_jahre': wortteile_jahre}
            suchindex_routes.anwenden(app)
            agent._tools = build_registry(app.state.store, task_store=app.state.tasks,
                                          workspace=app.state.workspace, episodes=episodes)
            # Wie `_build_agent`: Kalenderstand und Abdeckung kommen aus dem Bestand der App.
            agent._calendar_context = lambda: local_snapshot(getattr(app.state, 'mac_calendar', None))
            agent._memory_coverage = lambda: memory_coverage(app.state.episodes, app.state.proposals)
            agent._eigene = lambda: list(eigene)
            # Rolle „frage“: der Anbieter der Messung (`--modell-frage`), sonst versteht der Rückfall die Frage.
            agent._frage_anbieter = lambda: frage_provider
            # Rolle „pruefung“ (zweites Tor der Satzprüfung): der Anbieter der Messung (`--modell-pruefung`), sonst
            # ist das Tor still aus wie im Produkt ohne Zuweisung.
            from icarus_memory import satzpruefung_modell
            agent._pruefung = lambda: satzpruefung_modell.tor('an', pruef_provider)
            app.state.summarizer = Summarizer(episodes, provider=provider)
            _wire_scheduler(app)
            client = TestClient(app, headers={'X-Icarus-Token': TOKEN})
            try:
                # Erst nach `create_app`: Die Routen lösen ihre Typangaben beim Bau auf,
                # und eine Ersatzklasse für `datetime` wäre dort kein gültiger Feldtyp.
                with eingefrorene_zeit(stichtag):
                    yield Instanz(wurzel, app, client, agent, episodes, claims, tuple(eigene))
            finally:
                client.close()
                app.state.scheduler.stop()
                for name in ('audit', 'tasks', 'workspace', 'episodes', 'proposals', 'conversations',
                             'claims', 'regeln'):
                    close = getattr(getattr(app.state, name, None), 'close', None)
                    if callable(close):
                        close()
