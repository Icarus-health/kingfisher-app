"""Bewertung: viele kleine Fälle. Hier hängt das Vertrauen in jede Zahl der Messlatte."""
from __future__ import annotations

import pytest

from messlatte.bewertung import (
    aggregiere, bewerte_abruf, bewerte_antwort, enthaelt, erkenne_verhalten, fehlende_gruppen,
    gefundene_verbotene, ist_nicht_bekannt, normalisiere, x_von_n, zaehle_abruf,
)
from messlatte.daten import Erwartet, Frage, Verboten
from messlatte.ergebnisse import AbrufErgebnis, Angebot, AntwortErgebnis


def frage(verhalten='antworten', aussagen=(), bedeutungen=(), belege=(), v_aussagen=(), v_belege=(),
          id='t-1', kategorie='frist', schwere='kritisch', herkunft='welt'):
    return Frage(id=id, frage='?', kategorie=kategorie, schwere=schwere,
                 erwartet=Erwartet(verhalten, tuple(tuple(g) for g in aussagen),
                                   tuple(tuple(g) for g in bedeutungen), tuple(belege)),
                 verboten=Verboten(tuple(v_aussagen), tuple(v_belege)), herkunft=herkunft)


def antwort(text='', status='working_reports', belege=None, auswahl=(), fehler='', id='t-1'):
    return AntwortErgebnis(frage_id=id, text=text, status=status,
                           belege=None if belege is None else tuple(belege), auswahl=tuple(auswahl), fehler=fehler)


# -- Textvergleich ---------------------------------------------------------------


def test_normalisierung_ignoriert_gross_klein_und_leerraum():
    assert normalisiere('  Bis  ZUM\n 26.\tOktober ') == 'bis zum 26. oktober'


def test_normalisierung_entfernt_markdown_maskierung_des_produkts():
    assert normalisiere('03\\.10\\.2026 \\- Führung') == '03.10.2026 - führung'


def test_geschuetzte_leerzeichen_zaehlen_als_leerraum():
    assert enthaelt(normalisiere('26. Oktober'), '26. Oktober')


def test_alternativgruppe_eine_schreibweise_genuegt():
    assert fehlende_gruppen('Frist: 26.10.', [('26. Oktober', '26.10.')]) == ()


def test_jede_gruppe_muss_vorkommen():
    assert fehlende_gruppen('Frist 26.10.', [('26.10.',), ('Becker',)]) == (('Becker',),)


def test_leere_alternative_zaehlt_nie_als_treffer():
    assert not enthaelt('irgendein text', '   ')


def test_verbotene_aussage_wird_ohne_gross_klein_gefunden():
    assert gefundene_verbotene('Es gilt der 12. OKTOBER.', ['12. Oktober']) == ('12. Oktober',)


# -- Verhalten erkennen ----------------------------------------------------------


@pytest.mark.parametrize('text', [
    'Dazu liegt in den bisher eingeordneten Quellen keine Information vor.',
    'Im durchsuchten gespeicherten Text wurde keine verwendbare Originalstelle gefunden.',
    'Mit den hier ausgewählten Belegen kann ich diese Frage nicht belegt beantworten.',
    'Das kann ich mit den gefundenen Belegen nicht beantworten.',
    'Das weiß ich nicht.',
])
def test_nicht_bekannt_formulierungen_des_produkts(text):
    assert ist_nicht_bekannt(text)
    assert erkenne_verhalten(antwort(text, status='')) == 'nicht_bekannt'


def test_status_schlaegt_formulierung():
    # Eine Quelle, die zufällig „nicht bekannt“ sagt, macht die Antwort nicht zur Verweigerung.
    text = 'Quelle berichtet\nDer Preis ist noch nicht bekannt, Angebot bis 26. Oktober.'
    assert erkenne_verhalten(antwort(text, status='working_reports')) == 'antworten'


def test_bedeutungsfrage_ist_rueckfrage():
    assert erkenne_verhalten(antwort('Welchen meinst du?', status='meaning_choice')) == 'rueckfrage'


