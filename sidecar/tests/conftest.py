"""Tests arbeiten ausschließlich mit eigenen Daten und Schlüsselspeichern."""

import os

import pytest

from icarus_memory.secrets import KNOWN, PASSPHRASE_ENV, Keychain


@pytest.fixture(autouse=True)
def isolated_data_directory(tmp_path, monkeypatch):
    # Ältere HTTP-Fixtures übergeben nicht jeden inzwischen ergänzten Store.
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path / "app-data"))
    # Ein Mac-Test darf weder echte Schlüssel lesen noch Testwerte im
    # Betriebssystem-Schlüsselbund speichern. Dateispeicher bleiben testbar.
    monkeypatch.setattr(Keychain, "_detect", lambda self: "file" if os.environ.get(PASSPHRASE_ENV) else "none")
    names = (*KNOWN, "ICARUS_PROVIDER", "ICARUS_MODEL", "ICARUS_BASE_URL")
    previous = {name: os.environ.get(name) for name in names}
    for name in names:
        os.environ.pop(name, None)
    yield
    for name, value in previous.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


@pytest.fixture(autouse=True)
def ausstattung_nur_aus_dem_bericht(monkeypatch):
    # Ohne Bericht misst der Sidecar den Rechner selbst (Befund 10). Der Testrechner soll keine Empfehlung entscheiden:
    # Tests, die die eigene Messung prüfen, setzen sie ausdrücklich.
    from icarus_memory import device_profile
    monkeypatch.setattr(device_profile, "eigene_ausstattung", lambda: None)


@pytest.fixture(autouse=True)
def autoconfig_ohne_netz(monkeypatch):
    # Die Suche nach dem Mailserver einer eigenen Domain fragt deren Server nach der Autoconfig-Datei
    # (`server_finden.py`). In Tests geht das nie ins Netz: Ohne eigene Attrappe antwortet niemand, und jeder Fund
    # von vorher ist vergessen. Wer die Suche prüft, setzt `server_finden.TRANSPORT` auf `tests/autoconfig_attrappe.py`.
    import httpx
    from icarus_memory import server_finden

    class KeinNetz(httpx.BaseTransport):
        def handle_request(self, request):
            raise httpx.ConnectError("kein Netz in Tests", request=request)

    monkeypatch.setattr(server_finden, "TRANSPORT", KeinNetz())
    server_finden.vergessen()
    yield
    server_finden.vergessen()


@pytest.fixture(autouse=True)
def fassung_ohne_netz(monkeypatch):
    # Die tägliche Fassungsprüfung (`fassung.py`) fragt die Download-Seite. In Tests geht das nie ins Netz: leer heißt
    # „nicht nachsehen“, und der Zeitplan startet ihretwegen keinen Faden. Wer die Prüfung testet, setzt eine Attrappe.
    monkeypatch.setenv("KINGFISHER_UPDATE_URL", "")
    monkeypatch.delenv("KINGFISHER_FASSUNG", raising=False)


@pytest.fixture(autouse=True)
def hintergrund_ohne_ruhe(monkeypatch):
    # Die Steuerung des Hintergrunds pausiert 20 s nach jeder Anfrage (docs/46-hintergrund.md). Tests, die
    # anderes prüfen, stellen eine Anfrage und erwarten die Arbeit gleich danach; für sie gilt keine Ruhe.
    # Wer die Rücksicht prüft (test_hintergrund), setzt sie ausdrücklich.
    monkeypatch.setenv("KINGFISHER_HINTERGRUND_RUHE_S", "0")


@pytest.fixture(autouse=True)
def conflict_check_without_wall_clock(monkeypatch):
    # Die Konfliktprüfung bricht nach 1 s Wanduhrzeit vorsichtig mit
    # „ungeprüft“ ab. Unter Last traf das zufällig Tests, die gar nicht das
    # Zeitbudget prüfen. Hier gilt nur die feste Schrittgrenze; wer das
    # Zeitbudget testet, setzt seine eigene Uhr (test_knowledge_conflicts).
    from icarus_memory import knowledge_conflicts
    monkeypatch.setattr(knowledge_conflicts, "monotonic", lambda: 0.0)


@pytest.fixture
def mcp_tuer_offen(monkeypatch):
    # Die MCP-Tür ist in Produktion aus (KINGFISHER_MCP_TUER). Tests der Tür
    # schalten sie ausdrücklich ein; die Vorgabe selbst prüft test_mcp_tuer.
    from icarus_memory.config import MCP_TUER_ENV
    monkeypatch.setenv(MCP_TUER_ENV, "1")
