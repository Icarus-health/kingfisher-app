"""Tests der Absicherung der MCP-Tür (Etappe A1: Vertrauen sichern).

Fünf Zusagen, jede mit eigenem Test:

1. Die Tür ist in beide Richtungen **aus**, solange niemand sie ausdrücklich
   einschaltet — mit einer Meldung, die sagt, wie.
2. Ein Assistent von außen schreibt nicht ohne Vorschlag in den Bestand.
3. Der Kontext für die Tür ist immer auf `normal` gedeckelt.
4. Fremde Server bekommen eine minimale Umgebung, nie Token oder Schlüssel.
5. Werkzeugnamen angedockter Server passen zum Muster der Cloud-Schnittstellen.

Die Route-Tests laufen gegen den echten Sidecar-Stapel, wie `test_mcp.py`.
"""

from __future__ import annotations

import re
import subprocess
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory import mcp_client, server
from icarus_memory.audit import AuditLog
from icarus_memory.config import MCP_TUER_ENV, MCP_TUER_ZU_TEXT, Settings, mcp_tuer_offen
from icarus_memory.mcp import Bridge, Server, SidecarUnreachable
from icarus_memory.mcp_client import (
    MAX_NAMENSLAENGE,
    FremdesWerkzeug,
    MCPFehler,
    MCPVerbindung,
    Serverangabe,
    kind_umgebung,
)
from icarus_memory.model import Kind, Provenance, Sensitivity, SourceType
from icarus_memory.server import TOKEN_ENV, create_app
from icarus_memory.tasks import TaskStore
from icarus_memory.tools import build_registry
from icarus_memory.workspace import WorkspaceStore

CLOUD_MUSTER = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


@pytest.fixture
def app(tmp_path):
    store = SelfModelStore(MemoryBackend(), subject_id="test")
    return create_app(
        store,
        audit=AuditLog(tmp_path / "audit.sqlite3"),
        tasks=TaskStore(tmp_path / "tasks.sqlite3"),
        workspace=WorkspaceStore(tmp_path / "workspace.sqlite3"),
    )


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


# -- 1. Der Schalter --------------------------------------------------------

TUER_ROUTEN = [
    ("get", "/tools", None),
    ("post", "/tools/mail_senden", {}),
    ("get", "/context", None),
    ("get", "/mcp/tuer", None),
    ("get", "/mcp/server", None),
    ("post", "/mcp/server", {"name": "X", "befehl": "x"}),
    ("delete", "/mcp/server/X", None),
    ("post", "/mcp/pruefen", {"name": "X", "befehl": "x"}),
]


def test_vorgabe_ist_aus(monkeypatch) -> None:
    monkeypatch.delenv(MCP_TUER_ENV, raising=False)
    assert mcp_tuer_offen() is False


@pytest.mark.parametrize("wert,erwartet", [
    ("1", True), ("true", True), ("Ja", True), (" an ", True),
    ("0", False), ("", False), ("nein", False), ("vielleicht", False),
])
def test_schalter_versteht_nur_ein_ausdrueckliches_ja(monkeypatch, wert, erwartet) -> None:
    monkeypatch.setenv(MCP_TUER_ENV, wert)
    assert mcp_tuer_offen() is erwartet


@pytest.mark.parametrize("methode,pfad,koerper", TUER_ROUTEN)
def test_ausgeschaltete_tuer_antwortet_mit_klarer_meldung(
    client, monkeypatch, methode, pfad, koerper
) -> None:
    monkeypatch.delenv(MCP_TUER_ENV, raising=False)

    antwort = getattr(client, methode)(pfad, **({"json": koerper} if koerper is not None else {}))

    assert antwort.status_code == 403
    assert antwort.json()["detail"] == MCP_TUER_ZU_TEXT
    assert MCP_TUER_ENV in antwort.json()["detail"]  # Sie sagt, wie man einschaltet.


