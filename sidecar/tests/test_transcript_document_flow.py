from fastapi.testclient import TestClient
from icarus_memory.server import create_app


def test_preview_then_explicit_upload_deduplicates_without_claims():
    app = create_app()
    with TestClient(app) as client:
        raw = 'WEBVTT\n\n00:01.000 --> 00:02.000\n<v Example>Review the draft.\n'
        preview = client.post('/api/v1/sources/documents/preview-transcript', json={'text': raw, 'format': 'vtt'})
        assert preview.status_code == 200
        assert preview.json()['segment_count'] == 1
        assert app.state.episodes.all_episodes() == []
        assert 'Example' in preview.json()['body']
        payload = {'filename': 'Meeting.vtt', 'body': preview.json()['body']}
        first = client.post('/api/v1/sources/documents', json=payload).json()
        second = client.post('/api/v1/sources/documents', json=payload).json()
        assert first['created'] is True
        assert second['id'] == first['id'] and second['created'] is False
        assert app.state.claims.all_claims() == []
        source = client.get('/episodes/' + first['id']).json()
        assert source['body'] == preview.json()['body']
        assert source['provenance']['source_ref'] == 'upload:Meeting.vtt'


def test_invalid_transcript_preview_has_no_writes():
    app = create_app()
    with TestClient(app) as client:
        for raw, kind in [('not a subtitle', 'srt'), ('WEBVTT', 'vtt'), ('x', 'json'), ('\x00', 'vtt')]:
            assert client.post('/api/v1/sources/documents/preview-transcript', json={'text': raw, 'format': kind}).status_code == 422
        assert app.state.episodes.all_episodes() == []
