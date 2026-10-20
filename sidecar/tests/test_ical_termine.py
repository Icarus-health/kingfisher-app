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


# -- Serien --------------------------------------------------------------------------


VON, BIS = utc(2026, 10, 1), utc(2027, 1, 1)
BERLIN_9 = ['DTSTART;TZID=Europe/Berlin:20261019T090000', 'DTEND;TZID=Europe/Berlin:20261019T100000']


def serie(*zeilen: str, uid: str = 'serie@probe') -> list[str]:
    return [f'UID:{uid}', 'SUMMARY:Jour fixe', *zeilen]


def beginne(termine) -> list[datetime]:
    return [t.start for t in termine]


def test_serie_wird_im_fenster_ausgeklappt_und_bleibt_ueber_die_zeitumstellung_um_neun():
    termine = parse_events(ics(serie(*BERLIN_9, 'RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=4')), VON, BIS)
    assert beginne(termine) == [utc(2026, 10, 19, 7), utc(2026, 10, 21, 7), utc(2026, 10, 26, 8), utc(2026, 10, 28, 8)]
    assert all('09:00 bis 10:00 Uhr' in termin_text(t) and t.summary == 'Jour fixe' for t in termine)
    assert [t.uid for t in termine] == ['serie@probe#20261019T070000Z', 'serie@probe#20261021T070000Z',
                                        'serie@probe#20261026T080000Z', 'serie@probe#20261028T080000Z']
    assert {t.external_uid for t in termine} == {'serie@probe'}


def test_serie_mit_until_interval_und_ohne_ende():
    alle_zwei_tage, monatlich, letzter_freitag = (parse_events(ics(serie(*zeilen)), VON, BIS) for zeilen in (
        ['DTSTART:20261005T140000Z', 'DTEND:20261005T150000Z', 'RRULE:FREQ=DAILY;INTERVAL=2;UNTIL=20261011T140000Z'],
        ['DTSTART:20260115T140000Z', 'DURATION:PT1H', 'RRULE:FREQ=MONTHLY;BYMONTHDAY=15'],
        ['DTSTART;TZID=Europe/Berlin:20260130T160000', 'DURATION:PT1H', 'RRULE:FREQ=MONTHLY;BYDAY=-1FR']))
    assert beginne(alle_zwei_tage) == [utc(2026, 10, d, 14) for d in (5, 7, 9, 11)]  # UNTIL zählt mit
    assert beginne(monatlich) == [utc(2026, 10, 15, 14), utc(2026, 11, 15, 14), utc(2026, 12, 15, 14)]
    assert beginne(letzter_freitag) == [utc(2026, 10, 30, 15), utc(2026, 11, 27, 15), utc(2026, 12, 25, 15)]


def test_exdate_nimmt_einzelne_termine_heraus():
    termine = parse_events(ics(serie(*BERLIN_9, 'RRULE:FREQ=DAILY;COUNT=6',
                                     'EXDATE;TZID=Europe/Berlin:20261020T090000,20261022T090000',
                                     'EXDATE:20261024T070000Z')), VON, BIS)
    assert beginne(termine) == [utc(2026, 10, 19, 7), utc(2026, 10, 21, 7), utc(2026, 10, 23, 7)]
    # Eine Uhrzeit ohne Zone gilt in der Zone der Serie, nicht in der des Nutzers.
    new_york = parse_events(ics(serie('DTSTART;TZID=America/New_York:20261019T090000', 'DURATION:PT1H',
                                      'RRULE:FREQ=DAILY;COUNT=3', 'EXDATE:20261020T090000')), VON, BIS)
    assert beginne(new_york) == [utc(2026, 10, 19, 13), utc(2026, 10, 21, 13)]


def test_rdate_fuegt_einen_termin_hinzu():
    termine = parse_events(ics(serie(*BERLIN_9, 'RRULE:FREQ=WEEKLY;COUNT=2',
                                     'RDATE;TZID=Europe/Berlin:20261105T090000')), VON, BIS)
    assert beginne(termine) == [utc(2026, 10, 19, 7), utc(2026, 10, 26, 8), utc(2026, 11, 5, 8)]
    assert termine[-1].end == utc(2026, 11, 5, 9)


