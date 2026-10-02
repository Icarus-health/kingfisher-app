"""Der Nachtrag im Hintergrundtakt: klein, gedrosselt, freigabetreu, mit Fortschritt und Ende.

Zusicherungen: Pakete bleiben klein. Liegt die Einordnung im Rückstau, ruht der
Nachtrag und läuft danach weiter. Ohne Freigabe (auch wenn sie mitten im Paket
fällt) wird nichts geholt und nichts geschrieben. Mails, deren Server keine
Kopfzeilen liefert, blockieren die übrigen nicht. Der Fortschritt ist im
Aufnahmestatus sichtbar; ist alles ergänzt, endet der Lauf.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from icarus_memory import teilnehmer_nachtrag
from icarus_memory.mail_intake import Intake
from icarus_memory.mail_intake_routes import register

from .test_teilnehmer_nachtrag import Leser, _alte_mail, episodes  # noqa: F401 - Fixture wird mitgenommen


def _eingeordnet(episodes, episode_id):
    """Markiert eine Mail als auf ihrem jetzigen Stand eingeordnet."""
    with episodes.transaction():
        episodes._conn.execute(
            "INSERT OR REPLACE INTO mail_intake_analysis(episode_id,generation,status) "
            "SELECT id,support_generation,'complete' FROM episodes WHERE id=?", (episode_id,))


def _wartend(episodes, nummer):
    """Eine Mail mit Rollen, die noch auf ihre Einordnung wartet (wie nach einem Nachtrag)."""
    mail = _alte_mail(episodes, nummer)
    episodes.add_contacts(mail.id, [{"name": "A", "adresse": "a@x.example", "rolle": "von"}], [])
    return mail


def _lauf():
    return teilnehmer_nachtrag.Lauf(paket=2, grenze=3)


def _schritt(lauf, episodes, leser, **kw):
    kw.setdefault("permitted", lambda: True)
    kw.setdefault("mit_modell", False)
    return lauf.schritt(episodes, leser, "k", **kw)


def test_takt_arbeitet_in_kleinen_paketen_mit_fortschritt_und_endet(episodes):
    for nummer in range(1, 6):
        _eingeordnet(episodes, _alte_mail(episodes, nummer).id)
    lauf, leser = _lauf(), Leser()
    assert lauf.status("k") is None
    assert _schritt(lauf, episodes, leser)["ergaenzt"] == 2
    assert lauf.status("k") == {"offen": 3, "ergaenzt": 2, "ohne_kopfzeilen": 0, "gedrosselt": False, "fertig": False}
    assert _schritt(lauf, episodes, leser)["ergaenzt"] == 2
    assert _schritt(lauf, episodes, leser)["ergaenzt"] == 1
    assert _schritt(lauf, episodes, leser) is None
    assert lauf.status("k") == {"offen": 0, "ergaenzt": 5, "ohne_kopfzeilen": 0, "gedrosselt": False, "fertig": True}
    abrufe = len(leser.abrufe)
    assert _schritt(lauf, episodes, leser) is None and len(leser.abrufe) == abrufe


def test_rueckstau_der_einordnung_bremst_und_danach_geht_es_weiter(episodes):
    for nummer in range(1, 4):
        _eingeordnet(episodes, _alte_mail(episodes, nummer).id)
    for nummer in range(10, 15):
        _wartend(episodes, nummer)                       # 5 warten > Grenze 3
    lauf, leser = _lauf(), Leser()
    assert _schritt(lauf, episodes, leser, mit_modell=True) is None
    assert leser.abrufe == [] and lauf._konten["k"].gedrosselt
    for nummer in range(10, 15):
        _eingeordnet(episodes, teilnehmer_nachtrag_id(episodes, nummer))
    assert _schritt(lauf, episodes, leser, mit_modell=True)["ergaenzt"] == 2
    assert not lauf._konten["k"].gedrosselt


def test_ohne_modell_gibt_es_keinen_rueckstau_zu_beachten(episodes):
    for nummer in range(1, 4):
        _eingeordnet(episodes, _alte_mail(episodes, nummer).id)
    for nummer in range(10, 15):
        _wartend(episodes, nummer)
    assert _schritt(_lauf(), episodes, Leser(), mit_modell=False)["ergaenzt"] == 2


def teilnehmer_nachtrag_id(episodes, nummer):
    return episodes._conn.execute("SELECT episode_id FROM mail_intake_items WHERE uid=?", (nummer,)).fetchone()[0]


def test_ohne_freigabe_wird_weder_geholt_noch_geschrieben(episodes):
    mail = _alte_mail(episodes, 1)
    leser = Leser()
    assert _schritt(_lauf(), episodes, leser, permitted=lambda: False) is None
    assert leser.abrufe == [] and episodes.get(mail.id).contacts == []


def test_freigabe_zurueckgenommen_nach_dem_abruf_schreibt_nichts(episodes):
    mail = _alte_mail(episodes, 1)
    leser = Leser()
    aufrufe = []

    def freigabe():
        aufrufe.append(1)
        return not leser.abrufe            # gilt vor dem Abruf, danach nicht mehr

    _schritt(_lauf(), episodes, leser, permitted=freigabe)
    assert leser.abrufe == ["1.1"] and episodes.get(mail.id).contacts == []


def test_geschrieben_wird_unter_der_gemeinsamen_sperre(episodes):
    _alte_mail(episodes, 1)
    sperre = threading.RLock()
    gehalten = []
    original = episodes.add_contacts

    def add_contacts(*args, **kwargs):
        gehalten.append(sperre._is_owned())
        return original(*args, **kwargs)

    episodes.add_contacts = add_contacts
    _schritt(_lauf(), episodes, Leser(), permission_lock=sperre)
    assert gehalten == [True]


def test_mail_ohne_kopfzeilen_blockiert_die_uebrigen_nicht_und_wird_nicht_endlos_geholt(episodes):
    neueste_leer = _alte_mail(episodes, 9)               # von `Leser` nie mit Beteiligten beliefert
    _alte_mail(episodes, 1)

    class NurEine(Leser):
        def message_in_folder(self, folder, uid):
            nachricht = super().message_in_folder(folder, uid)
            if uid == "1.9":
                from dataclasses import replace
                return replace(nachricht, sender="", recipients=(), own_addresses=())
            return nachricht

    leser = NurEine()
    lauf = teilnehmer_nachtrag.Lauf(paket=1, grenze=3)
    for _ in range(4):
        _schritt(lauf, episodes, leser)
    assert leser.abrufe.count("1.9") == 1                # genau einmal versucht
    assert lauf.status("k")["ohne_kopfzeilen"] == 1 and lauf.status("k")["fertig"]
    assert episodes.get(neueste_leer.id).contacts == []


def test_gescheiterte_mail_ruht_und_kommt_nach_der_pause_wieder(episodes):
    _alte_mail(episodes, 1)
    leser = Leser()
    leser.scheitert = {"1.1"}
    zeit = [0.0]
    lauf = teilnehmer_nachtrag.Lauf(paket=1, grenze=3, uhr=lambda: zeit[0])
    assert _schritt(lauf, episodes, leser)["fehler"] == 1
    assert _schritt(lauf, episodes, leser) is None       # ruht, blockiert nichts
    assert not lauf.status("k")["fertig"]                # aber ist nicht vergessen
    leser.scheitert = set()
    zeit[0] += teilnehmer_nachtrag.PAUSE_NACH_FEHLER + 1
    assert _schritt(lauf, episodes, leser)["ergaenzt"] == 1


def test_eine_mail_in_zwei_ordnern_zaehlt_und_wird_einmal_geholt(episodes):
    mail = _alte_mail(episodes, 1)
    with episodes.transaction():
        episodes._conn.execute(
            "INSERT INTO mail_intake_items(account,folder,generation,uid,lane,status,episode_id) "
            "VALUES('k','Archiv','1',7,'history','duplicate',?)", (mail.id,))
    leser = Leser()
    assert teilnehmer_nachtrag.anzahl_offen(episodes, "k") == 1
    assert _schritt(_lauf(), episodes, leser)["ergaenzt"] == 1
    assert len(leser.abrufe) == 1


# --- Anzeige im Aufnahmestatus ----------------------------------------------

@pytest.fixture
def api(tmp_path, episodes, monkeypatch):
    app = FastAPI()
    app.state.episodes = episodes
    app.state.settings = SimpleNamespace(
        mail_accounts=[SimpleNamespace(id="k", label="Test", configured=True)],
        schedule=SimpleNamespace(mail_accounts=["k"], enabled=True))
    app.state.conversation_lock = threading.RLock()
    app.state.nachtrag = _lauf()
    monkeypatch.setattr("icarus_memory.mail_intake_routes.config.save", lambda *a: None)
    register(app, [], lambda: tmp_path, lambda app: None)
    with TestClient(app) as client:
        yield app, client


def test_status_zeigt_fortschritt_des_nachtrags(api, episodes):
    app, client = api
    Intake(episodes).start("k", ["INBOX"])
    assert client.get("/api/v1/mail/intake").json()["accounts"][0]["empfaengernachtrag"] is None
    for nummer in range(1, 4):
        _eingeordnet(episodes, _alte_mail(episodes, nummer).id)
    _schritt(app.state.nachtrag, episodes, Leser())
    zustand = client.get("/api/v1/mail/intake").json()["accounts"][0]["empfaengernachtrag"]
    assert zustand == {"offen": 1, "ergaenzt": 2, "ohne_kopfzeilen": 0, "gedrosselt": False, "fertig": False}
