"""Verbotene Belege im Kontext, getrennt: gesamt und ungekennzeichnet (die eigentlich gefährliche Größe)."""
from __future__ import annotations

from messlatte.bewertung import bewerte_abruf, zaehle_abruf
from messlatte.daten import Erwartet, Frage, Verboten
from messlatte.ergebnisse import AbrufErgebnis


def frage():
    return Frage(id='x-1', frage='?', kategorie='frist', schwere='normal',
                 erwartet=Erwartet('antworten', (('a',),), belege=('neu',)),
                 verboten=Verboten(belege=('alt', 'fremd')))


def test_gekennzeichnete_verbotene_belege_zaehlen_gesamt_aber_nicht_als_ungekennzeichnet():
    abruf = AbrufErgebnis(frage_id='x-1', weg='arbeitsstand', kandidaten=('neu', 'alt', 'fremd'),
                          gekennzeichnet=('alt',), kontext_zeichen=1000, kontext_quellen=3)
    bewertung = bewerte_abruf(frage(), abruf)
    assert bewertung.verboten_gesehen == ('alt', 'fremd')
    assert bewertung.verboten_ungekennzeichnet == ('fremd',)
    zaehler = zaehle_abruf([bewertung])
    assert (zaehler.fragen_mit_verbotenem_beleg, zaehler.fragen_mit_verbotenem_beleg_ungekennzeichnet) == (1, 1)
    assert (zaehler.verbotene_belege, zaehler.verbotene_belege_ungekennzeichnet) == (2, 1)
    assert zaehler.kontext_zeichen_mittel == 1000 and zaehler.kontext_quellen_mittel == 3.0


def test_ist_alles_gekennzeichnet_bleibt_keine_gefahr_uebrig():
    abruf = AbrufErgebnis(frage_id='x-1', weg='arbeitsstand', kandidaten=('neu', 'alt'), gekennzeichnet=('alt',))
    zaehler = zaehle_abruf([bewerte_abruf(frage(), abruf)])
    assert zaehler.fragen_mit_verbotenem_beleg == 1 and zaehler.fragen_mit_verbotenem_beleg_ungekennzeichnet == 0


def test_eine_kennzeichnung_ausserhalb_der_kandidaten_zaehlt_nicht():
    # Angebote und Kalender nennen keinen Stand: Nur Quellen im Kontext der Auswahl können gekennzeichnet sein.
    abruf = AbrufErgebnis(frage_id='x-1', weg='bedeutungsfrage', kandidaten=('neu',), gekennzeichnet=('alt',))
    bewertung = bewerte_abruf(frage(), abruf)
    assert bewertung.verboten_ungekennzeichnet == bewertung.verboten_gesehen == ()
