"""Posteingang lesen, ohne zu warten, wenn das Postfach gerade schweigt (Fremdprobe, Befunde 14 und 22).

Früher lasen „Nachrichten“ und „Heute“ den Posteingang bei jedem Aufruf neu. Schwieg das Postfach (Server nicht
erreichbar), sah man mehrere Sekunden lang Platzhalter, dann auf „Nachrichten“ den falschen Satz „Der lokale Posteingang
ist gerade nicht erreichbar“ – nicht erreichbar war das Postfach beim Anbieter, nicht etwas Lokales.

Jetzt:

* Jeder Abruf hat eine Wanduhr (`zeitgrenze.mit_zeitgrenze`, Vorgabe `ZEITGRENZE`).
* Scheitert er, wird der Grund in einem Satz gemerkt (`mail_anmeldung.einordnen`: „WEB.DE antwortet gerade nicht …“).
* Wer innerhalb von `MERKEN` Sekunden wieder fragt, bekommt diesen Satz **sofort**, ohne zu warten; im Hintergrund
  wird einmal neu versucht, und gelingt das, gilt das Postfach wieder als erreichbar.

Gemerkt wird je Abruf-Schlüssel (alle Postfächer oder ein Konto), nur im Speicher, ohne Inhalte.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, TypeVar

from .mail_anmeldung import Anmeldefehler, einordnen
from .zeitgrenze import mit_zeitgrenze

T = TypeVar('T')

#: So lange wartet ein Abruf des Posteingangs höchstens (Sekunden, Wanduhr).
ZEITGRENZE = 6.0
#: So lange gilt ein schweigendes Postfach als schweigend, ohne dass jemand erneut warten muss (Sekunden).
MERKEN = 120.0


class PostfachLage:
    def __init__(self, uhr: Callable[[], float] = time.monotonic) -> None:
        self._uhr = uhr
        self._sperre = threading.Lock()
        self._stumm: dict[str, tuple[float, Anmeldefehler]] = {}
        self._versuch: set[str] = set()

    def gemerkt(self, schluessel: str) -> Anmeldefehler | None:
        with self._sperre:
            eintrag = self._stumm.get(schluessel)
            if eintrag is None:
                return None
            seit, fehler = eintrag
            if self._uhr() - seit > MERKEN:
                del self._stumm[schluessel]
                return None
            return fehler

    def lesen(self, schluessel: str, aufruf: Callable[[], T], *, host: str, name: str,
              sekunden: float | None = None) -> T:
        """`aufruf()` mit Zeitgrenze, oder sofort `Anmeldefehler`, wenn das Postfach eben noch schwieg."""
        fehler = self.gemerkt(schluessel)
        if fehler is not None:
            self._neu_versuchen(schluessel, aufruf, host=host, name=name, sekunden=sekunden)
            raise fehler
        return self._abrufen(schluessel, aufruf, host=host, name=name, sekunden=sekunden)

    def _abrufen(self, schluessel: str, aufruf: Callable[[], T], *, host: str, name: str,
                 sekunden: float | None) -> T:
        try:
            ergebnis = mit_zeitgrenze(aufruf, ZEITGRENZE if sekunden is None else sekunden)
        except Exception as exc:  # noqa: BLE001 - jeder Fehler wird zu genau einem Satz
            fehler = einordnen(exc, host, name)
            with self._sperre:
                self._stumm[schluessel] = (self._uhr(), fehler)
            raise fehler from None
        with self._sperre:
            self._stumm.pop(schluessel, None)
        return ergebnis

    def _neu_versuchen(self, schluessel: str, aufruf: Callable[[], Any], **kwargs: Any) -> None:
        with self._sperre:
            if schluessel in self._versuch:
                return
            self._versuch.add(schluessel)

        def laufen() -> None:
            try:
                self._abrufen(schluessel, aufruf, **kwargs)
            except Exception:  # noqa: BLE001 - der Fehler ist gemerkt; der nächste Aufruf sagt ihn
                pass
            finally:
                with self._sperre:
                    self._versuch.discard(schluessel)

        threading.Thread(target=laufen, name='postfach-neu-versuchen', daemon=True).start()


def lage(app) -> PostfachLage:
    """Die eine Lage je App (auf `app.state`)."""
    vorhanden = getattr(app.state, 'postfach_lage', None)
    if vorhanden is None:
        vorhanden = PostfachLage()
        app.state.postfach_lage = vorhanden
    return vorhanden


def wer(app, account_id: str | None = None) -> tuple[str, str]:
    """(imap_host, Name) des Postfachs für den Satz; bei mehreren ohne Auswahl „Ein Postfach“."""
    konten = [e for e in app.state.settings.mail_accounts if getattr(e, 'configured', True)]
    if account_id is not None:
        konten = [e for e in konten if e.id == account_id]
    if len(konten) == 1:
        return str(getattr(konten[0], 'imap_host', '') or ''), str(konten[0].label or '')
    return '', 'Ein Postfach'


__all__ = ['MERKEN', 'PostfachLage', 'ZEITGRENZE', 'lage', 'wer']
