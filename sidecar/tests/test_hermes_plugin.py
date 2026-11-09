"""Tests des Hermes-Plugins (`integrations/hermes/icarus/`).

Die Kingfisher-Seite ist echt: Sidecar, Agent, Policy und Audit, über einen ASGI-Transport oder
— in einem Test — über echtes HTTP auf Loopback. Eine Brücke, die nur gegen nachgebaute
Antworten geprüft ist, beweist über die Brücke nichts (wie `test_mcp.py`).

Die Hermes-Seite: Ist `HERMES_AGENT_SRC` gesetzt (Pfad zu einer Arbeitskopie von
NousResearch/hermes-agent), lädt der Test die echte `MemoryProvider`-Schnittstelle. Sonst steht
eine schmale Nachbildung der drei benutzten Namen bereit, damit die Tests ohne Hermes laufen;
was sie nachbildet, steht in `_hermes_nachbildung`.

Zusagen, jede mit eigenem Test:

1. Die Mac-App wird ohne Einstellung gefunden; was fehlt, sagt ein Satz samt Weg.
2. Abruf bringt belegte Aussagen mit Quelle; besonders Geschütztes bleibt in Kingfisher.
3. Das Plugin schreibt nichts in Kingfisher — es hat keinen Weg dafür.
4. Eine geschlossene Tür, ein falsches Token oder ein fehlender Sidecar kosten nur den Abruf,
   nie die Antwort von Hermes, und die Meldung sagt, was zu tun ist.
5. Ein neues Token nach einem Neustart von Kingfisher wird ohne Neustart von Hermes gefunden.
"""

from __future__ import annotations

import abc
import importlib.util
import json
import os
import socket
import sys
import threading
import time
import types
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.audit import AuditLog
from icarus_memory.config import MCP_TUER_ENV
from icarus_memory.model import Kind, Provenance, Sensitivity, SourceType
from icarus_memory.server import TOKEN_ENV, create_app, write_connection_file
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore

PLUGIN = Path(__file__).resolve().parents[2] / "integrations" / "hermes" / "icarus"


# -- Hermes: echt oder schmal nachgebildet ------------------------------------------------------


def _hermes_nachbildung() -> dict[str, types.ModuleType]:
    """Die drei Namen aus `agent/memory_provider.py` und `get_secret`, sonst nichts.

    Abstrakt wie im Original sind `name`, `is_available`, `initialize` und `get_tool_schemas`;
    `sync_turn` und `on_memory_write` sind wie dort Methoden ohne Wirkung, damit sich prüfen
    lässt, dass das Plugin sie nicht überschreibt.
    """
    agent = types.ModuleType("agent")
    agent.__path__ = []  # type: ignore[attr-defined]
    provider = types.ModuleType("agent.memory_provider")

    @dataclass(frozen=True)
    class RecallStatus:
        provider_label: str
        count: int
        glyph: str = "🧠"

    class MemoryProvider(abc.ABC):
        @property
        @abc.abstractmethod
        def name(self) -> str: ...

        @abc.abstractmethod
        def is_available(self) -> bool: ...

        @abc.abstractmethod
        def initialize(self, session_id: str, **kwargs) -> None: ...

        @abc.abstractmethod
        def get_tool_schemas(self) -> list: ...

        def sync_turn(self, user_content, assistant_content, *, session_id="", messages=None,
                      turn_author=None) -> None:
            return None

        def on_memory_write(self, action, target, content, metadata=None) -> None:
            return None

    def is_trivial_prompt(text):
        rest = (text or "").strip()
        return not rest or rest.startswith("/") or rest.rstrip("!?.").lower() in {"ok", "danke", "ja", "nein"}

    provider.MemoryProvider = MemoryProvider  # type: ignore[attr-defined]
    provider.RecallStatus = RecallStatus  # type: ignore[attr-defined]
    provider.is_trivial_prompt = is_trivial_prompt  # type: ignore[attr-defined]
    geheim = types.ModuleType("agent.secret_scope")
    geheim.get_secret = lambda name, default=None: default  # type: ignore[attr-defined]
    return {"agent": agent, "agent.memory_provider": provider, "agent.secret_scope": geheim}