def test_zwei_knoepfe_sind_eine_rueckfrage():
    assert erkenne_verhalten(antwort('x', status='', auswahl=['A', 'B'])) == 'rueckfrage'


def test_freier_text_mit_frage_und_oder_ist_rueckfrage():
    assert erkenne_verhalten(antwort('Meinst du das Klinikum oder den Urlaub?', status='')) == 'rueckfrage'


def test_lokal_nur_ist_verweigert_und_leer_ist_fehler():
    assert erkenne_verhalten(antwort('Braucht ein lokales Modell.', status='local_only')) == 'verweigert'
    assert erkenne_verhalten(antwort('', status='')) == 'fehler'


# -- Antwortklassen ----------------------------------------------------------------


def test_richtige_antwort_mit_alternativgruppe():
    f = frage(aussagen=[['12. Oktober', '12.10.']], belege=['a-1'])
    b = bewerte_antwort(f, antwort('Bis zum 12.10.', belege=['a-1']))
    assert b.klasse == 'richtig' and not b.falsche_aussage


def test_verbotene_aussage_schlaegt_richtige_aussage():
    f = frage(aussagen=[['26. Oktober']], v_aussagen=['12. Oktober'])
    b = bewerte_antwort(f, antwort('Zuerst 12. Oktober, dann 26. Oktober.'))
    assert b.klasse == 'falsch' and b.falsche_aussage and b.verbotene_aussagen == ('12. Oktober',)


def test_verbotene_aussage_schlaegt_auch_eine_richtige_rueckfrage():
    f = frage('rueckfrage', bedeutungen=[['Klinikum'], ['Urlaub']], v_aussagen=['Therme'])
    b = bewerte_antwort(f, antwort('Klinikum, Urlaub oder Therme?', status='meaning_choice'))
    assert b.klasse == 'falsch'


def test_verbotene_aussage_in_den_angebotenen_knoepfen_zaehlt():
    f = frage('rueckfrage', bedeutungen=[['A'], ['B']], v_aussagen=['Therme'])
    b = bewerte_antwort(f, antwort('A oder B?', status='meaning_choice', auswahl=['A', 'Rheinhessen-Therme']))
    assert b.klasse == 'falsch'


def test_unvollstaendig_wenn_nur_ein_teil_der_pflichtaussagen():
    f = frage(aussagen=[['26.10.'], ['Becker']])
    b = bewerte_antwort(f, antwort('Bis 26.10.'))
    assert b.klasse == 'unvollstaendig' and b.fehlende_aussagen == (('Becker',),)


def test_falsch_wenn_keine_pflichtaussage_vorkommt():
    f = frage(aussagen=[['26.10.']])
    assert bewerte_antwort(f, antwort('Bis Ende des Monats.')).klasse == 'falsch'


def test_zitierter_verbotener_beleg_ist_falsch_auch_bei_richtigem_text():
    f = frage(aussagen=[['26.10.']], belege=['a-3'], v_belege=['a-1'])
    b = bewerte_antwort(f, antwort('26.10.', belege=['a-3', 'a-1']))
    assert b.klasse == 'falsch' and b.verbotene_belege == ('a-1',) and not b.falsche_aussage


def test_fehlender_beleg_macht_richtigen_text_unvollstaendig():
    f = frage(aussagen=[['26.10.']], belege=['a-3'])
    b = bewerte_antwort(f, antwort('26.10.', belege=['a-9']))
    assert b.klasse == 'unvollstaendig' and b.fehlende_belege == ('a-3',)


def test_ohne_ausgewiesene_belege_wird_der_beleg_nicht_verlangt():
    f = frage(aussagen=[['26.10.']], belege=['a-3'])
    assert bewerte_antwort(f, antwort('26.10.', belege=None, status='')).klasse == 'richtig'


