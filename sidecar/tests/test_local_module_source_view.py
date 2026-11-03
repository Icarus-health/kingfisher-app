"""The source pane's reading stamp belongs to its displayed original."""
from fastapi.testclient import TestClient

from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.server import create_app


def source(app, body='Bitte senden Sie die Unterlagen.'):
    return app.state.episodes.record(EpisodeKind.DOCUMENT, 'Künstliches Original', body,
        Provenance(source_type=SourceType.DOCUMENT))[0]


def test_main_app_reports_missing_optional_runtime_without_starting_it():
    app = create_app()
    with TestClient(app) as client:
        response = client.get('/api/v1/modules/local-source/status')
    assert response.status_code == 200
    assert response.json()['status'] == 'not_installed'
    assert getattr(app.state, 'local_source_controller', None) is None


def test_source_view_has_current_original_fingerprint_without_mutating_source():
    app = create_app()
    original = source(app)
    stamp = app.state.episodes.belegbarer_snapshot(original.id, max_bytes=256*1024).support_fingerprint()
    with TestClient(app) as client:
        response = client.get('/api/v1/episodes/' + original.id)
    assert response.status_code == 200
    assert response.json()['source_fingerprint'] == stamp
    assert response.json()['body'] == original.body
    assert app.state.episodes.get(original.id).to_dict() == original.to_dict()


def test_ignored_original_stays_readable_without_a_module_reading_stamp():
    app = create_app()
    original = source(app)
    app.state.episodes.ignore(original.id)
    with TestClient(app) as client:
        response = client.get('/api/v1/episodes/' + original.id)
    assert response.status_code == 200
    assert response.json()['body'] == original.body
    assert response.json()['source_fingerprint'] is None


def test_source_larger_than_module_scope_remains_readable_without_reading_stamp():
    app = create_app()
    original = source(app, 'A' * (256*1024+1))
    with TestClient(app) as client:
        response = client.get('/api/v1/episodes/' + original.id)
    assert response.status_code == 200
    assert response.json()['body'] == original.body
    assert response.json()['source_fingerprint'] is None
