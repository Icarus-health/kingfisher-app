"""Ein großes Postfach: Die Bestandsaufnahme erfasst die neuesten Mails zuerst (docs/46-hintergrund.md).

Vorher ging sie in Fenstern von 200 Nachrichtennummern aufsteigend durch das Postfach. Bei 5.000 Mails lagen so
zuerst die ältesten im Gedächtnis, und bei verstreuten Nummern (UIDs bis in die Hunderttausende) dauerte es Stunden,
bis überhaupt eine Mail von heute erfasst war. Jetzt beginnt die Bestandsaufnahme oben und arbeitet sich nach unten;
nach einem Abbruch geht sie genau dort weiter, ohne Lücke und ohne Doppelung. Nur synthetische Mails, kein Netz.
"""
import random

import pytest

from icarus_memory.connectors.mail import MailConfig, MailConnector, MailError
from icarus_memory.episodes import EpisodeStore
from icarus_memory.mail_intake import Intake


class GrossesPostfach:
    """Ein IMAP-Postfach im Speicher: vorhandene UIDs, UIDNEXT und UIDVALIDITY, nur lesende Befehle."""

    def __init__(self, vorhanden, *, uidnext=None, validity=b"7"):
        self.vorhanden = set(vorhanden)
        self.uidnext = uidnext or max(self.vorhanden) + 1
        self.validity = validity
        self.suchen = []
        #: Die nächste Suche scheitert (Server antwortet NO), danach geht es normal weiter.
        self.scheitern = False
        self.capabilities = (b"IMAP4REV1",)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def login(self, *args):
        pass

    def select(self, folder, readonly):
        assert readonly
        return "OK", [str(len(self.vorhanden)).encode()]

    def response(self, name):
        return name, [self.validity if name == "UIDVALIDITY" else str(self.uidnext).encode()]

    def uid(self, operation, *args):
        if operation == "search":
            if self.scheitern:
                self.scheitern = False
                return "NO", [None]
            von, bis = map(int, args[2].split(":"))
            assert von <= bis and "*" not in args[2]
            self.suchen.append((von, bis))
            return "OK", [" ".join(str(u) for u in sorted(self.vorhanden) if von <= u <= bis).encode()]
        assert operation == "fetch"
        nummer = int(args[0])
        roh = (f"Subject: Mail {nummer}\r\nFrom: absender@example.org\r\nMessage-ID: <m{nummer}@example.org>\r\n"
               f"Date: Thu, 01 Oct 2026 07:00:00 +0000\r\nContent-Type: text/plain\r\n\r\nText {nummer}").encode()
        return "OK", [(f"1 (UID {nummer} FLAGS () RFC822.SIZE {len(roh)})".encode(), roh)]


@pytest.fixture
def postfach(monkeypatch):
    def bauen(vorhanden, **kwargs):
        fake = GrossesPostfach(vorhanden, **kwargs)
        monkeypatch.setattr("icarus_memory.connectors.mail.imaplib.IMAP4_SSL", lambda *a, **kw: fake)
        return MailConnector(MailConfig("imap.example.org", "lena@example.org", "geheim")), fake
    return bauen


def _verlauf(ep, art="history"):
    with ep._lock:
        return [u for (u,) in ep._conn.execute(
            "SELECT uid FROM mail_intake_items WHERE lane=? ORDER BY uid", (art,))]


def _erfasst(ep):
    with ep._lock:
        return [u for (u,) in ep._conn.execute(
            "SELECT uid FROM mail_intake_items WHERE status='captured' ORDER BY uid")]


def test_grosses_postfach_erfasst_die_neuesten_zuerst(tmp_path, postfach):
    connector, fake = postfach(range(1, 5001))
    ep = EpisodeStore(tmp_path / "episodes.sqlite3")
    intake = Intake(ep)
    intake.start("a", ["INBOX"])
    intake.step("a", connector, batch=3)
    # Das erste Fenster liegt oben: die 200 jüngsten Nummern, und davon die drei jüngsten im Gedächtnis.
    assert _verlauf(ep) == list(range(4801, 5001))
    assert _erfasst(ep) == [4998, 4999, 5000]
    assert fake.suchen[0] == (4801, 5000)
    ep.close()