def test_schon_ausgeklappte_serie_hat_dieselben_kennungen_wie_eine_hier_ausgeklappte():
    """Falls ein Server doch ausklappt (RFC 4791, 9.6.5): Einzeltermine in UTC, der erste darf ohne RECURRENCE-ID sein."""
    hier = parse_events(ics(serie(*BERLIN_9, 'RRULE:FREQ=WEEKLY;COUNT=3')), VON, BIS)

    def instanz(beginn: str, mit_kennung: bool = True) -> list[str]:
        ende = beginn[:9] + f'{int(beginn[9:11]) + 1:02d}' + beginn[11:]
        return serie(*([f'RECURRENCE-ID:{beginn}'] if mit_kennung else []), f'DTSTART:{beginn}', f'DTEND:{ende}')

    for erster_mit_kennung in (True, False):
        vom_server = parse_events(ics(instanz('20261019T070000Z', erster_mit_kennung), instanz('20261026T080000Z'),
                                      instanz('20261102T080000Z')), VON, BIS)
        assert [(t.uid, t.start, t.end) for t in vom_server] == [(t.uid, t.start, t.end) for t in hier]


def test_beginn_ist_immer_ein_termin_auch_wenn_er_nicht_zur_regel_passt():
    """RFC 5545, 3.8.5.3: DTSTART zählt als erster Termin. dateutil allein ließe ihn hier (ein Dienstag) weg."""
    termine = parse_events(ics(serie('DTSTART;TZID=Europe/Berlin:20261020T090000', 'DURATION:PT1H',
                                     'RRULE:FREQ=WEEKLY;BYDAY=MO;UNTIL=20261103T000000Z')), VON, BIS)
    assert beginne(termine) == [utc(2026, 10, 20, 7), utc(2026, 10, 26, 8), utc(2026, 11, 2, 8)]


def test_verschobener_einzeltermin_ersetzt_den_urspruenglichen_und_behaelt_seine_kennung():
    regel = serie(*BERLIN_9, 'RRULE:FREQ=WEEKLY;COUNT=3')
    vorher = parse_events(ics(regel), VON, BIS)
    verschoben = ['UID:serie@probe', 'RECURRENCE-ID;TZID=Europe/Berlin:20261026T090000', 'SUMMARY:Jour fixe (später)',
                  'DTSTART;TZID=Europe/Berlin:20261027T140000', 'DTEND;TZID=Europe/Berlin:20261027T150000']
    nachher = parse_events(ics(regel, verschoben), VON, BIS)
    assert beginne(nachher) == [utc(2026, 10, 19, 7), utc(2026, 10, 27, 13), utc(2026, 11, 2, 8)]
    assert nachher[1].summary == 'Jour fixe (später)' and nachher[1].end == utc(2026, 10, 27, 14)
    assert [t.uid for t in nachher] == [t.uid for t in vorher]
    # Die Reihenfolge der Blöcke in der Datei spielt keine Rolle.
    assert [t.uid for t in parse_events(ics(verschoben, regel), VON, BIS)] == [t.uid for t in vorher]


def test_abgesagter_einzeltermin_fehlt_der_rest_der_serie_bleibt():
    termine = parse_events(ics(serie(*BERLIN_9, 'RRULE:FREQ=WEEKLY;COUNT=3'),
                               ['UID:serie@probe', 'RECURRENCE-ID:20261026T080000Z', 'STATUS:CANCELLED',
                                'DTSTART;TZID=Europe/Berlin:20261026T090000']), VON, BIS)
    assert beginne(termine) == [utc(2026, 10, 19, 7), utc(2026, 11, 2, 8)]
    assert parse_events(ics(serie(*BERLIN_9, 'RRULE:FREQ=WEEKLY;COUNT=3', 'STATUS:CANCELLED')), VON, BIS) == []


def test_serie_die_vor_dem_fenster_beginnt_liefert_nur_termine_im_fenster():
    termine = parse_events(ics(serie('DTSTART;TZID=Europe/Berlin:20200101T090000',
                                     'DTEND;TZID=Europe/Berlin:20200101T100000', 'RRULE:FREQ=DAILY')),
                           utc(2026, 10, 1, 7, 30), utc(2026, 10, 4))
    # Der Termin am 1.10. (07:00 bis 08:00 UTC) läuft noch, als das Fenster beginnt.
    assert beginne(termine) == [utc(2026, 10, d, 7) for d in (1, 2, 3)]


