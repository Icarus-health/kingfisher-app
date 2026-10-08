"""Satzprüfung (D3): ein Satz besteht nur, wenn seine Belege ihn tragen; streng, aber nicht gegen jede Umformulierung."""
from datetime import datetime, timezone

import pytest

from icarus_memory.satzpruefung import Beleg, Satz, pruefen, satz_pruefen

MONTAG = datetime(2026, 9, 21, 9, 0, tzinfo=timezone.utc)


def belege(*texte, zeit=MONTAG, kopf=''):
    return {str(n): Beleg(str(n), text, zeit, kopf) for n, text in enumerate(texte, 1)}


def urteil(satz, b, ids=None, **kwargs):
    ids = ids or tuple(b)
    return satz_pruefen(Satz(satz, tuple(ids)), b, **kwargs)


def besteht(satz, b, ids=None, **kwargs):
    u = urteil(satz, b, ids, **kwargs)
    assert u.bestanden, f'{satz!r} sollte bestehen, verworfen wegen {u.gruende}'


def faellt(satz, b, teil, ids=None, **kwargs):
    u = urteil(satz, b, ids, **kwargs)
    assert not u.bestanden, f'{satz!r} sollte verworfen werden'
    assert any(teil in g for g in u.gruende), f'{teil!r} nicht in {u.gruende}'


EINLADUNG = belege(
    'Wir laden Sie herzlich zum Bio-Fachtag am Klinikum Stuttgart am 14. Oktober 2026 ein. '
    'Der Vortrag beginnt um 11.00 Uhr. Das Programm liegt bei.')


# -- Korrekte Umformulierungen bestehen ------------------------------------------


@pytest.mark.parametrize('satz', [
    'Stuttgart: Bio-Fachtag am Klinikum Stuttgart am 14.10., Vortrag 11 Uhr, Programm liegt vor.',
    'Der Bio-Fachtag findet am 14. Oktober 2026 in Stuttgart statt.',
    'Am 14.10.2026 gibt es den Bio-Fachtag am Klinikum Stuttgart.',
    'Der Vortrag beginnt um 11:00 Uhr.',
    'Das Programm liegt vor.',
    'Die Einladung zum Fachtag in Stuttgart gilt für den 14.10.',
    'Der Fachtag am Klinikum Stuttgarts beginnt mit dem Vortrag.',
])
def test_korrekte_umformulierung_besteht(satz):
    besteht(satz, EINLADUNG)


def test_umformulierung_von_bitte_und_rechnung_besteht():
    b = belege('Bitte schicken Sie uns die Druckdaten für das Plakat bis Freitag. '
               'Die Rechnung über 1.200,50 Euro ist beigefügt.')
    besteht('Die Druckdaten für das Plakat werden bis 25.09.2026 erwartet.', b)
    besteht('Die Rechnung über 1200,50 Euro liegt vor.', b)
    besteht('Frist für die Druckdaten ist Freitag, der 25. September.', b)
    besteht('Bitte die Druckdaten schicken.', b)


def test_satz_bleibt_unveraendert_und_reihenfolge_bleibt():
    saetze = [Satz('Das Programm liegt vor.', ('1',)), Satz('Der Fachtag ist am 15.10.', ('1',)),
              Satz('Der Vortrag beginnt um 11 Uhr.', ('1',))]
    ergebnis = pruefen(saetze, EINLADUNG)
    assert [u.satz for u in ergebnis] == saetze
    assert [u.bestanden for u in ergebnis] == [True, False, True]


# -- (a) Belegnummern ---------------------------------------------------------------


def test_beleg_ohne_existenz_wird_verworfen():
    faellt('Das Programm liegt vor.', EINLADUNG, 'Beleg 7 gibt es nicht', ids=('7',))
    faellt('Das Programm liegt vor.', EINLADUNG, 'Beleg 7 gibt es nicht', ids=('1', '7'))


def test_satz_ohne_belegnummer_wird_verworfen():
    u = satz_pruefen(Satz('Das Programm liegt vor.', ()), EINLADUNG)
    assert not u.bestanden and u.grund == 'Kein Beleg genannt'


