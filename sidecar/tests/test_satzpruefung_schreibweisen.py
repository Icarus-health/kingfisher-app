"""Satzprüfung, Befund A1 der Persona-Prüfung: gleichwertige Schreibweisen bestehen, falsche Angaben nicht.

Helga Brandt fragte „Wann ist die nächste Vorstandssitzung?“. Der Satz „… um 18 Uhr im Vereinsheim“ fiel gegen den
Termin „18:00 bis 20:00 Uhr“, „Ja, Herr Meier hat die Rechnung … geschickt“ fiel am „Ja“. Beide Richtungen sind hier
geprüft: Was dasselbe sagt, besteht; eine andere Uhrzeit, ein anderes Datum, eine andere Zahl fällt weiter.
"""
from datetime import datetime, timezone

import pytest

from icarus_memory.satzpruefung import Beleg, Satz, satz_pruefen

QUELLENZEIT = datetime(2026, 10, 23, 19, 48, tzinfo=timezone.utc)

TERMIN = ('Termin: Vorstandssitzung Gartenverein\n'
          'Wann: Donnerstag, 29. Oktober 2026 (29.10.2026), 18:00 bis 20:00 Uhr\n'
          'Ort: Vereinsheim Sonnenhang')
EINLADUNG = ('Liebe Helga,\n\nhiermit lade ich dich herzlich zur nächsten Vorstandssitzung ein: am Donnerstag, '
             '29. Oktober, um 18 Uhr im Vereinsheim.\n\nBitte bring den Kassenbericht für das dritte Quartal mit.\n\n'
             'Herzliche Grüße\nErika (Schriftführerin)')
RECHNUNG = ('Sehr geehrte Frau Brandt,\n\nanbei erhalten Sie unsere Rechnung Nr. 2026-117 über 340,00 Euro für den '
            'Heckenschnitt am Vereinsheim. Bitte überweisen Sie den Betrag bis zum 6. November.\n\n'
            'Mit freundlichen Grüßen\nKlaus Meier\nGartenbau Meier')
BEITRAG = ('Liebe Frau Brandt,\n\nich habe den Mitgliedsbeitrag für 2026 noch nicht überwiesen. Kann ich ihn bei der '
           'nächsten Sitzung bar bei Ihnen bezahlen?\n\nViele Grüße\nWerner Koch, Parzelle 14')


def belege(**texte):
    return {nummer: Beleg(nummer, text, QUELLENZEIT) for nummer, text in texte.items()}


def urteil(satz, b, *ids):
    return satz_pruefen(Satz(satz, ids or tuple(b)), b)


def besteht(satz, b, *ids):
    u = urteil(satz, b, *ids)
    assert u.bestanden, f'{satz!r} sollte bestehen, verworfen wegen {u.gruende}'


def faellt(satz, b, teil, *ids):
    u = urteil(satz, b, *ids)
    assert not u.bestanden, f'{satz!r} sollte verworfen werden'
    assert any(teil in g for g in u.gruende), f'{teil!r} nicht in {u.gruende}'


# -- Uhrzeiten -----------------------------------------------------------------------------------------


@pytest.mark.parametrize('zeit', ['um 18 Uhr', 'um 18:00 Uhr', 'um 18.00 Uhr', 'um 18h', 'um 18:00', 'um 18.00',
                                  'um sechs Uhr abends', 'um 6 Uhr abends'])
def test_beginn_eines_termins_in_jeder_schreibweise(zeit):
    """Der Satz der Rentnerin: „um 18 Uhr“ nennt den Beginn des Termins „18:00 bis 20:00 Uhr“."""
    besteht(f'Die nächste Vorstandssitzung ist am Donnerstag, 29. Oktober 2026, {zeit} im Vereinsheim Sonnenhang.',
            belege(t=TERMIN))


def test_um_18_uhr_gegen_mail_und_termin_zugleich():
    """Mail sagt „um 18 Uhr“, Termin „18:00 bis 20:00“: Beide nennen denselben Beginn."""
    besteht('Die nächste Vorstandssitzung ist am Donnerstag, 29. Oktober 2026, um 18 Uhr im Vereinsheim.',
            belege(t=TERMIN, m=EINLADUNG))


@pytest.mark.parametrize('zeit', ['um 19 Uhr', 'um 19:00 Uhr', 'um 18:30 Uhr', 'um 17h', 'um sieben Uhr abends',
                                  'um 20 Uhr', 'ab 18 Uhr', 'um 6 Uhr morgens', 'um halb sieben'])