def test_ganztaegige_jahresserie():
    termine = parse_events(ics(serie('DTSTART;VALUE=DATE:19801024', 'RRULE:FREQ=YEARLY', uid='geburtstag')), VON, BIS)
    (geburtstag,) = termine
    assert (geburtstag.start, geburtstag.end, geburtstag.all_day) == (utc(2026, 10, 24), utc(2026, 10, 25), True)
    assert geburtstag.uid == 'geburtstag#20261024'


def test_until_in_anderer_form_als_der_beginn(monkeypatch):
    """RFC 5545 verlangt UNTIL in derselben Form wie DTSTART; Kalender halten sich nicht immer daran."""
    ortszeit, datum, ganztags = (parse_events(ics(serie(*zeilen)), VON, BIS) for zeilen in (
        ['DTSTART;TZID=America/New_York:20261019T090000', 'RRULE:FREQ=DAILY;UNTIL=20261021T090000'],
        [*BERLIN_9, 'RRULE:FREQ=DAILY;UNTIL=20261021'],
        ['DTSTART;VALUE=DATE:20261019', 'RRULE:FREQ=DAILY;UNTIL=20261021T215959Z']))
    assert beginne(ortszeit) == [utc(2026, 10, d, 13) for d in (19, 20, 21)]  # Ortszeit der Serie
    assert beginne(datum) == [utc(2026, 10, d, 7) for d in (19, 20, 21)]  # ein Datum zählt mit seinem Tag
    assert beginne(ganztags) == [utc(2026, 10, d) for d in (19, 20, 21)]
    # Ganztägig mit UTC-Grenze: Es zählt der Tag, auf den sie beim Nutzer fällt (hier das Ende des 21. in New York).
    monkeypatch.setenv('KINGFISHER_TIMEZONE', 'America/New_York')
    westen = parse_events(ics(serie('DTSTART;VALUE=DATE:20261019', 'RRULE:FREQ=DAILY;UNTIL=20261022T035959Z')), VON, BIS)
    assert beginne(westen) == [utc(2026, 10, d) for d in (19, 20, 21)]


def test_ohne_fenster_bleibt_eine_serie_ein_termin():
    """`kalender_abo.pruefe` zählt so die Termine einer Datei; unbegrenzte Serien hätten sonst kein Ende."""
    (termin,) = parse_events(ics(serie(*BERLIN_9, 'RRULE:FREQ=DAILY')))
    assert (termin.uid, termin.start) == ('serie@probe', utc(2026, 10, 19, 7))


def test_kennungen_sind_stabil_ueber_abrufe_und_fenster():
    kalender = ics(serie(*BERLIN_9, 'RRULE:FREQ=DAILY'))
    oktober = {t.start: t.uid for t in parse_events(kalender, VON, utc(2026, 11, 1))}
    spaeter = {t.start: t.uid for t in parse_events(kalender, utc(2026, 10, 15), utc(2026, 12, 1))}
    gemeinsam = set(oktober) & set(spaeter)
    assert len(gemeinsam) == 13 and all(oktober[s] == spaeter[s] for s in gemeinsam)  # 19. bis 31.10.
    assert len(set(oktober.values())) == len(oktober)
    # Ein herausgenommener Tag ändert die Kennungen der anderen nicht.
    ohne = {t.start: t.uid for t in parse_events(ics(serie(*BERLIN_9, 'RRULE:FREQ=DAILY',
                                                           'EXDATE;TZID=Europe/Berlin:20261020T090000')),
                                                 VON, utc(2026, 11, 1))}
    assert utc(2026, 10, 20, 7) not in ohne and all(oktober[s] == uid for s, uid in ohne.items())


def test_termin_ohne_uid_hat_trotzdem_eine_feste_kennung():
    kalender = ics(['SUMMARY:Ohne UID', 'DTSTART:20261020T090000Z'], ['SUMMARY:Serie ohne UID', *BERLIN_9,
                                                                     'RRULE:FREQ=DAILY;COUNT=2'])
    erste, zweite = (sorted(t.uid for t in parse_events(kalender, VON, BIS)) for _ in range(2))
    assert erste == zweite and len(set(erste)) == 3


