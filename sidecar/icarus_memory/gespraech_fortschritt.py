"""Zwischenstand einer Gesprächsantwort und Vorwärmen des Antwortmodells (Paket T, 26.10.2026).

Eine Gedächtnisantwort braucht lokal oft viele Sekunden. Bisher stand währenddessen nur „Kingfisher antwortet …“.
Jetzt sagt die Oberfläche den echten Schritt, den der Sidecar gerade geht, und nichts Erfundenes (keine geschätzte
Restzeit):

    GET  /api/v1/conversations/{id}/fortschritt   {"laeuft": bool, "schritt": str|None, "satz": str|None}
    POST /api/v1/gespraech/vorwaermen             {"ergebnis": str, "cloud": bool}

Die Schritte kommen aus der Zeitmessung (`zeitmessung.melde`, beim Beginn jedes Abschnitts) und aus zwei Stellen im
Agenten (Frage verstehen, freies Gespräch). Gespeichert wird nur der Name des Schritts je Gespräch, nie ein Fragetext,
und nur, solange die Antwort läuft (`laeuft`). Der Abruf nimmt keine Sperre des Gesprächs: Er antwortet sofort, auch
während die Antwort entsteht.

`vorwaermen` lädt das lokale Antwortmodell (Rolle `antwort`) im Hintergrund, wenn ein Gespräch geöffnet wird
(`ollama_memory.vorwaermen`): nie, wenn es kein lokales Modell ist, nie, solange ein Hintergrundaufruf läuft, und
höchstens einmal je Minute. `cloud` sagt der Oberfläche, ob Gedächtnisantworten gerade über die Cloud laufen dürfen
(gültige Einwilligung), damit der Satz „Lokal dauert das …“ nur erscheint, wenn die Cloud aus ist.
"""
from __future__ import annotations

import threading
from contextlib import ExitStack, contextmanager
from typing import Any, Iterator

from . import gedaechtnis_cloud, ollama_memory, zeitmessung

#: Schritt -> Satz für die Oberfläche. Die Namen sind die Abschnitte der Zeitmessung plus `start` und `chat`.
SAETZE = {
    'start': 'Liest deine Frage …',
    'frage': 'Versteht die Frage …',
    'suche': 'Sucht in deinen Quellen …',
    'antwort_modell': 'Wählt Quellen …',
    'saetze_modell': 'Formuliert …',
    'satzpruefung': 'Prüft die Sätze …',
    'pruefung_modell': 'Prüft die Sätze …',
    'chat': 'Formuliert …',
}


class Fortschritt:
    """Der laufende Schritt je Gespräch; mehrere gleichzeitige Anfragen eines Gesprächs zählen mit."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stand: dict[str, tuple[str, int]] = {}

    def beginne(self, gespraech: str) -> None:
        with self._lock:
            _, zahl = self._stand.get(gespraech, ('start', 0))
            self._stand[gespraech] = ('start', zahl + 1)

    def setze(self, gespraech: str, schritt: str) -> None:
        if schritt not in SAETZE:
            return
        with self._lock:
            if gespraech in self._stand:
                self._stand[gespraech] = (schritt, self._stand[gespraech][1])

    def ende(self, gespraech: str) -> None:
        with self._lock:
            schritt, zahl = self._stand.get(gespraech, ('start', 1))
            if zahl <= 1:
                self._stand.pop(gespraech, None)
            else:
                self._stand[gespraech] = (schritt, zahl - 1)

    def lesen(self, gespraech: str) -> dict[str, Any]:
        with self._lock:
            stand = self._stand.get(gespraech)
        if stand is None:
            return {'laeuft': False, 'schritt': None, 'satz': None}
        return {'laeuft': True, 'schritt': stand[0], 'satz': SAETZE[stand[0]]}


def _fortschritt(app: Any) -> Fortschritt:
    stand = getattr(app.state, 'gespraech_fortschritt', None)
    if not isinstance(stand, Fortschritt):
        stand = Fortschritt()
        app.state.gespraech_fortschritt = stand
    return stand


@contextmanager
def laeuft(app: Any, gespraech: str) -> Iterator[None]:
    """Um eine Gesprächsantwort: Zwischenstand führen und das Antwortmodell danach warm halten.

    Wirft selbst nie in die Antwort hinein; ein Fehler im Zwischenstand kostet keine Antwort.
    """
    stand = _fortschritt(app)
    stand.beginne(gespraech)
    agent = getattr(app.state, 'agent', None)
    try:
        with ExitStack() as stapel:
            stapel.enter_context(zeitmessung.beobachten(lambda schritt: stand.setze(gespraech, schritt)))
            stapel.enter_context(ollama_memory.im_gespraech(getattr(agent, 'provider', None)))
            yield
    finally:
        stand.ende(gespraech)


def cloud_an(app: Any) -> bool:
    """Laufen Gedächtnisantworten gerade über die Cloud (Einwilligung der Rolle `antwort` gültig)?"""
    agent = getattr(app.state, 'agent', None)
    try:
        return gedaechtnis_cloud.freigabe_gueltig(app, getattr(agent, 'provider', None))
    except Exception:  # noqa: BLE001 - im Zweifel: nein
        return False


def vorwaermen(app: Any, *, im_hintergrund: bool = True) -> str:
    """Startet das Vorwärmen des lokalen Antwortmodells; wartet nicht darauf. Gibt zurück, ob es läuft."""
    from .hintergrund import AMPEL
    agent = getattr(app.state, 'agent', None)
    anbieter = getattr(agent, 'provider', None)
    if ollama_memory._lokaler_ollama(anbieter) is None:  # kein lokales Modell: kein einziger Aufruf
        return 'kein_lokales_modell'

    def beschaeftigt() -> bool:
        belegt = AMPEL.belegt()
        return bool(belegt.get('vorne') or belegt.get('hinten'))

    if beschaeftigt():
        return 'beschaeftigt'
    if not im_hintergrund:
        return ollama_memory.vorwaermen(anbieter, beschaeftigt=beschaeftigt)
    threading.Thread(target=ollama_memory.vorwaermen, args=(anbieter,), kwargs={'beschaeftigt': beschaeftigt},
                     daemon=True, name='kingfisher-vorwaermen').start()
    return 'laeuft'


def register(app: Any, guard: Any) -> None:
    @app.get('/api/v1/conversations/{conversation_id}/fortschritt', dependencies=guard)
    def gespraech_fortschritt(conversation_id: str) -> dict[str, Any]:
        return _fortschritt(app).lesen(conversation_id)

    @app.post('/api/v1/gespraech/vorwaermen', dependencies=guard)
    def gespraech_vorwaermen() -> dict[str, Any]:
        cloud = cloud_an(app)
        return {'ergebnis': 'cloud' if cloud else vorwaermen(app), 'cloud': cloud}


__all__ = ['Fortschritt', 'SAETZE', 'cloud_an', 'laeuft', 'register', 'vorwaermen']