def test_unnoetige_rueckfrage_bei_eindeutiger_frage():
    f = frage(aussagen=[['26.10.']])
    assert bewerte_antwort(f, antwort('Welchen meinst du?', status='meaning_choice')).klasse == 'unnoetige_rueckfrage'


def test_verweigert_wenn_belegte_antwort_als_unbekannt_beantwortet_wird():
    f = frage(aussagen=[['26.10.']])
    assert bewerte_antwort(f, antwort('Dazu liegt keine Information vor.', status='working_unknown')).klasse == 'verweigert'


def test_verweigert_bei_verweigerungsstatus():
    f = frage(aussagen=[['26.10.']])
    assert bewerte_antwort(f, antwort('x', status='local_only')).klasse == 'verweigert'


def test_fehler_bei_technischem_fehler():
    f = frage(aussagen=[['26.10.']])
    assert bewerte_antwort(f, antwort('', status='', fehler='Zeitüberschreitung')).klasse == 'fehler'


def test_fehler_bei_auswahlfehler_des_produkts():
    f = frage(aussagen=[['26.10.']])
    assert bewerte_antwort(f, antwort('Bitte erneut fragen.', status='working_selection_failed')).klasse == 'fehler'


def test_rueckfrage_richtig_wenn_alle_bedeutungen_angeboten():
    f = frage('rueckfrage', bedeutungen=[['Klinikum'], ['Urlaub', 'Hotel']])
    b = bewerte_antwort(f, antwort('Welchen meinst du?\n· Klinikum Mainz\n· Hotel am Rhein', status='meaning_choice'))
    assert b.klasse == 'richtig'


def test_rueckfrage_unvollstaendig_wenn_eine_bedeutung_fehlt():
    f = frage('rueckfrage', bedeutungen=[['Klinikum'], ['Urlaub']])
    b = bewerte_antwort(f, antwort('Welchen meinst du? Das Klinikum?', status='meaning_choice'))
    assert b.klasse == 'unvollstaendig' and b.fehlende_bedeutungen == (('Urlaub',),)


def test_willkuerlich_gewaehlte_bedeutung_ist_falsch():
    f = frage('rueckfrage', bedeutungen=[['Klinikum'], ['Urlaub']])
    b = bewerte_antwort(f, antwort('Quelle berichtet: Angebot Klinikum', status='working_reports'))
    assert b.klasse == 'falsch' and 'willkürlich' in b.gruende[0]


def test_rueckfrage_erwartet_aber_unbekannt_ist_verweigert():
    f = frage('rueckfrage', bedeutungen=[['A'], ['B']])
    assert bewerte_antwort(f, antwort('Keine Information.', status='working_unknown')).klasse == 'verweigert'


def test_nicht_bekannt_richtig():
    f = frage('nicht_bekannt')
    assert bewerte_antwort(f, antwort('Dazu liegt keine Information vor.', status='working_unknown')).klasse == 'richtig'


def test_nicht_bekannt_aber_inhaltliche_antwort_ist_erfunden():
    f = frage('nicht_bekannt')
    b = bewerte_antwort(f, antwort('Quelle berichtet: 10. Oktober', status='working_reports'))
    assert b.klasse == 'falsch' and 'erfunden' in b.gruende[0]


def test_nicht_bekannt_mit_rueckfrage_ist_unnoetig():
    f = frage('nicht_bekannt')
    assert bewerte_antwort(f, antwort('Meinst du A oder B?', status='meaning_choice')).klasse == 'unnoetige_rueckfrage'


# -- Aggregation -----------------------------------------------------------------