def test_kaputte_oder_fremde_regel_kippt_nichts():
    kaputt, fremd = (parse_events(ics(serie(*BERLIN_9, regel), ['UID:x', 'SUMMARY:Daneben', 'DTSTART:20261023T090000Z']),
                                  VON, BIS) for regel in ('RRULE:FREQ=QUATSCH', 'RRULE:FREQ=DAILY;COUNT=2;X-PROBE=1'))
    # Unlesbar: wie bisher nur der erste Termin, die anderen Termine der Datei bleiben.
    assert [(t.summary, t.uid) for t in kaputt] == [('Jour fixe', 'serie@probe'), ('Daneben', 'x')]
    # Ein unbekannter Zusatz (X-…) ändert die Regel nicht.
    assert beginne(fremd) == [utc(2026, 10, 19, 7), utc(2026, 10, 20, 7), utc(2026, 10, 23, 9)]


def test_zu_dichte_serie_bleibt_ein_termin_mit_hinweis_statt_die_quelle_zu_kippen(caplog):
    """Mehr als 48 Termine am Tag (im Mittel ab dem ersten Termin) gelten als zu dicht; die anderen Termine bleiben."""
    import time
    for regel in ('FREQ=SECONDLY', 'FREQ=MINUTELY'):
        beginn = time.perf_counter()
        termine = parse_events(ics(serie('DTSTART:20200101T000000Z', f'RRULE:{regel}'), NORMAL), VON, BIS)
        assert time.perf_counter() - beginn < 1
        assert [t.uid for t in termine] == ['serie@probe', 'normal']
    assert 'zu dicht' in caplog.text


def test_dichte_aber_zulaessige_serie_kippt_nicht_mit_der_zeit():
    """Gezählt wird die Dichte, nicht die Zahl seit Serienbeginn: Stündlich seit 2015 und halbstündlich seit 2021
    bleiben auch Jahre später ausgeklappt (vorher fielen sie nach 100.000 Wiederholungen mit einem Fehler aus)."""
    from datetime import timedelta
    stuendlich = serie('DTSTART:20150101T000000Z', 'DURATION:PT15M', 'RRULE:FREQ=HOURLY')
    halbstuendlich = serie('DTSTART:20210101T000000Z', 'DURATION:PT15M', 'RRULE:FREQ=MINUTELY;INTERVAL=30', uid='halb')
    for von in (utc(2026, 10, 20), utc(2040, 1, 1)):
        termine = parse_events(ics(stuendlich, halbstuendlich), von, von + timedelta(days=1))
        assert sum(t.uid.startswith('serie@probe#') for t in termine) == 24
        assert sum(t.uid.startswith('halb#') for t in termine) == 48


# -- Serien in Abo, CalDAV und Gedächtnis -------------------------------------------


class Feed:
    """Ein iCalendar-Abo ohne Netz: liefert, was gerade in `text` steht."""

    def __init__(self, text: str) -> None:
        import httpx

        from icarus_memory.connectors.collections import ICalendarSubscription
        self.text = text
        self.leser = ICalendarSubscription('https://kalender.example.test/probe.ics', transport=httpx.MockTransport(
            lambda anfrage: httpx.Response(200, text=self.text)))


def test_abo_klappt_serien_im_abgefragten_fenster_aus_und_liefert_einzeltermine_wie_bisher():
    feed = Feed(ics(serie(*BERLIN_9, 'RRULE:FREQ=WEEKLY'),
                    ['UID:alt', 'SUMMARY:Archiv', 'DTSTART:20200103T100000Z', 'DTEND:20200103T110000Z']))
    termine = feed.leser.events(days=14, at=utc(2026, 10, 19))
    assert [(t.summary, t.start) for t in termine] == [
        ('Archiv', utc(2020, 1, 3, 10)), ('Jour fixe', utc(2026, 10, 19, 7)), ('Jour fixe', utc(2026, 10, 26, 8))]


