"""PDF-Text in einem kurzlebigen, begrenzten Prozess auslesen.

Zwei Arten:

* ohne Argument (Ordner, Hochladen): ein Text mit „Seite N“ vor jeder Seite (`main`),
* `--seiten N [--bilder]` (Anhänge einer Mail, `anhaenge.py`): höchstens N Seiten einzeln, dazu die leeren Seiten und,
  mit `--bilder`, je leerer Seite das erste eingebettete JPEG-Bild für eine Texterkennung. Gerechnet wird nichts:
  Ein JPEG wird roh weitergereicht, so wie es in der Datei steht.

Nie ausgeführt: pypdf liest nur Text und Bilddaten; Skripte, Formulare und Verweise in der PDF bleiben unberührt.
CPU-Zeit und Speicher sind begrenzt, der Aufrufer begrenzt die Wanduhr.
"""
import base64
import json
import sys
from io import BytesIO

MAX_BYTES = 5 * 1024 * 1024
MAX_TEXT = 512 * 1024
MAX_BILD = 3 * 1024 * 1024


def _grenzen():
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
    if sys.platform.startswith('linux'):
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))


def _lesen():
    from pypdf import PdfReader
    data = sys.stdin.buffer.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('PDF-Dateien dürfen höchstens 5 MiB groß sein.')
    reader = PdfReader(BytesIO(data))
    if reader.is_encrypted:
        raise ValueError('Bitte eine unverschlüsselte PDF-Datei auswählen.')
    if len(reader.pages) > 200:
        raise ValueError('PDF-Dateien dürfen höchstens 200 Seiten enthalten.')
    return reader


def main():
    _grenzen()
    reader = _lesen()
    parts, empty_pages, total = [], [], 0
    for number, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or '').strip()
        if not text:
            empty_pages.append(number)
        else:
            fragment = f'Seite {number}\n{text}'
            total += len(fragment.encode('utf-8')) + 2
            if total > MAX_TEXT:
                raise ValueError('Der PDF-Text überschreitet 512 KiB.')
            parts.append(fragment)
    if not parts:
        raise ValueError('Keine lesbare Textebene gefunden. Diese PDF benötigt möglicherweise Texterkennung (OCR).')
    body = '\n\n'.join(parts)
    if empty_pages:
        body = 'Hinweis zur Texterkennung: Seiten ' + ', '.join(map(str, empty_pages)) + ' ohne lesbare Textebene. Der ausgelesene Inhalt ist unvollständig.\n\n' + body
    if len(body.encode('utf-8')) > MAX_TEXT:
        raise ValueError('Der PDF-Text überschreitet 512 KiB.')
    if '\x00' in body:
        raise ValueError('Der PDF-Text enthält ungültige Zeichen.')
    print(json.dumps({'body': body, 'empty_pages': empty_pages}, ensure_ascii=True))


def _jpeg(page):
    """Das erste eingebettete JPEG der Seite, roh (ein Scan ist meist genau ein Bild je Seite), sonst None."""
    try:
        objekte = page['/Resources'].get_object().get('/XObject')
        objekte = objekte.get_object() if objekte is not None else {}
        for name in objekte:
            bild = objekte[name].get_object()
            filter_ = bild.get('/Filter')
            filter_ = filter_[0] if isinstance(filter_, list) and filter_ else filter_
            if bild.get('/Subtype') == '/Image' and filter_ == '/DCTDecode':
                roh = bild.get_data()
                return roh if 0 < len(roh) <= MAX_BILD else None
    except Exception:  # noqa: BLE001 - ohne lesbares Bild bleibt die Seite ungelesen
        return None
    return None


def seiten(max_seiten: int, bilder: bool):
    _grenzen()
    reader = _lesen()
    texte, leer, gefunden, total = [], [], {}, 0
    for number, page in enumerate(reader.pages[:max_seiten], 1):
        text = (page.extract_text() or '').strip()
        if '\x00' in text:
            raise ValueError('Der PDF-Text enthält ungültige Zeichen.')
        total += len(text.encode('utf-8'))
        if total > MAX_TEXT:
            raise ValueError('Der PDF-Text überschreitet 512 KiB.')
        texte.append(text)
        if not text:
            leer.append(number)
            if bilder and (roh := _jpeg(page)) is not None:
                gefunden[str(number)] = base64.b64encode(roh).decode('ascii')
    print(json.dumps({'seiten': texte, 'leer': leer, 'gesamt': len(reader.pages), 'bilder': gefunden}, ensure_ascii=True))


if __name__ == '__main__':
    try:
        if len(sys.argv) >= 3 and sys.argv[1] == '--seiten':
            seiten(max(1, min(200, int(sys.argv[2]))), '--bilder' in sys.argv[3:])
        else:
            main()
    except ValueError as exc:
        print(json.dumps({'error': str(exc)}))
    except Exception:
        print(json.dumps({'error': 'Die PDF-Datei ist beschädigt oder konnte nicht ausgelesen werden.'}))
