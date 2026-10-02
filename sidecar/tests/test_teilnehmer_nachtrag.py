"""Nachtrag der Beteiligten für Mails aus der Zeit vor der Rollenangabe.

Zusicherungen: Der Text bleibt, wie er war; nur Metadaten wachsen. Ausgeschlossene
Quellen bleiben unberührt. Ein Fehler beim Abruf lässt die Mail offen; sie kommt
beim nächsten Paket wieder. Ist alles ergänzt, gibt es nichts mehr zu holen.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from icarus_memory import personen, teilnehmer_nachtrag
from icarus_memory.connectors.mail import Message
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType

AT = datetime(2026, 9, 29, 10, 0, tzinfo=timezone.utc)
ICH = "lea@hartmann-beratung.example"


class Leser:
    """Ein Konto, das nur `message_in_folder` kennt."""

    def __init__(self):
        self.abrufe = []
        self.scheitert = set()

    def message_in_folder(self, folder, uid):
        self.abrufe.append(uid)
        if uid in self.scheitert:
            raise OSError("Verbindung abgebrochen")
        return Message(
            uid=uid, subject="Angebot", sender="Anna Keller <anna@x.example>", date=AT, preview="", unread=False,
            recipients=({"name": "Lea Hartmann", "adresse": ICH, "rolle": "an"},
                        {"name": "Bernd Moll", "adresse": "bernd@y.example", "rolle": "cc"}),
            own_addresses=(ICH,))


@pytest.fixture
def episodes(tmp_path: Path) -> EpisodeStore:
    return EpisodeStore(tmp_path / "episodes.sqlite3")


def _alte_mail(episodes, nummer, *, ignoriert=False):
    episode, _ = episodes.record(
        EpisodeKind.MESSAGE, "Angebot", f"Text {nummer}", Provenance(SourceType.EMAIL, f"k:{nummer}", AT),
        occurred_at=AT, participants=["Anna Keller <anna@x.example>"])
    with episodes.transaction():
        episodes._conn.execute(
            "INSERT INTO mail_intake_items(account,folder,generation,uid,lane,status,episode_id) "
            "VALUES('k','INBOX','1',?,'history','captured',?)", (nummer, episode.id))
    if ignoriert:
        episodes.ignore(episode.id)
    return episode


def test_beteiligte_werden_nachgetragen_und_der_text_bleibt(episodes):
    alt = _alte_mail(episodes, 1)
    ergebnis = teilnehmer_nachtrag.nachtragen(episodes, Leser(), "k")
    assert ergebnis == {"ergaenzt": 1, "fehlend": 0, "fehler": 0}
    neu = episodes.get(alt.id)
    assert neu.body == alt.body and neu.digest == alt.digest
    assert {(c["adresse"], c["rolle"]) for c in neu.contacts} == {
        ("anna@x.example", "von"), (ICH, "an"), ("bernd@y.example", "cc")}
    assert neu.participants[0] == "Anna Keller <anna@x.example>"
    # Eigene Adresse ist „ich“: Kontakte sind Anna und Bernd.
    assert {m.id for m in personen.alle(episodes=episodes, jetzt=AT)} == {"a:anna@x.example", "a:bernd@y.example"}


def test_zweiter_durchgang_findet_nichts_mehr(episodes):
    _alte_mail(episodes, 1)
    leser = Leser()
    teilnehmer_nachtrag.nachtragen(episodes, leser, "k")
    assert teilnehmer_nachtrag.nachtragen(episodes, leser, "k") == {"ergaenzt": 0, "fehlend": 0, "fehler": 0}
    assert len(leser.abrufe) == 1


def test_ausgeschlossene_quelle_wird_nicht_angefasst(episodes):
    _alte_mail(episodes, 1, ignoriert=True)
    leser = Leser()
    assert teilnehmer_nachtrag.nachtragen(episodes, leser, "k")["ergaenzt"] == 0
    assert leser.abrufe == []


def test_fehler_laesst_die_mail_offen_und_stoppt_das_paket_nicht(episodes):
    _alte_mail(episodes, 1)
    _alte_mail(episodes, 2)
    leser = Leser()
    leser.scheitert = {"1.1"}
    assert teilnehmer_nachtrag.nachtragen(episodes, leser, "k") == {"ergaenzt": 1, "fehlend": 0, "fehler": 1}
    leser.scheitert = set()
    assert teilnehmer_nachtrag.nachtragen(episodes, leser, "k")["ergaenzt"] == 1


def test_paketgroesse_ist_begrenzt(episodes):
    for nummer in range(1, 6):
        _alte_mail(episodes, nummer)
    leser = Leser()
    assert teilnehmer_nachtrag.nachtragen(episodes, leser, "k", limit=2)["ergaenzt"] == 2
    assert len(leser.abrufe) == 2