def test_caldav_klappt_serien_im_abgefragten_fenster_aus(monkeypatch):
    from icarus_memory.connectors.calendar import CalendarConfig, CalendarConnector
    from tests.caldav_attrappe import PASSWORT, CaldavAttrappe
    with CaldavAttrappe() as attrappe:
        monkeypatch.setenv('SSL_CERT_FILE', str(attrappe.zertifikat))
        attrappe.kalenderdaten = ics(serie(*BERLIN_9, 'RRULE:FREQ=WEEKLY;BYDAY=MO,WE'),
                                     ['UID:serie@probe', 'RECURRENCE-ID;TZID=Europe/Berlin:20261021T090000',
                                      'STATUS:CANCELLED', 'DTSTART;TZID=Europe/Berlin:20261021T090000'])
        leser = CalendarConnector(CalendarConfig(f'{attrappe.start}calendars/lena.probe/privat/', 'lena.probe',
                                                 PASSWORT))
        termine = leser.events(days=10, at=utc(2026, 10, 19))
    assert beginne(termine) == [utc(2026, 10, 19, 7), utc(2026, 10, 26, 8), utc(2026, 10, 28, 8)]
    assert 'start="20261019T000000Z" end="20261029T000000Z"' in attrappe.berichte[0]


JETZT = utc(2026, 10, 19, 8)


def test_serie_im_gedaechtnis_feste_kennungen_verschiebung_ist_neue_fassung(gedaechtnis):
    from datetime import timedelta

    from icarus_memory.calendar_memory import fenster, kalender_job
    from icarus_memory.connectors.collections import NamedCalendar
    regel = serie('DTSTART;TZID=Europe/Berlin:20250107T140000', 'DURATION:PT1H', 'RRULE:FREQ=WEEKLY')
    einzeln = ['UID:einzeln', 'SUMMARY:Einzeln', 'DTSTART:20261020T100000Z', 'DTEND:20261020T110000Z']
    feed = Feed(ics(regel, einzeln))
    quellen = [NamedCalendar('abo', 'Abo', feed.leser)]
    _, bis = fenster(JETZT)
    wochen, beginn = 0, datetime(2025, 1, 7, 13, tzinfo=UTC)
    while beginn < bis:
        wochen, beginn = wochen + 1, beginn + timedelta(weeks=1)

    erster = kalender_job(gedaechtnis, quellen, at=JETZT)['abo']
    assert (erster.neu, erster.fehler) == (wochen + 1, [])
    zweiter = kalender_job(gedaechtnis, quellen, at=JETZT)['abo']
    assert (zweiter.neu, zweiter.geaendert, zweiter.entzogen, zweiter.unveraendert) == (0, 0, 0, wochen + 1)

    feed.text = ics(regel, einzeln, ['UID:serie@probe', 'RECURRENCE-ID;TZID=Europe/Berlin:20261027T140000',
                                     'SUMMARY:Jour fixe', 'DTSTART;TZID=Europe/Berlin:20261028T140000',
                                     'DURATION:PT1H'])
    verschoben = kalender_job(gedaechtnis, quellen, at=JETZT)['abo']
    assert (verschoben.neu, verschoben.geaendert, verschoben.entzogen) == (0, 1, 0)

    feed.text = ics(regel + ['EXDATE;TZID=Europe/Berlin:20261103T140000'], einzeln)
    ausgenommen = kalender_job(gedaechtnis, quellen, at=JETZT)['abo']
    # 3.11. fällt weg (entzogen); der 27.10. ist zurück an seinem Platz, seine erste Fassung gilt wieder.
    assert (ausgenommen.neu, ausgenommen.geaendert, ausgenommen.entzogen, ausgenommen.wiederhergestellt) == (0, 0, 1, 1)
    assert gedaechtnis.anzahl('abo') == wochen


def test_obergrenze_gilt_beim_abo_je_abschnitt(gedaechtnis, monkeypatch):
    from icarus_memory import calendar_memory
    from icarus_memory.connectors.collections import NamedCalendar
    monkeypatch.setattr(calendar_memory, 'MAX_TERMINE_JE_ABSCHNITT', 5)
    monatlich = Feed(ics(serie('DTSTART:20261115T100000Z', 'DURATION:PT1H', 'RRULE:FREQ=MONTHLY;COUNT=12')))
    ergebnis = calendar_memory.kalender_job(gedaechtnis, [NamedCalendar('abo', 'Abo', monatlich.leser)], at=JETZT)
    assert (ergebnis['abo'].neu, ergebnis['abo'].fehler) == (12, [])
    taeglich = Feed(ics(serie('DTSTART:20261115T100000Z', 'DURATION:PT1H', 'RRULE:FREQ=DAILY;COUNT=6')))
    ergebnis = calendar_memory.kalender_job(gedaechtnis, [NamedCalendar('dicht', 'D', taeglich.leser)], at=JETZT)
    assert (ergebnis['dicht'].neu, ergebnis['dicht'].fehler) == (0, ['zu viele Termine im Abschnitt'])


