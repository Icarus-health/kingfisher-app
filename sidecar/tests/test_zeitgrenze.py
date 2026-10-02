"""Zeitgrenze: Ergebnis und Fehler kommen unverändert, Warten endet pünktlich."""
from __future__ import annotations

import threading
import time

import pytest

from icarus_memory.zeitgrenze import mit_zeitgrenze


def test_ergebnis_kommt_unveraendert() -> None:
    assert mit_zeitgrenze(lambda: [1, 2], 1.0) == [1, 2]


def test_fehler_kommt_unveraendert() -> None:
    def kaputt():
        raise ValueError("kaputt")

    with pytest.raises(ValueError, match="kaputt"):
        mit_zeitgrenze(kaputt, 1.0)


def test_haengender_aufruf_endet_mit_timeout() -> None:
    freigabe = threading.Event()
    beginn = time.monotonic()
    try:
        with pytest.raises(TimeoutError):
            mit_zeitgrenze(lambda: freigabe.wait(10), 0.2)
    finally:
        freigabe.set()
    assert time.monotonic() - beginn < 2
