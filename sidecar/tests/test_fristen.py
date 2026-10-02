"""Fristen aus Text: nur eindeutige Auflösung, Bezug ist die Quelle."""
from datetime import date, datetime, timezone

import pytest

from icarus_memory.fristen import fristen_in

# Donnerstag, 3. September 2026
BEZUG = datetime(2026, 9, 3, 9, 0, tzinfo=timezone.utc)


def _tage(text, bezug=BEZUG):
    suche = fristen_in(text, bezug)
    return [f.datum for f in suche.fristen], suche.ohne_datum


@pytest.mark.parametrize('text,erwartet', [
    ('bis Freitag', date(2026, 9, 4)),
    ('bis zum 12.10.', date(2026, 10, 12)),
    ('bis zum 12.10.2026', date(2026, 10, 12)),
    ('bis zum 12.10.26', date(2026, 10, 12)),
    ('Die neue Einreichfrist ist der 12. November 2026, 12 Uhr.', date(2026, 11, 12)),
    ('bis 29. Oktober', date(2026, 10, 29)),
    ('Ende Oktober', date(2026, 10, 31)),
    ('Ende Februar 2028', date(2028, 2, 29)),
    ('in zwei Wochen', date(2026, 9, 17)),
    ('in 3 Tagen', date(2026, 9, 6)),
    ('in einem Monat', date(2026, 10, 3)),
    ('in einer Woche', date(2026, 9, 10)),
    ('bis morgen', date(2026, 9, 4)),
    ('Ende des Monats', date(2026, 9, 30)),
])
def test_eindeutige_angaben_werden_aufgeloest(text, erwartet):
    tage, offen = _tage(text)
    assert tage == [erwartet] and offen == []


@pytest.mark.parametrize('text', [
    'nächste Woche', 'nächsten Freitag', 'Mitte Oktober', 'Anfang November', 'KW 42', 'zeitnah',
    'in drei bis vier Wochen',
    'bis Donnerstag',   # am selben Wochentag: heute oder in einer Woche?
    'am 25.08.',        # 9 Tage zurück: vergangen oder nächstes Jahr, nicht zu entscheiden
    'am 3. Mai',
])
def test_uneindeutiges_bleibt_text_ohne_datum(text):
    tage, offen = _tage(text)
    assert tage == []
    assert offen, 'die Angabe muss als Text sichtbar bleiben'


def test_wochentag_am_selben_tag_ist_uneindeutig_und_wird_genannt():
    tage, offen = _tage('bis Donnerstag')
    assert tage == [] and offen == ['bis Donnerstag']


def test_bezug_ist_die_quelle_nicht_heute():
    maerz = datetime(2025, 3, 5, 9, 0, tzinfo=timezone.utc)  # Mittwoch
    assert _tage('bis Freitag', maerz)[0] == [date(2025, 3, 7)]
    assert _tage('Ende Oktober', maerz)[0] == [date(2025, 10, 31)]


def test_datum_ohne_jahr_im_folgejahr_nur_wenn_eindeutig():
    dezember = datetime(2026, 12, 10, 9, 0, tzinfo=timezone.utc)
    assert _tage('bis 15.1.', dezember)[0] == [date(2027, 1, 15)]
    assert _tage('bis 15.1.', BEZUG)[0] == []  # September: Januar liegt weder nah noch klar vergangen


def test_tausenderpunkt_und_versionsnummer_sind_kein_datum():
    assert _tage('Honorar 1.450 Euro, Version 1.2.3, Tel. 0611 555-0142')[0] == []
    assert _tage('Belegnummer 112.10.2026 bezahlt')[0] == []  # Teil einer längeren Zahlenfolge


def test_ausdruck_und_stelle_stimmen_mit_dem_text_ueberein():
    text = 'Bitte bis zum 12.10. antworten, Rest Ende Oktober.'
    suche = fristen_in(text, BEZUG)
    assert [text[f.start:f.ende].strip() for f in suche.fristen] == [f.ausdruck for f in suche.fristen]
    assert [f.datum for f in suche.fristen] == [date(2026, 10, 12), date(2026, 10, 31)]


def test_zeitzone_des_nutzers_bestimmt_den_bezugstag(monkeypatch):
    from zoneinfo import ZoneInfo
    monkeypatch.setattr('icarus_memory.fristen.user_timezone', lambda: ZoneInfo('Europe/Berlin'))
    spaet = datetime(2026, 9, 3, 23, 30, tzinfo=timezone.utc)  # in Berlin schon Freitag, 4.9.
    assert _tage('bis morgen', spaet)[0] == [date(2026, 9, 5)]


def test_jede_textstelle_zaehlt_einmal():
    # „12. Oktober 2026“ ist nicht zugleich ein zweites Datum „12.10.“ oder „Oktober“.
    tage, _ = _tage('bis zum 12. Oktober 2026 (12.10.2026)')
    assert tage == [date(2026, 10, 12), date(2026, 10, 12)]
    assert len(fristen_in('bis zum 12. Oktober 2026', BEZUG).fristen) == 1
