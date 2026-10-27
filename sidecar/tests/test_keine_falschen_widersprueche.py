"""Persona-Prüfung (Assistentin): Kingfisher meldete Widersprüche zwischen Akten, die keine sind.

„Frist „Informationen“: Die Akte von Jürgen Möller nennt noch den 10.07., die Akte von Stadtwerke Taunusstein kennt
schon den 16.10.“ Zwei verschiedene Mails, zwei verschiedene Dinge („Freigabe Budget“ und „Newsletter Oktober“), je
„Ich schicke Ihnen die Unterlagen bis Freitag.“ Ursachen in `akten._fristen`:

1. Der Satz um eine Frist endete nicht nach einem schließenden Anführungszeichen („…zu „Newsletter Oktober“. Ich
   schicke …“); so zählte der Vorsatz („anbei wie besprochen die Informationen zu …“) zum Gegenstand der Frist.
2. Ein allgemeines Wort („Unterlagen“, „Informationen“) machte zwei Fristen verschiedener Mails zu demselben
   Gegenstand.

Zusicherungen, in beide Richtungen:
* Verschiedene Mails, gleiche Floskel, verschiedene Dinge: keine Frist ersetzt die andere, kein Befund im Lint.
* Im selben Mailverlauf ersetzt eine neue Frist für „die Unterlagen“ die alte weiter.
* Ein bestimmter Gegenstand („Belegungsplan“, „Einreichfrist“) ersetzt über verschiedene Mails hinweg weiter, und
  der Lint meldet ihn weiter als Widerspruch zwischen Akten.
"""
from datetime import timedelta

from icarus_memory import EpisodeKind, Provenance, SourceType
from icarus_memory.akten import _umfeld
from icarus_memory.lint import Pruefer
from tests.test_akten import SACHE, akten, einordnen, mail, neu_rechnen  # noqa: F401
from tests.test_bezuege import ICH, JETZT, welt  # noqa: F401

LEA = f'Lea Hartmann <{ICH}>'


def verlaufsmail(episodes, titel, abschnitte, tage, *, von, an, kennung, antwort_auf=None):
    text = ' '.join(t for t, _ in abschnitte)
    tags = [f'mail:message:{kennung}'] + ([f'mail:reply:{antwort_auf}'] if antwort_auf else [])
    e, _ = episodes.record(EpisodeKind.MESSAGE, titel, text, Provenance(SourceType.EMAIL, source_ref=f't:{kennung}'),
                           participants=[von, an], occurred_at=JETZT - timedelta(days=tage), tags=tags)
    einordnen(episodes, e, abschnitte)
    return e


def test_satz_endet_auch_nach_einem_schliessenden_anfuehrungszeichen():
    text = 'anbei wie besprochen die Informationen zu „Newsletter Oktober“. Ich schicke Ihnen die Unterlagen bis Freitag.'
    start = text.index('bis Freitag')
    assert _umfeld(text, start, start + 11) == 'Ich schicke Ihnen die Unterlagen bis Freitag.'
    # Ein Datum mit Punkt ist kein Satzende.
    text = 'Bitte bis 15. Januar 2027 den Plan schicken.'
    assert _umfeld(text, 5, 24) == text


def test_gleiche_floskel_in_verschiedenen_mails_ersetzt_keine_frist(welt, akten):
    episodes, _, _ = welt
    alt = 'anbei wie besprochen die Informationen zu „Freigabe Budget 962“. Ich schicke Ihnen die Unterlagen bis Freitag.'
    neu = 'anbei wie besprochen die Informationen zu „Newsletter Oktober“. Ich schicke Ihnen die Unterlagen bis Freitag.'
    mail(episodes, 'Freigabe Budget 962', [(alt, 'commitment')], tage=80)
    mail(episodes, 'Newsletter Oktober', [(neu, 'commitment')], tage=10)
    fristen = neu_rechnen(akten).akte(SACHE, jetzt=JETZT, alle=True)['fristen']
    assert fristen['ersetzt'] == [] and fristen['gesamt']['ersetzt'] == 0


def test_verschiedene_bitten_mit_frist_ersetzen_sich_nicht(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Termin nächste Woche', [('anbei wie besprochen die Informationen zu „Termin nächste Woche“. '
                                            'Bitte bestätigen Sie den Termin bis Donnerstag.', 'request')], tage=60)
    mail(episodes, 'Zwischenstand Projekt', [('anbei wie besprochen die Informationen zu „Zwischenstand Projekt“. '
                                              'Ich schicke Ihnen die Unterlagen bis Freitag.', 'commitment')], tage=8)
    assert neu_rechnen(akten).akte(SACHE, jetzt=JETZT, alle=True)['fristen']['ersetzt'] == []


