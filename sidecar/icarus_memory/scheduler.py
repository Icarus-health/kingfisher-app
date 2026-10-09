"""Der Prozess, der mitläuft.

Bis hierher passierte alles auf Zuruf: Aufnehmen, wenn jemand auf „Aufnehmen“
drückt; Verdichten, wenn jemand auf „Verdichten“ drückt. Für ein Werkzeug ist
das richtig. Für einen Assistenten, der ein Arbeitsleben begleiten soll, ist es
zu wenig — was nur passiert, wenn man daran denkt, passiert nicht.

## Was er darf und was nicht

Genau das, was die Verdichtung ohnehin darf: **ordnen, nicht behaupten.**

| Läuft von selbst | Passiert nie ohne Menschen |
| --- | --- |
| Ordner erneut einlesen (Digest verhindert Doppel) | Eine Aussage in den Bestand schreiben |
| Regelbasierte Vorschläge erzeugen | Einen Vorschlag annehmen |
| Alte Monate zusammenfassen (Quellen bleiben) | Eine Quelle löschen |
| Sicherung anlegen | Etwas Außenwirksames tun |

Der Zeitplan macht die Vorschlagsschlange voller, nicht den Bestand. Das ist
die einzige Eigenschaft, die diesen Prozess unbedenklich macht: Im schlimmsten
Fall entsteht Arbeit, die jemand ignoriert — nie ein falscher Fakt.

## Warum er standardmäßig aus ist

Zwei Gründe, und beide sind ernst.

**Kosten.** Die modellgestützte Ableitung ruft einen Anbieter. Ein Zeitplan, der
das ungefragt stündlich tut, gibt fremdes Geld aus. Deshalb ist nicht nur der
Zeitplan aus, sondern die Modellnutzung darin noch einmal getrennt zu schalten.

**Lärm.** Ein Prozess, der stündlich Unbrauchbares vorlegt, ist schlimmer als
keiner: Die Schlange wächst, niemand sieht mehr hinein, und dann ist auch das
Nützliche darin unsichtbar. Erst wenn die Vorschläge im Alltag taugen, gehört
der Takt hoch.

## Warum ein Thread und kein Cron

Icarus ist eine Desktop-App. Der Sidecar lebt, solange die App offen ist — ein
Systemdienst, der im Hintergrund weiterläuft, wäre eine andere Zusage als die,
die das Projekt gibt („alles bleibt auf diesem Rechner, und du siehst zu“).

Also: ein Thread im Sidecar. Er läuft, wenn die App läuft. Das ist ehrlich und
reicht: Wer die App eine Woche nicht öffnet, hat auch keine Vorschläge geprüft.

Im Container gilt dasselbe mit anderem Vorzeichen — dort läuft der Sidecar
dauerhaft, und der Zeitplan trägt tatsächlich durch die Nacht.
"""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from . import logbuch
from .restore_boundary import guarded

from .model import now

#: Kürzester zulässiger Abstand. Kein technisches Limit, sondern eine Bremse:
#: Alles darunter erzeugt Lärm, bevor jemand die erste Runde geprüft hat.
MIN_INTERVAL_MINUTES = 15

#: Voreinstellung, wenn jemand den Zeitplan einschaltet, ohne einen Takt zu
#: nennen. Vier Stunden heißt: ein paar Mal am Arbeitstag, nicht ständig.
DEFAULT_INTERVAL_MINUTES = 30
#: Höchstens so oft eine Sicherung im Zeitplan: Seit er alle 30 Minuten läuft, hielten 14 aufbewahrte Sicherungen
#: sonst nur sieben Stunden zurück statt gut zwei Tage.
SICHERUNG_ABSTAND = timedelta(hours=4)

#: Wie oft der Thread aufwacht, um zu prüfen, ob etwas fällig ist. Klein genug,
#: dass eine Änderung am Takt schnell greift, groß genug, um nichts zu kosten.
TICK_SECONDS = 30.0
PROMPT_BATCH_SIZE = 5
MAX_PENDING_UPLOADS = 200
PROMPT_PAUSE_SECONDS = 1.0


