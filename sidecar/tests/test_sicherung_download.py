"""Sicherung ohne Helfer (Fremdprobe, Befund 8): Kingfisher schreibt das Archiv selbst, der Browser lädt es herunter."""
from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.audit import AuditLog
from icarus_memory.backup import BackupError
from icarus_memory.crypto import DecryptionError
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType, now
from icarus_memory.recovery_bundle import restore_bundle
from icarus_memory.server import create_app
from icarus_memory.sicherung_download import erstellen, konfiguration
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore

PASSWORT = 'ein-langes-sicherungspasswort'


@pytest.fixture
def api(tmp_path, monkeypatch):
    daten = tmp_path / 'daten'
    daten.mkdir()
    monkeypatch.setenv('ICARUS_DATA_DIR', str(daten))
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'probe-token')
    monkeypatch.setenv('ICARUS_SECRETS_PASSPHRASE', 'probe-passphrase')
    episoden = EpisodeStore(daten / 'episodes.sqlite3')
    episoden.record(EpisodeKind.DOCUMENT, 'Vertrag', 'Kündbar bis 30.11.',
                    Provenance(source_type=SourceType.DOCUMENT, source_ref='probe:vertrag', captured_at=now()))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'), audit=AuditLog(daten / 'audit.sqlite3'),
                     tasks=TaskStore(daten / 'tasks.sqlite3'), workspace=WorkspaceStore(daten / 'workspace.sqlite3'),
                     episodes=episoden)
    with TestClient(app, headers={'X-Icarus-Token': 'probe-token'}) as client:
        yield app, client, tmp_path


def test_download_ist_verschluesselt_geprueft_und_wiederherstellbar(api, caplog):
    _, client, tmp_path = api
    with caplog.at_level(logging.DEBUG):
        antwort = client.post('/api/v1/recovery/herunterladen', json={'password': PASSWORT})
    assert antwort.status_code == 200, antwort.text
    assert antwort.headers['content-disposition'].startswith('attachment; filename="Kingfisher-Sicherung-')
    assert antwort.headers['cache-control'] == 'no-store'
    assert b'Vertrag' not in antwort.content and b'probe-passphrase' not in antwort.content  # nur verschlüsselt
    assert PASSWORT not in caplog.text
    archiv = tmp_path / 'sicherung.recovery'
    archiv.write_bytes(antwort.content)
    with pytest.raises(DecryptionError):
        restore_bundle(archiv, tmp_path / 'falsch', 'ein-anderes-passwort-xyz')
    ziel = restore_bundle(archiv, tmp_path / 'wieder', PASSWORT)
    assert 'Vertrag' in [e.title for e in EpisodeStore(ziel / 'data' / 'episodes.sqlite3').all_episodes(limit=10)]
    # Die Konfiguration für die Wiederherstellung ist dabei, damit die gespeicherten Passwörter lesbar bleiben.
    assert 'ICARUS_SECRETS_PASSPHRASE=probe-passphrase' in (ziel / 'settings.env').read_text()
    # Auf dem Rechner bleibt keine Kopie liegen.
    assert not list((tmp_path / 'daten').glob('*.recovery'))


def test_ohne_langes_passwort_keine_sicherung(api):
    _, client, _ = api
    for falsch in ({'password': 'zu-kurz'}, {}, {'password': 123}):
        antwort = client.post('/api/v1/recovery/herunterladen', json=falsch)
        assert antwort.status_code == 422 and '16' in antwort.json()['detail']


def test_nur_mit_zugang(api):
    app, _, _ = api
    with TestClient(app) as fremd:
        assert fremd.post('/api/v1/recovery/herunterladen', json={'password': PASSWORT}).status_code in (401, 403)


def test_konfiguration_nimmt_nur_gesetzte_einzeilige_werte():
    text = konfiguration({'ICARUS_SIDECAR_TOKEN': 't', 'ICARUS_MODEL': '', 'KINGFISHER_USER_NAME': 'a\nb', 'FREMD': 'x'})
    assert text == 'ICARUS_SIDECAR_TOKEN=t\n'


def test_erstellen_ohne_datenbank_sagt_es(tmp_path):
    with pytest.raises(BackupError):
        erstellen(tmp_path, PASSWORT, {})
