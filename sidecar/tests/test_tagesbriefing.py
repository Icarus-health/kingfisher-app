"""Tagesbriefing: drei bis fünf Zeilen, ein Urteil; jede Zeile mit Aktion; nichts ohne Beleg."""
from datetime import date, datetime, timedelta, timezone

from icarus_memory import tagesbriefing as tb
from icarus_memory.einpacken import Packstueck
from icarus_memory.fristlage import Frist
from icarus_memory.terminvorbereitung import Beleg, Person, Termin, Vorbereitung, Zeile

ZONE = timezone(timedelta(hours=2))
JETZT = datetime(2026, 9, 30, 8, 0, tzinfo=ZONE)


def beleg(i='e1', datum='2026-09-22T14:40:00+02:00'):
    return Beleg(i, 'Zahlen für unser Gespräch', datum, 'Mail')


def vorbereitung(stunde=14, tage=0, ort='Uferweg 7, Wiesbaden', weg=None, personen=True, einpacken=True, uid='t1'):
    beginn = (JETZT + timedelta(days=tage)).replace(hour=stunde, minute=0)
    v = Vorbereitung(termin=Termin(uid, 'Gespräch Rheinauenblick', beginn, beginn + timedelta(hours=1), ort=ort))
    if personen:
        v.personen = [
            Person('Dr. Ruth Engel', 'r@x.example', 'person:a:r@x.example', True,
                   will=[Zeile('Das Screening hätte ich gern ab Januar 2027 in der Routine.', beleg('e-wunsch'), 'Wunsch',
                               'wunsch', True)], letzter_kontakt=Zeile('Danke.', beleg())),
            Person('Marcel Odenthal', 'm@x.example', 'person:a:m@x.example', True,
                   will=[Zeile('Ich würde mir eine Schulung fürs Küchenteam wünschen.', beleg('e-odenthal'), 'Wunsch',
                               'wunsch', True)])]
    if einpacken:
        v.einpacken = [Packstueck('Laptop, Handout Dysphagiekost mitnehmen.', 'e-notiz', 'Vorbereitung', JETZT, 'notiz')]
    v.wegezeit = weg
    return v


def frist(status='kommend', tage=1, text='Ich sende die Unterlagen bis Freitag.'):
    return Frist(datum=date(2026, 9, 30) + timedelta(days=tage), text=text, ausdruck='30.09.2026', episode_id='e-frist',
                 titel='Unterlagen', quelle_datum=None, quelle_art='Mail', art='Zusage', richtung='von_mir', status=status,
                 tage=tage, vermutlich=status == 'verstrichen')


WETTER = {'location': 'Wiesbaden', 'temperature_c': 14, 'condition': 'Bewölkt'}
WEG = {'status': 'berechnet', 'minuten': 35, 'verkehrsmittel': 'auto', 'quelle': 'Apple Karten', 'puffer_min': 10,
       'losfahren': '2026-09-30T13:15:00+02:00', 'knapp': '', 'hinweis': ''}


def test_drei_bis_fuenf_zeilen_in_der_reihenfolge_wohin_wer_was_mit_was_draengt_wetter():
    lage = tb.erstellen([vorbereitung(weg=WEG)], [frist()], WETTER, jetzt=JETZT)
    assert [z.art for z in lage.zeilen] == ['termin', 'leute', 'einpacken', 'fristen', 'wetter'] and len(lage.zeilen) <= tb.MAX_ZEILEN
    assert lage.einleitung == 'Das zählt heute.' and lage.tag == 'heute'
    termin, leute, packen, fristen, wetter = (z.text for z in lage.zeilen)
    assert termin.startswith('Heute um 14:00 Uhr: „Gespräch Rheinauenblick“ bei Uferweg 7') and 'Losfahren um 13:15 Uhr' in termin
    assert 'etwa 35 Minuten mit dem Auto (Apple Karten)' in termin
    assert leute.startswith('Mit Dr. Ruth Engel und Marcel Odenthal.') and 'Screening' in leute and 'Schulung' in leute
    assert 'Dr. Ruth Engel schrieb am 22. September: „Das Screening hätte ich gern ab Januar 2027 in der Routine.“' in leute
    assert 'vermutlich' not in leute  # ein wörtlich zitierter Wunsch ist keine Vermutung über offene Punkte
    assert packen.startswith('Einpacken, aus einer Notiz: „Laptop, Handout Dysphagiekost mitnehmen') and 'Quelle' not in packen
    assert 'zugesagt' in fristen and 'morgen' in fristen and wetter == 'Wetter in Wiesbaden: 14 °C, bewölkt.'


