from fastapi.testclient import TestClient
from icarus_memory.server import create_app
from icarus_memory import config


def test_account_without_credentials_cannot_be_selected():
    app = create_app()
    app.state.settings.mail_accounts = [config.MailAccountSettings(id='empty', imap_host='example.invalid', user='x')]
    with TestClient(app) as client:
        result = client.put('/api/v1/schedule', json={'mail_accounts':['empty']})
        assert result.status_code == 422


def test_scheduler_failure_status_survives_reload():
    app = create_app()
    app.state.settings.schedule.mail_accounts = ['missing']
    with TestClient(app) as client:
        client.post('/schedule/run')
        status = client.get('/api/v1/schedule').json()['mail_status']['missing']
        assert status['consecutive_failures'] == 1
        assert status['last_failure'] == 'credentials_missing'
        assert config.load(app.state.episodes._path.parent).mail_sync_status['missing'] == status
