"""Cloud-Einordnung neuer Mails (Anthropic) mit eigener Einwilligung: nur Einordnung, Themen, Bitten und Zusagen.

Alles mit Attrappen und synthetischen Daten, kein Netz. Die Zusicherungen (`hintergrund_cloud.py`):
nur mit Einwilligung für genau die Rolle `hintergrund`, nur Anthropic, nur mit vorbereitetem Zugang, nur Mails,
nur im Tagesbudget, nie bei Pause, nie Verdichtung, Lage oder Mailhilfe; `provider("hintergrund")` bleibt lokal oder None.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from icarus_memory import EpisodeKind, Provenance, SourceType
from icarus_memory import hintergrund_cloud
from icarus_memory.cloud_import_provider import AnthropicImportProvider
from icarus_memory.hintergrund import als_hintergrund
from icarus_memory.model_roles import TAGESBUDGET, hintergrund_anbieter, rollen_von
from icarus_memory.scheduler import JobResult
from icarus_memory.secrets import PASSPHRASE_ENV
from icarus_memory.server import create_app
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.ollama_fake import FakeOllama

AT = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)
MAILTEXT = "Hallo Lea, bitte schick mir das Angebot für die Dachsanierung bis Freitag.\n\nViele Grüße, Jonas"
ZITAT = "bitte schick mir das Angebot für die Dachsanierung bis Freitag."
DOKUTEXT = "Vertrauliches synthetisches Dokument über die Dachsanierung, nur für dieses Gerät."
ROLLE = "/api/v1/models/roles/hintergrund"
ZUGANG = "/api/v1/models/cloud-access/anthropic"


class Zeitplan:
    """Kein Faden: die Läufe werden im Test direkt aufgerufen (`_run_working_memory`, `_run_task_detection`)."""

    def __init__(self):
        self.config = None
        self.started = False

    def configure(self, **kwargs):
        self.config = kwargs

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def prompt_allowed(self):
        return True

    def request_working_memory(self, episode_id):
        return True

    def state(self):
        return {"enabled": bool(self.config and self.config["enabled"]),
                "with_model": bool(self.config and self.config["with_model"])}


def _app(monkeypatch, *, lokal: bool):
    monkeypatch.setenv(PASSPHRASE_ENV, "synthetic-encryption-passphrase-only")
    if lokal:
        monkeypatch.setenv("ICARUS_PROVIDER", "ollama")
        monkeypatch.setenv("ICARUS_BASE_URL", "http://127.0.0.1:11434/v1")
        monkeypatch.setenv("ICARUS_MODEL", "standard-modell")
    app = create_app()
    app.state.ollama_transport = FakeOllama(installiert=["standard-modell", "gross:35b", "bge-m3"]).transport
    app.state.ollama_inventar.vergiss()
    app.state.scheduler = Zeitplan()
    return app


@pytest.fixture
def ohne_lokal(monkeypatch):
    """Kein lokales Modell: `provider("hintergrund")` ist None."""
    app = _app(monkeypatch, lokal=False)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield app, client


@pytest.fixture
def mit_lokal(monkeypatch):
    """Ein belegt lokales Standardmodell (Attrappe von Ollama)."""
    app = _app(monkeypatch, lokal=True)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield app, client


def zugang(client, schluessel="synthetic-claude-key", modell="claude-synthetic"):
    antwort = client.put(ZUGANG, json={"api_key": schluessel, "model": modell})
    assert antwort.status_code == 200, antwort.text


def einschalten(client):
    return client.put(ROLLE, json={"cloud": True, "anbieter": "anthropic", "einwilligung": True})


def freigeben(app):
    plan = app.state.settings.schedule
    plan.enabled = plan.with_model = plan.local_model_only = True
    from icarus_memory.server import _wire_scheduler
    _wire_scheduler(app)


def mail(app, body=MAILTEXT, titel="Angebot Dachsanierung", absender="Jonas Beispiel <jonas@example.org>", ref="1"):
    episode, created = app.state.episodes.record(
        EpisodeKind.MESSAGE, titel, body, Provenance(SourceType.EMAIL, source_ref=f"mail:synthetic:{ref}"),
        participants=[absender], at=AT)
    assert created
    return episode


def dokument(app, body=DOKUTEXT):
    episode, created = app.state.episodes.record(
        EpisodeKind.DOCUMENT, "Notiz.md", body, Provenance(SourceType.DOCUMENT, source_ref="upload:Notiz.md"), at=AT)
    assert created
    return episode


class Attrappe:
    """Antwortet wie die Claude API auf jede der vier Fragen (Einordnung, Themen, Bitten, Prüfung); zählt mit."""

    def __init__(self, monkeypatch, vor_antwort=None):
        self.sendungen: list[dict] = []
        self.vor_antwort = vor_antwort
        monkeypatch.setattr(AnthropicImportProvider, "_client",
                            lambda provider: httpx.Client(transport=httpx.MockTransport(self.handler)))

    def handler(self, request):
        payload = json.loads(request.content)
        schema = payload["tools"][0]["input_schema"]["properties"]
        frage = json.loads(payload["messages"][-1]["content"])
        if "reviews" in schema:
            art, ergebnis = "pruefung", {"reviews": [{"id": i, "kind": "request_to_recipient", "title_supported": True}
                                                     for i in range(len(frage["candidates"]))]}
        elif "items" in schema and schema["items"]["type"] == "object":
            art, ergebnis = "einordnung", {"items": {block["block_id"]: "request" for block in frage["blocks"]}}
        elif "items" in schema:
            art = "bitten"
            ergebnis = {"items": [{"title": "Angebot schicken", "quote": ZITAT}] if ZITAT in frage["body"] else []}
        else:
            art, ergebnis = "themen", {"categories": [], "entities": []}
        self.sendungen.append({"art": art, "frage": frage, "modell": payload["model"]})
        if self.vor_antwort is not None:
            self.vor_antwort(self)
        return httpx.Response(200, json={"stop_reason": "tool_use", "content": [
            {"type": "tool_use", "name": "memory_result", "input": ergebnis}]})

    def texte(self) -> str:
        return json.dumps([s["frage"] for s in self.sendungen], ensure_ascii=False)

    def arten(self) -> list[str]:
        return [s["art"] for s in self.sendungen]


def lauf(app) -> list[JobResult]:
    return [app.state.scheduler._run_working_memory(True), app.state.scheduler._run_task_detection(True)]


# -- 1. Einwilligung nur für diese Rolle, nur Anthropic ----------------------------------------------------------

def test_ohne_einwilligung_kein_anbieter_und_fremde_einwilligung_gilt_nicht(ohne_lokal):
    app, client = ohne_lokal
    zugang(client)
    assert hintergrund_cloud.anbieter(app) is None
    assert rollen_von(app).hintergrund_cloud_wahl() is None
    # Die Einwilligung der Antwort gilt nicht für den Hintergrund.
    assert client.put("/api/v1/models/roles/antwort",
                      json={"cloud": True, "anbieter": "anthropic", "einwilligung": True}).status_code == 200
    assert hintergrund_cloud.anbieter(app) is None
    assert hintergrund_cloud.stand(app)["aktiv"] is False and hintergrund_cloud.stand(app)["zugang_da"] is True
    # Ein Handeintrag mit anderem Anbieter wirkt nicht.
    app.state.settings.model_roles["hintergrund"] = {"cloud": True, "anbieter": "openai",
                                                     "cloud_einwilligung": AT.isoformat()}
    assert rollen_von(app).hintergrund_cloud_wahl() is None and hintergrund_cloud.anbieter(app) is None


@pytest.mark.parametrize("anbieter", ["mistral", "openrouter", "openai", "ollama-cloud"])
def test_andere_anbieter_sind_fuer_den_hintergrund_nicht_vorgesehen(mit_lokal, anbieter, monkeypatch):
    app, client = mit_lokal
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("MISTRAL_API_KEY", "k")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    app.state.settings.cloud_models.update({"mistral": "m", "openrouter": "m"})
    antwort = client.put(ROLLE, json={"cloud": True, "anbieter": anbieter, "einwilligung": True, "modell": "x:cloud"})
    assert antwort.status_code == 422, antwort.text
    assert "hintergrund" not in app.state.settings.model_roles
    assert rollen_von(app).provider("hintergrund").is_local


def test_rollenzustand_nennt_den_erlaubten_anbieter_und_den_stand(ohne_lokal):
    app, client = ohne_lokal
    zeilen = {z["rolle"]: z for z in client.get("/api/v1/models/roles").json()["rollen"]}
    assert zeilen["hintergrund"]["cloud_anbieter"] == ["anthropic"] and zeilen["hintergrund"]["cloud_moeglich"] is True
    assert "Anthropic" in zeilen["hintergrund"]["cloud_satz"] and str(TAGESBUDGET) in zeilen["hintergrund"]["cloud_satz"]
    assert set(zeilen["frage"]["cloud_anbieter"]) >= {"anthropic", "openai", "mistral", "openrouter"}
    assert zeilen["pruefung"]["cloud_moeglich"] is False and zeilen["einbettung"]["cloud_moeglich"] is False
    stand = zeilen["hintergrund"]["cloud_einordnung"]
    assert stand == {"aktiv": False, "modell": "", "seit": None, "heute": 0, "tagesbudget": TAGESBUDGET,
                     "erschoepft": False, "zugang_da": False}


# -- 2. Zugang ------------------------------------------------------------------------------------------------------

def test_einschalten_braucht_den_vorbereiteten_zugang(mit_lokal):
    app, client = mit_lokal
    antwort = einschalten(client)
    assert antwort.status_code == 422 and "Claude-Zugang" in antwort.json()["detail"]
    assert "hintergrund" not in app.state.settings.model_roles
    ohne_ja = client.put(ROLLE, json={"cloud": True, "anbieter": "anthropic"})
    zugang(client)
    assert ohne_ja.status_code == 422 and client.put(ROLLE, json={"cloud": True, "anbieter": "anthropic"}).status_code == 422
    antwort = einschalten(client)
    assert antwort.status_code == 200, antwort.text
    gespeichert = app.state.settings.model_roles["hintergrund"]
    assert gespeichert["cloud"] and gespeichert["anbieter"] == "anthropic" and gespeichert["cloud_einwilligung"]
    stand = {z["rolle"]: z for z in antwort.json()["rollen"]}["hintergrund"]["cloud_einordnung"]
    assert stand["aktiv"] is True and stand["modell"] == "claude-synthetic" and stand["seit"] == gespeichert["cloud_einwilligung"]
    assert isinstance(hintergrund_cloud.anbieter(app), AnthropicImportProvider)
    # Die Rolle selbst bleibt lokal: Verdichtung, Lage und Mailhilfe sehen den Cloud-Anbieter nie.
    assert rollen_von(app).provider("hintergrund").is_local and hintergrund_anbieter(app).is_local
    assert stand["aktiv"] and app.state.scheduler.config["with_model"] is False  # der Zeitplan ist noch aus


def test_schluesselwechsel_loescht_die_einwilligung_und_laesst_das_lokale_modell(mit_lokal):
    app, client = mit_lokal
    zugang(client)
    assert client.put(ROLLE, json={"modell": "gross:35b"}).status_code == 200
    assert einschalten(client).status_code == 200
    assert app.state.settings.model_roles["hintergrund"]["modell"] == "gross:35b"  # das lokale Modell bleibt beim Einschalten
    assert rollen_von(app).provider("hintergrund").model == "gross:35b"
    zugang(client, schluessel="synthetic-claude-key-2")
    assert rollen_von(app).hintergrund_cloud_wahl() is None and hintergrund_cloud.anbieter(app) is None
    assert rollen_von(app).provider("hintergrund").model == "gross:35b"
    assert app.state.settings.model_roles["hintergrund"].get("modell") == "gross:35b"
    # Ausschalten mit einem Klick lässt das lokale Modell ebenfalls stehen.
    assert einschalten(client).status_code == 200
    assert client.put(ROLLE, json={"cloud": False}).status_code == 200
    assert app.state.settings.model_roles["hintergrund"]["modell"] == "gross:35b"
    assert not app.state.settings.model_roles["hintergrund"]["cloud"]
    assert client.delete(ZUGANG).status_code == 200
    assert hintergrund_cloud.stand(app)["zugang_da"] is False


# -- 3. Der Lauf -----------------------------------------------------------------------------------------------------

def test_eine_neue_mail_geht_vollstaendig_durch_einordnung_themen_und_zusagen(ohne_lokal, monkeypatch):
    app, client = ohne_lokal
    attrappe = Attrappe(monkeypatch)
    zugang(client)
    assert einschalten(client).status_code == 200
    freigeben(app)
    assert app.state.scheduler.config["with_model"] is True
    episode = mail(app)
    doku = dokument(app)
    ergebnisse = lauf(app)
    assert attrappe.arten() == ["einordnung", "themen", "bitten", "pruefung"], attrappe.arten()
    assert "\n\n".join(b["text"] for b in attrappe.sendungen[0]["frage"]["blocks"]) == MAILTEXT  # der volle Text
    assert attrappe.sendungen[2]["frage"]["body"] == MAILTEXT and attrappe.sendungen[2]["frage"]["subject"] == episode.title
    assert all(s["modell"] == "claude-synthetic" for s in attrappe.sendungen)
    assert DOKUTEXT not in attrappe.texte()
    speicher = WorkingMemoryStore(app.state.episodes)
    assert speicher.source_state(episode.id) == "complete"
    assert speicher.source_state(doku.id) == "pending"  # das Dokument wartet auf ein lokales Modell
    with app.state.episodes._lock:
        row = app.state.episodes._conn.execute(
            "SELECT model FROM working_memory_sources WHERE episode_id=?", (episode.id,)).fetchone()
    assert row[0] == "anthropic:claude-synthetic"
    from icarus_memory.proposals import ProposalKind
    vorschlaege = app.state.proposals.pending(ProposalKind.TASK)
    assert len(vorschlaege) == 1 and vorschlaege[0].evidence[0].quote == ZITAT
    assert vorschlaege[0].proposed_by.startswith("anthropic/claude-synthetic")
    assert ergebnisse[0].ok and "Anthropic" in ergebnisse[0].detail and "lokales Modell" in ergebnisse[0].detail
    assert ergebnisse[1].ok and "1 Quellen geprüft" in ergebnisse[1].detail
    assert hintergrund_cloud.stand(app)["heute"] == 4
    # Ein zweiter Lauf fragt nichts erneut.
    lauf(app)
    assert len(attrappe.sendungen) == 4


def test_werbemail_und_dokument_gehen_nicht_in_die_cloud(ohne_lokal, monkeypatch):
    app, client = ohne_lokal
    attrappe = Attrappe(monkeypatch)
    zugang(client)
    assert einschalten(client).status_code == 200
    freigeben(app)
    werbung = mail(app, body="Nur heute 20 % auf alles im Shop.", titel="20 % Rabatt auf alles",
                   absender="newsletter@shop.example", ref="werbung")
    dokument(app)
    lauf(app)
    assert attrappe.sendungen == []
    assert WorkingMemoryStore(app.state.episodes).source_state(werbung.id) == "pending"


def test_bei_pause_kein_aufruf(ohne_lokal, monkeypatch):
    app, client = ohne_lokal
    attrappe = Attrappe(monkeypatch)
    zugang(client)
    assert einschalten(client).status_code == 200
    freigeben(app)
    mail(app)
    app.state.hintergrund.pausieren(True)
    with als_hintergrund():
        lauf(app)
    assert attrappe.sendungen == []
    app.state.hintergrund.pausieren(False)
    with als_hintergrund():
        lauf(app)
    assert attrappe.arten()[:1] == ["einordnung"]


def test_widerruf_mitten_im_lauf_stoppt_jeden_weiteren_aufruf(ohne_lokal, monkeypatch):
    app, client = ohne_lokal

    def widerrufen(attrappe):
        if len(attrappe.sendungen) == 1:
            app.state.settings.model_roles.pop("hintergrund")

    attrappe = Attrappe(monkeypatch, vor_antwort=widerrufen)
    zugang(client)
    assert einschalten(client).status_code == 200
    freigeben(app)
    erste, zweite = mail(app, ref="a"), mail(app, ref="b", body="Zweite synthetische Mail mit Bitte um Rückruf.")
    ergebnisse = lauf(app)
    assert len(attrappe.sendungen) == 1  # die Antwort auf den ersten Aufruf wird verworfen, kein zweiter
    speicher = WorkingMemoryStore(app.state.episodes)
    assert speicher.source_state(erste.id) != "complete" and speicher.source_state(zweite.id) != "complete"
    assert hintergrund_cloud.anbieter(app) is None
    assert ergebnisse[0].name == "gedaechtnis"


def test_eingegrenzt_prueft_quelle_und_fassung_bei_jedem_aufruf(ohne_lokal, monkeypatch):
    app, client = ohne_lokal
    zugang(client)
    assert einschalten(client).status_code == 200
    freigeben(app)
    episode = mail(app)
    anbieter = hintergrund_cloud.anbieter(app)
    scoped, policy = hintergrund_cloud.eingegrenzt(app, anbieter, episode)
    assert policy.permits(scoped, episode) is True
    assert policy.permits(anbieter, episode) is False  # nur der eingegrenzte Anbieter
    assert policy.permits(scoped, dokument(app)) is False
    app.state.settings.schedule.with_model = False
    assert policy.permits(scoped, episode) is False
    app.state.settings.schedule.with_model = True
    assert policy.permits(scoped, episode) is True
    assert hintergrund_cloud.eingegrenzt(app, anbieter, dokument(app, body="Zweites Dokument"))[1] is None
    # Eine Quelle, die nicht mehr aktuell ist (zurückgezogen), wird nicht mehr freigegeben.
    WorkingMemoryStore(app.state.episodes).dismiss(episode.id)
    assert policy.permits(scoped, episode) is False


# -- 4. Tagesbudget ---------------------------------------------------------------------------------------------------

def test_tagesbudget_weist_den_aufruf_301_ab_und_zaehlt_am_naechsten_tag_neu(ohne_lokal, monkeypatch):
    app, client = ohne_lokal
    attrappe = Attrappe(monkeypatch)
    zugang(client)
    assert einschalten(client).status_code == 200
    freigeben(app)
    budget = hintergrund_cloud.budget(app)
    for _ in range(TAGESBUDGET - 1):
        assert budget.zaehlen()
    assert budget.stand() == TAGESBUDGET - 1 and not hintergrund_cloud.stand(app)["erschoepft"]
    mail(app)
    ergebnis = app.state.scheduler._run_working_memory(True)
    assert len(attrappe.sendungen) == 1  # Aufruf Nr. 300 ging hinaus, Nr. 301 (Themen) nicht
    assert budget.stand() == TAGESBUDGET
    assert hintergrund_cloud.stand(app)["erschoepft"] is True
    assert hintergrund_cloud.SATZ_ERSCHOEPFT in ergebnis.detail and str(TAGESBUDGET) in ergebnis.detail
    # Ein weiterer Lauf ruft nichts, sagt aber warum.
    weitere = lauf(app)
    assert len(attrappe.sendungen) == 1 and budget.stand() == TAGESBUDGET
    assert hintergrund_cloud.SATZ_ERSCHOEPFT in weitere[0].detail
    assert hintergrund_cloud.SATZ_ERSCHOEPFT in weitere[1].detail
    # Am nächsten Tag geht es weiter.
    monkeypatch.setattr(hintergrund_cloud, "heute", lambda: "2026-10-21")
    assert budget.stand() == 0 and not hintergrund_cloud.stand(app)["erschoepft"]
    lauf(app)
    assert len(attrappe.sendungen) > 1


def test_das_budget_wird_einmal_je_tag_im_logbuch_vermerkt(ohne_lokal, monkeypatch):
    app, client = ohne_lokal
    from icarus_memory import logbuch
    vermerke = []
    monkeypatch.setattr(logbuch, "vermerke", lambda art, **daten: vermerke.append((art, daten)) or True)
    budget = hintergrund_cloud.budget(app)
    for _ in range(TAGESBUDGET):
        assert budget.zaehlen()
    assert not budget.zaehlen() and not budget.zaehlen()
    assert [v for v in vermerke if v[0] == "cloud_einordnung"] == [("cloud_einordnung", {"tag": hintergrund_cloud.heute(), "tagesbudget": TAGESBUDGET})]


# -- 5. Was nie in die Cloud geht -----------------------------------------------------------------------------------

def test_verdichtung_lage_und_mailhilfe_bekommen_den_cloud_anbieter_nie(ohne_lokal, monkeypatch):
    app, client = ohne_lokal
    attrappe = Attrappe(monkeypatch)
    zugang(client)
    assert einschalten(client).status_code == 200
    freigeben(app)
    mail(app)
    assert hintergrund_anbieter(app) is None
    assert app.state.consolidator._provider is None and app.state.summarizer._provider is None
    from icarus_memory.mail_reply_suggestions import _mailhilfe_provider
    assert _mailhilfe_provider(app) is None
    assert client.post("/api/v1/messages/a%3A1.1/reply-suggestion", json={}).status_code == 503
    lage = app.state.scheduler._run_lage(True)
    assert lage.name == "lage" and attrappe.sendungen == []
    verdichtung = client.post("/consolidate", json={"with_model": True}).json()
    assert verdichtung["used_model"] is False and attrappe.sendungen == []
    client.post("/summaries/run", json={"with_model": True})
    assert attrappe.sendungen == []


def test_ein_lokales_modell_bearbeitet_andere_quellen_und_mails_gehen_in_die_cloud(mit_lokal, monkeypatch):
    app, client = mit_lokal
    attrappe = Attrappe(monkeypatch)
    lokal_aufrufe = []

    class Antwort:
        tool_calls = []

        def __init__(self, text):
            self.text = text

    from icarus_memory.providers import OpenAICompatible

    def lokal(self, messages, *, max_tokens, schema):
        frage = json.loads(messages[-1]["content"])
        lokal_aufrufe.append(frage)
        if "blocks" in frage:
            return Antwort(json.dumps({"items": {b["block_id"]: "fact" for b in frage["blocks"]}}))
        if "candidates" in frage:
            return Antwort(json.dumps({"reviews": []}))
        if "body" in frage and "subject" in frage:
            return Antwort(json.dumps({"items": []}))
        return Antwort(json.dumps({"categories": [], "entities": []}))

    monkeypatch.setattr(OpenAICompatible, "complete_json", lokal, raising=False)
    monkeypatch.setattr("icarus_memory.local_model_guard.verify_local_model", lambda provider: None)
    zugang(client)
    assert einschalten(client).status_code == 200
    freigeben(app)
    brief = mail(app)
    doku = dokument(app)
    lauf(app)
    assert MAILTEXT not in json.dumps(lokal_aufrufe, ensure_ascii=False)
    assert DOKUTEXT not in attrappe.texte()
    assert any(DOKUTEXT in json.dumps(frage, ensure_ascii=False) for frage in lokal_aufrufe)
    speicher = WorkingMemoryStore(app.state.episodes)
    assert speicher.source_state(brief.id) == "complete" and speicher.source_state(doku.id) == "complete"


# -- 6. Automatik und Stand ----------------------------------------------------------------------------------------

def test_automatik_laesst_sich_ohne_lokales_modell_einschalten_wenn_die_cloud_einordnung_aktiv_ist(ohne_lokal):
    app, client = ohne_lokal
    assert client.put("/api/v1/memory/automation", json={"enabled": True}).status_code == 409
    zugang(client)
    assert einschalten(client).status_code == 200
    antwort = client.put("/api/v1/memory/automation", json={"enabled": True})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["state"] == "cloud_aktiv" and antwort.json()["cloud_einordnung"]["aktiv"] is True
    plan = app.state.settings.schedule
    assert (plan.enabled, plan.with_model, plan.local_model_only) == (True, True, True)
    assert client.get("/api/v1/memory/automation").json()["state"] == "cloud_aktiv"
    assert client.get("/api/v1/memory/coverage").json()["automation"]["state"] == "cloud_aktiv"
    assert client.get("/api/v1/mail/intake").json()["analysis_active"] is True
    assert client.get("/api/v1/hintergrund").json()["zustand"] != "ohne_modell"
    assert client.put(ROLLE, json={"cloud": False}).status_code == 200
    assert client.get("/api/v1/memory/automation").json()["state"] == "model_missing"
    assert client.get("/api/v1/mail/intake").json()["analysis_active"] is False


# -- 7. Das vorbereitete Modell gilt, nicht die Vorgabe ---------------------------------------------------------------

def test_vorbereitetes_modell_statt_vorgabe_auch_fuer_die_antwort(ohne_lokal):
    app, client = ohne_lokal
    zugang(client, modell="claude-synthetic-prepared")
    antwort = client.put("/api/v1/models/roles/antwort", json={"cloud": True, "anbieter": "anthropic", "einwilligung": True})
    assert antwort.status_code == 200, antwort.text
    anbieter = rollen_von(app).provider("antwort")
    assert anbieter.name == "anthropic" and anbieter.model == "claude-synthetic-prepared"
    assert app.state.settings.model_roles["antwort"]["modell"] == "claude-synthetic-prepared"
    assert einschalten(client).status_code == 200
    assert hintergrund_cloud.anbieter(app).model == "claude-synthetic-prepared"