def test_jede_zeile_ausser_dem_wetter_hat_eine_aktion_und_eine_quelle_wo_es_eine_gibt():
    lage = tb.erstellen([vorbereitung(weg=WEG)], [frist()], WETTER, jetzt=JETZT)
    for zeile in lage.zeilen:
        if zeile.art != 'wetter':
            assert zeile.aktionen, zeile.art
    arten = {z.art: [a.art for a in z.aktionen] for z in lage.zeilen}
    assert arten['termin'] == ['vorbereitung'] and arten['leute'] == ['vorbereitung', 'quelle']
    assert arten['einpacken'] == ['quelle', 'vorbereitung'] and arten['fristen'] == ['quelle']
    leute = next(z for z in lage.zeilen if z.art == 'leute')
    assert leute.aktionen[1].ref == 'e-wunsch'
    assert all(a.beschriftung for z in lage.zeilen for a in z.aktionen)


def test_eine_bitte_steht_als_vermutlich_noch_offen_da():
    v = vorbereitung()
    v.personen[0].will = [Zeile('Bitte schick mir die Druckdaten bis Freitag.', beleg('e-bitte'), 'Bitte', 'sie_bittet', True)]
    zeile = tb.erstellen([v], [], None, jetzt=JETZT).zeilen[1]
    assert 'Dr. Ruth Engel bat am 22. September: „Bitte schick mir die Druckdaten bis Freitag.“ (vermutlich noch offen)' in zeile.text
    assert zeile.vermutlich


def test_ohne_beleg_fehlen_einpacken_und_wetter_statt_erfunden_zu_werden():
    lage = tb.erstellen([vorbereitung(einpacken=False)], [], None, jetzt=JETZT)
    assert [z.art for z in lage.zeilen] == ['termin', 'leute']


def test_ohne_fahrzeit_steht_ein_ehrlicher_satz_und_der_weg_zur_einwilligung():
    weg = {'status': 'aus', 'hinweis': 'einwilligung', 'satz': 'Ort: X. Fahrzeit unbekannt.'}
    zeile = tb.erstellen([vorbereitung(weg=weg)], [], None, jetzt=JETZT).zeilen[0]
    assert 'Fahrzeit unbekannt.' in zeile.text and 'Losfahren' not in zeile.text and 'Minuten' not in zeile.text
    assert [a.art for a in zeile.aktionen] == ['vorbereitung', 'fahrzeiten']
    heimat = tb.erstellen([vorbereitung(weg={'status': 'ohne_start', 'hinweis': 'heimat'})], [], None, jetzt=JETZT).zeilen[0]
    assert [a.art for a in heimat.aktionen] == ['vorbereitung', 'heimat']


def test_ohne_ort_steht_keine_fahrzeit_und_keine_frage_danach():
    zeile = tb.erstellen([vorbereitung(ort='', weg={'status': 'ohne_ort'})], [], None, jetzt=JETZT).zeilen[0]
    assert 'Fahrzeit' not in zeile.text and [a.art for a in zeile.aktionen] == ['vorbereitung']


def test_knapp_wird_im_satz_gesagt():
    weg = {**WEG, 'knapp': 'Der Termin davor endet erst um 13:30 Uhr. Das wird knapp.'}
    assert 'Das wird knapp.' in tb.erstellen([vorbereitung(weg=weg)], [], None, jetzt=JETZT).zeilen[0].text


def test_ist_heute_nichts_mehr_dran_gilt_der_morgige_termin_und_die_zeile_sagt_morgen():
    lage = tb.erstellen([vorbereitung(stunde=7, tage=0), vorbereitung(stunde=9, tage=1, uid='t2')], [], None, jetzt=JETZT)
    assert lage.tag == 'morgen' and lage.einleitung == 'Das zählt morgen.' and lage.zeilen[0].text.startswith('Morgen um 9:00 Uhr')


def test_weitere_termine_am_selben_tag_werden_genannt_nicht_aufgelistet():
    lage = tb.erstellen([vorbereitung(stunde=10), vorbereitung(stunde=14, uid='t2'), vorbereitung(stunde=16, uid='t3')], [], None, jetzt=JETZT)
    assert 'Danach noch 2 Termine.' in lage.zeilen[0].text and lage.zeilen[0].text.startswith('Heute um 10:00 Uhr')


def test_verstrichene_zusage_steht_als_vermutung_da_und_weitere_fristen_werden_gezaehlt():
    lage = tb.erstellen([], [frist('verstrichen', -3), frist(tage=2), frist(tage=4)], None, jetzt=JETZT)
    zeile = lage.zeilen[0]
    assert zeile.art == 'fristen' and zeile.vermutlich and 'vermutlich noch offen' in zeile.text and 'warten noch 2' in zeile.text


def test_ehrlich_wenn_nichts_anliegt():
    lage = tb.erstellen([], [], None, jetzt=JETZT)
    assert lage.zeilen == [] and lage.einleitung == 'Heute liegt nichts an, das ich vorbereiten müsste.'


def test_beendete_und_ganztaegige_termine_zaehlen_nicht_als_naechster():
    vorbei = vorbereitung(stunde=6)
    ganz = vorbereitung(stunde=12, uid='g')
    ganz.termin.ganztaegig = True
    assert tb.naechster([vorbei, ganz], JETZT) == (None, 'heute')