@pytest.mark.parametrize('cr_als_zeichenreferenz', [False, True])
def test_caldav_liest_den_kalender_aus_dem_xml_nicht_aus_dem_rohtext(monkeypatch, cr_als_zeichenreferenz):
    """Im REPORT steht der Kalender als XML-Text: „&“ kommt als „&amp;“, manche Server schreiben CR als „&#13;“."""
    from icarus_memory.connectors.calendar import CalendarConfig, CalendarConnector
    from tests.caldav_attrappe import PASSWORT, CaldavAttrappe
    with CaldavAttrappe() as attrappe:
        monkeypatch.setenv('SSL_CERT_FILE', str(attrappe.zertifikat))
        attrappe.cr_als_zeichenreferenz = cr_als_zeichenreferenz
        attrappe.kalenderdaten = ics(['UID:steuer', 'SUMMARY:Steuer & Recht <Jahresabschluss>',
                                      'LOCATION:Müller & Söhne', 'DTSTART;TZID=Europe/Berlin:20261020T090000',
                                      'DTEND;TZID=Europe/Berlin:20261020T100000'])
        leser = CalendarConnector(CalendarConfig(f'{attrappe.start}calendars/lena.probe/privat/', 'lena.probe',
                                                 PASSWORT))
        (termin,) = leser.events(days=10, at=utc(2026, 10, 19))
    assert (termin.summary, termin.location) == ('Steuer & Recht <Jahresabschluss>', 'Müller & Söhne')
    assert (termin.start, termin.end) == (utc(2026, 10, 20, 7), utc(2026, 10, 20, 8))


# -- Größe eines Abos ----------------------------------------------------------------


def grosser_kalender(megabyte: float) -> str:
    """Termine wie in Googles Datei (Teilnehmer, Notiz), bis die Datei `megabyte` groß ist."""
    termin = ['SUMMARY:Abstimmung', 'DESCRIPTION:' + 'Agenda und Protokoll\\n' * 40,
              *[f'ATTENDEE;CN=Person {k};PARTSTAT=ACCEPTED:mailto:person{k}@example.org' for k in range(5)]]
    eins = len(ics([*termin, 'UID:x', 'DTSTART:20200101T090000Z']).encode())
    anzahl = int(megabyte * 1_000_000 / (eins - 60)) + 1
    return ics(*([*termin, f'UID:t{n}', f'DTSTART:{20200101 + n % 28:08d}T090000Z', 'DURATION:PT1H']
                 for n in range(anzahl)))


def test_ein_abo_ueber_fuenf_mb_wird_gelesen_beim_einrichten_und_danach():
    """Googles geheime Adresse liefert die ganze Geschichte des Kalenders; fünf MB sind wenige Jahre."""
    import httpx

    from icarus_memory import kalender_abo
    text = grosser_kalender(6)
    assert len(text.encode()) > 6_000_000
    transport = httpx.MockTransport(lambda anfrage: httpx.Response(200, text=text))
    _, abo = kalender_abo.pruefe('https://kalender.example.test/gross.ics', transport=transport)
    feed = Feed(text)
    assert abo.termine == len(feed.leser.events(days=1, at=utc(2020, 1, 1))) > 3000


