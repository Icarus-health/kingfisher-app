"""Automatische lokale Einordnung; der Quellenbestand und bestätigte Claims bleiben getrennt."""
from .memory_analysis import model_key
from . import abschnitte
from .working_memory_analysis import UnsupportedSource, abschnitte_der, interpret_abschnitt
from .working_memory_store import WorkingMemoryStore, source_fingerprint
from .scheduler import JobResult
from .hintergrund import BackgroundInterrupted
from collections import OrderedDict, deque
import threading
import time

#: So viele Abschnitte (Modellaufrufe) darf ein Paket mindestens bearbeiten; ein Paket mit mehr Quellen darf je Quelle
#: einen. Eine lange Quelle bekommt damit nie alle ihre Abschnitte in einem Paket, sondern Häppchen über mehrere.
ABSCHNITTE_JE_PAKET = 8


class Zwischenstand:
    """Fertige Abschnitte langer Quellen zwischen zwei Paketen, nur im Speicher.

    Gemerkt werden Stellen und Arten ({start, end, kind}), nie Text. Der Eintrag gilt für genau eine Fassung der Quelle
    (Fingerabdruck) und ein Modell; ändert sich eines, fängt die Quelle von vorn an. Nach einem Neustart fehlt er:
    Die Abschnitte werden dann erneut eingeordnet, der Bestand bleibt davon unberührt, denn geschrieben wird erst
    mit dem letzten Abschnitt (`WorkingMemoryStore.commit`).
    """

    def __init__(self, maximum: int = 256):
        self._maximum = maximum
        self._eintraege: OrderedDict[str, tuple[str, str, list]] = OrderedDict()
        self._lock = threading.Lock()

    def holen(self, episode_id: str, fingerprint: str, modell: str) -> list:
        with self._lock:
            eintrag = self._eintraege.get(episode_id)
            if eintrag is None or eintrag[0] != fingerprint or eintrag[1] != modell:
                return []
            return list(eintrag[2])

    def ablegen(self, episode_id: str, fingerprint: str, modell: str, ergebnisse: list) -> None:
        with self._lock:
            self._eintraege[episode_id] = (fingerprint, modell, list(ergebnisse))
            self._eintraege.move_to_end(episode_id)
            while len(self._eintraege) > self._maximum:
                self._eintraege.popitem(last=False)

    def verwerfen(self, episode_id: str) -> None:
        with self._lock:
            self._eintraege.pop(episode_id, None)

    def offene(self) -> list[str]:
        """Quellen mit angefangener Arbeit, die älteste zuerst."""
        with self._lock:
            return list(self._eintraege)


STAND = Zwischenstand()
"""Der Zwischenstand des Produkts (ein Prozess, ein Bestand); Tests geben einen eigenen mit."""


class Pace:
    """Tatsächlicher Durchsatz der Hintergrund-Einordnung, nur im Speicher.

    Misst Wanduhrzeit zwischen Paketen einschließlich der Pausen, weil genau
    das bestimmt, wann der Rückstand abgebaut ist. Ohne mindestens zwei Pakete
    mit Ergebnis gibt es keine Schätzung; geraten wird nicht.
    """

    def __init__(self, window: int = 12, clock=time.monotonic):
        self._runs = deque(maxlen=window)
        self._clock = clock
        self._lock = threading.Lock()

    def record(self, processed: int) -> None:
        if processed > 0:
            with self._lock:
                self._runs.append((self._clock(), processed))

    def seconds_per_source(self) -> float | None:
        with self._lock:
            runs = list(self._runs)
        if len(runs) < 2:
            return None
        elapsed = runs[-1][0] - runs[0][0]
        processed = sum(count for _, count in runs[1:])
        if elapsed <= 0 or processed <= 0:
            return None
        return elapsed / processed

    def estimate(self, remaining: int) -> int | None:
        pace = self.seconds_per_source()
        return None if pace is None or remaining <= 0 else int(round(remaining * pace))


def _abschnitte_einordnen(snapshot, provider, plan, bisher, rest, lock, permitted, initial_model,
                          processing_policy=None):
    """Gibt Ergebnisse, Verbrauch, gestoppt und ggf. den geordneten Abbruch zurück."""
    ergebnisse = list(bisher)
    verbraucht = 0
    while len(ergebnisse) < len(plan) and verbraucht < rest:
        with lock:
            if not permitted() or model_key(provider) != initial_model:
                return ergebnisse, verbraucht, True, None
        try:
            ergebnisse.append(interpret_abschnitt(provider, snapshot.episode, plan[len(ergebnisse)], len(plan),
                                                   policy=processing_policy))
        except BackgroundInterrupted as interruption:
            # Save completed sections in the caller before unwinding job locks.
            return ergebnisse, verbraucht, True, interruption
        verbraucht += 1
    return ergebnisse, verbraucht, False, None


