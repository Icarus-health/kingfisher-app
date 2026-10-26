"""Heute ohne Termine nennt den nächsten Termin der Woche (Paket U, H8), aus denselben Kalenderdaten des Briefings."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from icarus_memory.morning import compose

BERLIN = ZoneInfo('Europe/Berlin')
JETZT = datetime(2026, 9, 29, 7, 30, tzinfo=BERLIN)


def _dashboard(*termine: dict) -> dict:
    return {'briefing': {'punkte': []}, 'calendar': {'items': list(termine)}, 'mail': {'items': []}, 'tasks': {},
            'episodes': {}, 'proposals': {}}


def test_ohne_termin_heute_steht_der_naechste_da() -> None:
    ergebnis = compose(_dashboard(
        {'uid': 'spaet', 'summary': 'Referenzen besprechen', 'start': '2026-10-02T09:00:00+02:00'},
        {'uid': 'frueh', 'summary': 'Rheinauenblick', 'start': '2026-09-30T12:00:00+00:00'},
    ), now=JETZT, target=date(2026, 9, 29))
    assert ergebnis['later_today'] == []
    assert ergebnis['naechster_termin'] == {'title': 'Rheinauenblick', 'start': '2026-09-30T14:00:00+02:00',
                                            'ganztags': False}


def test_heutige_und_vergangene_termine_sind_nicht_der_naechste() -> None:
    ergebnis = compose(_dashboard(
        {'uid': 'heute', 'summary': 'Heute', 'start': '2026-09-29T15:00:00+02:00'},
        {'uid': 'gestern', 'summary': 'Gestern', 'start': '2026-09-28T15:00:00+02:00'},
    ), now=JETZT, target=date(2026, 9, 29))
    assert [termin['title'] for termin in ergebnis['later_today']] == ['Heute']
    assert ergebnis['naechster_termin'] is None


def test_ganztaegiges_ohne_zeitzone_gilt_in_der_zone_des_briefings() -> None:
    ergebnis = compose(_dashboard(
        {'uid': 'g', 'summary': 'Geburtstag von Anna', 'start': '2026-10-01T00:00:00', 'all_day': True},
        {'uid': 't', 'summary': 'Später', 'start': '2026-10-01T09:00:00+02:00'},
    ), now=JETZT, target=date(2026, 9, 29))
    assert ergebnis['naechster_termin'] == {'title': 'Geburtstag von Anna', 'start': '2026-10-01T00:00:00+02:00',
                                            'ganztags': True}
