"""Beteiligte mit Rolle und Identität über Adressen (Etappe C3).

Zusicherungen, jede mit einer Sabotageprobe (siehe docs/evaluations/messlatte/C3-identitaet.md):

1. To und Cc einer Mail werden Beteiligte, mit Rolle; Bcc nur bei eigener Kopie.
2. Die eigenen Adressen sind „ich“ und zählen nicht als fremde Person.
3. Gleiche Adresse ist dieselbe Person, gleich wie der Anzeigename lautet.
4. Gleicher Name mit verschiedenen Adressen sind zwei Personen.
5. Ein Name ohne Adresse wird nur bei Eindeutigkeit zugeordnet.
6. Eine Mail ohne Rollen, später mit Empfängern gelesen, wird ergänzt statt verdoppelt.
"""

from __future__ import annotations

from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

import pytest

from icarus_memory import identitaet, kontakte, mail_ingestion, personen
from icarus_memory.connectors.mail import Message, _empfaenger
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.source_versions import track_source

JETZT = datetime(2026, 9, 29, 10, 0, tzinfo=timezone.utc)
ICH = "lea@hartmann-beratung.example"


@pytest.fixture
def episodes(tmp_path: Path) -> EpisodeStore:
    return EpisodeStore(tmp_path / "episodes.sqlite3")


def _mail(uid, sender, an=(), cc=(), bcc=(), *, text="Guten Tag", eigene=(ICH,), mid=None):
    def liste(rolle, werte):
        return [{"name": kontakte.anzeigename(w), "adresse": (w.split("<")[-1].strip(">") if "<" in w else w).casefold(),
                 "rolle": rolle} for w in werte]
    return Message(
        uid=f"k:{uid}", subject=f"Betreff {uid}", sender=sender, date=JETZT, preview=text, unread=False,
        body=text, message_id=mid or f"<{uid}@x.example>", account_id="k",
        recipients=tuple(liste("an", an) + liste("cc", cc) + liste("bcc", bcc)),
        own_addresses=tuple(eigene))


# -- 1. To/Cc werden Beteiligte ---------------------------------------------

def test_an_und_cc_werden_beteiligte_mit_rolle(episodes):
    ergebnis = mail_ingestion.remember(episodes, _mail(
        "1", "Anna Keller <anna@x.example>", an=["Lea Hartmann <" + ICH + ">"],
        cc=["Bernd Moll <bernd@y.example>"]))
    episode = episodes.get(ergebnis["episode"]["id"])
    rollen = {(c["adresse"], c["rolle"]) for c in episode.contacts}
    assert rollen == {("anna@x.example", "von"), (ICH, "an"), ("bernd@y.example", "cc")}
    assert episode.participants[0] == "Anna Keller <anna@x.example>"
    # Die eigene Adresse als Empfänger steht in contacts (ich), nicht in participants:
    # Sonst fände die Wortsuche über den eigenen Namen jede empfangene Mail.
    assert episode.participants == ["Anna Keller <anna@x.example>", "Bernd Moll <bernd@y.example>"]
    assert [c["adresse"] for c in episode.contacts if c["ich"]] == [ICH]


def test_bcc_nur_in_der_eigenen_gesendeten_mail(episodes):
    eigene = mail_ingestion.remember(episodes, _mail(
        "2", f"Lea Hartmann <{ICH}>", an=["anna@x.example"], bcc=["chef@z.example"], mid="<2@x>"))
    fremde = mail_ingestion.remember(episodes, _mail(
        "3", "Anna Keller <anna@x.example>", an=[ICH], bcc=["heimlich@z.example"], mid="<3@x>"))
    assert ("chef@z.example", "bcc") in {(c["adresse"], c["rolle"]) for c in episodes.get(eigene["episode"]["id"]).contacts}
    assert "heimlich@z.example" not in {c["adresse"] for c in episodes.get(fremde["episode"]["id"]).contacts}