def test_eingeschaltete_tuer_laesst_die_routen_durch(client, monkeypatch) -> None:
    monkeypatch.setenv(MCP_TUER_ENV, "1")

    assert client.get("/tools").status_code == 200
    assert client.get("/context").status_code == 200
    assert client.get("/mcp/tuer").json() == {"offen": True}
    assert client.get("/mcp/server").status_code == 200


def test_die_app_selbst_bleibt_ohne_die_tuer_benutzbar(client, monkeypatch) -> None:
    """Nur die Tür ist zu — Gedächtnis und Oberfläche laufen weiter."""
    monkeypatch.delenv(MCP_TUER_ENV, raising=False)

    assert client.get("/health").status_code == 200
    assert client.get("/assertions").status_code == 200
    assert client.get("/approvals").status_code == 200


def test_das_token_wird_vor_dem_schalter_geprueft(app, monkeypatch) -> None:
    """Ohne Anmeldung erfährt niemand, ob die Tür an ist."""
    monkeypatch.setenv(TOKEN_ENV, "richtig")
    monkeypatch.delenv(MCP_TUER_ENV, raising=False)
    geschuetzt = TestClient(create_app(SelfModelStore(MemoryBackend(), subject_id="t")))

    assert geschuetzt.get("/tools").status_code == 401
    assert geschuetzt.get("/tools", headers={"x-icarus-token": "richtig"}).status_code == 403


@pytest.mark.parametrize("aufruf", [
    lambda s: s.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}),
    lambda s: s.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                        "params": {"name": "icarus_heute"}}),
    lambda s: s.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                        "params": {"name": "icarus_freigaben"}}),
    lambda s: s.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                        "params": {"name": "icarus_kontext"}}),
])
def test_bruecke_reicht_die_meldung_verstaendlich_durch(client, monkeypatch, aufruf) -> None:
    """Auch `icarus_heute` und `icarus_freigaben` (ungesperrte App-Endpunkte)."""
    monkeypatch.delenv(MCP_TUER_ENV, raising=False)
    bruecke = Server(Bridge("http://test", None, client=client))

    antwort = aufruf(bruecke)

    assert antwort["error"]["code"] == -32001
    assert antwort["error"]["message"] == MCP_TUER_ZU_TEXT


def test_bruecke_wirft_bei_403_die_meldung_des_sidecars(client, monkeypatch) -> None:
    monkeypatch.delenv(MCP_TUER_ENV, raising=False)
    with pytest.raises(SidecarUnreachable, match="ausgeschaltet"):
        Bridge("http://test", None, client=client).get("/tools")


# -- Startpfad: keine fremden Server bei ausgeschalteter Tür ----------------


def _app_mit_eintrag(tmp_path, monkeypatch) -> SimpleNamespace:
    gestartet: list[str] = []

    def start(self) -> None:
        gestartet.append(self._angabe.name)
        raise MCPFehler("nur gezählt")

    monkeypatch.setattr(MCPVerbindung, "start", start)
    einstellungen = Settings()
    einstellungen.mcp_server = [{"name": "Fremd", "befehl": ["gibt-es-nicht"], "aktiv": True}]
    return SimpleNamespace(state=SimpleNamespace(settings=einstellungen, mcp={}),
                           gestartet=gestartet)