@pytest.fixture
def hermes(monkeypatch):
    quelle = os.environ.get("HERMES_AGENT_SRC")
    if quelle:
        monkeypatch.syspath_prepend(quelle)
    else:
        for name, modul in _hermes_nachbildung().items():
            monkeypatch.setitem(sys.modules, name, modul)
    return importlib.import_module("agent.memory_provider")


@pytest.fixture
def plugin(hermes, monkeypatch):
    """Das Plugin als Paket, wie Hermes es aus `$HERMES_HOME/plugins/icarus/` lädt."""
    name = "_hermes_icarus_test"
    for modul in [m for m in sys.modules if m.startswith(name)]:
        monkeypatch.delitem(sys.modules, modul)
    spec = importlib.util.spec_from_file_location(
        name, PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
    modul = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, modul)
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture
def tuer_modul(monkeypatch):
    """`icarus_tuer` allein — braucht weder Hermes noch Kingfisher."""
    spec = importlib.util.spec_from_file_location("icarus_tuer_test", PLUGIN / "icarus_tuer.py")
    modul = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, modul)
    spec.loader.exec_module(modul)
    return modul


# -- Kingfisher: echter Sidecar-Stapel ----------------------------------------------------------


def _app(tmp_path: Path, token: str | None = None):
    # Der Sidecar liest sein Token beim Bauen der App; danach gilt wieder die Umgebung von vorher.
    vorher = os.environ.pop(TOKEN_ENV, None)
    if token:
        os.environ[TOKEN_ENV] = token
    try:
        store = SelfModelStore(MemoryBackend(), subject_id="test")
        return create_app(
            store,
            audit=AuditLog(tmp_path / "audit.sqlite3"),
            tasks=TaskStore(tmp_path / "tasks.sqlite3"),
            workspace=WorkspaceStore(tmp_path / "workspace.sqlite3"),
        )
    finally:
        os.environ.pop(TOKEN_ENV, None)
        if vorher is not None:
            os.environ[TOKEN_ENV] = vorher


class AsgiWeg:
    """Transport des Plugins gegen den echten Stapel, ohne Port. Zählt die Anfragen."""

    def __init__(self, app) -> None:
        self.client = TestClient(app)
        self.anfragen: list[tuple[str, str]] = []

    def __call__(self, methode, pfad, nutzlast, verbindung):
        self.anfragen.append((methode, pfad))
        kopf = {"x-icarus-token": verbindung.token} if verbindung.token else {}
        antwort = self.client.request(methode, pfad, json=nutzlast, headers=kopf)
        return antwort.status_code, (antwort.json() if antwort.content else None)


def _merken(app, satz: str, *, quelle: str = "chat:12",
            schutz: Sensitivity = Sensitivity.NORMAL) -> None:
    app.state.store.record(
        statement=satz, kind=Kind.PREFERENCE, sensitivity=schutz,
        provenance=Provenance(source_type=SourceType.CHAT, source_ref=quelle))


def _mac_app(zuhause: Path, token: str = "mac-token", extra: str = "") -> Path:
    env = zuhause / "Library" / "Application Support" / "Kingfisher" / "kingfisher.env"
    env.parent.mkdir(parents=True)
    env.write_text(
        "# Von der Kingfisher-App erzeugt – nicht weitergeben.\n"
        f'export ICARUS_SIDECAR_TOKEN="{token}"\n'
        "ICARUS_SECRETS_PASSPHRASE=bleibt-unberuehrt\n" + extra, encoding="utf-8")
    return env


def _anbieter(plugin, weg, zuhause: Path, hermes_home: Path | None = None):
    anbieter = plugin.IcarusMemoryProvider(transport=weg, zuhause=zuhause)
    anbieter.initialize("sitzung-1", hermes_home=str(hermes_home or zuhause / ".hermes"),
                        platform="cli")
    return anbieter


