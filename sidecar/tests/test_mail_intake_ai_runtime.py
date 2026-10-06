"""The real scheduler callback wires filtering, review and permissions together."""
from dataclasses import replace
from types import SimpleNamespace

from fastapi.testclient import TestClient

from icarus_memory import config, mail_filter
from icarus_memory.mail_intake import Intake
from icarus_memory.server import create_app
from .test_mail_intake import Reader
from .test_decision_consumers import DecisionProvider


def test_scheduler_filters_with_small_local_provider_and_exposes_review(monkeypatch):
    app = create_app()
    reader = Reader()
    reader.count = 2
    provider = DecisionProvider('newsletter')
    monkeypatch.setattr(mail_filter, 'screening_provider', lambda app, **kw: provider)
    with TestClient(app) as client:
        app.state.mail = SimpleNamespace(reader_for=lambda account: reader)
        app.state.settings.mail_accounts = [config.MailAccountSettings(id='a', imap_host='example.test', user='a')]
        app.state.settings.schedule.enabled = app.state.settings.schedule.with_model = True
        app.state.settings.schedule.mail_accounts = ['a']
        app.state.settings.mail_filter = {'ai_enabled': True}
        intake = Intake(app.state.episodes)
        intake.start('a', ['Archive'])
        app.state.scheduler._run_mail_intake()
        assert len(provider.seen) == 2
        state = intake.status('a')['folders'][0]
        assert state['captured'] == 0 and state['filtered_by'] == {'newsletter': 2}
        pending = client.get('/api/v1/mail-filter').json()['pending']
        assert len(pending) == 2 and all(p['folder'] == 'Archive' for p in pending)
        assert sum(app.state.episodes.counts().values()) == 0


def test_filter_change_during_decision_discards_old_result(monkeypatch):
    app = create_app()
    reader = Reader()
    reader.count = 1
    provider = DecisionProvider()
    original = provider.decide
    def change_policy(*args, **kwargs):
        result = original(*args, **kwargs)
        app.state.settings.mail_filter = {'ai_enabled': False, 'revision': 1}
        return result
    provider.decide = change_policy
    monkeypatch.setattr(mail_filter, 'screening_provider', lambda app, **kw: provider)
    with TestClient(app):
        app.state.mail = SimpleNamespace(reader_for=lambda account: reader)
        app.state.settings.mail_accounts = [config.MailAccountSettings(id='a', imap_host='example.test', user='a')]
        app.state.settings.schedule.enabled = app.state.settings.schedule.with_model = True
        app.state.settings.schedule.mail_accounts = ['a']
        app.state.settings.mail_filter = {'ai_enabled': True}
        intake = Intake(app.state.episodes)
        intake.start('a', ['INBOX'])
        app.state.scheduler._run_mail_intake()
        assert len(provider.seen) == 1
        assert sum(app.state.episodes.counts().values()) == 0
        assert intake.status('a')['folders'][0]['pending'] == 1