def test_ungueltiger_beleg_wird_verworfen():
    b = {'1': Beleg('1', 'Das Programm liegt bei.', MONTAG, gueltig=False)}
    faellt('Das Programm liegt vor.', b, 'gilt nicht mehr')


def test_belegnummern_als_zahl_oder_text():
    b = belege('Das Programm liegt bei.')
    assert satz_pruefen(Satz('Das Programm liegt vor.', (1,)), b).bestanden  # type: ignore[arg-type]
    assert satz_pruefen(Satz('Das Programm liegt vor.', ('1',)), b).bestanden


def test_leerer_oder_zu_langer_satz_wird_verworfen():
    assert not urteil('   ', EINLADUNG).bestanden
    assert not urteil('Das Programm liegt vor. ' * 40, EINLADUNG).bestanden


# -- (b) Daten ------------------------------------------------------------------------


@pytest.mark.parametrize('form', ['12.10.', '12. Oktober', '12.10.2026', '2026-10-12', '12.10.26', '12. Oktober 2026',
                                  '12.Okt.', '12 Oktober', '12.10.2026,', 'am 12.10.'])
def test_datum_in_allen_deutschen_formen_ist_dasselbe(form):
    b = belege('Der Termin ist am 12. Oktober 2026.')
    besteht(f'Der Termin ist {form}' if not form.startswith('am') else f'Der Termin ist {form}', b)


@pytest.mark.parametrize('beleg', ['am 12.10.2026', 'am 12.10.', 'am 12. Oktober', 'am 2026-10-12', 'am 12.10.26'])
def test_datum_im_beleg_in_jeder_form(beleg):
    b = belege(f'Der Termin ist {beleg}.')
    besteht('Der Termin ist am 12. Oktober 2026.', b)
    besteht('Der Termin ist am 12.10.', b)


@pytest.mark.parametrize('satz,teil', [
    ('Der Termin ist am 13.10.', '13.10.'),
    ('Der Termin ist am 12.11.', '12.11.'),
    ('Der Termin ist am 12.10.2027.', 'Jahr 2027'),
    ('Der Termin ist am 2026-10-13.', '13.10.2026'),
    ('Der Termin ist am 13. Oktober 2026.', '13.10.2026'),
])
def test_erfundenes_oder_falsches_datum_wird_verworfen(satz, teil):
    faellt(satz, belege('Der Termin ist am 12. Oktober 2026.'), teil)


def test_datum_ohne_jahr_im_beleg_erlaubt_kein_erfundenes_jahr():
    b = belege('Der Termin ist am 12.10.', zeit=datetime(2026, 9, 1, tzinfo=timezone.utc))
    besteht('Der Termin ist am 12.10.2026.', b)  # Jahr aus dem Zeitpunkt der Quelle aufgelöst
    faellt('Der Termin ist am 12.10.2027.', b, 'Jahr 2027')
    unklar = belege('Der Termin ist am 12.10.', zeit=datetime(2026, 12, 1, tzinfo=timezone.utc))
    faellt('Der Termin ist am 12.10.2026.', unklar, 'Jahr 2026')  # uneindeutig: kein Jahr ergänzen
    besteht('Der Termin ist am 12.10.', unklar)


def test_datumsbereich_und_zusammengezogene_daten():
    b = belege('Die Tagung ist vom 12.-14. Oktober 2026 im Klinikum Stuttgart.')
    besteht('Die Tagung ist am 12.10. und am 14.10.2026 im Klinikum Stuttgart.', b)
    faellt('Die Tagung ist am 13.10. im Klinikum Stuttgart.', b, '13.10.')


def test_relative_angabe_der_quelle_wird_mit_dem_zeitpunkt_der_quelle_aufgeloest():
    b = belege('Bitte schicken Sie uns die Unterlagen bis Freitag.', zeit=MONTAG)  # Montag, 21.09.2026
    besteht('Die Unterlagen werden bis 25.09.2026 erwartet.', b)
    faellt('Die Unterlagen werden bis 02.10.2026 erwartet.', b, '02.10.2026')
    spaeter = belege('Bitte schicken Sie uns die Unterlagen bis Freitag.', zeit=datetime(2026, 3, 2, tzinfo=timezone.utc))
    besteht('Die Unterlagen werden bis 06.03.2026 erwartet.', spaeter)
    faellt('Die Unterlagen werden bis 25.09.2026 erwartet.', spaeter, '25.09.2026')
    wochen = belege('Wir melden uns in zwei Wochen.', zeit=MONTAG)
    besteht('Rückmeldung am 05.10.2026.', wochen)


