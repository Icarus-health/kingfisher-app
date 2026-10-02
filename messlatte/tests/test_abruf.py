"""Die Abrufstufe misst die Suche des Produkts ohne Modell."""
from __future__ import annotations

from messlatte.abruf import Kandidatenerfasser, abrufen
from messlatte.bewertung import bewerte_abruf


def abruf(bestand, kennung):
    frage = bestand.frage(kennung)
    ergebnis = abrufen(bestand.instanz, frage, bestand.rueck)
    return frage, ergebnis, bewerte_abruf(frage, ergebnis)


def test_eindeutige_frage_findet_den_erwarteten_beleg_mit_rang(bestand):
    _, ergebnis, bewertung = abruf(bestand, 'rechnung-02')
    assert ergebnis.fehler == '' and ergebnis.weg == 'arbeitsstand'
    assert bewertung.gefunden == ('rechnung-004',) and bewertung.raenge['rechnung-004'] == 1
    assert bewertung.fehlend == ()


def test_recall_ueber_mehrere_quellen_zwischen_falschen(bestand):
    _, ergebnis, bewertung = abruf(bestand, 'mainz-01')
    assert 'mainz-003' in bewertung.gefunden
    # Kandidaten sind Welt-IDs, nie Episoden-IDs des Produkts.
    assert all(k.startswith(('mainz-', 'rechnung-')) for k in ergebnis.kandidaten)


def test_verbotene_belege_im_kontext_werden_gemeldet_wenn_sie_dort_sind(bestand):
    frage, ergebnis, bewertung = abruf(bestand, 'mainz-01')
    erwartet = tuple(b for b in frage.verboten.belege if b in ergebnis.kandidaten)
    assert bewertung.verboten_gesehen == erwartet


def test_mehrdeutige_frage_geht_ueber_die_erste_suchstufe(bestand):
    _, ergebnis, bewertung = abruf(bestand, 'mainz-02')
    assert ergebnis.weg == 'bedeutungsfrage' and ergebnis.status == 'meaning_choice'
    assert ergebnis.angebote, 'Das Produkt bietet Bedeutungen an'
    # Belege hinter den angebotenen Bedeutungen zählen als gefunden, mit Herkunft „angebot“.
    assert set(bewertung.gefunden) == {'mainz-003', 'mainz-004'}
    assert set(bewertung.quelle.values()) <= {'angebot', 'kandidat', 'kalender'}
    # Die Bewertung der Bedeutungsgruppen folgt dem, was angeboten wird (nicht einer festen Erwartung).
    text = ' '.join(a.label + ' ' + a.detail for a in ergebnis.angebote).casefold()
    fehlend = tuple(g for g in bestand.frage('mainz-02').erwartet.bedeutungen if not any(a.casefold() in text for a in g))
    assert bewertung.fehlende_bedeutungen == fehlend
    assert bewertung.rueckfrage_angeboten == (not fehlend)


def test_termin_wird_als_bedeutung_ueber_den_kalender_gefunden(bestand):
    _, ergebnis, _ = abruf(bestand, 'mainz-02')
    assert 'mainz-006' in ergebnis.termine_kalender


def test_frage_ohne_beleg_liefert_ein_ergebnis_ohne_absturz(bestand):
    frage, ergebnis, bewertung = abruf(bestand, 'rechnung-03')
    assert ergebnis.fehler == '' and bewertung.erwartet == () and bewertung.fehlend == ()


def test_kontext_wird_gemessen(bestand):
    _, ergebnis, _ = abruf(bestand, 'rechnung-01')
    assert ergebnis.kontext_zeichen > 0 and ergebnis.dauer_s >= 0


def test_erfasser_waehlt_alles_und_merkt_den_kontext():
    import json
    erfasser = Kandidatenerfasser()
    antwort = erfasser.complete_json([{'role': 'system', 'content': 'x'},
                                      {'role': 'user', 'content': json.dumps({'question': 'q', 'sources': [
                                          {'id': 'S1'}, {'id': 'K1'}, {'id': 'S2'}]})}])
    assert json.loads(antwort.text) == {'status': 'source_reports', 'ids': ['S1', 'S2']}
    assert erfasser.anfragen == 1 and erfasser.kontext_zeichen > 0


def test_produkt_und_anbieter_sind_nach_dem_abruf_wieder_unveraendert(bestand):
    vorher = bestand.instanz.agent._provider
    abruf(bestand, 'rechnung-01')
    assert bestand.instanz.agent._provider is vorher
