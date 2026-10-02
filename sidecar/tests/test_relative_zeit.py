"""Relative Zeitangaben im Antwortsatz: gegen den Stichtag aufgelöst, sonst nicht erlaubt."""
from datetime import date, datetime, timezone

from icarus_memory.relative_zeit import aufloesen, mit_datum

DIENSTAG = datetime(2026, 9, 29, 8, 0, tzinfo=timezone.utc)  # Dienstag


def tage(text, jetzt=DIENSTAG):
    return [(a.ausdruck, a.von, a.bis) for a in aufloesen(text, jetzt)]


def test_einzelne_tage_werden_gegen_den_stichtag_aufgeloest():
    assert tage('Heute ist es soweit.') == [('Heute', date(2026, 9, 29), date(2026, 9, 29))]
    assert tage('Morgen um 14 Uhr.') == [('Morgen', date(2026, 9, 30), date(2026, 9, 30))]
    assert tage('Übermorgen oder uebermorgen') == [
        ('Übermorgen', date(2026, 10, 1), date(2026, 10, 1)), ('uebermorgen', date(2026, 10, 1), date(2026, 10, 1))]
    assert tage('gestern und vorgestern') == [('gestern', date(2026, 9, 28), date(2026, 9, 28)),
                                              ('vorgestern', date(2026, 9, 27), date(2026, 9, 27))]


def test_wochen_und_monate_werden_zu_zeitraeumen():
    assert tage('nächste Woche') == [('nächste Woche', date(2026, 10, 5), date(2026, 10, 11))]
    assert tage('diese Woche') == [('diese Woche', date(2026, 9, 28), date(2026, 10, 4))]
    assert tage('in der letzten Woche') == [('letzten Woche', date(2026, 9, 21), date(2026, 9, 27))]
    assert tage('nächsten Monat') == [('nächsten Monat', date(2026, 10, 1), date(2026, 10, 31))]
    assert tage('letzten Monat') == [('letzten Monat', date(2026, 8, 1), date(2026, 8, 31))]


def test_in_n_tagen_wochen_monaten():
    assert tage('in zwei Wochen') == [('in zwei Wochen', date(2026, 10, 13), date(2026, 10, 13))]
    assert tage('in 3 Tagen') == [('in 3 Tagen', date(2026, 10, 2), date(2026, 10, 2))]
    assert tage('in einem Monat') == [('in einem Monat', date(2026, 10, 29), date(2026, 10, 29))]


def test_monatsende_wird_beim_addieren_nicht_ueberschritten():
    assert tage('in einem Monat', datetime(2026, 1, 31, tzinfo=timezone.utc))[0][1] == date(2026, 2, 28)


def test_unbekanntes_bleibt_unaufgeloest():
    for text in ('demnächst', 'bald', 'kürzlich', 'übers Wochenende', 'Ende des Monats', 'Morgenstund'):
        assert tage(text) == [], text


def test_das_datum_steht_in_klammern_hinter_dem_ausdruck():
    text = 'Morgen ist die Sitzung, nächste Woche der Vortrag.'
    assert mit_datum(text, aufloesen(text, DIENSTAG)) == (
        'Morgen (30.09.2026) ist die Sitzung, nächste Woche (05.10.–11.10.2026) der Vortrag.')


def test_der_stichtag_bestimmt_den_tag():
    assert tage('morgen', datetime(2026, 12, 31, tzinfo=timezone.utc)) == [('morgen', date(2027, 1, 1), date(2027, 1, 1))]