def test_wochentag_muss_belegt_oder_zum_datum_passend_sein():
    b = belege('Der Termin ist am 16. Oktober 2026.')
    besteht('Der Termin ist Freitag, der 16.10.', b)  # 16.10.2026 ist ein Freitag
    faellt('Der Termin ist Donnerstag, der 16.10.', b, 'Donnerstag')
    faellt('Der Termin ist am Montag.', b, 'Montag')
    besteht('Der Termin ist am Montag.', belege('Der Termin ist am Montag.'))


def test_monat_und_monatsphrase_muessen_belegt_sein():
    b = belege('Die Abgabe ist Ende Oktober.')
    besteht('Die Abgabe ist Ende Oktober.', b)
    faellt('Die Abgabe ist Mitte Oktober.', b, 'Mitte Oktober')
    faellt('Die Abgabe ist im November.', b, 'November')


def test_relative_zeitangaben_ohne_bezug_werden_verworfen():
    b = belege('Der Fachtag ist am 14. Oktober 2026.')
    faellt('Der Fachtag ist morgen.', b, 'Relative Zeitangabe')
    faellt('Der Fachtag ist nächste Woche.', b, 'Relative Zeitangabe')
    faellt('Der Fachtag ist in zwei Wochen.', b, 'Relative Zeitangabe')
    besteht('Der Fachtag ist morgen.', b, relative_zeit_erlaubt=True)


# -- Uhrzeiten --------------------------------------------------------------------------


@pytest.mark.parametrize('beleg', ['11 Uhr', '11:00 Uhr', '11.00 Uhr', '11:00', '11 Uhr 00'])
@pytest.mark.parametrize('satz', ['um 11 Uhr', 'um 11:00 Uhr', 'um 11.00 Uhr'])
def test_uhrzeit_in_allen_formen(beleg, satz):
    besteht(f'Der Vortrag ist {satz}.', belege(f'Vortrag um {beleg}.'))


def test_erfundene_uhrzeit_und_zeitbereich():
    b = belege('Der Vortrag ist von 11 bis 12 Uhr.')
    besteht('Der Vortrag dauert von 11 bis 12 Uhr.', b)
    faellt('Der Vortrag ist um 13 Uhr.', b, '13:00')
    faellt('Der Vortrag ist um 11:30 Uhr.', b, '11:30')


def test_zeitbedingung_erst_nach_darf_nicht_zu_ab_abgeschwaecht_werden():
    b = belege('Für den Keramiktest bitte erst nach 10 Uhr anrufen; morgens bin ich in der Werkstatt.')

    u = urteil('Für den Keramiktest kann man ab 10.00 Uhr anrufen.', b)

    assert not u.bestanden


@pytest.mark.parametrize('quelle', [
    'Rufbereitschaft nur zwischen 10–12 Uhr.',
    'Rufbereitschaft von 10 bis 12 Uhr.',
    'Rufbereitschaft zwischen 10 und 12 Uhr.',
    'Rufbereitschaft zwischen 10.00 und 12.00 Uhr.',
    'Rufbereitschaft von 10.00–12.00 Uhr.',
    'Rufbereitschaft von 10 Uhr bis 12 Uhr.',
    'Rufbereitschaft von 10:00 bis 12:00.',
])
def test_zeitbereich_ist_keine_zwei_genauen_uhrzeiten(quelle):
    faellt('Die Rufbereitschaft ist um 10 Uhr und 12 Uhr.', belege(quelle), 'Zeitbedingung')
    faellt('Die Rufbereitschaft ist um 12 Uhr.', belege(quelle), 'Zeitbedingung')