def test_kopfzeilen_mit_komma_im_namen_bleiben_ganz():
    roh = EmailMessage()
    roh["To"] = '"Keller, Anna" <anna@x.example>, bernd@y.example'
    roh["Cc"] = "=?utf-8?q?M=C3=BCller=2C_Jan?= <jan@z.example>"
    eintraege = _empfaenger(roh)
    assert [(e["rolle"], e["adresse"], e["name"]) for e in eintraege] == [
        ("an", "anna@x.example", "Keller, Anna"), ("an", "bernd@y.example", ""),
        ("cc", "jan@z.example", "Müller, Jan")]


# -- 2. Eigene Adresse ist ich -----------------------------------------------

def test_eigene_adresse_ist_ich_und_keine_fremde_person(episodes):
    mail_ingestion.remember(episodes, _mail("4", "Anna Keller <anna@x.example>", an=[ICH]))
    mail_ingestion.remember(episodes, _mail("5", f"Lea Hartmann <{ICH}>", an=["Bernd Moll <bernd@y.example>"], mid="<5@x>"))
    menschen = personen.alle(episodes=episodes, jetzt=JETZT)
    assert {m.id for m in menschen} == {"a:anna@x.example", "a:bernd@y.example"}


def test_eigene_adresse_aus_den_einstellungen_gilt_auch_fuer_altbestand(episodes):
    episodes.record(EpisodeKind.MESSAGE, "Alt", "Text", Provenance(SourceType.EMAIL, "m1", JETZT),
                    occurred_at=JETZT, participants=[f"Lea Hartmann <{ICH}>"])
    assert [m.id for m in personen.alle(episodes=episodes, jetzt=JETZT)] == [f"a:{ICH}"]
    assert personen.alle(episodes=episodes, jetzt=JETZT, eigene=[ICH]) == []


# -- 3. Gleiche Adresse, eine Person -----------------------------------------

def test_gleiche_adresse_mit_verschiedenen_namen_ist_eine_person(episodes):
    mail_ingestion.remember(episodes, _mail("6", '"Keller, Anna" <anna@x.example>', an=[ICH], mid="<6@x>"))
    mail_ingestion.remember(episodes, _mail("7", "Anna Keller <anna@x.example>", an=[ICH], mid="<7@x>"))
    mail_ingestion.remember(episodes, _mail("8", "anna@x.example", an=[ICH], mid="<8@x>"))
    menschen = personen.alle(episodes=episodes, jetzt=JETZT)
    assert len(menschen) == 1
    anna = menschen[0]
    assert anna.episoden_anzahl == 3
    assert anna.adressen == ["anna@x.example"]
    assert set(anna.namen) == {"Keller, Anna", "Anna Keller"}


# -- 4. Gleicher Name, zwei Adressen ----------------------------------------

def test_gleicher_name_mit_verschiedenen_adressen_sind_zwei_personen(episodes):
    mail_ingestion.remember(episodes, _mail("9", "Alex Winter <alex.winter@winter-catering.example>", an=[ICH], mid="<9@x>"))
    mail_ingestion.remember(episodes, _mail("10", "Alex Winter <alex.winter@ifeh-hessen.example>", an=[ICH], mid="<10@x>"))
    menschen = personen.alle(episodes=episodes, jetzt=JETZT)
    assert len(menschen) == 2
    assert {m.unterscheidung for m in menschen} == {"winter-catering.example", "ifeh-hessen.example"}
    assert all("(" in m.anzeige for m in menschen)  # der Leser sieht den Unterschied


def test_mehrdeutiger_name_ergibt_keine_einzelperson(episodes):
    mail_ingestion.remember(episodes, _mail("11", "Alex Winter <a@catering.example>", an=[ICH], mid="<11@x>"))
    mail_ingestion.remember(episodes, _mail("12", "Alex Winter <a@institut.example>", an=[ICH], mid="<12@x>"))
    with pytest.raises(personen.Mehrdeutig) as fehler:
        personen.eine("Alex Winter", episodes=episodes, jetzt=JETZT)
    assert {p.id for p in fehler.value.kandidaten} == {"a:a@catering.example", "a:a@institut.example"}
    assert personen.eine("a@institut.example", episodes=episodes, jetzt=JETZT).id == "a:a@institut.example"


# -- 5. Name ohne Adresse: nur bei Eindeutigkeit -------------------------------

