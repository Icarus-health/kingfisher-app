"""Verdrahtung der Lage: die Bausteine der App und der Lauf im Zeitplan.

Die Regeln stehen in `lage.py` (Erzeugen, Speichern) und `satzpruefung.py`
(Prüfen). Hier steht nur, wie der Server sie mit seinen Speichern und dem
Zeitplan verbindet. Es gibt keine Route, die ein Modell aufruft: Die Lage
entsteht ausschließlich im Zeitplan, mit derselben Freigabe, denselben Sperren
und derselben Pflicht zum lokalen Modell wie die übrigen Hintergrundläufe. Gelesen
wird sie mit der Akte (`GET /api/v1/akten/akte`, Feld `lage`).
"""
from __future__ import annotations

from typing import Any, Callable

from .lage import Lagen
from .scheduler import JobResult

#: So viele Sachen bekommen höchstens in einem Schritt des Zeitplans eine neue Lage (ein Modellaufruf je Sache).
PAKET = 2


def lagen_von(app) -> Lagen:
    """Die Lagen dieser App, an den aktuellen Speicher gebunden (wie `akten_routes.bausteine`)."""
    from .akten_routes import bausteine
    _, akten = bausteine(app)
    vorhanden = getattr(app.state, 'lagen_baustein', None)
    if vorhanden is not None and vorhanden[0] is akten:
        return vorhanden[1]
    lagen = Lagen(app.state.episodes, akten)
    app.state.lagen_baustein = (akten, lagen)
    return lagen


def lauf(app, provider: Any, *, permitted: Callable[[], bool], permission_lock: Any = None,
         paket: int = PAKET) -> JobResult:
    """Ein kleines Paket Lagen im Zeitplan: wichtigste Sachen zuerst, nur mit lokalem Modell und Freigabe.

    `provider` ist bereits der geprüfte lokale Anbieter der Rolle `hintergrund` (im Server
    `scheduled_provider`, also `VerifiedLocalProvider`, wo der Zeitplan lokal bindet); `permitted`
    prüft die Freigabe vor jedem Schritt. Ohne lokales Modell passiert nichts.
    """
    if provider is None or not getattr(provider, 'is_local', False):
        return JobResult('lage', True, 'Für die Lage wird ein lokales Modell benötigt.')
    if not permitted():
        return JobResult('lage', True, 'Lage nach geänderter Freigabe gestoppt.')
    from .memory_analysis import model_key
    lagen = lagen_von(app)
    try:
        # Zuerst Bezüge nachführen: Eine Akte ohne aktuelle Bezüge wäre die Eingabe von gestern.
        from .akten_routes import nachfuehren
        nachfuehren(app)
        sachen = lagen.kandidaten(paket, modell=model_key(provider))
    except Exception:  # noqa: BLE001 - Keine Quelldaten in Statusmeldungen; der nächste Lauf versucht es erneut.
        return JobResult('lage', False, 'Lage konnte nicht vorbereitet werden. Erneuter Versuch folgt.')
    erzeugt = verworfen = fehler = 0
    for sache in sachen:
        if not permitted():
            return JobResult('lage', True, 'Lage nach geänderter Freigabe gestoppt.')
        ergebnis = lagen.erzeugen(sache, provider, permitted=permitted, permission_lock=permission_lock)
        erzeugt += ergebnis.status == 'erzeugt'
        verworfen += ergebnis.verworfen
        fehler += ergebnis.status == 'fehler'
        if ergebnis.status == 'gestoppt':
            return JobResult('lage', True, 'Lage nach geänderter Freigabe gestoppt.')
    if not sachen:
        return JobResult('lage', True, 'Alle Lagen sind aktuell.')
    detail = f'{erzeugt} Lagen erstellt'
    if verworfen:
        detail += f', {verworfen} Sätze ohne ausreichenden Beleg verworfen'
    if fehler:
        detail += f', {fehler} ohne brauchbare Antwort; erneuter Versuch folgt'
    return JobResult('lage', fehler == 0, detail)


__all__ = ['PAKET', 'lagen_von', 'lauf']