@pytest.fixture
def zuhause(tmp_path) -> Path:
    ort = tmp_path / "zuhause"
    ort.mkdir()
    return ort


# -- 1. Finden ----------------------------------------------------------------------------------


def test_mac_app_wird_ohne_einstellung_gefunden(tuer_modul, zuhause) -> None:
    env = _mac_app(zuhause)

    verbindung = tuer_modul.finde_verbindung({}, None, zuhause)

    assert verbindung.adresse == "http://127.0.0.1:8890"
    assert verbindung.token == "mac-token"  # ohne `export` und Anführungszeichen
    assert verbindung.schalter_datei == env
    assert "bleibt-unberuehrt" not in repr(verbindung)


def test_einstellung_schlaegt_die_mac_app(tuer_modul, zuhause) -> None:
    _mac_app(zuhause)

    verbindung = tuer_modul.finde_verbindung({"adresse": "http://127.0.0.1:9000/"}, "eigen", zuhause)

    assert (verbindung.adresse, verbindung.token) == ("http://127.0.0.1:9000", "eigen")


def test_direkt_gestarteter_sidecar_wird_ueber_die_verbindungsdatei_gefunden(tuer_modul, zuhause) -> None:
    ordner = zuhause / "Library" / "Application Support" / "Icarus"
    write_connection_file(ordner, 8765, "dev-token")

    verbindung = tuer_modul.finde_verbindung({}, None, zuhause)

    assert (verbindung.adresse, verbindung.token) == ("http://127.0.0.1:8765", "dev-token")
    assert verbindung.schalter_datei is None


def test_ohne_kingfisher_sagt_ein_satz_was_fehlt(plugin, zuhause) -> None:
    anbieter = plugin.IcarusMemoryProvider(zuhause=zuhause)

    assert anbieter.is_available() is False
    grund = anbieter.unavailable_reason()
    assert "kingfisher.env" in grund and "verbindung.json" in grund
    assert "icarus.json" in grund  # und wo man es sonst einträgt


# -- 2. Abruf -----------------------------------------------------------------------------------


@pytest.fixture
def offen(monkeypatch):
    monkeypatch.setenv(MCP_TUER_ENV, "1")


@pytest.mark.usefixtures("offen")
def test_abruf_bringt_belegte_aussagen_mit_quelle(plugin, tmp_path, zuhause) -> None:
    app = _app(tmp_path)
    _merken(app, "Mag ruhige, klare Oberflächen.")
    _mac_app(zuhause)
    anbieter = _anbieter(plugin, AsgiWeg(app), zuhause)

    text = anbieter.prefetch("Welche Oberflächen mag ich?", session_id="sitzung-1")

    assert "Mag ruhige, klare Oberflächen." in text
    assert "chat:12" in text  # die Quelle steht dabei
    assert anbieter.recall_status().count == 1
    assert anbieter.is_available() is True


@pytest.mark.usefixtures("offen")
def test_besonders_geschuetztes_bleibt_in_kingfisher(plugin, tmp_path, zuhause) -> None:
    app = _app(tmp_path)
    _merken(app, "Mag ruhige, klare Oberflächen.")
    _merken(app, "Mag Diabetes-Sprechstunden am Morgen.", schutz=Sensitivity.SPECIAL_CATEGORY)
    _mac_app(zuhause)
    anbieter = _anbieter(plugin, AsgiWeg(app), zuhause)

    abruf = anbieter.prefetch("Diabetes Sprechstunden Morgen")
    suche = anbieter.handle_tool_call(plugin.SUCHEN, {"query": "Diabetes"})
    kontext = anbieter.handle_tool_call(plugin.KONTEXT, {})

    for text in (abruf, suche, kontext):
        assert "Sprechstunden" not in text
    assert "Mag ruhige, klare Oberflächen." in json.loads(kontext)["ergebnis"]