def test_zu_grosses_abo_bricht_frueh_ab_und_sagt_es_in_einem_satz(monkeypatch):
    import httpx

    from icarus_memory import kalender_abo
    from icarus_memory.connectors import collections
    from icarus_memory.connectors.calendar import CalendarError
    from icarus_memory.mail_anmeldung import Anmeldefehler
    monkeypatch.setattr(collections, 'ABO_GROESSE', 2_000_000)
    monkeypatch.setattr(kalender_abo, 'GROESSE', 2_000_000)
    gelesen = []

    def zehn_mb():
        for _ in range(2000):
            gelesen.append(1)
            yield b'BEGIN:VEVENT\r\nUID:x\r\nDTSTART:20261020T090000Z\r\nEND:VEVENT\r\n' * 100

    transport = httpx.MockTransport(lambda anfrage: httpx.Response(200, content=zehn_mb()))
    satz = 'Dieser Kalender ist größer als 2 MB; so viel liest Kingfisher über eine Adresse nicht.'
    with pytest.raises(CalendarError) as fehler:
        collections.ICalendarSubscription('https://kalender.example.test/riesig.ics', transport=transport).events()
    assert str(fehler.value) == satz
    assert len(gelesen) < 500  # nicht erst alles laden und dann ablehnen
    with pytest.raises(Anmeldefehler) as fehler:
        kalender_abo.pruefe('https://kalender.example.test/riesig.ics', transport=transport)
    assert (fehler.value.grund, fehler.value.satz) == ('zu_gross', satz)


# -- Robustheit: unmögliche Daten, unerfüllbare und zu dichte Regeln (Review) ----------


EXTREM = [['UID:x1', 'SUMMARY:Letzter Tag', 'DTSTART;VALUE=DATE:99991231'],
          ['UID:x2', 'SUMMARY:Westküste', 'DTSTART;TZID=America/Los_Angeles:99991231T230000'],
          ['UID:x3', 'SUMMARY:Ewig', 'DTSTART:20261020T090000Z', 'DURATION:P999999999W'],
          ['UID:x4', 'SUMMARY:Lange Serie', 'DTSTART:20261020T090000Z', 'DURATION:P150000W', 'RRULE:FREQ=WEEKLY'],
          ['UID:x5', 'SUMMARY:Bis zum Schluss', 'DTSTART;VALUE=DATE:20261020', 'RRULE:FREQ=YEARLY;UNTIL=99991231T235959Z']]
NORMAL = ['UID:normal', 'SUMMARY:Normal', 'DTSTART:20261021T090000Z', 'DTEND:20261021T100000Z']


def test_ein_termin_mit_unmoeglichem_datum_kippt_die_quelle_nicht():
    """Ein Datum am Rand des Darstellbaren (Jahr 9999, riesige Dauer): Der Termin bleibt, was sich nicht darstellen
    lässt (Ende, Beginn in UTC), ist unbekannt; die anderen Termine der Quelle bleiben unberührt."""
    import httpx

    from icarus_memory import kalender_abo
    kalender = ics(*EXTREM, NORMAL)
    for fenster in ((), (VON, BIS)):
        termine = {t.uid.partition('#')[0]: t for t in parse_events(kalender, *fenster)}
        assert set(termine) == {'x1', 'x2', 'x3', 'x4', 'x5', 'normal'}
        assert termine['x1'].end is None and termine['x2'].start is None and termine['x3'].end is None
    assert 'Normal' in [t.summary for t in Feed(kalender).leser.events(days=30, at=utc(2026, 10, 15))]
    # „Kalender verbinden“ zählt die Termine; das darf nicht mit einem Serverfehler enden.
    _, abo = kalender_abo.pruefe('https://kalender.example.test/rand.ics',
                                 transport=httpx.MockTransport(lambda anfrage: httpx.Response(200, text=kalender)))
    assert abo.termine >= 1


def test_ein_unerwarteter_fehler_in_einem_termin_nimmt_die_anderen_nicht_mit(monkeypatch):
    from icarus_memory.connectors import calendar
    echt = calendar._termin

    def kaputt(termin, uid, *rest):
        if uid.startswith('x1'):
            raise OverflowError('Probe')
        return echt(termin, uid, *rest)

    monkeypatch.setattr(calendar, '_termin', kaputt)
    assert [t.uid for t in parse_events(ics(EXTREM[0], NORMAL))] == ['normal']