def test_name_ohne_adresse_wird_bei_genau_einem_kandidaten_zugeordnet(episodes):
    mail_ingestion.remember(episodes, _mail("13", "Anna Keller <anna@x.example>", an=[ICH], mid="<13@x>"))
    episodes.record(EpisodeKind.MESSAGE, "Gespräch", "Text", Provenance(SourceType.DOCUMENT, "n.md", JETZT),
                    occurred_at=JETZT, participants=["Keller, Anna"])
    menschen = personen.alle(episodes=episodes, jetzt=JETZT)
    assert [m.id for m in menschen] == ["a:anna@x.example"]
    assert menschen[0].episoden_anzahl == 2


def test_name_ohne_adresse_bleibt_bei_zwei_kandidaten_offen(episodes):
    mail_ingestion.remember(episodes, _mail("14", "Alex Winter <a@catering.example>", an=[ICH], mid="<14@x>"))
    mail_ingestion.remember(episodes, _mail("15", "Alex Winter <a@institut.example>", an=[ICH], mid="<15@x>"))
    episodes.record(EpisodeKind.MESSAGE, "Gespräch", "Text", Provenance(SourceType.DOCUMENT, "n.md", JETZT),
                    occurred_at=JETZT, participants=["Alex Winter"])
    menschen = {m.id: m for m in personen.alle(episodes=episodes, jetzt=JETZT)}
    offen = menschen["n:alex winter"]
    assert offen.offen_mit == ["a@catering.example", "a@institut.example"]
    assert menschen["a:a@catering.example"].episoden_anzahl == 1  # die Nennung wurde niemandem zugeschlagen
    assert menschen["a:a@institut.example"].episoden_anzahl == 1


def test_name_ohne_adresse_ohne_kandidat_bleibt_eigene_person(episodes):
    episodes.record(EpisodeKind.MESSAGE, "Gespräch", "Text", Provenance(SourceType.DOCUMENT, "n.md", JETZT),
                    occurred_at=JETZT, participants=["Frau Reinhardt"])
    assert [m.id for m in personen.alle(episodes=episodes, jetzt=JETZT)] == ["n:frau reinhardt"]


# -- 6. Nachtrag statt Verdopplung -------------------------------------------

def test_mail_ohne_rollen_wird_beim_erneuten_lesen_ergaenzt_nicht_verdoppelt(episodes):
    alt = _mail("16", "Anna Keller <anna@x.example>", mid="<16@x>")
    vorher, _ = episodes.record(EpisodeKind.MESSAGE, alt.subject, alt.body,
                                Provenance(SourceType.EMAIL, "k:<16@x>", JETZT), occurred_at=JETZT,
                                participants=[alt.sender], source_key=_schluessel(alt))
    track_source(episodes, None, _schluessel(alt), vorher)
    neu = _mail("16", "Anna Keller <anna@x.example>", an=[ICH], cc=["Bernd Moll <bernd@y.example>"], mid="<16@x>")
    ergebnis = mail_ingestion.remember(episodes, neu)
    assert ergebnis["new"] is False
    assert sum(1 for _ in episodes.each_episode()) == 1
    episode = episodes.get(ergebnis["episode"]["id"])
    assert {c["rolle"] for c in episode.contacts} == {"von", "an", "cc"}
    assert episode.body == alt.body


def _schluessel(nachricht):
    import hashlib
    import json
    uid = nachricht.uid[len(nachricht.account_id) + 1:]
    return "mail:" + hashlib.sha256(json.dumps([nachricht.account_id, uid]).encode()).hexdigest()


# -- Kleinteile -------------------------------------------------------------

@pytest.mark.parametrize("links,rechts", [
    ("Keller, Anna", "Anna Keller"), ('"Anna Keller"', "anna  keller"), ("ANNA KELLER", "Anna Keller")])
def test_namen_zum_vergleichen(links, rechts):
    assert identitaet.name_schluessel(links) == identitaet.name_schluessel(rechts)


def test_verschiedene_namen_bleiben_verschieden():
    assert identitaet.name_schluessel("Anna Keller") != identitaet.name_schluessel("Anna Kellner")
    assert identitaet.name_schluessel("Meier, Dr. Thomas, MBA") == "meier, dr. thomas, mba"
