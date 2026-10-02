"""Ein Aufruf mit Zeitgrenze, ohne den Aufrufer warten zu lassen.

Die Startseite darf nicht hängen, weil ein Postfach nicht antwortet. Der
Aufruf läuft in einem eigenen Faden; ist er nach `sekunden` nicht fertig,
bekommt der Aufrufer `TimeoutError`, und der Faden läuft im Hintergrund zu
Ende (seine Netzverbindung hat ihre eigene Zeitgrenze). Ergebnis und Fehler
kommen unverändert zurück.
"""
from __future__ import annotations

import threading
from typing import Callable, TypeVar

T = TypeVar('T')


def mit_zeitgrenze(aufruf: Callable[[], T], sekunden: float) -> T:
    ergebnis: dict[str, object] = {}

    def laufen() -> None:
        try:
            ergebnis['wert'] = aufruf()
        except BaseException as exc:  # noqa: BLE001 - wird beim Aufrufer erneut geworfen
            ergebnis['fehler'] = exc

    faden = threading.Thread(target=laufen, name='mit-zeitgrenze', daemon=True)
    faden.start()
    faden.join(sekunden)
    if faden.is_alive():
        raise TimeoutError(sekunden)
    if 'fehler' in ergebnis:
        raise ergebnis['fehler']  # type: ignore[misc]
    return ergebnis['wert']  # type: ignore[return-value]


__all__ = ['mit_zeitgrenze']
