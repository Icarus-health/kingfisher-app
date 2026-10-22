"""Cloud-Einordnung neuer Mails: Anthropic (Claude API) mit eigener Einwilligung, getrennt von der Rolle `hintergrund`.

Was es tut: Ist der Schalter „Neue Mails in der Cloud einordnen“ an (Rolle `hintergrund`, Anbieter `anthropic`,
gültige Einwilligung, vorbereiteter Claude-Zugang unter KI & Modelle), dann laufen genau drei Alltagsläufe über einen
eingegrenzten `AnthropicImportProvider`: die Einordnung (`working_memory_worker`), Themen und Entitäten
(`memory_categories.Categories`) und Bitten und Zusagen (`task_detection` mit `memory_analysis.interpret` und
`task_review.review_tasks`). Jede Quelle bekommt dafür ihre eigene `ExplicitSourcePolicy`, die bei jedem Aufruf neu
prüft, ob sie noch gehen darf (`Einordnung.freigegeben`).

Was es nie tut:

* nie Verdichtung, nie Zusammenfassungen, nie Lage, nie Entwürfe oder Mailhilfe, nie Überblicke, nie Prüfung,
  Einbettung oder Texterkennung: all das fragt `rollen_von(app).provider("hintergrund")`, und der bleibt lokal oder
  None (`model_roles.anbieter_nur_lokal`);
* nie ohne Einwilligung für genau diese Rolle (die Einwilligung der Antwort gilt nicht), nie mit einem anderen
  Anbieter als Anthropic, nie ohne den vorbereiteten Zugang mit derselben Zugangsfassung wie beim Bau;
* nie etwas anderes als eine Mail (`SourceType.EMAIL`), nie eine Mail, die der Vorfilter aussortiert, nie eine
  geänderte oder zurückgezogene Fassung;
* nie über dem Tagesbudget (`TAGESBUDGET` Aufrufe je Kalendertag, gezählt in `hintergrund_cloud.sqlite`);
* nie bei Pause, Akku- oder Speichersperre (`hintergrund.modellarbeit_frei`), nie ohne freigegebenen Zeitplan.

Das Datum des Tagesbudgets ist der UTC-Kalendertag (`heute`): ein fester Wechsel um Mitternacht UTC ist für den
Nutzer in Europa ein Wechsel am frühen Morgen und braucht keine Zeitzoneneinstellung.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import logbuch
from .cloud_credentials import PREPARED_CLOUD_KEYS
from .cloud_import_provider import AnthropicImportProvider, credential_status
from .model import SourceType
from .model_roles import TAGESBUDGET, rollen_von
from .providers import ProviderError
from .source_processing_policy import ExplicitSourcePolicy, ScopedProvider
from .working_memory_store import WorkingMemoryStore

DATEI = "hintergrund_cloud.sqlite"
SATZ_ERSCHOEPFT = f"Heute sind die {TAGESBUDGET} Cloud-Aufrufe aufgebraucht; morgen geht es weiter."
SATZ_ANDERE_QUELLEN = "Andere Quellen als Mails warten auf ein lokales Modell."


def heute() -> str:
    """Der Kalendertag des Budgets (UTC, ISO-Datum); Tests ersetzen die Funktion."""
    return datetime.now(timezone.utc).date().isoformat()


class Tagesbudget:
    """Zählt die Aufrufe je Kalendertag in einer eigenen kleinen SQLite-Datei; überdauert Neustarts."""

    def __init__(self, pfad: Path) -> None:
        self.pfad = Path(pfad)
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._vermerkt: str | None = None
        with self._verbinden() as db:
            db.execute("CREATE TABLE IF NOT EXISTS anfragen(tag TEXT PRIMARY KEY, anzahl INTEGER NOT NULL)")

    def _verbinden(self) -> sqlite3.Connection:
        return sqlite3.connect(self.pfad, timeout=10)

    def stand(self, tag: str | None = None) -> int:
        tag = heute() if tag is None else tag
        with self._lock, self._verbinden() as db:
            row = db.execute("SELECT anzahl FROM anfragen WHERE tag=?", (tag,)).fetchone()
        return int(row[0]) if row else 0

    def erschoepft(self, tag: str | None = None) -> bool:
        return self.stand(tag) >= TAGESBUDGET

    def zaehlen(self, tag: str | None = None) -> bool:
        """Zählt einen Aufruf; `False` (und nichts gezählt), wenn das Budget des Tages erreicht ist."""
        tag = heute() if tag is None else tag
        with self._lock, self._verbinden() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT anzahl FROM anfragen WHERE tag=?", (tag,)).fetchone()
            anzahl = int(row[0]) if row else 0
            if anzahl >= TAGESBUDGET:
                erster = self._vermerkt != tag
                self._vermerkt = tag
            else:
                db.execute("INSERT INTO anfragen(tag, anzahl) VALUES(?,?) ON CONFLICT(tag) DO UPDATE SET anzahl=excluded.anzahl",
                           (tag, anzahl + 1))
                return True
        if erster:
            logbuch.vermerke("cloud_einordnung", tag=tag, tagesbudget=TAGESBUDGET)
        return False


def budget(app: Any) -> Tagesbudget:
    """Das Tagesbudget der Anwendung, einmal je Prozess gebaut (Datei im Datenverzeichnis)."""
    gemerkt = getattr(app.state, "hintergrund_cloud_budget", None)
    if gemerkt is None:
        from .server import _data_dir
        gemerkt = Tagesbudget(_data_dir() / DATEI)
        app.state.hintergrund_cloud_budget = gemerkt
    return gemerkt


def _zugang(app: Any) -> dict[str, Any]:
    return credential_status(getattr(app.state, "keychain", None), app.state.settings)


def anbieter(app: Any) -> AnthropicImportProvider | None:
    """Der Cloud-Anbieter der Einordnung, oder None: nur mit gültiger Einwilligung der Rolle und vorbereitetem Zugang.

    Wird jedes Mal neu gebaut (an die Zugangsfassung gebunden wie `cloud_memory_routes.build_api_provider`); nichts wird
    über Einstellungen hinweg gemerkt. Ohne Einwilligung fragt das den Schlüsselspeicher gar nicht erst.
    """
    if rollen_von(app).hintergrund_cloud_wahl() is None:
        return None
    zugang = _zugang(app)
    schluessel = os.environ.get(PREPARED_CLOUD_KEYS["anthropic"])
    if not zugang.get("available") or not zugang.get("model") or not schluessel:
        return None
    return AnthropicImportProvider(zugang["model"], schluessel, zugang["credential_revision"],
                                   lambda: _zugang(app).get("credential_revision"))


def aktiv(app: Any) -> bool:
    return anbieter(app) is not None


def einordnung_moeglich(app: Any, episode: Any = None) -> bool:
    """Kann eine Quelle eingeordnet werden: lokales Modell, oder (nur für Mails) die Cloud-Einordnung."""
    lokal = bool(getattr(rollen_von(app).provider("hintergrund"), "is_local", False))
    if lokal:
        return True
    if episode is not None and not ist_mail(episode):
        return False
    return aktiv(app)


def ist_mail(quelle: Any) -> bool:
    episode = getattr(quelle, "episode", quelle)
    return getattr(getattr(episode, "provenance", None), "source_type", None) is SourceType.EMAIL


def stand(app: Any) -> dict[str, Any]:
    """Der Stand für Oberfläche und Automatik; ohne Rohtext, ohne Schlüssel."""
    wahl = rollen_von(app).hintergrund_cloud_wahl()
    zugang = _zugang(app)
    zaehler = budget(app)
    return {"aktiv": wahl is not None and bool(zugang.get("available")),
            "modell": zugang.get("model", "") if zugang.get("available") else "",
            "seit": wahl.cloud_einwilligung if wahl is not None else None,
            "heute": zaehler.stand(), "tagesbudget": TAGESBUDGET,
            "erschoepft": zaehler.erschoepft(),
            "zugang_da": bool(zugang.get("available"))}


class Einordnung:
    """Ein Lauf der Cloud-Einordnung: ein eingegrenzter Anbieter, je Quelle eine Policy.

    `scoped` ist der Anbieter, den Einordnung, Themen und Zusagenerkennung bekommen (stabil für `model_key`);
    `policy_for(quelle)` bindet ihn an genau eine Quelle, oder gibt None, wenn die Quelle nicht in die Cloud darf
    (kein Mail, nicht aktuell). Die Läufe überspringen Quellen ohne Policy, statt sie als gescheitert zu merken.
    """

    def __init__(self, app: Any, provider: AnthropicImportProvider, *, plan_at_start: dict | None = None,
                 agent: Any = None) -> None:
        self.app = app
        self.provider = provider
        self.memory = WorkingMemoryStore(app.state.episodes)
        self._wahl = rollen_von(app).hintergrund_cloud_wahl()
        self._agent = agent
        self._gebunden: tuple[Any, Any] | None = None  # (episode, snapshot) der laufenden Quelle
        self.scoped = ScopedProvider(provider, None, self._vor_dem_senden)

    # -- Freigabe je Aufruf ----------------------------------------------------------------------------------------

    def freigegeben(self, episode: Any, snapshot: Any) -> bool:
        """Darf diese Quelle jetzt (noch) in die Cloud? Bei jedem Aufruf neu geprüft."""
        app = self.app
        try:
            from .hintergrund import modellarbeit_frei
            from .mail_filter import classify_episode, policy as filter_policy
            wahl = rollen_von(app).hintergrund_cloud_wahl()
            if wahl is None or self._wahl is None or wahl.cloud_einwilligung != self._wahl.cloud_einwilligung:
                return False
            if not self.provider.available():
                return False
            plan = app.state.settings.schedule
            if not plan.enabled or not plan.with_model:
                return False
            if self._agent is not None and getattr(app.state, "agent", None) is not self._agent:
                return False
            if not modellarbeit_frei(app):
                return False
            if not ist_mail(episode):
                return False
            if not classify_episode(episode, filter_policy(app.state.settings)).include:
                return False
            if snapshot is None or not self.memory.is_current(snapshot):
                return False
            if self.memory.source_state(snapshot.episode.id) in {"excluded", "dismissed"}:
                return False  # zurückgezogen oder ausdrücklich ausgeschlossen
            return getattr(episode, "id", None) == snapshot.episode.id and getattr(episode, "digest", None) == snapshot.episode.digest
        except Exception:  # noqa: BLE001 - im Zweifel nichts senden
            return False

    def _vor_dem_senden(self) -> None:
        with self.app.state.conversation_lock:
            if self._gebunden is None or not self.freigegeben(*self._gebunden):
                raise ProviderError("Die Freigabe oder Quellenfassung hat sich geändert.")
            if not budget(self.app).zaehlen():
                raise ProviderError("Das Tagesbudget der Cloud-Einordnung ist erreicht.")

    def eingegrenzt(self, quelle: Any) -> tuple[ScopedProvider, ExplicitSourcePolicy | None]:
        """Der eingegrenzte Anbieter samt Policy für diese Quelle (Snapshot oder Episode); Policy None = nicht vorgesehen."""
        episode = getattr(quelle, "episode", quelle)
        snapshot = quelle if hasattr(quelle, "episode") else self.memory._snapshot(getattr(episode, "id", ""))
        if not ist_mail(episode) or snapshot is None or not self.memory._eligible(snapshot):
            return self.scoped, None
        # Was der Vorfilter aussortiert (Werbung, gesperrte Absender) oder was zurückgezogen ist, bleibt unberührt
        # liegen (wartet auf ein lokales Modell), statt als gescheitert zu gelten.
        try:
            from .mail_filter import classify_episode, policy as filter_policy
            if (not classify_episode(episode, filter_policy(self.app.state.settings)).include
                    or self.memory.source_state(episode.id) in {"excluded", "dismissed"}):
                return self.scoped, None
        except Exception:  # noqa: BLE001 - im Zweifel nicht in die Cloud
            return self.scoped, None
        policy = ExplicitSourcePolicy(self.scoped, episode.id, lambda ep: self.freigegeben(ep, snapshot))
        self._gebunden = (episode, snapshot)
        self.scoped._episode = episode
        self.scoped._policy = policy
        return self.scoped, policy

    def policy_for(self, quelle: Any) -> ExplicitSourcePolicy | None:
        return self.eingegrenzt(quelle)[1]


def eingegrenzt(app: Any, provider: AnthropicImportProvider, quelle: Any) -> tuple[ScopedProvider, ExplicitSourcePolicy | None]:
    """Kurzform für eine einzelne Quelle (Prüfungen): `(scoped, policy)`; Policy None, wenn die Quelle nicht in die Cloud darf."""
    return Einordnung(app, provider).eingegrenzt(quelle)


__all__ = ["DATEI", "SATZ_ANDERE_QUELLEN", "SATZ_ERSCHOEPFT", "TAGESBUDGET", "Einordnung", "Tagesbudget", "aktiv",
           "anbieter", "budget", "eingegrenzt", "einordnung_moeglich", "heute", "ist_mail", "stand"]
