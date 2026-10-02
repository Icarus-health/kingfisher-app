"""Stufe „Privat“ (M4): Kreise, private Akten-Arten und Fristen der Welt, nichts Falsches, nichts ohne Klick.

Wie `test_lint.py` gegen die **echte Welt** (`messlatte/welt`, Szenario `privat` und die Kreise der Arbeit), weil
er festhält, was Kingfisher dort vorschlagen muss. Die Welt wird nur gelesen.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from messlatte import privat as stufe
from messlatte import rauschen
from messlatte.daten import AKTEN_ARTEN, KREISE
from messlatte.welt import WeltFehler, lade_welt

WELT = Path(__file__).resolve().parents[1] / 'welt'


@pytest.fixture(scope='module')
def messung():
    from messlatte import handlungen
    from messlatte.akten import RegelEinordnung
    from messlatte.aufnahme import aufnehmen
    from messlatte.instanz import instanz_starten

    welt = lade_welt(WELT)
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, eigene=tuple(welt.nutzer.adressen)) as instanz:
        aufgenommen = aufnehmen(instanz, welt.quellen, welt.stichtag, modell=RegelEinordnung())
        handlungen.ausfuehren(instanz, [welt], aufgenommen.episoden)
        yield stufe.messen(instanz, [welt], aufgenommen)


def test_alle_erwarteten_kreise_mit_begruendung_und_kein_falscher_innerer_kreis(messung):
    assert [(k.adresse, k.vorgeschlagen, k.fehlende_merkmale) for k in messung.kreise if not k.richtig] == []
    assert messung.kreise_richtig == len(messung.kreise) >= 9
    assert {k.erwartet for k in messung.kreise} == set(KREISE)
    assert messung.falsche_innere == []


def test_alle_akten_arten_und_fristen_ohne_erfundene_zahl(messung):
    assert [a for a in messung.arten if a[1] != a[2]] == []
    assert {a[1] for a in messung.arten} == set(AKTEN_ARTEN)
    assert [f for f in messung.fristen if not f[4]] == []
    assert messung.fristen_gefunden == len(messung.fristen) >= 4
    assert messung.zahlen_ohne_beleg == [] and messung.verbotene_fristen == []
    assert messung.fristen_ohne_erwartung == []


def test_die_stufe_schreibt_nichts_alles_bleibt_vorschlag(messung):
    assert messung.nur_vorschlaege and messung.bestaetigt_nachher == 0
    assert messung.aufgaben_vorher == messung.aufgaben_nachher


def test_bericht_nennt_die_zielwerte(messung):
    text = '\n'.join(stufe.markdown(messung))
    assert f'Kreise wie erwartet vorgeschlagen (mit allen Merkmalen in der Begründung): {len(messung.kreise)} von' in text
    assert 'Falsche innere Kreise (innerer Kreis ohne Erwartung, Welt und Rauschen): 0' in text
    assert 'Zahlen ohne Beleg: 0' in text and 'alles Vorschlag: ja' in text
    daten = stufe.zu_dict(messung)
    assert daten['kreise']['richtig'] == daten['kreise']['erwartet'] and daten['fristen']['zahlen_ohne_beleg'] == []


def test_zuordnung_ist_streng_falsche_innere_und_fehlende_merkmale_zaehlen():
    treffer = stufe.KreisTreffer('a@b.example', 'innerer_kreis', 'innerer_kreis', 'Zwei Mails, privater Anbieter.',
                                 stufe._fehlende(('privater Anbieter', 'gemeinsamer Termin'), 'Zwei Mails, privater Anbieter.'))
    assert treffer.fehlende_merkmale == ('gemeinsamer Termin',) and not treffer.richtig
    m = stufe.PrivatMessung(falsche_innere=[('x@y.example', 'rauschen', '…')])
    assert 'Falsche innere Kreise (innerer Kreis ohne Erwartung, Welt und Rauschen): 1' in '\n'.join(stufe.markdown(m))


def test_falscher_innerer_kreis_ist_jeder_innere_ohne_erwartung():
    vorschlaege = {'person:a:mama@gmx.example': ('innerer_kreis', 'a'), 'person:a:chef@firma.example': ('innerer_kreis', 'b'),
                   'person:a:x.y@privat-bank-3.example': ('innerer_kreis', 'c'), 'person:a:k@firma.example': ('kollegen', 'd')}
    erwartet = {'mama@gmx.example': 'innerer_kreis', 'chef@firma.example': 'kollegen'}
    assert stufe.falsche_innere(vorschlaege, erwartet, {'mama@gmx.example', 'chef@firma.example'}) == [
        ('chef@firma.example', 'welt', 'b'), ('x.y@privat-bank-3.example', 'rauschen', 'c')]


def test_vor_m4_zaehlt_jede_erwartung_als_nicht_vorgeschlagen():
    welt = lade_welt(WELT)
    m = stufe._vor_m4([welt], stufe.PrivatMessung())
    assert not m.produkt_kennt_es and m.kreise_richtig == m.arten_richtig == m.fristen_gefunden == 0
    assert len(m.kreise) == len(welt.kreis_erwartungen) and 'noch nicht (Stand vor M4)' in '\n'.join(stufe.markdown(m))


def test_konstanten_wie_im_produkt():
    from icarus_memory import akten_arten, kreis
    assert KREISE == kreis.KREISE and AKTEN_ARTEN == akten_arten.ARTEN


def test_private_szenarien_aendern_das_rauschen_nicht(welt_kopie):
    welt_kopie('rechnung', lambda d: d.update(bereich='privat'))
    ohne = lade_welt(welt_kopie.pfad)
    welt_kopie('rechnung', lambda d: d.update(bereich='beruf'))
    mit = lade_welt(welt_kopie.pfad)
    assert ohne.private_szenarien == {'rechnung'} and mit.private_szenarien == frozenset()
    # Ein privates Szenario gibt dem Rauschen keine Wörter: Ohne es gezogen, wäre es dasselbe.
    welt_kopie('rechnung', lambda d: (d.update(bereich='privat'), d['quellen'].append(
        {'id': 'rechnung-099', 'art': 'mail', 'zeit': '2026-09-01T08:00:00+02:00',
         'von': {'name': 'Zahnarztpraxis Wunderlich', 'adresse': 'praxis@zahnarzt-wunderlich.example'},
         'an': [{'name': 'Lea Hartmann', 'adresse': 'lea@hartmann-beratung.example'}],
         'betreff': 'Quittungsbeleg Prophylaxe', 'text': 'Danke.'})))
    erweitert = lade_welt(welt_kopie.pfad)
    assert rauschen.erzeuge(300, [erweitert], 3) == rauschen.erzeuge(300, [ohne], 3)


def test_weltpruefung_kennt_die_neuen_felder(welt_kopie):
    def falsch(d):
        d['bereich'] = 'urlaub'
        d['kreise'] = [{'adresse': 'niemand@nirgends.example', 'kreis': 'familie'}]
        d['akten_arten'] = [{'adresse': 'x@y.example', 'art': 'hobby'}]
        d['fristen'] = [{'quelle': 'rechnung-gibtsnicht', 'art': 'zahlung', 'datum': '12.10.2026'}]
        d['keine_fristen'] = ['rechnung-auchnicht']
    welt_kopie('rechnung', falsch)
    with pytest.raises(WeltFehler) as fehler:
        lade_welt(welt_kopie.pfad)
    text = str(fehler.value)
    for teil in ('„bereich“ muss einer von', '„kreis“ muss einer von', '„art“ muss eine von', '„datum“ muss ein Kalendertag',
                 '„keine_fristen“: Quelle gibt es nicht'):
        assert teil in text, teil


# -- Geburtstage und Wiederkehrendes (Rest von M4) -------------------------------------------------------------------


def test_geburtstage_nur_im_inneren_kreis_und_alles_wiederkehrende_belegt(messung):
    assert messung.wk_kennt_es
    assert [g for g in messung.geburtstage if not g[2]] == []
    assert messung.geburtstage_gefunden == len(messung.geburtstage) >= 3
    # Nie für Kollegen oder Kontakte, auch wenn ihr Geburtstag im Kalender steht.
    assert messung.geburtstage_falsch == []
    assert [w for w in messung.wiederkehrend if not w[2]] == []
    assert messung.wiederkehrend_gefunden == len(messung.wiederkehrend) >= 7
    assert messung.wk_zahlen_ohne_beleg == [] and messung.wiederkehrend_verboten == []
    assert messung.wissen_nachher == 0 and messung.nur_vorschlaege


def test_briefing_nennt_den_geburtstag_des_inneren_kreises_und_keinen_kontakt(messung):
    assert messung.briefing['gemessen'] and messung.briefing['gleich'], messung.briefing
    assert messung.briefing['kontakte_im_briefing'] == 0


def test_pdf_anhaenge_werden_quelle_und_ihre_fristen_gefunden(messung):
    assert [a for a in messung.anhaenge if not a[3]] == []
    assert messung.anhaenge_richtig == len(messung.anhaenge) >= 3
    assert {a[1] for a in messung.anhaenge} == {'gelesen', 'gescannt'}
    aus_pdf = [f for f in messung.fristen if '#anhang-' in f[0]]
    assert len(aus_pdf) >= 2 and all(f[4] for f in aus_pdf)
    assert '| privat-043#anhang-1 | gescannt | gescannt | ja |' in '\n'.join(stufe.markdown(messung))


def test_pdf_der_welt_liest_das_produkt_wie_eine_echte_rechnung():
    from icarus_memory.document_text import pdf_seiten
    from messlatte.pdf import scan_pdf, text_pdf
    gelesen = pdf_seiten(text_pdf([['Rechnungsbetrag: 147,60 €', 'Bitte überweisen Sie bis zum 22.10.2026 (Konto „A“).'],
                                   ['Seite zwei']]))
    assert gelesen['seiten'] == ['Rechnungsbetrag: 147,60 €\nBitte überweisen Sie bis zum 22.10.2026 (Konto „A“).',
                                 'Seite zwei']
    assert pdf_seiten(scan_pdf(2))['leer'] == [1, 2]


def test_anhang_hat_eine_eigene_welt_id():
    from messlatte.postfach import quelle_aus_message_id
    assert quelle_aus_message_id('konto:<privat-041@messlatte.example>') == 'privat-041'
    assert quelle_aus_message_id('konto:<privat-041@messlatte.example>#anhang:1:Rechnung.pdf') == 'privat-041#anhang-1'


def test_weltpruefung_kennt_anhaenge(welt_kopie):
    def falsch(d):
        d['quellen'][0]['anhaenge'] = [{'datei': 'Rechnung.docx', 'seiten': [['x']]}, {'datei': 'Leer.pdf'}]
        d['fristen'] = [{'quelle': d['quellen'][0]['id'] + '#anhang-9', 'art': 'zahlung', 'datum': '2026-10-12'}]
    welt_kopie('rechnung', falsch)
    with pytest.raises(WeltFehler) as fehler:
        lade_welt(welt_kopie.pfad)
    text = str(fehler.value)
    for teil in ('„datei“ muss ein PDF-Dateiname sein', 'Ein Anhang braucht Seiten mit Text oder „gescannt“',
                 'Eine erwartete Frist braucht eine Mail dieser Welt (oder ihren Anhang) als Quelle'):
        assert teil in text, teil


def test_falscher_geburtstag_und_unbelegte_zahl_stehen_im_bericht():
    m = stufe.PrivatMessung(geburtstage=[('a@b.example', '09-30', False, '')],
                            geburtstage_falsch=[('kollege@firma.example', '01-02', 'K hat am 2. Januar Geburtstag.')],
                            wk_zahlen_ohne_beleg=[('privat-x', 'Monatlich: Abschlag, 95,00 €', ['95,00'])])
    text = '\n'.join(stufe.markdown(m))
    assert 'Geburtstage gefunden (nur innerer Kreis): 0 von 1' in text
    assert 'Geburtstage ohne Erwartung (Kollegen, Kontakte, falscher Tag): 1' in text
    assert 'Zahlen ohne Beleg: 1' in text and 'kollege@firma.example' in text


def test_weltpruefung_kennt_geburtstage_und_wiederkehrendes(welt_kopie):
    def falsch(d):
        d['geburtstage'] = [{'adresse': 'niemand@nirgends.example', 'datum': '30.09.'}]
        d['wiederkehrend'] = [{'quelle': 'rechnung-gibtsnicht', 'enthaelt': ['Monatlich']}]
        d['keine_wiederkehrend'] = ['rechnung-auchnicht']
    welt_kopie('rechnung', falsch)
    with pytest.raises(WeltFehler) as fehler:
        lade_welt(welt_kopie.pfad)
    text = str(fehler.value)
    for teil in ('„datum“ muss Monat und Tag sein', '„wiederkehrend“: Quelle gibt es nicht',
                 '„keine_wiederkehrend“: Quelle gibt es nicht'):
        assert teil in text, teil
