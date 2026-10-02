"""Transkript-Eingang: was eine exportierte Mitschrift buchstäblich hergibt (F3)."""
from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone

import pytest

from icarus_memory.transkript_eingang import episode_daten, lesen, sprecher_und_text, zeit_aus_text

MEETING = ('Anna Berg: Guten Tag zusammen.\nLena Probe: Hallo, wir starten mit dem Budget.\n'
           'Anna Berg: Das Budget beträgt 40.000 Euro.\nBert Kraus: Einverstanden.\n')


def docx(*absaetze: str) -> bytes:
    ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    inhalt = ''.join(f'<w:p><w:r><w:t>{a}</w:t></w:r></w:p>' for a in absaetze)
    xml = f'<?xml version="1.0"?><w:document xmlns:w="{ns}"><w:body>{inhalt}</w:body></w:document>'
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, 'w') as archiv:
        archiv.writestr('word/document.xml', xml)
    return puffer.getvalue()


def test_alle_fuenf_formate_werden_gelesen():
    vtt = 'WEBVTT\n\n00:00:01.000 --> 00:00:03.000\n<v Anna Berg>Hallo</v>\n\n00:00:04.000 --> 00:00:06.000\n<v Bert Kraus>Moin</v>\n\n00:00:07.000 --> 00:00:09.000\n<v Anna Berg>Weiter</v>\n'
    srt = '1\n00:00:01,000 --> 00:00:03,000\nAnna Berg: Hallo\n\n2\n00:00:04,000 --> 00:00:06,000\nAnna Berg: Weiter\n'
    for name, daten in [('a.txt', MEETING.encode()), ('a.vtt', vtt.encode()), ('a.srt', srt.encode()),
                        ('a.docx', docx(*MEETING.splitlines())), ('a.md', MEETING.encode())]:
        t = lesen(name, daten)
        assert 'Anna Berg' in t.sprecher, name
        assert t.text.strip(), name
    assert lesen('a.vtt', vtt.encode()).sprecher == ('Anna Berg', 'Bert Kraus')


def test_andere_formate_und_zu_grosse_dateien_werden_abgelehnt():
    with pytest.raises(ValueError):
        lesen('bild.png', b'x')
    with pytest.raises(ValueError):
        lesen('a.txt', b'x' * (512 * 1024 + 1))
    with pytest.raises(ValueError):
        lesen('leer.txt', b'   \n')
    with pytest.raises(ValueError):
        lesen('kaputt.docx', b'kein zip')


def test_sprecher_nur_echte_namen():
    text = ('Speaker 1: Hallo\nSpeaker 2: Moin\nSpeaker 1: weiter\n'
            'Anna Berg: ja\nAnna Berg: nein\nErgebnis: alles offen\nTeilnehmer: viele\nDatum: heute\n')
    echte, anonym, bereinigt = sprecher_und_text(text)
    assert echte == ['Anna Berg']          # „Ergebnis“ und „Datum“ sind Kopfwörter, „Speaker 1“ kein Name
    assert anonym == 2
    assert 'Ergebnis: alles offen' in bereinigt   # der Text bleibt vollständig erhalten


def test_zeitmarken_und_teams_zeilenform():
    teams = 'Anna Berg 0:05\nHallo zusammen\nBert Kraus 0:09\nMoin\nAnna Berg 0:12\nWeiter\n'
    t = lesen('Teams.txt', teams.encode())
    assert t.sprecher == ('Anna Berg', 'Bert Kraus')
    assert 'Anna Berg: Hallo zusammen' in t.text
    klammern = '[00:00:01] Anna Berg: Hallo\n[00:00:05] Bert Kraus: Moin\n[00:00:09] Anna Berg: Ja\n'
    assert lesen('x.txt', klammern.encode()).sprecher == ('Anna Berg', 'Bert Kraus')
    assert '00:00' not in lesen('x.txt', klammern.encode()).text


@pytest.mark.parametrize('name,erwartet', [
    ('2026-09-28 14.30 Jour fixe Winter.txt', datetime(2026, 9, 28, 12, 30, tzinfo=timezone.utc)),
    ('Team sync (2026-09-28 at 14:02 GMT+2) - Transcript.txt', datetime(2026, 9, 28, 12, 2, tzinfo=timezone.utc)),
    ('Besprechung-20260928_143012.vtt', datetime(2026, 9, 28, 12, 30, 12, tzinfo=timezone.utc)),
    ('Kundentermin 28.09.2026 14:30.txt', datetime(2026, 9, 28, 12, 30, tzinfo=timezone.utc)),
])
def test_zeit_aus_dem_dateinamen(name, erwartet):
    # Zeiten ohne Zone gelten in der Zeitzone des Nutzers (Europe/Berlin, im September UTC+2).
    moment, tag = zeit_aus_text(name)
    assert moment is not None and moment.astimezone(timezone.utc) == erwartet
    assert tag.isoformat() == '2026-09-28'


def test_nur_ein_tag_und_kein_datum():
    assert zeit_aus_text('Protokoll 2026-09-28.txt') == (None, datetime(2026, 9, 28).date())
    assert zeit_aus_text('Meeting.txt') == (None, None)
    assert zeit_aus_text('Version 12345678 final') == (None, None)   # keine erfundenen Daten aus Zahlenfolgen


def test_titel_ohne_datum_und_dateizeitpunkt_wird_nie_zur_quellenzeit():
    geaendert = datetime(2026, 9, 30, 9, 0, tzinfo=timezone.utc)
    t = lesen('2026-09-28 14.30 Jour fixe Winter.txt', MEETING.encode(), geaendert)
    assert t.titel == 'Jour fixe Winter'
    ohne = lesen('Meeting.txt', MEETING.encode(), geaendert)
    assert ohne.beginn is None and ohne.tag is None
    daten = episode_daten(ohne)
    assert daten['occurred_at'] is None          # mtime ändert sich beim Kopieren; die Quelle darf daran nicht hängen
    assert geaendert.isoformat() in str(ohne.hinweise())   # für die Zuordnung bleibt sie als schwaches Zeichen erhalten
    assert daten['tags'] == ['transkript']
    assert daten['participants'] == ['Anna Berg', 'Lena Probe', 'Bert Kraus']


def test_kopfzeile_und_frontmatter_liefern_die_zeit():
    md = '---\ntitle: Kundengespräch Winter\ndate: 2026-09-28T14:30:00+02:00\n---\nAnna Berg: a\nAnna Berg: b\n'
    t = lesen('notiz.md', md.encode())
    assert t.titel == 'Kundengespräch Winter' and t.zeit_quelle == 'kopf'
    assert t.beginn.astimezone(timezone.utc) == datetime(2026, 9, 28, 12, 30, tzinfo=timezone.utc)
    kopf = lesen('m.txt', b'Datum: 28.09.2026 14:30\nAnna Berg: a\nAnna Berg: b\n')
    assert kopf.zeit_quelle == 'kopf' and kopf.beginn is not None


def test_windows_zeichensatz_wird_gelesen():
    t = lesen('a.txt', 'Anna Berg: Grüße\nAnna Berg: Weiter\n'.encode('cp1252'))
    assert 'Grüße' in t.text