def test_falsche_uhrzeit_oder_grenze_faellt_weiter(zeit):
    """Die Gegenrichtung: Eine andere Uhrzeit, das Ende statt des Beginns oder ein offenes „ab“ besteht nicht."""
    u = urteil(f'Die Vorstandssitzung ist am 29. Oktober 2026 {zeit}.', belege(t=TERMIN))
    assert not u.bestanden, f'{zeit!r} hätte verworfen werden müssen'


def test_beginn_gilt_nicht_fuer_einen_eingeschraenkten_zeitraum():
    u = urteil('Die Rufbereitschaft ist um 10 Uhr.', belege(q='Rufbereitschaft nur zwischen 10 und 12 Uhr.'))
    assert not u.bestanden and any('Zeitbedingung' in g for g in u.gruende)


def test_beginn_gilt_nicht_neben_einer_anderen_grenze_zur_selben_uhrzeit():
    u = urteil('Die Sitzung ist um 18 Uhr.', belege(t=TERMIN, r='Anrufe bitte erst nach 18 Uhr.'))
    assert not u.bestanden


@pytest.mark.parametrize(('quelle', 'satz'), [
    ('Wir treffen uns um halb sieben abends am Tor.', 'Wir treffen uns um 18:30 Uhr am Tor.'),
    ('Wir treffen uns um 18:30 Uhr am Tor.', 'Wir treffen uns um halb sieben am Tor.'),
    ('Wir treffen uns um halb sieben am Tor.', 'Wir treffen uns um halb sieben am Tor.'),
    ('Wir treffen uns um 7 Uhr am Tor.', 'Wir treffen uns um sieben Uhr am Tor.'),
    ('Abfahrt um halb acht morgens am Tor.', 'Die Abfahrt ist um 7:30 Uhr am Tor.'),
])
def test_uhrzeit_in_worten_wo_eindeutig(quelle, satz):
    besteht(satz, belege(q=quelle))


@pytest.mark.parametrize(('quelle', 'satz', 'teil'), [
    # „halb sieben“ ohne Tageszeit ist 6:30 oder 18:30: Der Beleg macht es nicht eindeutig.
    ('Wir treffen uns um halb sieben am Tor.', 'Wir treffen uns um 18:30 Uhr am Tor.', '18:30'),
    ('Wir treffen uns um halb sieben am Tor.', 'Wir treffen uns um 6:30 Uhr am Tor.', '6:30'),
    ('Wir treffen uns um 18:30 Uhr und um 6:30 Uhr am Tor.', 'Wir treffen uns um halb sieben am Tor.', 'halb sieben'),
    ('Wir treffen uns um 19:30 Uhr am Tor.', 'Wir treffen uns um halb sieben am Tor.', 'halb sieben'),
    ('Wir treffen uns um halb sieben abends am Tor.', 'Wir treffen uns um 6:30 Uhr am Tor.', '6:30'),
])
def test_uhrzeit_in_worten_nicht_geraten(quelle, satz, teil):
    faellt(satz, belege(q=quelle), teil)


# -- Daten, Wochentage, Zahlen ---------------------------------------------------------------------------


@pytest.mark.parametrize('datum', ['3. November', '03.11.', '3.11.', '3.11.2026', '03.11.2026', '3. Nov.',
                                   'Dienstag, 3. November 2026', '2026-11-03'])
def test_datum_in_jeder_schreibweise(datum):
    besteht(f'Die Kassenprüfung ist am {datum}.', belege(q='Kassenprüfung am Dienstag, 3. November 2026, um 11 Uhr.'))


@pytest.mark.parametrize('datum', ['4. November', '03.12.', '3.11.2025', 'Mittwoch, 3. November 2026'])
def test_falsches_datum_oder_wochentag_faellt(datum):
    u = urteil(f'Die Kassenprüfung ist am {datum}.', belege(q='Kassenprüfung am Dienstag, 3. November 2026.'))
    assert not u.bestanden


@pytest.mark.parametrize(('quelle', 'satz'), [
    ('Es kommen 3 Gäste und 12 Helfer.', 'Es kommen drei Gäste und zwölf Helfer.'),
    ('Es kommen drei Gäste und zwölf Helfer.', 'Es kommen 3 Gäste und 12 Helfer.'),
    ('Wir brauchen elf Stühle.', 'Wir brauchen 11 Stühle.'),
])
def test_zahlen_in_worten_bis_zwoelf(quelle, satz):
    besteht(satz, belege(q=quelle))


def test_falsche_zahl_in_worten_faellt():
    faellt('Wir brauchen zehn Stühle.', belege(q='Wir brauchen elf Stühle.'), 'Zahl 10')


# -- Antwortpartikel am Satzanfang -------------------------------------------------------------------------