def test_im_selben_verlauf_ersetzt_die_neue_frist_fuer_die_unterlagen_weiter(welt, akten):
    episodes, _, _ = welt
    stiftung = 'Förderteam <foerderung@stiftung.example>'
    verlaufsmail(episodes, 'Antrag', [('Ich schicke Ihnen die Unterlagen bis 2. Oktober 2026.', 'commitment')], 20,
                 von=stiftung, an=LEA, kennung='u1')
    verlaufsmail(episodes, 'AW: Antrag', [('Es wird leider später: Ich schicke Ihnen die Unterlagen bis 9. Oktober 2026.', 'change')], 5,
                 von=stiftung, an=LEA, kennung='u2', antwort_auf='u1')
    fristen = neu_rechnen(akten).akte(SACHE, jetzt=JETZT, alle=True)['fristen']
    assert [f['datum'] for f in fristen['ersetzt']] == ['2026-10-02']
    assert fristen['ersetzt'][0]['ersetzt_durch']['datum'] == '2026-10-09'


def test_bestimmter_gegenstand_ersetzt_ueber_mails_hinweg_und_bleibt_ein_widerspruch(welt, akten):
    episodes, _, bezuege = welt
    haus = 'Volker Busch <v.busch@tagungshaus-rhein.example>'
    reihe = 'Ina Reihe <ina@fortbildung.example>'
    mail(episodes, 'Belegung', [('Bitte schicken Sie mir den Belegungsplan bis zum 15. Januar 2027, damit wir die Räume '
                                 'einteilen können.', 'request')], tage=110, absender=haus, weitere=(reihe,))
    mail(episodes, 'Verlängerung', [('Der Belegungsplan verschiebt sich deshalb auf den 29. Januar 2027; Herr Busch '
                                     'bekommt ihn dann direkt von uns.', 'change')], tage=50, absender=reihe)
    neu_rechnen(akten)
    reihe_akte = akten.akte('person:a:ina@fortbildung.example', jetzt=JETZT, alle=True)['fristen']
    assert [f['datum'] for f in reihe_akte['kommend']] == ['2027-01-29']
    # Die Akte des Tagungshauses kennt die Verschiebung nicht: Das ist ein echter Widerspruch zwischen Akten.
    befunde = Pruefer(episodes, bezuege, akten, jetzt=JETZT).pruefen().befunde
    assert [b.text for b in befunde if b.art == 'widerspruch'] == [
        'Frist „Belegungsplan“: Die Akten von Tagungshaus Rhein und Volker Busch nennen noch den 15.01.2027, die Akten '
        'von Fortbildung und Ina Reihe kennen schon den 29.01.2027 („Verlängerung“ vom 10.08.2026).']


def test_die_floskel_meldet_im_lint_keinen_widerspruch(welt, akten):
    episodes, _, bezuege = welt
    mail(episodes, 'Freigabe Budget 962', [('anbei wie besprochen die Informationen zu „Freigabe Budget 962“. Ich '
                                            'schicke Ihnen die Unterlagen bis Freitag.', 'commitment')], tage=80,
         absender='Jürgen Möller <j.moeller@stadtwerke.example>', weitere=('Kai Kollege <kai@kollegen.example>',))
    mail(episodes, 'Newsletter Oktober', [('anbei wie besprochen die Informationen zu „Newsletter Oktober“. Ich '
                                           'schicke Ihnen die Unterlagen bis Freitag.', 'commitment')], tage=10,
         absender='Ulrike Möller <u.moeller@verband.example>', weitere=('Jürgen Möller <j.moeller@stadtwerke.example>',))
    neu_rechnen(akten)
    befunde = Pruefer(episodes, bezuege, akten, jetzt=JETZT).pruefen().befunde
    assert [b.text for b in befunde if b.art == 'widerspruch'] == []


def test_bestaetigen_sie_den_termin_in_zwei_mails_sind_zwei_termine(welt, akten):
    episodes, _, _ = welt
    mail(episodes, 'Rückfrage', [('Bitte bestätigen Sie den Termin bis Donnerstag.', 'request')], tage=10)
    mail(episodes, 'Kurze Bitte', [('Bitte bestätigen Sie den Termin bis Donnerstag, danke.', 'request')], tage=3)
    fristen = neu_rechnen(akten).akte(SACHE, jetzt=JETZT, alle=True)['fristen']
    assert fristen['gesamt']['kommend'] + fristen['gesamt']['verstrichen'] == 2
    assert neu_rechnen(akten).akte(SACHE, jetzt=JETZT, alle=True)['fristen']['ersetzt'] == []