def test_ausgeschaltete_tuer_startet_keine_fremden_server(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(MCP_TUER_ENV, raising=False)
    attrappe = _app_mit_eintrag(tmp_path, monkeypatch)

    server._docke_mcp_an(attrappe)

    assert attrappe.gestartet == []
    assert attrappe.state.mcp == {}
    assert attrappe.state.mcp_fehler == {}


def test_eingeschaltete_tuer_startet_die_eingetragenen_server(tmp_path, monkeypatch) -> None:
    """Gegenprobe: Der Test oben fängt wirklich den Schalter, nicht Zufall."""
    monkeypatch.setenv(MCP_TUER_ENV, "1")
    attrappe = _app_mit_eintrag(tmp_path, monkeypatch)

    server._docke_mcp_an(attrappe)

    assert attrappe.gestartet == ["Fremd"]


# -- 2. Kein direktes Schreiben in den Bestand von außen --------------------


@pytest.mark.parametrize("werkzeug,argumente", [
    ("merken", {"statement": "Ist Vegetarier.", "kind": "state"}),
    ("episode_festhalten", {"titel": "T", "text": "Text", "art": "observation"}),
    # Meldete über die Tür Erfolg, ohne dass je ein Vorschlag entstand.
    ("gedaechtnis_vorschlagen", {"statement": "Ist Vegetarier.", "kind": "state"}),
])
def test_invoke_verweigert_direktes_schreiben_und_verweist_auf_den_vorschlag(
    app, werkzeug, argumente
) -> None:
    antwort = app.state.agent.invoke(werkzeug, argumente)

    assert antwort["ok"] is False
    assert "gedaechtnis_vorschlagen" in antwort["text"]
    assert app.state.store.usable() == []
    assert app.state.episodes.all_episodes() == []
    eintraege = [e for e in app.state.audit.entries(10) if e["tool"] == werkzeug]
    assert [e["outcome"] for e in eintraege] == ["refused"]


def test_die_werkzeugroute_verweigert_merken_auch_mit_offener_tuer(
    client, app, monkeypatch
) -> None:
    monkeypatch.setenv(MCP_TUER_ENV, "1")

    antwort = client.post("/tools/merken", json={"statement": "Ist Vegetarier."})

    assert antwort.status_code == 200
    assert antwort.json()["ok"] is False
    assert app.state.store.usable() == []


def test_die_tuer_bietet_die_gesperrten_werkzeuge_nicht_an(app) -> None:
    agent = app.state.agent
    fuer_tuer = {t["name"] for t in agent.tool_schemas(fuer_tuer=True)}
    alle = {t["name"] for t in agent.tool_schemas()}

    gesperrt = {"merken", "episode_festhalten", "gedaechtnis_vorschlagen"}
    assert gesperrt <= alle
    assert not gesperrt & fuer_tuer
    assert "projekt_anlegen" in fuer_tuer  # Alles andere bleibt.


# -- 3. Kontext für die Tür: immer NORMAL -----------------------------------


def test_kontext_der_tuer_ist_auf_normal_gedeckelt(app, client, monkeypatch) -> None:
    monkeypatch.setenv(MCP_TUER_ENV, "1")
    for text, stufe in (("Trinkt gern Tee.", Sensitivity.NORMAL),
                        ("Nimmt ein Medikament gegen Bluthochdruck.", Sensitivity.SENSITIVE)):
        app.state.store.record(
            statement=text, kind=Kind.STATE,
            provenance=Provenance(source_type=SourceType.USER_STATED), sensitivity=stufe,
        )
    # Ein lokales Hausmodell darf `sensitive` sehen — die Tür nicht.
    agent = app.state.agent
    agent._provider = SimpleNamespace(is_local=True, model="lokal")
    agent._max_sensitivity = Sensitivity.SENSITIVE
    assert "Bluthochdruck" in agent.context()  # Kontrolle: das Haus sieht es.

    text = client.get("/context").json()["context"]

    assert "Trinkt gern Tee." in text
    assert "Bluthochdruck" not in text


# -- 4. Minimale Umgebung für Kindprozesse ----------------------------------

BASIS = {
    "PATH": "/usr/bin", "HOME": "/home/x", "LANG": "de_DE.UTF-8", "LC_ALL": "de_DE.UTF-8",
    "TMPDIR": "/tmp", "USER": "x", "SHELL": "/bin/sh",
    "ICARUS_SIDECAR_TOKEN": "geheim-token", "OPENAI_API_KEY": "sk-geheim",
    "ANTHROPIC_API_KEY": "sk-ant-geheim", "ICARUS_SMTP_PASSWORD": "pw",
}


def test_kind_umgebung_gibt_nur_die_erlaubte_liste_weiter() -> None:
    umgebung = kind_umgebung({}, BASIS)

    assert umgebung == {k: BASIS[k] for k in
                        ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "USER", "SHELL")}


