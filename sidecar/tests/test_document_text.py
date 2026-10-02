import base64
from io import BytesIO
from zipfile import ZipFile
import pytest
from fastapi.testclient import TestClient
from icarus_memory.document_text import docx_text, NAMESPACE
from icarus_memory.server import create_app


def packed(xml):
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        archive.writestr('word/document.xml', xml)
    return stream.getvalue()


def test_word_preview_preserves_text_and_does_not_store():
    xml = f'<w:document xmlns:w="{NAMESPACE}"><w:body><w:p><w:r><w:t>Hallo</w:t><w:tab/><w:t>Welt</w:t></w:r><w:del><w:r><w:delText>Entfernt</w:delText></w:r></w:del></w:p><w:p><w:r><w:t>Zweite Zeile</w:t></w:r></w:p></w:body></w:document>'
    data = packed(xml)
    assert docx_text(data) == 'Hallo\tWelt\nZweite Zeile'
    app = create_app()
    client = TestClient(app)
    response = client.post('/api/v1/sources/documents/preview-docx', json={'content_base64': base64.b64encode(data).decode()})
    assert response.status_code == 200
    assert client.get('/api/v1/sources/documents').json()['items'] == []
    saved = client.post('/api/v1/sources/documents', json={'filename':'Notiz.docx', 'body':response.json()['body']})
    assert saved.status_code == 200
    assert len(client.get('/api/v1/sources/documents').json()['items']) == 1


@pytest.mark.parametrize('xml', ['<!DOCTYPE x [<!ENTITY e "boom">]><x/>', '<broken', '<x/>'])
def test_invalid_word_content_is_rejected(xml):
    with pytest.raises(ValueError):
        docx_text(packed(xml))


def test_invalid_or_oversized_archive_is_rejected():
    for data in [b'not zip', b'x' * (5 * 1024 * 1024 + 1), packed('x' * (2 * 1024 * 1024 + 1))]:
        with pytest.raises(ValueError):
            docx_text(data)


def test_damaged_compressed_word_returns_validation_error_without_source():
    from zipfile import ZIP_DEFLATED
    stream = BytesIO()
    name = 'word/document.xml'
    with ZipFile(stream, 'w', compression=ZIP_DEFLATED) as archive:
        archive.writestr(name, f'<w:document xmlns:w="{NAMESPACE}"><w:body><w:p><w:r><w:t>Text</w:t></w:r></w:p></w:body></w:document>')
    data = bytearray(stream.getvalue())
    # Lokaler ZIP-Header: 30 Bytes plus Dateiname; 0xff ist ein ungültiger
    # DEFLATE-Blocktyp. Zentralverzeichnis und Größen bleiben unverändert.
    data[30 + len(name)] = 0xff
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post('/api/v1/sources/documents/preview-docx', json={'content_base64': base64.b64encode(data).decode()})
    assert response.status_code == 422
    assert 'beschädigt' in response.json()['detail']
    assert client.get('/api/v1/sources/documents').json()['items'] == []