@pytest.mark.parametrize('partikel', ['Ja', 'Genau', 'Richtig', 'Stimmt', 'Ja,'])
def test_antwortpartikel_ist_keine_behauptung(partikel):
    trenner = ' ' if partikel.endswith(',') else ', '
    besteht(f'{partikel}{trenner}die nächste Vorstandssitzung ist am 29. Oktober 2026.', belege(m=EINLADUNG))


def test_ja_der_rentnerin_mit_rechnung():
    """Der Kopf des Belegs nennt den Absender wie in `satzantwort` („…; von Klaus Meier; 22.10.2026“)."""
    kopf = 'Rechnung Heckenschnitt Nr. 2026-117; von Klaus Meier; 22.10.2026'
    b = {'r': Beleg('r', RECHNUNG, QUELLENZEIT, kopf)}
    besteht('Ja, Herr Meier hat die Rechnung Nr. 2026-117 über 340,00 Euro für den Heckenschnitt geschickt.', b)
    besteht('Klaus Meier hat die Rechnung Nr. 2026-117 geschickt.', b)
    # Wer die Mail nicht geschickt hat, hat die Rechnung damit nicht geschickt.
    faellt('Erika Schulte hat die Rechnung Nr. 2026-117 geschickt.', b, 'Erika Schulte')
    # „anbei“ ist kein Beleg für eine Zahlung.
    faellt('Ja, Herr Meier hat die Rechnung Nr. 2026-117 bezahlt.', b, 'bezahlt')


def test_ohne_anhang_ist_geschickt_nicht_belegt():
    b = {'r': Beleg('r', 'Die Rechnung Nr. 2026-117 kommt nächste Woche.', QUELLENZEIT, 'Rechnung; von Klaus Meier')}
    faellt('Herr Meier hat die Rechnung Nr. 2026-117 geschickt.', b, 'geliefert')


def test_ja_rettet_keinen_falschen_inhalt():
    faellt('Ja, die Vorstandssitzung ist am 30. Oktober 2026.', belege(m=EINLADUNG), '30.10')
    faellt('Ja, die Vorstandssitzung ist um 19 Uhr.', belege(m=EINLADUNG), '19:00')


def test_nein_mit_belegter_verneinung_besteht():
    b = {'k': Beleg('k', BEITRAG, QUELLENZEIT, 'Mitgliedsbeitrag 2026; von Werner Koch; 25.10.2026')}
    besteht('Nein, Herr Koch hat den Mitgliedsbeitrag für 2026 noch nicht überwiesen.', b)


def test_nein_dreht_einen_belegten_satz_nicht_um():
    """„Nein, die Sitzung ist am 29. Oktober“ hieße als Antwort auf „Ist sie am 29.?“ das Gegenteil des Belegs."""
    faellt('Nein, die Vorstandssitzung ist am 29. Oktober 2026.', belege(m=EINLADUNG), 'Nein')


def test_nein_ohne_verneinung_im_beleg_faellt():
    faellt('Nein, die Vorstandssitzung findet nicht am 29. Oktober 2026 statt.', belege(m=EINLADUNG), 'verneint')


@pytest.mark.parametrize('satz', ['Ja.', 'Nein.', 'Genau!'])
def test_partikel_allein_ist_nicht_pruefbar(satz):
    faellt(satz, belege(m=EINLADUNG), 'allein')


def test_ja_mitten_im_satz_bleibt_ein_wort():
    """Nur am Anfang ist „Ja“ ein Antwortpartikel; ein großgeschriebenes „Ja“ als Name prüft die Namensregel."""
    faellt('Die Sitzung leitet Ja Ming am 29. Oktober 2026.', belege(m=EINLADUNG), 'Ja Ming')


def test_absender_spricht_nur_in_eigener_sache():
    """Der Absender im Kopf trägt einen Namen nur für die erste Person, nie für einen Dritten oder Weitergeleitetes."""
    kopf = 'Beitrag; von Werner Koch; 25.10.2026'
    dritter = {'k': Beleg('k', 'Herr Schulz hat den Mitgliedsbeitrag noch nicht überwiesen.', QUELLENZEIT, kopf)}
    faellt('Herr Koch hat den Mitgliedsbeitrag noch nicht überwiesen.', dritter, 'Status')
    weiter = {'k': Beleg('k', '---------- Weitergeleitete Nachricht ----------\nIch habe den Mitgliedsbeitrag noch '
                              'nicht überwiesen.', QUELLENZEIT, kopf)}
    faellt('Herr Koch hat den Mitgliedsbeitrag noch nicht überwiesen.', weiter, 'Status')
    zitat = {'k': Beleg('k', 'Gern.\n\n> Ich habe den Mitgliedsbeitrag noch nicht überwiesen.', QUELLENZEIT, kopf)}
    faellt('Herr Koch hat den Mitgliedsbeitrag noch nicht überwiesen.', zitat, 'Status')
