"""Begrenzte DOCX-Textvorschau ohne Dateien zu entpacken oder Links abzurufen."""
from io import BytesIO
import zlib
import threading
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree

MAX_FILE = 5 * 1024 * 1024
MAX_XML = 2 * 1024 * 1024
MAX_TEXT = 512 * 1024
NAMESPACE = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def docx_text(data: bytes) -> str:
    return docx_struktur(data)[0]


def docx_struktur(data: bytes) -> tuple[str, tuple[tuple[int, int], ...]]:
    """Derselbe Haupttext, optional mit eindeutig abbildbaren einfachen Tabellenzeilen."""
    if len(data) > MAX_FILE:
        raise ValueError('Word-Dateien dürfen höchstens 5 MiB groß sein.')
    try:
        with ZipFile(BytesIO(data)) as archive:
            matches = [entry for entry in archive.infolist() if entry.filename == 'word/document.xml']
            if len(matches) != 1 or matches[0].file_size > MAX_XML:
                raise ValueError('Der Word-Haupttext fehlt oder ist zu groß.')
            with archive.open(matches[0]) as source:
                xml = source.read(MAX_XML + 1)
    except (BadZipFile, KeyError, RuntimeError, NotImplementedError, zlib.error, OSError, EOFError) as exc:
        raise ValueError('Die Word-Datei ist beschädigt oder verschlüsselt.') from exc
    if len(xml) > MAX_XML:
        raise ValueError('Der Word-Haupttext ist zu groß.')
    # UTF-16/32 ebenfalls erfassen, bevor ein XML-Parser Entitäten behandelt.
    probe = xml.replace(b'\x00', b'').upper()
    if b'<!DOCTYPE' in probe or b'<!ENTITY' in probe:
        raise ValueError('XML-Entitäten werden nicht unterstützt.')
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise ValueError('Der Word-Haupttext ist nicht lesbar.') from exc
    tag = lambda name: f'{{{NAMESPACE}}}{name}'
    body = root.find(tag('body'))
    if root.tag != tag('document') or body is None:
        raise ValueError('Kein unterstütztes Word-Dokument.')
    parts, rows = [], []
    props = {tag(n) for n in ('trPr', 'tcPr', 'pPr', 'rPr')}
    plain_tags = {tag(n) for n in ('tr', 'tc', 'p', 'r', 't', 'tab', 'br', 'cr')}

    def plain(element):
        if element.tag in props:
            return not any((e.text or '').strip() or (e.tail or '').strip() or e.tag in plain_tags for e in element.iter())
        return (element.tag in plain_tags and (element.tag == tag('t') or not (element.text or '').strip())
                and not (element.tail or '').strip() and all(plain(child) for child in element))
    # Ereignisse vermeiden doppelte Texte bei verschachtelten Absätzen.
    def walk(element, out=parts, in_cell=False):
        if element.tag in (tag('del'), tag('moveFrom')):
            return
        if element.tag == tag('tr'):
            cells = []
            for child in element:
                if child.tag == tag('tc'):
                    cell_parts = []
                    walk(child, cell_parts, True)
                    cells.append(''.join(cell_parts).strip('\n'))
                else:
                    walk(child, out, in_cell)
            row = '\t'.join(cells)
            if not in_cell and plain(element):
                rows.append(row)
            out.append(row + '\n\n')
            return
        if element.tag == tag('tbl') and in_cell:
            # Eine verschachtelte Tabelle beginnt eigene Zeilen; ihr Inhalt
            # darf nicht an ein vorangehendes äußeres Feld angehängt werden.
            out.append('\n\n')
        if element.tag == tag('t'):
            out.append(element.text or '')
        elif element.tag == tag('tab'):
            out.append('\t')
        elif element.tag in (tag('br'), tag('cr')):
            out.append('\n')
        for child in element:
            walk(child, out, in_cell)
        if element.tag == tag('p'):
            out.append('\n' if in_cell else '\n\n')
    try:
        walk(body)
    except RecursionError as exc:
        raise ValueError('Die Word-Datei ist zu stark verschachtelt.') from exc
    text = ''.join(parts).strip()
    if not text or '\x00' in text or len(text.encode('utf-8')) > MAX_TEXT:
        raise ValueError('Der Word-Text ist leer oder überschreitet 512 KiB.')
    if len(rows) > 64:
        return text, ()
    spans = tuple((text.index(row), text.index(row) + len(row)) for row in rows
                  if row and row == row.strip() and text.count(row) == 1)
    return text, spans if len(spans) <= 64 else ()


_PDF_SLOT = threading.BoundedSemaphore(1)


def pdf_text(data: bytes) -> dict:
    if not _PDF_SLOT.acquire(blocking=False):
        raise ValueError('Eine PDF wird bereits ausgelesen. Bitte danach erneut versuchen.')
    try:
        return _pdf_text(data)
    finally:
        _PDF_SLOT.release()


def pdf_seiten(data: bytes, *, max_seiten: int = 30, bilder: bool = False, warten: float = 20.0,
               zeitgrenze: float = 12.0) -> dict:
    """Die Seiten einer PDF einzeln (für Anhänge, `anhaenge.py`): `seiten`, `leer`, `gesamt`, `bilder` (Seite -> JPEG).

    Derselbe begrenzte Prozess wie `pdf_text`; wartet bis `warten` Sekunden, wenn gerade eine andere PDF gelesen wird,
    und bricht nach `zeitgrenze` Sekunden ab. Wirft `ValueError` mit einem Satz für den Nutzer.
    """
    if not _PDF_SLOT.acquire(timeout=warten):
        raise ValueError('Eine andere PDF wird gerade ausgelesen; der Anhang kommt beim nächsten Durchgang.')
    try:
        argumente = ['--seiten', str(max_seiten), *(['--bilder'] if bilder else [])]
        return _worker(data, argumente, zeitgrenze)
    finally:
        _PDF_SLOT.release()


def _worker(data: bytes, argumente: list[str], zeitgrenze: float) -> dict:
    import json
    import os
    import subprocess
    import sys
    if len(data) > MAX_FILE:
        raise ValueError('PDF-Dateien dürfen höchstens 5 MiB groß sein.')
    try:
        result = subprocess.run(
            [sys.executable, "-m", "icarus_memory.pdf_text_worker", *argumente],
            input=data, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=zeitgrenze, check=False,
            env={'PATH': os.defpath, 'PYTHONPATH': os.pathsep.join(sys.path), 'PYTHONDONTWRITEBYTECODE': '1'},
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError('Das Auslesen der PDF hat zu lange gedauert. Bitte eine kleinere Datei auswählen.') from exc
    if result.returncode != 0:
        raise ValueError('Die PDF überschreitet die verfügbaren Ressourcen oder ist nicht lesbar.')
    try:
        extracted = json.loads(result.stdout)
    except (ValueError, UnicodeError) as exc:
        raise ValueError('Die PDF konnte nicht ausgelesen werden.') from exc
    if 'error' in extracted:
        raise ValueError(extracted['error'])
    return extracted


def _pdf_text(data: bytes) -> dict:
    return _worker(data, [], 12)