@pytest.mark.parametrize(('quelle', 'satz'), [
    ('Rufbereitschaft nur zwischen 10–12 Uhr.', 'Rufbereitschaft nur zwischen 10 bis 12 Uhr.'),
    ('Rufbereitschaft zwischen 10 und 12 Uhr.', 'Rufbereitschaft von 10 bis 12 Uhr.'),
    ('Rufbereitschaft von 10 bis 12 Uhr.', 'Rufbereitschaft von 10:00 bis 12:00 Uhr.'),
    ('Rufbereitschaft zwischen 10.15 und 12.30 Uhr.', 'Rufbereitschaft von 10:15 bis 12:30 Uhr.'),
    ('Rufbereitschaft von 10.00–12.00 Uhr.', 'Rufbereitschaft von 10:00 bis 12:00.'),
    ('Rufbereitschaft von 10 Uhr bis 12 Uhr.', 'Rufbereitschaft von 10:00 bis 12:00 Uhr.'),
])
def test_gleicher_zeitbereich_bleibt_erhalten(quelle, satz):
    besteht(satz, belege(quelle))


def test_verneinter_zeitbereich_ist_kein_bestaetigter_zeitbereich():
    faellt('Rufbereitschaft von 10 bis 12 Uhr.',
           belege('Rufbereitschaft nicht von 10 bis 12 Uhr.'), 'Zeitbedingung')


def test_zeitbereiche_duerfen_nicht_neu_gepaart_werden():
    faellt('Rufbereitschaft von 10 bis 14 Uhr.',
           belege('Rufbereitschaft von 10 bis 12 Uhr und von 13 bis 14 Uhr.'), 'Zeitbedingung')


@pytest.mark.parametrize(('quelle', 'satz'), [
    ('Bitte nur nach 10 Uhr anrufen.', 'Bitte erst nach 10.00 Uhr anrufen.'),
    ('Das Fenster frühestens ab 14 Uhr öffnen.', 'Das Fenster ab 14.00 Uhr öffnen.'),
    ('Der Laden ist spätestens bis 17 Uhr erreichbar.', 'Der Laden ist bis 17.00 Uhr erreichbar.'),
    ('Der Laden ist bis 17 Uhr erreichbar.', 'Der Laden ist bis 17.00 Uhr erreichbar.'),
])
def test_gleichwertige_zeitbedingungen_und_formatierung_bestehen(quelle, satz):
    besteht(satz, belege(quelle))


@pytest.mark.parametrize(('quelle', 'satz'), [
    ('Das Fenster frühestens ab 14 Uhr öffnen.', 'Das Fenster vor 14 Uhr öffnen.'),
    ('Der Laden ist bis 17 Uhr erreichbar.', 'Der Laden ist um 17 Uhr erreichbar.'),
    ('Der Anruf ist um 10 Uhr möglich.', 'Der Anruf ist ab 10 Uhr möglich.'),
])
def test_geaenderte_zeitgrenze_wird_verworfen(quelle, satz):
    u = urteil(satz, belege(quelle))

    assert not u.bestanden


def test_quellenkopf_fuegt_keine_zeitbedingung_zum_inhalt_hinzu():
    b = {'1': Beleg('1', 'Der Anruf ist um 10 Uhr möglich.', MONTAG, 'Quelle: erst nach 11 Uhr')}

    u = urteil('Der Anruf ist erst nach 11 Uhr möglich.', b)

    assert not u.bestanden
    assert any('Zeitbedingung' in grund for grund in u.gruende)


def test_nicht_vor_und_vor_haben_verschiedene_uhrzeitbedingungen():
    b = belege('Der Raum darf nicht vor 14 Uhr betreten werden.')

    u = urteil('Der Raum darf vor 14 Uhr betreten werden.', b)

    assert not u.bestanden
    assert any('Zeitbedingung' in grund for grund in u.gruende)


def test_gleiche_uhrzeit_in_mehreren_ereignissen_wird_vorsichtshalber_verworfen():
    b = belege('Der Keramiktest ist um 10 Uhr. Der Rückruf ist erst nach 10 Uhr möglich.')

    u = urteil('Der Keramiktest ist um 10 Uhr.', b)

    assert not u.bestanden
    assert any('Zeitbedingung' in grund for grund in u.gruende)


# -- Zahlen und Beträge -----------------------------------------------------------------


def test_zahlen_werden_normalisiert():
    b = belege('Der Betrag ist 1.234,50 Euro, die Teilnahme kostet 200 € bei 3 Personen und zwei Tagen.')
    besteht('Der Betrag ist 1234,50 Euro.', b)
    besteht('Die Teilnahme kostet 200 Euro.', b)
    besteht('Es kommen drei Personen.', b)
    besteht('Es sind 2 Tage.', b)