def test_connector_liefert_fenster_von_oben_nach_unten(postfach):
    connector, fake = postfach({1, 103, 105, 207, 310}, uidnext=311)
    erste = connector.inventory_page("INBOX", limit=100, absteigend=True)
    assert erste == {"folder": "INBOX", "uidvalidity": "7", "upper_uid": 310, "uids": [310],
                     "next_uid": 0, "next_before_uid": 210, "done": False}
    zweite = connector.inventory_page("INBOX", before_uid=210, limit=100, absteigend=True)
    assert zweite["uids"] == [207] and zweite["next_before_uid"] == 110 and not zweite["done"]
    dritte = connector.inventory_page("INBOX", before_uid=110, limit=100, absteigend=True)
    assert dritte["uids"] == [103, 105] and dritte["next_before_uid"] == 10 and not dritte["done"]
    letzte = connector.inventory_page("INBOX", before_uid=10, limit=100, absteigend=True)
    assert letzte["uids"] == [1] and letzte["next_before_uid"] == 0 and letzte["done"]
    assert fake.suchen == [(211, 310), (111, 210), (11, 110), (1, 10)]
    # Untere Grenze aus einer früheren, aufsteigenden Bestandsaufnahme: Darunter wird nichts noch einmal gesucht.
    rest = connector.inventory_page("INBOX", after_uid=100, before_uid=150, limit=100, absteigend=True)
    assert rest["uids"] == [103, 105] and rest["next_before_uid"] == 100 and rest["done"]
    assert fake.suchen[-1] == (101, 150)
    # Nichts mehr offen: keine Suche, auch keine rückwärts gerichtete.
    fertig = connector.inventory_page("INBOX", after_uid=100, before_uid=100, limit=100, absteigend=True)
    assert fertig["done"] and fertig["uids"] == [] and fake.suchen[-1] == (101, 150)


def test_abbruch_und_neustart_ohne_luecken_und_doppelungen(tmp_path, postfach):
    zufall = random.Random(46)
    vorhanden = set(zufall.sample(range(1, 20001), 700))
    connector, fake = postfach(vorhanden, uidnext=20001)
    pfad = tmp_path / "episodes.sqlite3"
    ep = EpisodeStore(pfad)
    intake = Intake(ep)
    intake.start("a", ["INBOX"])
    neu_waehrenddessen = None
    for takt in range(400):
        if takt == 7:
            fake.scheitern = True  # Der Server antwortet einmal nicht: Der Zeiger darf nicht weiterrücken.
        if takt == 20:
            ep.close()  # Neustart mitten in der Bestandsaufnahme.
            ep = EpisodeStore(pfad)
            intake = Intake(ep)
        if takt == 30:
            # Neue Post während der Bestandsaufnahme: geht über die Spur „neu“, nicht in den Verlauf.
            neu_waehrenddessen = fake.uidnext
            fake.vorhanden.add(neu_waehrenddessen)
            fake.uidnext += 1
        intake.step("a", connector, batch=1)
        if intake.status("a")["folders"][0]["inventory_complete"]:
            break
    else:
        pytest.fail("Die Bestandsaufnahme wurde nicht fertig.")
    verlauf = _verlauf(ep)
    assert len(verlauf) == len(set(verlauf)) == len(vorhanden)
    assert set(verlauf) == vorhanden
    assert _verlauf(ep, "live") == [neu_waehrenddessen]
    # Von oben nach unten: Jedes Fenster liegt unter dem vorigen.
    assert all(spaeter[1] < frueher[0] for frueher, spaeter in zip(fake.suchen, fake.suchen[1:])
               if spaeter[1] <= 20000 and frueher[1] <= 20000)
    ep.close()


def test_angefangene_aufsteigende_bestandsaufnahme_laeuft_nach_update_ohne_doppelung_weiter(tmp_path, postfach, monkeypatch):
    connector, fake = postfach(range(1, 1051))
    ep = EpisodeStore(tmp_path / "episodes.sqlite3")
    intake = Intake(ep)
    intake.start("a", ["INBOX"])
    # Stand vor dem Update: aufsteigend bis 400 erfasst, obere Grenze 1050 gemerkt.
    monkeypatch.setattr(MailConnector, "bestand_neueste_zuerst", False, raising=False)
    for _ in range(2):
        intake.step("a", connector, batch=1)
    assert _verlauf(ep) == list(range(1, 401))
    monkeypatch.setattr(MailConnector, "bestand_neueste_zuerst", True, raising=False)
    fake.suchen.clear()
    for _ in range(10):
        intake.step("a", connector, batch=1)
    assert _verlauf(ep) == list(range(1, 1051))
    assert intake.status("a")["folders"][0]["inventory_complete"]
    # Nur der offene Bereich (400, 1050] wurde noch durchsucht, von oben nach unten; das letzte Fenster endet an 400.
    assert [f for f in fake.suchen if f[1] <= 1050] == [(851, 1050), (651, 850), (451, 650), (401, 450)]
    ep.close()


def test_abgebrochenes_fenster_wird_wiederholt_nicht_uebersprungen(tmp_path, postfach):
    connector, fake = postfach(range(1, 601))
    ep = EpisodeStore(tmp_path / "episodes.sqlite3")
    intake = Intake(ep)
    intake.start("a", ["INBOX"])
    intake.step("a", connector, batch=1)
    assert _verlauf(ep) == list(range(401, 601))
    fake.scheitern = True
    with pytest.raises(MailError):
        connector.inventory_page("INBOX", before_uid=400, limit=200, absteigend=True)
    fake.scheitern = True
    intake.step("a", connector, batch=1)
    assert _verlauf(ep) == list(range(401, 601))
    intake.step("a", connector, batch=1)
    assert _verlauf(ep) == list(range(201, 601))
    ep.close()