UNERFUELLBAR = [
    'FREQ=DAILY;BYMONTH=2;BYMONTHDAY=30',
    'FREQ=HOURLY;BYMONTH=2;BYMONTHDAY=30',
    'FREQ=MINUTELY;BYHOUR=9;BYMINUTE=0;BYMONTH=2;BYMONTHDAY=30',
    'FREQ=WEEKLY;BYMONTH=4;BYMONTHDAY=31',
    'FREQ=YEARLY;BYYEARDAY=60;BYMONTH=6',
    'FREQ=MONTHLY;BYDAY=1MO;BYMONTHDAY=20',
    'FREQ=MONTHLY;BYDAY=MO;BYSETPOS=6',
    'FREQ=MONTHLY;BYDAY=6MO',
    'FREQ=MONTHLY;INTERVAL=2;BYMONTH=2',
    'FREQ=DAILY;INTERVAL=7;BYDAY=TU',
    'FREQ=YEARLY;INTERVAL=2;BYMONTH=2;BYMONTHDAY=29',
    'FREQ=WEEKLY;BYDAY=MO;BYSETPOS=2',
]


@pytest.mark.parametrize('regel', UNERFUELLBAR)
def test_unerfuellbare_regel_bleibt_ein_termin_und_kostet_keine_zeit(regel):
    """dateutil rechnet eine Regel, die nie trifft, bis ins Jahr 9999 (bis zu Minuten je Aufruf). Sie wird vorher
    erkannt und bleibt wie eine unlesbare Regel ihr erster Termin. Beginn: Montag, 6. Januar 2025."""
    import time
    beginn = time.perf_counter()
    termine = parse_events(ics(serie('DTSTART;TZID=Europe/Berlin:20250106T090000', 'DURATION:PT1H', f'RRULE:{regel}'),
                               NORMAL), VON, BIS)
    assert time.perf_counter() - beginn < 1
    assert [t.uid for t in termine] == ['serie@probe', 'normal']


@pytest.mark.parametrize(('regel', 'von', 'bis', 'anzahl'), [
    ('FREQ=YEARLY;BYMONTH=2;BYMONTHDAY=29', utc(2028, 1, 1), utc(2028, 3, 1), 1),
    ('FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-1', VON, BIS, 3),
    ('FREQ=MONTHLY;BYDAY=5FR', VON, BIS, 1),
    ('FREQ=MONTHLY;INTERVAL=2;BYMONTH=3,5', utc(2027, 1, 1), utc(2027, 7, 1), 2),
    ('FREQ=DAILY;INTERVAL=7;BYDAY=MO', VON, utc(2026, 11, 1), 4),
    ('FREQ=DAILY;INTERVAL=2;BYDAY=TU', VON, utc(2026, 11, 1), 2),
    ('FREQ=DAILY;BYMONTH=2;BYMONTHDAY=29;BYDAY=MO', utc(2044, 2, 1), utc(2044, 3, 1), 1),
    ('FREQ=WEEKLY;BYMONTH=2;BYMONTHDAY=29', utc(2028, 2, 1), utc(2028, 3, 1), 1),
])
def test_seltene_aber_erfuellbare_regeln_werden_weiter_ausgeklappt(regel, von, bis, anzahl):
    termine = parse_events(ics(serie('DTSTART;TZID=Europe/Berlin:20250106T090000', 'DURATION:PT1H', f'RRULE:{regel}')),
                           von, bis)
    assert len(termine) == anzahl and all('#' in t.uid for t in termine)


def test_zeitzone_mit_vorangestelltem_herausgeber_von_libical_und_mozilla():
    for tzid, erwartet in (('/freeassociation.sourceforge.net/Europe/Berlin', 'Europe/Berlin'),
                           ('/freeassociation.sourceforge.net/Tzfile/Europe/Berlin', 'Europe/Berlin'),
                           ('/mozilla.org/20070129_1/Europe/Berlin', 'Europe/Berlin'),
                           ('/softwarestudio.org/Olson_20011030_5/America/Argentina/Buenos_Aires',
                            'America/Argentina/Buenos_Aires')):
        assert str(zone(tzid)) == erwartet, tzid
    assert zone('/mozilla.org/20070129_1/Berlin') is None  # kein IANA-Name darin: nicht raten
    (termin,) = parse_events(ics(['UID:l', 'DTSTART;TZID=/freeassociation.sourceforge.net/Europe/Berlin:20261020T090000',
                                  'DTEND;TZID=/freeassociation.sourceforge.net/Europe/Berlin:20261020T100000']))
    assert (termin.start, termin.end) == (utc(2026, 10, 20, 7), utc(2026, 10, 20, 8))