@pytest.mark.parametrize('satz,teil', [
    ('Der Betrag ist 1.234,60 Euro.', '1234.6'),
    ('Die Teilnahme kostet 250 Euro.', '250'),
    ('Es kommen 4 Personen.', 'Zahl 4'),
    ('Es kommen fünf Personen.', 'Zahl 5'),
    ('Die Kosten sind 3.000 Euro.', '3000'),
])
def test_erfundene_zahl_wird_verworfen(satz, teil):
    faellt(satz, belege('Der Betrag ist 1.234,50 Euro, die Teilnahme kostet 200 € bei 3 Personen.'), teil)


def test_betrag_braucht_dieselbe_waehrung_und_summen_sind_erfunden():
    b = belege('Die Rechnung kostet 200 Euro. Dazu kommen 50 Euro Versand.')
    faellt('Die Rechnung kostet 200 Dollar.', b, 'usd')
    faellt('Die Rechnung kostet zusammen 250 Euro.', b, '250')
    besteht('Die Rechnung kostet 200 Euro plus 50 Euro Versand.', b)


def test_jahreszahl_allein_muss_im_beleg_stehen():
    besteht('Das war im Jahr 2026.', belege('Die Veranstaltung war 2026 sehr gut.'))
    faellt('Das war im Jahr 2025.', belege('Die Veranstaltung war 2026 sehr gut.'), '2025')


# -- Adressen, Links, Kennungen -----------------------------------------------------------


def test_mailadresse_link_und_kennung_muessen_stehen():
    b = belege('Schreiben Sie an foerderung@stiftung.example, Aktenzeichen AZ-2026/17, Infos: https://stiftung.example/programm.')
    besteht('Schreiben Sie an FOERDERUNG@stiftung.example.', b)
    besteht('Das Aktenzeichen ist AZ-2026/17.', b)
    besteht('Infos unter https://stiftung.example/programm.', b)
    faellt('Schreiben Sie an anna@stiftung.example.', b, 'anna@stiftung.example')
    faellt('Das Aktenzeichen ist AZ-2026/18.', b, 'az-2026/18')
    faellt('Infos unter https://stiftung.example/anderes.', b, 'https://stiftung.example/anderes')


# -- Eigennamen und Orte -------------------------------------------------------------------


def test_erfundener_name_oder_ort_wird_verworfen():
    faellt('Der Bio-Fachtag ist am Klinikum Hamburg.', EINLADUNG, 'Hamburg')
    faellt('Frau Kranz hat eingeladen.', EINLADUNG, 'Kranz')
    faellt('Kranz schickt das Programm.', EINLADUNG, 'Kranz')  # auch am Satzanfang


def test_namensfolge_muss_zusammen_im_beleg_stehen():
    b = belege('Das Klinikum Nord liegt in Stuttgart. Die Firma Winter Catering GmbH liefert.')
    besteht('Das Klinikum Nord in Stuttgart.', b)
    faellt('Das Klinikum Stuttgart lädt ein.', b, 'Klinikum Stuttgart')  # Nord liegt in Stuttgart, ist aber ein anderer Name
    besteht('Winter Catering GmbH liefert.', b)
    faellt('Catering Winter liefert.', b, 'Namensfolge')


def test_beugung_und_umlautschreibung_sind_kein_fehler():
    b = belege('Herr Müller vom Klinikum Freiburg bestätigt die Anmeldung.')
    besteht('Mueller vom Klinikum Freiburg hat die Anmeldung bestätigt.', b)
    besteht('Die Anmeldung von Herrn Müller.', b)
    besteht('Klinikums Freiburg bestätigt.', b)
    faellt('Herr Müllner bestätigt.', b, 'Müllner')


def test_sachname_darf_im_satz_stehen_auch_wenn_er_nicht_im_beleg_steht():
    b = belege('Die Druckdaten sind da.')
    faellt('Stuttgart: Die Druckdaten sind da.', b, 'Stuttgart')
    besteht('Stuttgart: Die Druckdaten sind da.', b, zusatz_woerter=['Stuttgart'])
    faellt('Hamburg: Die Druckdaten sind da.', b, 'Hamburg', zusatz_woerter=['Stuttgart'])