def test_aggregation_zaehlt_je_kategorie_schwere_und_herkunft():
    f1 = frage(aussagen=[['a']], id='w-1', kategorie='frist', schwere='kritisch', v_aussagen=['x'])
    f2 = frage(aussagen=[['a']], id='w-2', kategorie='frist', schwere='normal')
    f3 = frage(aussagen=[['a']], id='h-1', kategorie='profil', schwere='normal', herkunft='holdout')
    paare = [(f1, bewerte_antwort(f1, antwort('a x'))), (f2, bewerte_antwort(f2, antwort('a'))),
             (f3, bewerte_antwort(f3, antwort('b')))]
    ergebnis = aggregiere(paare)
    assert (ergebnis.gesamt.n, ergebnis.gesamt.richtig, ergebnis.gesamt.falsch) == (3, 1, 2)
    assert ergebnis.gesamt.falsche_aussagen == 1
    assert ergebnis.je_kategorie['frist'].n == 2 and ergebnis.je_kategorie['profil'].falsch == 1
    assert ergebnis.je_schwere['kritisch'].falsche_aussagen == 1
    assert set(ergebnis.je_herkunft) == {'welt', 'holdout'}
    assert ergebnis.kritisch_nicht_richtig == ('w-1',)


def test_zahlen_erscheinen_als_x_von_n():
    assert x_von_n(3, 8) == '3 von 8'


# -- Abruf -----------------------------------------------------------------------


def abruf(kandidaten=(), angebote=(), weg='arbeitsstand', kalender=()):
    return AbrufErgebnis(frage_id='t-1', weg=weg, kandidaten=tuple(kandidaten), angebote=tuple(angebote),
                         termine_kalender=tuple(kalender))


def test_abruf_recall_rang_und_verbotene():
    f = frage(belege=['a-3', 'a-4'], v_belege=['a-1'])
    b = bewerte_abruf(f, abruf(['a-1', 'a-3', 'r-9']))
    assert b.gefunden == ('a-3',) and b.fehlend == ('a-4',)
    assert b.raenge == {'a-3': 2} and b.verboten_gesehen == ('a-1',)


def test_abruf_beleg_ueber_angebot_und_kalender_zaehlt_mit_herkunft():
    f = frage('rueckfrage', bedeutungen=[['A'], ['B']], belege=['a-3', 'a-6'])
    b = bewerte_abruf(f, abruf([], [Angebot('betreff', 'A', '', ('a-3',))], 'bedeutungsfrage', ['a-6']))
    assert b.quelle == {'a-3': 'angebot', 'a-6': 'kalender'} and not b.fehlend


def test_abruf_rueckfrage_erst_angeboten_wenn_alle_bedeutungen_im_angebot_stehen():
    f = frage('rueckfrage', bedeutungen=[['Klinikum'], ['Urlaub']])
    voll = abruf([], [Angebot('betreff', 'Betreff Klinikum'), Angebot('absender', 'Mails zum Urlaub')], 'bedeutungsfrage')
    teil = abruf([], [Angebot('betreff', 'Betreff Klinikum')], 'bedeutungsfrage')
    assert bewerte_abruf(f, voll).rueckfrage_angeboten
    b = bewerte_abruf(f, teil)
    assert not b.rueckfrage_angeboten and b.fehlende_bedeutungen == (('Urlaub',),)


def test_abruf_gewaehlte_bedeutung_ohne_rueckfrage_wird_gemeldet():
    f = frage('rueckfrage', bedeutungen=[['A'], ['B']])
    assert bewerte_abruf(f, abruf(['a-1'], [Angebot('projekt', 'A')], 'gewaehlte_bedeutung')).ohne_rueckfrage_gewaehlt


def test_abruf_zaehler_x_von_n():
    f1, f2 = frage(belege=['a-1', 'a-2'], id='t-1'), frage(belege=['a-3'], id='t-2')
    b1 = bewerte_abruf(f1, abruf(['a-1', 'x-1']))
    b2 = bewerte_abruf(f2, abruf(['q'] * 6 + ['a-3']))
    z = zaehle_abruf([b1, b2])
    assert (z.belege_erwartet, z.belege_gefunden) == (3, 2)
    assert (z.fragen_mit_belegen, z.fragen_alle_belege) == (2, 1)
    assert (z.rang_1, z.rang_bis_5, z.rang_bis_12) == (1, 1, 2)