@pytest.mark.usefixtures("offen")
def test_kurze_bestaetigungen_holen_nichts(plugin, tmp_path, zuhause) -> None:
    app = _app(tmp_path)
    _merken(app, "Mag ruhige, klare Oberflächen.")
    _mac_app(zuhause)
    weg = AsgiWeg(app)
    anbieter = _anbieter(plugin, weg, zuhause)

    assert anbieter.prefetch("ok") == ""
    assert weg.anfragen == []  # nicht einmal gefragt
    assert anbieter.recall_status() is None


@pytest.mark.usefixtures("offen")
def test_ohne_treffer_kommt_nichts_in_den_kontext(plugin, tmp_path, zuhause) -> None:
    _mac_app(zuhause)
    anbieter = _anbieter(plugin, AsgiWeg(_app(tmp_path)), zuhause)

    assert anbieter.prefetch("Wie heißt mein Hund?") == ""
    assert anbieter.recall_status() is None


# -- 3. Kein Schreiben --------------------------------------------------------------------------


@pytest.mark.usefixtures("offen")
def test_das_plugin_hat_keinen_weg_zu_schreiben(plugin, hermes, tmp_path, zuhause) -> None:
    app = _app(tmp_path)
    _merken(app, "Mag ruhige, klare Oberflächen.")
    vorher = len(app.state.store.usable())
    _mac_app(zuhause)
    weg = AsgiWeg(app)
    anbieter = _anbieter(plugin, weg, zuhause)
    basis = hermes.MemoryProvider

    # Die Wege, auf denen Hermes Gesagtes an einen Anbieter gibt, bleiben die leeren der Basis.
    assert type(anbieter).sync_turn is basis.sync_turn
    assert type(anbieter).on_memory_write is basis.on_memory_write
    assert {w["name"] for w in anbieter.get_tool_schemas()} == {plugin.SUCHEN, plugin.KONTEXT}

    anbieter.sync_turn("Merk dir: ich wohne in Staufen.", "Gemerkt.", session_id="sitzung-1")
    anbieter.on_memory_write("add", "user", "Wohnt in Staufen.")
    antwort = json.loads(anbieter.handle_tool_call("icarus_merken", {"statement": "Wohnt in Staufen."}))
    anbieter.prefetch("Wo wohne ich?")

    assert "Unbekanntes Werkzeug" in antwort["fehler"]
    assert len(app.state.store.usable()) == vorher
    assert {pfad for _, pfad in weg.anfragen} <= {"/tools/gedaechtnis_suchen", "/context"}


# -- 4. Fehler kosten nur den Abruf -------------------------------------------------------------


def test_geschlossene_tuer_sagt_wo_man_sie_oeffnet(plugin, tmp_path, zuhause, monkeypatch) -> None:
    monkeypatch.delenv(MCP_TUER_ENV, raising=False)
    app = _app(tmp_path)
    _merken(app, "Mag ruhige, klare Oberflächen.")
    env = _mac_app(zuhause)
    anbieter = _anbieter(plugin, AsgiWeg(app), zuhause)

    assert anbieter.prefetch("Welche Oberflächen mag ich?") == ""
    fehler = json.loads(anbieter.handle_tool_call(plugin.KONTEXT, {}))["fehler"]

    assert "ausgeschaltet" in fehler
    assert "KINGFISHER_MCP_TUER=1" in fehler and str(env) in fehler


@pytest.mark.usefixtures("offen")
def test_falsches_token_wird_benannt(plugin, tmp_path, zuhause) -> None:
    app = _app(tmp_path, token="richtig")
    _mac_app(zuhause, token="veraltet")
    anbieter = _anbieter(plugin, AsgiWeg(app), zuhause)

    assert anbieter.prefetch("Welche Oberflächen mag ich?") == ""
    fehler = json.loads(anbieter.handle_tool_call(plugin.SUCHEN, {"query": "Oberflächen"}))["fehler"]
    assert "Token abgelehnt" in fehler and "kingfisher.env" in fehler