def test_kind_umgebung_nimmt_die_ausdruecklich_eingetragene_dazu() -> None:
    umgebung = kind_umgebung({"WETTER_KEY": "abc", "PATH": "/opt/bin"}, BASIS)

    assert umgebung["WETTER_KEY"] == "abc"
    assert umgebung["PATH"] == "/opt/bin"  # Eingetragenes schlägt die Basis.


def test_das_sidecar_token_kommt_auch_ueber_die_eintragung_nicht_hinein() -> None:
    umgebung = kind_umgebung({"ICARUS_SIDECAR_TOKEN": "geheim-token"}, BASIS)

    assert "ICARUS_SIDECAR_TOKEN" not in umgebung


def test_der_gestartete_prozess_bekommt_die_minimale_umgebung(monkeypatch) -> None:
    """Am echten Startaufruf, nicht nur an der Hilfsfunktion."""
    for name, wert in BASIS.items():
        monkeypatch.setenv(name, wert)
    gesehen: dict = {}

    def abfangen(*args, **kwargs):
        gesehen.update(kwargs["env"])
        raise OSError("nur mitgeschnitten")

    monkeypatch.setattr(subprocess, "Popen", abfangen)

    with pytest.raises(MCPFehler):
        MCPVerbindung(Serverangabe(name="P", befehl=["x"], umgebung={"REGION": "eu"})).start()

    assert gesehen["REGION"] == "eu" and "PATH" in gesehen
    assert not {"ICARUS_SIDECAR_TOKEN", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                "ICARUS_SMTP_PASSWORD"} & gesehen.keys()


# -- 5. Werkzeugnamen -------------------------------------------------------


@pytest.mark.parametrize("dienst,name", [
    ("Probe", "wetter"),
    ("Mein Dienst", "etwas.tun"),
    ("dienst.mit.punkt", "server.tool"),
    ("Käse-Shop", "größe ändern"),
    ("a" * 80, "b" * 80),
    ("///", "???"),
    ("x", "__doppelt__unterstrich__"),
])
def test_werkzeugnamen_passen_zum_muster_der_cloud_schnittstellen(dienst, name) -> None:
    voll = FremdesWerkzeug(server=dienst, name=name, beschreibung="", schema={}).voller_name

    assert CLOUD_MUSTER.match(voll), voll
    assert len(voll) <= MAX_NAMENSLAENGE
    assert "." not in voll


def test_der_name_zeigt_dienst_und_werkzeug_getrennt_durch_doppelten_unterstrich() -> None:
    assert FremdesWerkzeug("Probe", "wetter", "", {}).voller_name == "Probe__wetter"
    assert FremdesWerkzeug("Mein Dienst", "a.b", "", {}).voller_name == "Mein_Dienst__a_b"


def test_lange_namen_bleiben_verschieden() -> None:
    a = FremdesWerkzeug("dienst", "w" * 100 + "eins", "", {}).voller_name
    b = FremdesWerkzeug("dienst", "w" * 100 + "zwei", "", {}).voller_name

    assert a != b and len(a) <= MAX_NAMENSLAENGE and len(b) <= MAX_NAMENSLAENGE


def test_zusammenfallende_namen_ueberschreiben_sich_in_der_registry_nicht() -> None:
    """`a b` und `a_b` werden beide zu `a_b`; beide Werkzeuge müssen bleiben."""
    aufrufe: list[str] = []

    class Verbindung:
        def rufe(self, name, argumente):
            aufrufe.append(name)
            return "ok"

    verbindung = Verbindung()
    fremde = [FremdesWerkzeug("S", "a b", "", {}), FremdesWerkzeug("S", "a_b", "", {})]

    registry = build_registry(store=None, mcp_verbindungen={"S": (verbindung, fremde)})

    namen = sorted(n for n in registry if n.startswith("S__"))
    assert namen == ["S__a_b", "S__a_b_2"]
    for name in namen:
        assert CLOUD_MUSTER.match(name)
        registry[name].run()
    assert aufrufe == ["a b", "a_b"]  # Jeder Name führt zum richtigen Fremdwerkzeug.