def test_titel_der_quelle_gehoert_zum_beleg():
    b = belege('Das Programm liegt bei.', kopf='Einladung Bio-Fachtag Stuttgart, Quelle vom 21.09.2026')
    besteht('Das Programm zum Bio-Fachtag in Stuttgart liegt vor (Quelle vom 21.09.2026).', b)


# -- Status -----------------------------------------------------------------------------------


def test_statusaussage_braucht_dieselbe_wortgruppe_im_beleg():
    b = belege('Bitte überweisen Sie den Betrag bis Freitag. Die Unterlagen sind unterschrieben.')
    faellt('Die Rechnung ist bezahlt.', b, 'bezahlt')
    faellt('Die Rechnung ist erledigt.', b, 'erledigt')
    besteht('Die Unterlagen sind unterzeichnet.', b)
    besteht('Der Betrag wird bis Freitag erwartet.', b)
    # Bewusst streng: „überwiesen“ ist eine Erledigt-Aussage, auch wo der Beleg nur „überweisen Sie“ bittet.
    faellt('Der Betrag soll überwiesen werden.', b, 'bezahlt')


# -- (c) Verneinung -----------------------------------------------------------------------------


@pytest.mark.parametrize('beleg,satz', [
    ('Der Workshop am 28. Oktober wurde abgesagt.', 'Der Workshop am 28.10. findet statt.'),
    ('Der Workshop am 28. Oktober findet nicht statt.', 'Der Workshop am 28.10. findet statt.'),
    ('Der Workshop entfällt.', 'Der Workshop ist geplant.'),
    ('Wir haben keine Einwände gegen den Vertrag.', 'Wir haben Einwände gegen den Vertrag.'),
    ('Die Zahlung ist noch nicht erfolgt.', 'Die Zahlung ist erfolgt.'),
])
def test_verneinungsumkehr_des_belegs_wird_verworfen(beleg, satz):
    faellt(satz, belege(beleg), 'verneint')


@pytest.mark.parametrize('beleg,satz', [
    ('Der Workshop am 28. Oktober findet statt.', 'Der Workshop am 28.10. findet nicht statt.'),
    ('Die Zahlung ist erfolgt.', 'Die Zahlung ist nicht erfolgt.'),
    ('Wir haben Einwände gegen den Vertrag.', 'Wir haben keine Einwände gegen den Vertrag.'),
])
def test_verneinung_die_der_beleg_nicht_traegt_wird_verworfen(beleg, satz):
    faellt(satz, belege(beleg), 'Der Satz verneint')


@pytest.mark.parametrize('beleg,satz', [
    ('Der Workshop am 28. Oktober wurde abgesagt.', 'Der Workshop am 28.10. ist abgesagt.'),
    ('Der Workshop am 28. Oktober wurde abgesagt.', 'Der Workshop am 28.10. entfällt.'),
    ('Der Workshop am 28. Oktober findet nicht statt.', 'Der Workshop am 28.10. wurde abgesagt.'),
    ('Wir haben keine Einwände.', 'Es gibt keine Einwände.'),
])
def test_korrekt_uebernommene_verneinung_besteht(beleg, satz):
    besteht(satz, belege(beleg))


def test_verneinung_in_anderem_satzteil_ist_kein_widerspruch():
    b = belege('Herr Keller kommt nicht, die Einreichfrist ist der 12. November 2026.')
    besteht('Die Einreichfrist ist der 12.11.2026.', b)
    faellt('Herr Keller kommt.', b, 'verneint')


def test_mehrere_belege_tragen_gemeinsam():
    b = belege('Der Fachtag ist am 14. Oktober 2026.', 'Der Vortrag ist um 11 Uhr im Klinikum Stuttgart.')
    besteht('Am 14.10. ist der Vortrag um 11 Uhr im Klinikum Stuttgart.', b)
    faellt('Am 14.10. ist der Vortrag um 11 Uhr.', b, 'Uhrzeit', ids=('1',))
    faellt('Am 14.10. ist der Vortrag um 11 Uhr im Klinikum Stuttgart.', b, 'Klinikum', ids=('1',))