def test_ohne_laufenden_sidecar_kommt_eine_meldung_statt_eines_absturzes(plugin, zuhause) -> None:
    with socket.socket() as frei:
        frei.bind(("127.0.0.1", 0))
        port = frei.getsockname()[1]
    hermes_home = zuhause / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "icarus.json").write_text(json.dumps({"adresse": f"http://127.0.0.1:{port}"}))
    anbieter = plugin.IcarusMemoryProvider(zuhause=zuhause)
    anbieter.initialize("sitzung-1", hermes_home=str(hermes_home))

    assert anbieter.prefetch("Welche Oberflächen mag ich?") == ""
    assert "nicht erreichbar" in json.loads(anbieter.handle_tool_call(plugin.KONTEXT, {}))["fehler"]


# -- 5. Neustart von Kingfisher -----------------------------------------------------------------


@pytest.mark.usefixtures("offen")
def test_neues_token_nach_neustart_wird_ohne_neustart_von_hermes_gefunden(plugin, tmp_path, zuhause) -> None:
    ordner = zuhause / "Library" / "Application Support" / "Icarus"
    erste = _app(tmp_path / "eins", token="erstes")
    _merken(erste, "Mag ruhige, klare Oberflächen.")
    write_connection_file(ordner, 8765, "erstes")
    weg = AsgiWeg(erste)
    anbieter = _anbieter(plugin, weg, zuhause)
    assert "Oberflächen" in anbieter.prefetch("Welche Oberflächen mag ich?")

    # Kingfisher startet neu: neues Token, neue Verbindungsdatei. Hermes läuft weiter.
    zweite = _app(tmp_path / "zwei", token="zweites")
    _merken(zweite, "Mag ruhige, klare Oberflächen.")
    weg.client = TestClient(zweite)
    write_connection_file(ordner, 8765, "zweites")

    assert "Oberflächen" in anbieter.prefetch("Welche Oberflächen mag ich?")


# -- Über echtes HTTP ---------------------------------------------------------------------------


@pytest.mark.usefixtures("offen")
def test_ueber_echtes_http_auf_loopback(plugin, tmp_path, zuhause) -> None:
    import uvicorn

    app = _app(tmp_path, token="loopback")
    _merken(app, "Mag ruhige, klare Oberflächen.")
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    faden = threading.Thread(target=server.run, daemon=True)
    faden.start()
    try:
        frist = time.monotonic() + 10
        while not server.started and time.monotonic() < frist:
            time.sleep(0.02)
        assert server.started, "Sidecar ist nicht gestartet"
        port = server.servers[0].sockets[0].getsockname()[1]
        write_connection_file(zuhause / "Library" / "Application Support" / "Icarus", port, "loopback")
        anbieter = plugin.IcarusMemoryProvider(zuhause=zuhause)  # Vorgabe: urllib
        anbieter.initialize("sitzung-1", hermes_home=str(zuhause / ".hermes"))

        assert "chat:12" in anbieter.prefetch("Welche Oberflächen mag ich?")
        assert "Mag ruhige" in json.loads(anbieter.handle_tool_call(plugin.KONTEXT, {}))["ergebnis"]
    finally:
        server.should_exit = True
        faden.join(timeout=10)


# -- hermes icarus pruefen ----------------------------------------------------------------------


def test_pruefbefehl_sagt_in_einem_satz_was_fehlt(plugin, zuhause, monkeypatch, capsys) -> None:
    spec = importlib.util.spec_from_file_location(f"{plugin.__name__}.cli", PLUGIN / "cli.py")
    cli = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, cli)
    spec.loader.exec_module(cli)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: zuhause))

    assert cli.icarus_command(None) == 1
    ausgabe = capsys.readouterr().out
    assert ausgabe.startswith("Kingfisher nicht gefunden") and "kingfisher.env" in ausgabe