@dataclass
class JobResult:
    """Was ein einzelner Schritt getan hat."""

    name: str
    ok: bool = True
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunReport:
    started_at: datetime
    finished_at: datetime | None = None
    jobs: list[JobResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(j.ok for j in self.jobs)

    def to_dict(self) -> dict[str, Any]:
        def iso(v: datetime | None) -> str | None:
            return v.astimezone().isoformat() if v else None

        return {
            "started_at": iso(self.started_at),
            "finished_at": iso(self.finished_at),
            "ok": self.ok,
            "jobs": [j.to_dict() for j in self.jobs],
        }

    def summary(self) -> str:
        if not self.jobs:
            return "Nichts zu tun."
        return " · ".join(f"{j.name}: {j.detail or ('ok' if j.ok else 'Fehler')}"
                          for j in self.jobs)


class Scheduler:
    """Führt Aufnahme, Verdichtung und Sicherung nach Zeitplan aus.

    Die eigentliche Arbeit steckt in den übergebenen Funktionen. Diese Klasse
    kennt nur den Takt, den Zustand und die Regel, dass ein Fehler in einem
    Schritt die anderen nicht verhindert.
    """

    def __init__(
        self,
        run_ingest: Callable[[], list[JobResult]] | None = None,
        run_consolidation: Callable[[bool], JobResult] | None = None,
        run_backup: Callable[[], JobResult] | None = None,
        run_summary: Callable[[bool], JobResult] | None = None,
        run_task_detection: Callable[[bool], JobResult] | None = None,
        run_working_memory: Callable[[bool], JobResult] | None = None,
        run_prompt_working_memory: Callable[[list[str]], JobResult] | None = None,
    ) -> None:
        self._run_ingest = run_ingest
        self._run_consolidation = run_consolidation
        self._run_summary = run_summary
        self._run_task_detection = run_task_detection
        self._run_working_memory = run_working_memory
        self._run_prompt_working_memory = run_prompt_working_memory
        self._run_backup = run_backup
        #: Zwei Quellenversuche für neue/korrigierte Post zwischen großen Durchgängen.
        self._run_priority_tasks: Callable[[], JobResult] | None = None
        #: Lagen (Ebene 3) in kleinen Paketen; wie die Einordnung nur mit Modellprüfung und Freigabe.
        self._run_lage: Callable[[bool], JobResult] | None = None

        self._enabled = False
        self._interval = timedelta(minutes=DEFAULT_INTERVAL_MINUTES)
        self._with_model = False

        self._last: RunReport | None = None
        self._last_at: datetime | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._lock = threading.Lock()
        self._run_lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._restart_requested = False
        self._memory_pending: dict[str, None] = {}
        self._memory_active: set[str] = set()
        self._next_memory_at = 0.0
        #: Die Steuerung des Hintergrunds (`hintergrund.Steuerung`): Pause, Rücksicht, Reihenfolge, Drosselung.
        #: Ohne sie verhält sich der Zeitplan wie zuvor (etwa in Tests, die ihn allein prüfen).
        self._steuerung: Any = None
        #: Eine leichte Aufgabe, die bei jedem Aufwachen läuft, auch wenn der Zeitplan selbst aus ist (die tägliche
        #: Fassungsprüfung, `fassung_routes.py`). Sie entscheidet selbst, ob sie fällig ist, und wirft nie.
        self._nebenbei: Callable[[], None] | None = None

    def anschliessen(self, steuerung: Any) -> None:
        """Hängt die Steuerung an. Der letzte volle Durchgang kommt aus ihrem gemerkten Zustand.

        So läuft nach einem Neustart nicht sofort der teuerste Durchgang, sondern
        erst, wenn er fällig ist (oder nach dem Anlauf, wenn noch keiner gemerkt ist).
        """
        with self._lock:
            self._steuerung = steuerung
            if self._last_at is None:
                self._last_at = steuerung.erster_voller_lauf(self._interval)

    def nebenbei_setzen(self, aufgabe: Callable[[], None] | None) -> None:
        """Setzt (oder löst mit None) die leichte Aufgabe, die in jedem Takt läuft."""
        with self._lock:
            self._nebenbei = aufgabe

    def wecken(self) -> None:
        self._wake.set()

    def aufnahme_wecken(self) -> None:
        """Die Mailaufnahme beim nächsten Durchgang der Schleife laufen lassen, nicht erst nach dem Takt („Erneut versuchen“)."""
        self._next_intake_at = 0.0
        self._wake.set()

    # -- Einstellen --------------------------------------------------------

    def configure(
        self,
        enabled: bool | None = None,
        interval_minutes: int | None = None,
        with_model: bool | None = None,
    ) -> None:
        with self._lock:
            if enabled is not None:
                self._enabled = enabled
            if interval_minutes is not None:
                self._interval = timedelta(
                    minutes=max(MIN_INTERVAL_MINUTES, int(interval_minutes))
                )
            if with_model is not None:
                self._with_model = with_model
            if not self._enabled or not self._with_model:
                self._memory_pending.clear()

    def request_working_memory(self, episode_id: str) -> bool:
        """Queue only an episode ID; the ordinary scan remains the overflow path."""
        with self._lock:
            if (not episode_id or not isinstance(episode_id, str)
                    or not self._enabled or not self._with_model
                    or self._run_prompt_working_memory is None
                    or self._stop.is_set()
                    or self._thread is None or not self._thread.is_alive()):
                return False
            if episode_id in self._memory_pending or episode_id in self._memory_active:
                return True
            if len(self._memory_pending) >= MAX_PENDING_UPLOADS:
                # The source stays in SQLite for the ordinary scheduled scan.
                return False
            self._memory_pending[episode_id] = None
        self._wake.set()
        return True

    def memory_state(self, episode_id: str) -> str | None:
        with self._lock:
            if episode_id in self._memory_active:
                return 'processing'
            if episode_id in self._memory_pending:
                return 'queued'
        return None

    def _serve_waiting_uploads(self, report: RunReport, with_model: bool) -> None:
        """One bounded priority batch, between jobs while run_once owns run_lock.

        Do not interrupt an in-flight model call or create another model thread.
        A continuous upload stream cannot prevent the ordinary pass from ending.
        """
        with self._lock:
            if (not with_model or not self._enabled or not self._with_model
                    or self._stop.is_set() or self._run_prompt_working_memory is None):
                return
            ids = list(self._memory_pending)[:PROMPT_BATCH_SIZE]
            for identifier in ids:
                del self._memory_pending[identifier]
            self._memory_active.update(ids)
        if not ids:
            return
        try:
            report.jobs.append(self._run_prompt_working_memory(ids))
        except Exception:
            report.jobs.append(JobResult('gedaechtnis', False, 'Neue Quellen konnten noch nicht eingeordnet werden.'))
        finally:
            with self._lock:
                self._memory_active.difference_update(ids)
                self._next_memory_at = time.monotonic() + PROMPT_PAUSE_SECONDS

    def prompt_allowed(self) -> bool:
        with self._lock:
            return self._enabled and self._with_model and not self._stop.is_set()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def next_run(self) -> datetime | None:
        if not self._enabled:
            return None
        if self._last_at is None:
            return now()
        return self._last_at + self._interval

    def state(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "interval_minutes": int(self._interval.total_seconds() // 60),
            "with_model": self._with_model,
            "min_interval_minutes": MIN_INTERVAL_MINUTES,
            # Der Faden kann für die leichte Aufgabe laufen, während der Zeitplan aus ist; das ist kein laufender Plan.
            "running": self._enabled and self._thread is not None and self._thread.is_alive(),
            "last_run": self._last.to_dict() if self._last else None,
            "next_run": (
                self.next_run().astimezone().isoformat() if self.next_run() else None
            ),
        }

    # -- Laufen ------------------------------------------------------------

    @guarded
    def run_once(self, with_model: bool | None = None) -> RunReport:
        """Ein Durchgang. Auch von Hand auslösbar.

        Jeder Schritt ist einzeln fehlertolerant. Ein Mailserver, der hakt, darf
        nicht verhindern, dass die Sicherung läuft — genau diese Kopplung macht
        Hintergrundprozesse unbrauchbar, weil sie irgendwann ganz ausfallen und
        niemand merkt, warum.
        """
        # Handaufruf und Hintergrundlauf teilen dieselben Ablagen. Ein
        # zweiter Durchgang wartet, statt Aufnahme und Verdichtung zu mischen.
        with self._run_lock:
            return self._run_once(with_model)

    def _run_once(self, with_model: bool | None = None) -> RunReport:
        report = RunReport(started_at=now())
        modell = self._with_model if with_model is None else with_model

        if self._run_ingest is not None:
            try:
                report.jobs.extend(self._run_ingest())
            except Exception as exc:  # noqa: BLE001
                report.jobs.append(
                    JobResult("aufnahme", False, f"{type(exc).__name__}: {exc}")
                )

        if self._run_working_memory is not None:
            try:
                report.jobs.append(self._run_working_memory(modell))
            except Exception:
                report.jobs.append(JobResult("gedaechtnis", False, "Quellen konnten noch nicht eingeordnet werden."))

        if any((self._run_task_detection, self._run_consolidation, self._run_summary)):
            self._serve_waiting_uploads(report, modell)

        if self._run_lage is not None:
            try:
                report.jobs.append(self._run_lage(modell))
            except Exception:  # Keine Quelldaten oder Modellantworten im Status.
                report.jobs.append(JobResult("lage", False, "Lagen konnten noch nicht erstellt werden."))

        if self._run_task_detection is not None:
            try:
                report.jobs.append(self._run_task_detection(modell))
            except Exception:  # Keine fremden Quellen oder Modellantworten im Status.
                report.jobs.append(JobResult("zusagen", False, "Zusagen konnten nicht geprüft werden. Bitte erneut versuchen."))

        if self._run_consolidation is not None:
            try:
                report.jobs.append(self._run_consolidation(modell))
            except Exception as exc:  # noqa: BLE001
                report.jobs.append(
                    JobResult("verdichtung", False, f"{type(exc).__name__}: {exc}")
                )

        if self._run_summary is not None:
            try:
                report.jobs.append(self._run_summary(modell))
            except Exception as exc:  # noqa: BLE001
                report.jobs.append(
                    JobResult("zusammenfassung", False, f"{type(exc).__name__}: {exc}")
                )

        if self._run_backup is not None:
            try:
                report.jobs.append(self._run_backup())
            except Exception as exc:  # noqa: BLE001
                report.jobs.append(
                    JobResult("sicherung", False, f"{type(exc).__name__}: {exc}")
                )

        report.finished_at = now()
        logbuch.fehler_des_laufs(report.jobs)
        with self._lock:
            self._last = report
            self._last_at = report.finished_at
            steuerung = self._steuerung
        if steuerung is not None:
            steuerung.voller_lauf_fertig(report.finished_at)
        return report

    def _start_locked(self) -> None:
        self._stop.clear()
        self._wake.clear()
        self._thread = threading.Thread(
            target=self._worker, name="icarus-zeitplan", daemon=True
        )
        self._thread.start()

    def start(self) -> None:
        with self._lifecycle_lock:
            if self._thread is not None and self._thread.is_alive():
                if self._stop.is_set():
                    self._restart_requested = True
                return
            self._restart_requested = False
            self._start_locked()

    def stop(self, timeout: float = 5.0) -> None:
        with self._lifecycle_lock:
            self._restart_requested = False
            self._stop.set()
            with self._lock:
                self._memory_pending.clear()
            self._wake.set()
            worker = self._thread
        # Der auslaufende Worker benötigt die Lebenszyklus-Sperre selbst.
        # Während join darf sie deshalb nicht gehalten werden.
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=timeout)
        with self._lifecycle_lock:
            if self._thread is worker and worker is not None and not worker.is_alive():
                self._thread = None

    def _worker(self) -> None:
        from .hintergrund import als_hintergrund, niedrige_prioritaet
        # Dieser Faden ist der Hintergrund: niedrige Priorität, und jeder Modellaufruf darin
        # geht über die Ampel mit der Sperre der Steuerung (`hintergrund.ModellAmpel`).
        niedrige_prioritaet()
        def sperre():
            steuerung = self._steuerung
            if steuerung is None:
                return None
            # Manual pause keeps precedence in the UI, but must not hide an
            # energy interruption that needs to release this job's locks.
            external_gate = getattr(steuerung, 'external_gate', None)
            external = external_gate() if callable(external_gate) else None
            return external if external is not None else steuerung.sperre()
        try:
            with als_hintergrund(sperre, stopped=self._stop.is_set):
                self._loop()
        finally:
            with self._lifecycle_lock:
                if self._thread is threading.current_thread():
                    self._thread = None
                    if self._restart_requested:
                        self._restart_requested = False
                        self._start_locked()

    def _loop(self) -> None:
        from .hintergrund import BackgroundInterrupted
        while not self._stop.is_set():
            try:
                self._loop_until_interrupted()
            except BackgroundInterrupted:
                # A pause must unwind job/restore locks, not become a failed
                # source. Original sources remain pending for the next AC tick.
                # Finished memory sections are kept in its bounded RAM cache;
                # committed results and original sources remain intact.
                continue

    def _loop_until_interrupted(self) -> None:
        #: Pause, die die Steuerung nach einem Häppchen oder einer Sperre vorgibt (sonst der gewohnte Takt).
        pause: float | None = None
        while not self._stop.is_set():
            # In kleinen Schritten warten statt einmal lang: Sonst hängt das
            # Beenden der App am Takt, und vier Stunden Wartezeit fühlen sich
            # wie ein Absturz an.
            with self._lock:
                delay = max(0.0, self._next_memory_at - time.monotonic()) if self._memory_pending else TICK_SECONDS
            if pause is not None:
                delay = pause
            self._wake.wait(min(TICK_SECONDS, delay))
            self._wake.clear()
            pause = None
            if self._stop.is_set():
                return
            nebenbei = self._nebenbei
            if nebenbei is not None:
                try:
                    nebenbei()
                except Exception:  # noqa: BLE001 - der Thread darf nie sterben
                    pass
            steuerung = self._steuerung
            if steuerung is not None and self._enabled:
                if self._with_model:
                    steuerung.probe()
                # Pausiert, jemand arbeitet, eine Antwort entsteht: dieser Takt tut nichts.
                if steuerung.sperre() is not None:
                    pause = steuerung.wartezeit()
                    continue
            begonnen = time.monotonic()
            # Was morgen zählt, geht auch neuen Uploads vor (Reihenfolge nach Nutzen).
            vorrang = bool(steuerung is not None and self._enabled and self._with_model
                           and self._run_working_memory is not None and steuerung.dringend_offen())
            with self._lock:
                prompt = (not vorrang and bool(self._memory_pending) and self._enabled and self._with_model
                          and time.monotonic() >= self._next_memory_at)
                if prompt:
                    ids = list(self._memory_pending)[:PROMPT_BATCH_SIZE]
                    for episode_id in ids:
                        del self._memory_pending[episode_id]
                    self._memory_active.update(ids)
                    self._next_memory_at = time.monotonic() + PROMPT_PAUSE_SECONDS
            if prompt:
                try:
                    self._run_prompt_once(ids)
                except Exception:  # noqa: BLE001 - next scheduled pass may retry
                    pass
                finally:
                    with self._lock:
                        self._memory_active.difference_update(ids)
                # A steady stream of uploads must not starve an already due
                # ordinary pass (intake and backup share this same thread).
            if self._stop.is_set():
                return
            if not self._enabled:
                continue
            intake = getattr(self, '_run_mail_intake', None)
            if intake is not None and time.monotonic() >= getattr(self, '_next_intake_at', 0):
                self._next_intake_at = time.monotonic() + TICK_SECONDS
                try:
                    self._run_background_mail_intake()
                except Exception:
                    pass  # Restore boundary can reject work while recovery is pending.
            faellig = self.next_run()
            voller_lauf = faellig is not None and now() >= faellig
            if voller_lauf:
                try:
                    self.run_once()
                except Exception:  # noqa: BLE001 - der Thread darf nie sterben
                    # run_once fängt bereits jeden Schritt einzeln ab; was hier
                    # ankommt, wäre ein Fehler im Berichten selbst. Weiterlaufen
                    # ist trotzdem richtig: Ein Zeitplan, der nach einem
                    # Ausrutscher still aufhört, ist schlimmer als einer, der
                    # es erneut versucht.
                    with self._lock:
                        self._last_at = now()
            else:
                # Neue/korrigierte Aufgaben warten weder auf den großen Lauf noch auf die Upload-Schlange.
                try:
                    self._run_background_tasks()
                except Exception:
                    pass  # Auch die Restore-Sperre vor dem Aufruf darf den Zeitplanfaden nicht beenden.
            if not prompt and not voller_lauf:
                # Rückstände der lokalen Quellen-Einordnung laufen in kleinen
                # Batches zwischen den regulären (teuren) Aufnahme-/Sicherungs-
                # Durchgängen. Upload-Signale haben Vorrang; die Store-Seite
                # begrenzt den Batch und steuert Scan-Cursor sowie Backoff.
                self._run_background_working_memory(vorrang=vorrang)
                if not vorrang:
                    self._run_background_lage()
            if steuerung is not None:
                # Drosselung: Wer gearbeitet hat, ruht danach (höchstens die Hälfte der Zeit Arbeit).
                dauer = time.monotonic() - begonnen
                if dauer >= 0.5:
                    pause = steuerung.pause_nach(dauer)

    @guarded
    def _run_background_mail_intake(self):
        if not self._run_lock.acquire(blocking=False):
            return
        try:
            if self._enabled and not self._stop.is_set():
                callback = getattr(self, '_run_mail_intake', None)
                if callback is not None:
                    callback()
        finally:
            self._run_lock.release()

    @guarded
    def _run_background_tasks(self) -> None:
        """Begrenzte Wiedervorlage im selben Faden; alle Freigaben und Sperren gelten."""
        if self._run_priority_tasks is None or not self._run_lock.acquire(blocking=False):
            return
        try:
            with self._lock:
                permitted = self._enabled and self._with_model and not self._stop.is_set()
                steuerung = self._steuerung
            if permitted and (steuerung is None or steuerung.sperre() is None):
                try:
                    self._run_priority_tasks()
                except Exception:
                    pass  # Dauerhafte Wiedervorlage bleibt für den nächsten erlaubten Takt erhalten.
        finally:
            self._run_lock.release()

    def _run_background_working_memory(self, vorrang: bool = False) -> None:
        """Run one backlog batch only when no higher-priority work is waiting.

        Mit Steuerung kommen die Quellen in der Reihenfolge nach Nutzen
        (`hintergrund.ordnen`); `vorrang` heißt: nur die Stufe „morgen“, und zwar
        auch dann, wenn Uploads warten. Ohne Steuerung oder ohne geplante Quelle
        läuft der ordentliche Durchlauf des Speichers.
        """
        if self._run_working_memory is None or not self._run_lock.acquire(blocking=False):
            return
        try:
            with self._lock:
                permitted = (
                    self._enabled and self._with_model and not self._stop.is_set()
                    and (vorrang or (not self._memory_pending and not self._memory_active))
                )
                steuerung = self._steuerung
            if permitted:
                try:
                    ids = (steuerung.naechste_quellen(PROMPT_BATCH_SIZE, nur='morgen' if vorrang else None)
                           if steuerung is not None else [])
                    if ids:
                        self._run_working_memory(True, source_ids=ids)
                    elif not vorrang:
                        self._run_working_memory(True)
                except Exception:
                    # Wie beim regulären Schritt darf ein Fehler den Thread
                    # nicht beenden; der Store setzt den Retry-Backoff.
                    pass
        finally:
            self._run_lock.release()

    def _run_background_lage(self) -> None:
        """Ein kleines Paket Lagen, wenn nichts Dringenderes wartet (Einordnung neuer Quellen hat Vorrang).

        Derselbe Thread und dieselbe Sperre wie alle Hintergrundläufe: kein eigener Faden,
        keine zweite Modellanfrage nebenher.
        """
        if self._run_lage is None or not self._run_lock.acquire(blocking=False):
            return
        try:
            with self._lock:
                permitted = (
                    self._enabled and self._with_model and not self._stop.is_set()
                    and not self._memory_pending and not self._memory_active
                )
            if permitted:
                try:
                    self._run_lage(True)
                except Exception:
                    pass  # Der nächste Durchgang versucht es erneut; der Thread darf nie sterben.
        finally:
            self._run_lock.release()

    @guarded
    def _run_prompt_once(self, episode_ids: list[str]) -> JobResult:
        with self._run_lock:
            if not self.prompt_allowed():
                return JobResult('gedaechtnis', True, 'Einordnung nach geänderter Freigabe gestoppt.')
            return self._run_prompt_working_memory(episode_ids)


# -- Die Schritte -----------------------------------------------------------
#
# Bewusst hier und nicht im Server: Sie sind ohne HTTP prüfbar.


def ingest_job(
    episodes: Any, roots: list[Path], adapters: dict[str, str], *, on_source=None, on_complete=None,
    on_transcript=None,
) -> Callable[[], list[JobResult]]:
    """Liest die eingestellten Ordner erneut ein.

    Dass ein zweiter Lauf über denselben Vault nichts doppelt anlegt, ist keine
    Nettigkeit, sondern die Voraussetzung dafür, dass dieser Schritt überhaupt
    wiederholbar ist — sie steckt im Digest der Episodenschicht.
    """
    from .ingest import ingest_directory

    def run() -> list[JobResult]:
        ergebnisse: list[JobResult] = []
        for pfad, adapter in adapters.items():
            try:
                report = ingest_directory(episodes, pfad, adapter, roots=roots, on_source=on_source, on_complete=on_complete,
                                          on_transcript=on_transcript)
                ergebnisse.append(JobResult(
                    f"aufnahme:{Path(pfad).name}",
                    not report.errors,
                    f"{report.recorded} neu, {report.duplicates} bekannt, {report.skipped} übersprungen, {report.changed} geändert, {report.removed} entfernt"
                    + (". " + " · ".join(report.errors[:3]) if report.errors else ""),
                ))
            except Exception as exc:  # noqa: BLE001 - ein Ordner darf den Lauf nicht kippen
                ergebnisse.append(JobResult(
                    f"aufnahme:{Path(pfad).name}", False, f"{type(exc).__name__}: {exc}"
                ))
        return ergebnisse

    return run


def consolidation_job(consolidator: Any) -> Callable[[bool], JobResult]:
    def run(with_model: bool) -> JobResult:
        report = consolidator.run(with_model=with_model)
        return JobResult("verdichtung", not report.errors, report.summary())

    return run


def summary_job(summarizer: Any) -> Callable[[bool], JobResult]:
    """Fasst alte Monate zusammen — nach der Verdichtung, nicht davor.

    Die Reihenfolge ist keine Feinheit: Zusammenfassen archiviert die Quellen.
    Liefe es zuerst, verschwände Material aus der Verdichtung, das noch nie
    jemand angesehen hat. So sieht die Verdichtung erst alles, und erst danach
    wird gekürzt.
    """
    def run(with_model: bool) -> JobResult:
        report = summarizer.run(with_model=with_model)
        return JobResult("zusammenfassung", not report.errors, report.summary())

    return run


def backup_job(data_dir: Path) -> Callable[[], JobResult]:
    """Legt einen Snapshot an — der billigste Schritt mit dem größten Nutzen.

    Ein Gedächtnis, das zwanzig Jahre halten soll, hat genau einen
    katastrophalen Fehlerfall, und eine Sicherung, die nur läuft, wenn jemand
    daran denkt, verhindert ihn nicht.
    """
    from .backup import list_snapshots, snapshot_all

    def run() -> JobResult:
        datenbanken = list(data_dir.glob("*.sqlite3"))
        juengste = next((s for s in list_snapshots(data_dir / "sicherungen") if s.get("kind") == "kingfisher-snapshot"), None)
        if datenbanken and juengste is not None:
            try:
                erstellt = datetime.fromisoformat(str(juengste["created"]))
            except ValueError:
                erstellt = None
            if erstellt is not None and erstellt.tzinfo is not None and now() - erstellt < SICHERUNG_ABSTAND:
                return JobResult("sicherung", True, "letzte Sicherung ist jünger als vier Stunden")
        if not datenbanken:
            # Beim ersten Start gibt es noch nichts zu sichern, und im
            # Speicherbetrieb nie. Das als Fehler zu melden hieße, dass ein
            # neuer Nutzer bei jedem Lauf einen roten Schritt sieht — und wer
            # sich an rote Meldungen gewöhnt, übersieht die eine, die zählt.
            return JobResult("sicherung", True, "nichts zu sichern")
        pfad = snapshot_all(data_dir, data_dir / "sicherungen")
        return JobResult("sicherung", True, pfad.name)

    return run


__all__ = [
    "DEFAULT_INTERVAL_MINUTES",
    "MIN_INTERVAL_MINUTES",
    "TICK_SECONDS",
    "JobResult",
    "RunReport",
    "Scheduler",
    "backup_job",
    "consolidation_job",
    "ingest_job",
]
