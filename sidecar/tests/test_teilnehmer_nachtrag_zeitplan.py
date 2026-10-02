"""Der Nachtrag hängt im Mailtakt des Zeitplans (`server._wire_scheduler`).

Zusicherung: Er läuft nur bei verbundenem Konto und laufender (nicht
pausierter) Aufnahme; sonst wird nichts geholt und nichts geschrieben.
"""

from __future__ import annotations

from types import SimpleNamespace

from icarus_memory import config
from icarus_memory.mail_intake import Intake

from .test_teilnehmer_nachtrag import Leser, _alte_mail, episodes  # noqa: F401 - Fixture wird mitgenommen


def _app_mit_konto(tmp_path, monkeypatch, leser):
    from icarus_memory.server import _wire_scheduler, create_app
    monkeypatch.setenv("ICARUS_DATA_DIR", str(tmp_path))
    app = create_app()
    konto = config.MailAccountSettings(id="k", label="T", imap_host="h", smtp_host="s",
                                       user="u@x.example", sender="u@x.example")
    app.state.settings.mail_accounts = [konto]
    app.state.settings.schedule.mail_accounts = ["k"]
    app.state.settings.schedule.enabled = True
    app.state.mail = SimpleNamespace(reader_for=lambda konto_id: leser)
    Intake(app.state.episodes).start("k", ["INBOX"])
    _wire_scheduler(app)
    return app


def test_zeitplan_hat_den_nachtrag_im_mailtakt(tmp_path, monkeypatch):
    app = _app_mit_konto(tmp_path, monkeypatch, Leser())
    mail = _alte_mail(app.state.episodes, 1)
    app.state.scheduler._run_mail_intake()
    assert {c["rolle"] for c in app.state.episodes.get(mail.id).contacts} == {"von", "an", "cc"}
    assert app.state.nachtrag.status("k")["ergaenzt"] == 1


def test_zeitplan_ruht_bei_pausierter_aufnahme(tmp_path, monkeypatch):
    leser = Leser()
    app = _app_mit_konto(tmp_path, monkeypatch, leser)
    mail = _alte_mail(app.state.episodes, 1)
    Intake(app.state.episodes).pause("k", True)
    app.state.scheduler._run_mail_intake()
    assert leser.abrufe == [] and app.state.episodes.get(mail.id).contacts == []


def test_zeitplan_ruht_ohne_verbundenes_konto(tmp_path, monkeypatch):
    leser = Leser()
    app = _app_mit_konto(tmp_path, monkeypatch, leser)
    mail = _alte_mail(app.state.episodes, 1)
    app.state.settings.mail_accounts[0].imap_host = ""       # nicht mehr verbunden
    app.state.scheduler._run_mail_intake()
    assert leser.abrufe == [] and app.state.episodes.get(mail.id).contacts == []
