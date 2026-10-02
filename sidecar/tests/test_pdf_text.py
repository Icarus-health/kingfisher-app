from io import BytesIO
import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from icarus_memory.document_text import pdf_text


def sample(text=True, encrypted=False, blank_extra=False):
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    if text:
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(b'BT /F1 12 Tf 30 200 Td (Local PDF source) Tj ET')
        page[NameObject('/Contents')] = writer._add_object(stream)
    if blank_extra:
        writer.add_blank_page(width=300, height=300)
    if encrypted:
        writer.encrypt('test-secret')
    output = BytesIO(); writer.write(output)
    return output.getvalue()


def test_pdf_text_keeps_page_reference_and_reports_missing_text():
    result = pdf_text(sample(blank_extra=True))
    assert result['body'].endswith('Seite 1\nLocal PDF source')
    assert 'Seiten 2 ohne lesbare Textebene' in result['body']
    assert result['empty_pages'] == [2]


@pytest.mark.parametrize('data', [b'broken', sample(encrypted=True), sample(text=False)])
def test_unreadable_pdf_is_rejected(data):
    with pytest.raises(ValueError):
        pdf_text(data)


def test_pdf_timeout_is_reported(monkeypatch):
    import subprocess
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('worker', 12)
    monkeypatch.setattr(subprocess, 'run', timeout)
    with pytest.raises(ValueError, match='lange'):
        pdf_text(b'%PDF')


def test_parallel_pdf_does_not_start_another_worker_and_slot_is_released(monkeypatch):
    import threading
    import subprocess
    entered, release = threading.Event(), threading.Event()
    calls = []
    failures = []
    def fake_run(*args, **kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(2)
        raise subprocess.TimeoutExpired('worker', 12)
    monkeypatch.setattr(subprocess, 'run', fake_run)
    def first():
        try:
            pdf_text(b'%PDF')
        except ValueError as exc:
            failures.append(str(exc))
    worker = threading.Thread(target=first)
    worker.start()
    try:
        assert entered.wait(1)
        with pytest.raises(ValueError, match='bereits'):
            pdf_text(b'%PDF')
        assert len(calls) == 1
    finally:
        release.set()
        worker.join(2)
    assert not worker.is_alive()
    assert failures and 'lange' in failures[0]
    # Auch nach einem Fehler ist der Platz wieder frei.
    with pytest.raises(ValueError, match='lange'):
        pdf_text(b'%PDF')
    assert len(calls) == 2
