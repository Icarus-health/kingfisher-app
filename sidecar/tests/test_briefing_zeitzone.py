"""Der Briefing-Kopf nennt die eingestellte Zeitzone, nicht die des Rechners (Fremdprobe 2, Befund 9)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from icarus_memory.server import create_app


def test_ohne_angabe_gilt_die_eingestellte_zeitzone(monkeypatch, tmp_path):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('ICARUS_SIDECAR_TOKEN', raising=False)
    monkeypatch.setenv('TZ', 'UTC')  # der Container läuft in UTC
    monkeypatch.setenv('KINGFISHER_TIMEZONE', 'Europe/Berlin')
    with TestClient(create_app()) as client:
        assert client.get('/api/v1/morning-briefing', params={'post': 'false'}).json()['timezone'] == 'Europe/Berlin'
        monkeypatch.setenv('KINGFISHER_TIMEZONE', 'America/New_York')
        assert client.get('/api/v1/morning-briefing', params={'post': 'false'}).json()['timezone'] == 'America/New_York'
        # Wer ausdrücklich eine Zone nennt, bekommt sie (Schnittstelle unverändert).
        assert client.get('/api/v1/morning-briefing', params={'timezone': 'UTC', 'post': 'false'}).json()['timezone'] == 'UTC'


def test_die_oberflaeche_schickt_keine_zeitzone_des_browsers():
    from pathlib import Path
    api = (Path(__file__).resolve().parents[2] / 'app' / 'kingfisher' / 'src' / 'api.ts').read_text(encoding='utf-8')
    zeile = next(z for z in api.splitlines() if z.strip().startswith('morning:'))
    assert 'resolvedOptions' not in zeile and 'timezone=' not in zeile