def run(episodes, provider, lock, *, permitted=lambda: True, limit=5,
        source_ids: list[str] | None = None, pace: Pace | None = None,
        abschnitte_je_lauf: int | None = None, stand: Zwischenstand | None = None,
        processing_policy=None):
    """Ein Paket Einordnung: bis `limit` Quellen, höchstens `abschnitte_je_lauf` Modellaufrufe.

    Eine lange Quelle geht in Abschnitten durch das Modell (`abschnitte.py`). Reicht das Maß des Pakets nicht für alle,
    merkt sich `stand` die fertigen Abschnitte, und die Quelle kommt im nächsten Paket zuerst wieder dran; in den
    Bestand geschrieben wird erst, wenn der letzte Abschnitt fertig ist. Ein Fehler oder eine Änderung der Quelle
    wirft den Zwischenstand der Quelle weg.
    """
    local = provider is not None and getattr(provider, 'is_local', False)
    scoped_remote = (provider is not None and callable(processing_policy)
                     and getattr(provider, 'is_remote', False))
    if provider is None or (not local and not scoped_remote):
        return JobResult('gedaechtnis', True, 'Für die automatische Einordnung wird ein lokales Modell benötigt.')
    stand = STAND if stand is None else stand
    store = WorkingMemoryStore(episodes)
    initial_model = model_key(provider)
    rest = max(ABSCHNITTE_JE_PAKET, limit) if abschnitte_je_lauf is None else max(1, abschnitte_je_lauf)
    with lock:
        if not permitted():
            return JobResult('gedaechtnis', True, 'Einordnung nach geänderter Freigabe gestoppt.')
        # Angefangene Quellen zuerst, dann neue; der Scan-Zeiger rückt nur um die Zahl der freien Plätze vor.
        angefangen = stand.offene()
        fortsetzen = store.pending(limit=min(limit, 200), episode_ids=angefangen) if angefangen else []
        for kennung in set(angefangen) - {s.episode.id for s in fortsetzen}:
            stand.verwerfen(kennung)  # inzwischen eingeordnet, zurückgestellt, geändert oder entzogen
        frei = limit - len(fortsetzen)
        neu = store.pending(limit=frei, episode_ids=source_ids) if frei >= 1 else []
        bekannt = {s.episode.id for s in fortsetzen}
        sources = fortsetzen + [s for s in neu if s.episode.id not in bekannt]
    completed = failed = deferred = teil = 0
    for nummer, snapshot in enumerate(sources):
        if rest <= 0:
            # Das Maß des Pakets ist aufgebraucht. Was noch fehlt, bleibt offen und kommt im nächsten Paket zuerst dran.
            for uebrig in sources[nummer:]:
                if not stand.holen(uebrig.episode.id, source_fingerprint(uebrig), initial_model):
                    stand.ablegen(uebrig.episode.id, source_fingerprint(uebrig), initial_model, [])
            break
        with lock:
            if not permitted() or model_key(provider) != initial_model:
                break
            if not store.is_current(snapshot):
                stand.verwerfen(snapshot.episode.id)
                continue
        episode = snapshot.episode
        fingerprint = source_fingerprint(snapshot)
        policy = processing_policy(snapshot) if callable(processing_policy) else None
        try:
            plan = abschnitte_der(episode)
            bisher = stand.holen(episode.id, fingerprint, initial_model)
            ergebnisse, verbraucht, gestoppt, interruption = _abschnitte_einordnen(
                snapshot, provider, plan, bisher, rest, lock, permitted, initial_model,
                processing_policy=policy)
        except UnsupportedSource:
            stand.verwerfen(episode.id)
            with lock:
                if permitted():
                    store.defer(snapshot)
            deferred += 1
            continue
        except Exception:
            # Weder fremde Texte noch Anbieterantworten im Betriebsstatus speichern.
            stand.verwerfen(episode.id)
            with lock:
                if permitted():
                    store.fail(snapshot)
            failed += 1
            continue
        rest -= verbraucht
        if gestoppt:
            stand.ablegen(episode.id, fingerprint, initial_model, ergebnisse)
            if interruption is not None:
                raise interruption
            break
        if len(ergebnisse) < len(plan):
            stand.ablegen(episode.id, fingerprint, initial_model, ergebnisse)
            teil += 1
            continue
        with lock:
            if not permitted() or model_key(provider) != initial_model:
                break
            stand.verwerfen(episode.id)
            completed += int(store.commit(snapshot, abschnitte.zusammenfuehren(ergebnisse), model=initial_model))
    if pace is not None:
        pace.record(completed + deferred)
    detail = f'{completed} Quellen automatisch eingeordnet'
    if teil:
        detail += f', {teil} lange Quellen in Abschnitten noch in Arbeit'
    if deferred:
        detail += f', {deferred} mit unvollständiger oder zu umfangreicher Grundlage'
    if failed:
        detail += f', {failed} noch nicht verarbeitet; erneuter Versuch folgt'
    return JobResult('gedaechtnis', failed == 0, detail)
