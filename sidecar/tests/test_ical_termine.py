"""Termine aus iCalendar-Text (CalDAV und Abo, etwa Googles geheime iCal-Adresse): Zeitzonen, Absagen, Serien.

Nur synthetische Termine. Der Nutzer sitzt in Europe/Berlin (Vorgabe von `KINGFISHER_TIMEZONE`); die Sommerzeit endet
2026 am 25. Oktober. Ein Termin am 20.10. um 09:00 Berliner Zeit ist deshalb 07:00 UTC, einer am 2.11. 08:00 UTC.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from icarus_memory.calendar_memory import termin_text
from icarus_memory.connectors.calendar import parse_events
from icarus_memory.connectors.zeitzonen import WINDOWS_ZONEN, zone

UTC = timezone.utc


def ics(*termine: list[str]) -> str:
    """Ein Kalender mit je einem VEVENT pro Zeilenliste."""
    return ('BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Probe//Kalender//DE\r\n'
            + ''.join('BEGIN:VEVENT\r\n' + ''.join(z + '\r\n' for z in t) + 'END:VEVENT\r\n' for t in termine)
            + 'END:VCALENDAR\r\n')


def utc(*teile: int) -> datetime:
    return datetime(*teile, tzinfo=UTC)


@pytest.fixture(autouse=True)
def berlin(monkeypatch):
    monkeypatch.setenv('KINGFISHER_TIMEZONE', 'Europe/Berlin')


# -- Zeitzonen -----------------------------------------------------------------


def test_tzid_wird_in_die_richtige_zeit_umgerechnet():
    sommer, winter = parse_events(ics(
        ['UID:s', 'SUMMARY:Sommerzeit', 'DTSTART;TZID=Europe/Berlin:20261020T090000',
         'DTEND;TZID=Europe/Berlin:20261020T100000'],
        ['UID:w', 'SUMMARY:Winterzeit', 'DTSTART;TZID=Europe/Berlin:20261102T090000',
         'DTEND;TZID=Europe/Berlin:20261102T100000']))
    assert (sommer.start, sommer.end) == (utc(2026, 10, 20, 7), utc(2026, 10, 20, 8))
    assert (winter.start, winter.end) == (utc(2026, 11, 2, 8), utc(2026, 11, 2, 9))
    # Was der Nutzer im Gedächtnis liest: die Uhrzeit, die im Kalender steht.
    assert 'Dienstag, 20. Oktober 2026 (20.10.2026), 09:00 bis 10:00 Uhr' in termin_text(sommer)
    assert 'Montag, 2. November 2026 (02.11.2026), 09:00 bis 10:00 Uhr' in termin_text(winter)


def test_outlook_zeitzonennamen_werden_zugeordnet():
    outlook, pazifik = parse_events(ics(
        ['UID:o', 'SUMMARY:Outlook', 'DTSTART;TZID=W. Europe Standard Time:20261020T090000',
         'DTEND;TZID=W. Europe Standard Time:20261020T093000'],
        ['UID:p', 'SUMMARY:Westküste', 'DTSTART;TZID="Pacific Standard Time":20261020T090000',
         'DTEND;TZID="Pacific Standard Time":20261020T100000']))
    assert (outlook.start, outlook.end) == (utc(2026, 10, 20, 7), utc(2026, 10, 20, 7, 30))
    assert pazifik.start == utc(2026, 10, 20, 16)  # Sommerzeit dort: UTC−7


def test_zuordnung_der_windows_zonen_ist_aufloesbar_und_raet_nicht():
    assert all(zone(name) is not None for name in WINDOWS_ZONEN)
    assert str(zone('W. Europe Standard Time')) == 'Europe/Berlin'
    assert str(zone('"Europe/Berlin"')) == 'Europe/Berlin'
    for unbekannt in ('Customized Time Zone', '(UTC+01:00) Amsterdam, Berlin', 'W. Europe', '../etc/passwd',
                      '/etc/localtime', '', None):
        assert zone(unbekannt) is None, unbekannt


def test_unbekannte_zeitzone_behaelt_die_bisherige_rueckfallregel():
    """Nicht raten: Die Uhrzeit gilt wie bisher als UTC. Ein Doppelpunkt im Namen zerlegt die Zeile nicht mehr."""
    eigen, angepasst = parse_events(ics(
        ['UID:e', 'SUMMARY:Eigene Zone', 'DTSTART;TZID="(UTC+01:00) Amsterdam, Berlin, Bern, Rom":20261020T090000',
         'DTEND;TZID="(UTC+01:00) Amsterdam, Berlin, Bern, Rom":20261020T100000'],
        ['UID:c', 'SUMMARY:Angepasst', 'DTSTART;TZID=Customized Time Zone:20261021T090000',
         'DTEND;TZID=Customized Time Zone:20261021T100000']))
    assert (eigen.summary, eigen.start, eigen.end) == ('Eigene Zone', utc(2026, 10, 20, 9), utc(2026, 10, 20, 10))
    assert (angepasst.start, angepasst.end) == (utc(2026, 10, 21, 9), utc(2026, 10, 21, 10))


def test_utc_und_ganztaegig_bleiben_wie_bisher():
    in_utc, ganztags = parse_events(ics(
        ['UID:u', 'SUMMARY:UTC', 'DTSTART:20261020T090000Z', 'DTEND:20261020T100000Z'],
        ['UID:g', 'SUMMARY:Ganztags', 'DTSTART;VALUE=DATE:20261021', 'DTEND;VALUE=DATE:20261022']))
    assert (in_utc.start, in_utc.end, in_utc.all_day) == (utc(2026, 10, 20, 9), utc(2026, 10, 20, 10), False)
    assert (ganztags.start, ganztags.end, ganztags.all_day) == (utc(2026, 10, 21), utc(2026, 10, 22), True)
    assert 'Wann: ganztägig, Mittwoch, 21. Oktober 2026 (21.10.2026)\n' in termin_text(ganztags) + '\n'


def test_termin_ohne_zeitzone_gilt_in_der_zeit_des_nutzers(monkeypatch):
    """RFC 5545, 3.3.5: eine Uhrzeit ohne Zone („floating“) ist die Ortszeit dessen, der sie liest."""
    kalender = ics(['UID:f', 'SUMMARY:Ortszeit', 'DTSTART:20261020T090000', 'DTEND:20261020T100000'])
    (termin,) = parse_events(kalender)
    assert (termin.start, termin.end) == (utc(2026, 10, 20, 7), utc(2026, 10, 20, 8))
    monkeypatch.setenv('KINGFISHER_TIMEZONE', 'America/New_York')
    (termin,) = parse_events(kalender)
    assert termin.start == utc(2026, 10, 20, 13)


def test_ende_in_einer_anderen_zone_als_der_beginn():
    (flug,) = parse_events(ics(['UID:flug', 'SUMMARY:Flug', 'DTSTART;TZID=Europe/Berlin:20261020T100000',
                                'DTEND;TZID=America/New_York:20261020T130000']))
    assert (flug.start, flug.end) == (utc(2026, 10, 20, 8), utc(2026, 10, 20, 17))


def test_doppelpunkt_und_semikolon_in_anfuehrungszeichen_gehoeren_zum_parameter():
    (termin,) = parse_events(ics(['UID:q', 'SUMMARY:Runde', 'DTSTART:20261020T090000Z',
                                  'ATTENDEE;CN="Keller: Anna; Büro";RSVP=TRUE:mailto:anna@x.example']))
    assert termin.attendees == ['Keller: Anna; Büro <anna@x.example>']


# -- Absagen und Erinnerungen ----------------------------------------------------


@pytest.fixture
def gedaechtnis(tmp_path):
    from icarus_memory.calendar_memory import KalenderGedaechtnis
    from icarus_memory.claims import ClaimStore
    from icarus_memory.episodes import EpisodeStore
    episodes, claims = EpisodeStore(tmp_path / 'episodes.sqlite3'), ClaimStore(tmp_path / 'knowledge.sqlite3')
    yield KalenderGedaechtnis(episodes, claims)
    episodes.close()
    claims.close()


def test_abgesagter_termin_wird_nicht_uebernommen():
    termine = parse_events(ics(
        ['UID:a', 'SUMMARY:Abgesagt', 'STATUS:CANCELLED', 'DTSTART:20261020T090000Z', 'DTEND:20261020T100000Z'],
        ['UID:b', 'SUMMARY:Klein geschrieben', 'STATUS:cancelled', 'DTSTART:20261021T090000Z'],
        ['UID:c', 'SUMMARY:Bestätigt', 'STATUS:CONFIRMED', 'DTSTART:20261022T090000Z', 'DTEND:20261022T100000Z'],
        ['UID:d', 'SUMMARY:Vorläufig', 'STATUS:TENTATIVE', 'DTSTART:20261023T090000Z', 'DTEND:20261023T100000Z']))
    assert [t.summary for t in termine] == ['Bestätigt', 'Vorläufig']


def test_abgesagter_termin_wird_im_gedaechtnis_entzogen(gedaechtnis):
    """Wie bei Google und Microsoft: Eine Absage ist für das Gedächtnis eine entzogene Quelle."""
    von, bis = utc(2026, 10, 1), utc(2026, 12, 30)
    runde = ['UID:runde', 'SUMMARY:Runde', 'DTSTART:20261020T090000Z', 'DTEND:20261020T100000Z']
    andere = ['UID:andere', 'SUMMARY:Andere', 'DTSTART:20261021T090000Z', 'DTEND:20261021T100000Z']
    assert gedaechtnis.abgleichen('abo', 'Abo', parse_events(ics(runde, andere)), von, bis).neu == 2
    ergebnis = gedaechtnis.abgleichen('abo', 'Abo', parse_events(ics(runde + ['STATUS:CANCELLED'], andere)), von, bis)
    assert (ergebnis.entzogen, ergebnis.unveraendert) == (1, 1)
    assert gedaechtnis.anzahl('abo') == 1


def test_erinnerung_ueberschreibt_titel_und_notiz_nicht():
    """Google schreibt in jede Erinnerung (VALARM) „This is an event reminder“; das ist nicht die Notiz des Termins."""
    (termin,) = parse_events(ics(['UID:e', 'SUMMARY:Jour fixe', 'DESCRIPTION:Agenda', 'DTSTART:20261020T090000Z',
                                  'BEGIN:VALARM', 'ACTION:EMAIL', 'SUMMARY:Erinnerung',
                                  'DESCRIPTION:This is an event reminder', 'TRIGGER:-P0DT0H30M0S',
                                  'ATTENDEE:mailto:ich@x.example', 'END:VALARM']))
    assert (termin.summary, termin.notes, termin.attendees) == ('Jour fixe', 'Agenda', [])
    (ohne_notiz,) = parse_events(ics(['UID:o', 'DTSTART:20261020T090000Z', 'BEGIN:VALARM', 'ACTION:DISPLAY',
                                      'DESCRIPTION:This is an event reminder', 'END:VALARM', 'SUMMARY:Danach']))
    assert (ohne_notiz.summary, ohne_notiz.notes) == ('Danach', '')


# -- Ende aus DURATION und nach RFC 5545 ----------------------------------------------


def test_ende_aus_dauer_oder_nach_der_regel_des_standards(gedaechtnis):
    """RFC 5545, 3.6.1: ohne DTEND gilt DURATION; fehlt beides, dauert ein Datum einen Tag, eine Uhrzeit null."""
    dauer, tag, tage, punkt = parse_events(ics(
        ['UID:d', 'SUMMARY:Mit Dauer', 'DTSTART;TZID=Europe/Berlin:20261020T090000', 'DURATION:PT1H30M'],
        ['UID:t', 'SUMMARY:Steuertermin', 'DTSTART;VALUE=DATE:20261021'],
        ['UID:w', 'SUMMARY:Urlaub', 'DTSTART;VALUE=DATE:20261022', 'DURATION:P1W'],
        ['UID:p', 'SUMMARY:Erinnerung', 'DTSTART:20261023T090000Z']))
    assert (dauer.start, dauer.end) == (utc(2026, 10, 20, 7), utc(2026, 10, 20, 8, 30))
    assert (tag.start, tag.end, tag.all_day) == (utc(2026, 10, 21), utc(2026, 10, 22), True)
    assert (tage.start, tage.end) == (utc(2026, 10, 22), utc(2026, 10, 29))
    assert punkt.end == punkt.start
    # Ohne Ende fehlten solche Termine bisher still im Gedächtnis.
    ergebnis = gedaechtnis.abgleichen('abo', 'Abo', [dauer, tag, tage, punkt], utc(2026, 10, 1), utc(2026, 12, 1))
    assert (ergebnis.neu, ergebnis.ausserhalb) == (4, 0)


def test_kaputte_dauer_ist_kein_ende():
    (termin,) = parse_events(ics(['UID:k', 'DTSTART:20261020T090000Z', 'DURATION:eine Stunde']))
    assert termin.start == utc(2026, 10, 20, 9) and termin.end is None
