"""Synthetische PDFs für die Welt der Messlatte: Rechnungen mit Textebene und gescannte Seiten ohne Text.

Bewusst ohne Bibliothek und von Hand geschrieben, wie ein kleiner Rechnungsdrucker es täte: Helvetica mit
WinAnsiEncoding (Umlaute, „€“), eine Zeile je `Tj`, Querverweistabelle mit richtigen Versätzen. Eine gescannte Seite
trägt nur ein eingebettetes JPEG (`DCTDecode`) und keinen Text, so wie ein Scanner sie liefert.

Die Welt nennt nur Text (`anhaenge` einer Mail in FORMAT.md); die Datei entsteht erst beim Einspielen
(`postfach.rohmail`). So bleibt die Welt lesbar und prüfbar, und jede Zahl, die ein Vorschlag nennt, steht im Text.
"""
from __future__ import annotations

import base64

#: Ein gültiges JPEG von 1 × 1 Bildpunkt (weiß). Mehr braucht eine gescannte Seite ohne Textebene hier nicht.
JPEG_1x1 = base64.b64decode(
    '/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////'
    '////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA=')


def _zeichenkette(zeile: str) -> bytes:
    roh = zeile.encode('cp1252', errors='replace')
    return b'(' + roh.replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)') + b')'


def _datei(objekte: list[bytes]) -> bytes:
    ausgabe = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    versaetze = []
    for nummer, inhalt in enumerate(objekte, 1):
        versaetze.append(len(ausgabe))
        ausgabe += f'{nummer} 0 obj\n'.encode() + inhalt + b'\nendobj\n'
    tabelle = len(ausgabe)
    ausgabe += f'xref\n0 {len(objekte) + 1}\n0000000000 65535 f \n'.encode()
    for versatz in versaetze:
        ausgabe += f'{versatz:010d} 00000 n \n'.encode()
    ausgabe += f'trailer\n<< /Size {len(objekte) + 1} /Root 1 0 R >>\nstartxref\n{tabelle}\n%%EOF\n'.encode()
    return bytes(ausgabe)


def _strom(daten: bytes, zusatz: str = '') -> bytes:
    return f'<< /Length {len(daten)}{zusatz} >>\nstream\n'.encode() + daten + b'\nendstream'


def text_pdf(seiten: list[list[str]]) -> bytes:
    """Eine PDF mit Textebene: je Seite die Zeilen von oben nach unten."""
    objekte: list[bytes] = [b'', b'', b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>']
    kinder = []
    for zeilen in seiten:
        inhalt = b'BT /F1 11 Tf 14 TL 50 790 Td\n' + b''.join(_zeichenkette(z) + b" Tj T*\n" for z in zeilen) + b'ET'
        objekte.append(_strom(inhalt))
        objekte.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> '
                       f'/Contents {len(objekte)} 0 R >>'.encode())
        kinder.append(len(objekte))
    objekte[0] = b'<< /Type /Catalog /Pages 2 0 R >>'
    objekte[1] = f'<< /Type /Pages /Kids [{" ".join(f"{k} 0 R" for k in kinder)}] /Count {len(kinder)} >>'.encode()
    return _datei(objekte)


def scan_pdf(seiten: int = 1) -> bytes:
    """Eine gescannte PDF: je Seite nur ein Bild, keine Textebene."""
    objekte: list[bytes] = [b'', b'', _strom(JPEG_1x1, ' /Type /XObject /Subtype /Image /Width 1 /Height 1 '
                                                       '/ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /DCTDecode')]
    kinder = []
    for _ in range(seiten):
        objekte.append(_strom(b'q 595 0 0 842 0 0 cm /Im1 Do Q'))
        objekte.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /XObject << /Im1 3 0 R >> >> '
                       f'/Contents {len(objekte)} 0 R >>'.encode())
        kinder.append(len(objekte))
    objekte[0] = b'<< /Type /Catalog /Pages 2 0 R >>'
    objekte[1] = f'<< /Type /Pages /Kids [{" ".join(f"{k} 0 R" for k in kinder)}] /Count {len(kinder)} >>'.encode()
    return _datei(objekte)


__all__ = ['JPEG_1x1', 'scan_pdf', 'text_pdf']
