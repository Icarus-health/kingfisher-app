"""Kennzahl „Kontext abgeschnitten“: gefunden, aber vom Zeichenbudget verdrängt, getrennt von „nicht gefunden“.

Zusicherungen (Sabotageproben in `docs/35-belegte-antworten.md`, Abschnitt „Zweistufige Auswahl“):

1. Das Produkt nennt die Quellen, die das Budget verdrängte (`search.abgeschnitten`); der Abruf übersetzt sie in Welt-IDs.
2. Die Bewertung zählt einen erwarteten Beleg nur dann als abgeschnitten, wenn er nicht im Kontext stand, aber gefunden
   war. Ein Beleg, den die Suche nie lieferte, ist „nicht gefunden“, nicht „abgeschnitten“.
3. „Ohne tragende Stelle“: Der Beleg steht im Kontext, aber keine Pflichtaussage, die der Volltext der Quelle trägt, ist
   noch zu sehen. Trägt der Volltext keine, gibt es nichts zu verlieren.
4. Zu lange Quellen (über dem Auswertungsbudget des Arbeitsgedächtnisses) sind eine eigene Lücke.
5. Der Bericht führt beide Kennzahlen aus.
"""
from __future__ import annotations

from dataclasses import replace

from icarus_memory.working_memory_store import MAX_SOURCE_CHARS
from messlatte.abruf import abrufen, quellentext
from messlatte.bewertung import bewerte_abruf, ohne_tragende_stelle, zaehle_abruf
from messlatte.daten import Erwartet, Frage, Verboten
from messlatte.ergebnisse import AbrufErgebnis


def frage_mit(belege, aussagen=(('a',),)):
    return Frage(id='x-1', frage='?', kategorie='frist', schwere='normal',
                 erwartet=Erwartet('antworten', aussagen, belege=belege), verboten=Verboten())


# -- 2. Bewertung ---------------------------------------------------------------------------------------------


def test_abgeschnitten_heisst_gefunden_aber_verdraengt_nicht_gefunden_bleibt_nicht_gefunden():
    ergebnis = AbrufErgebnis(frage_id='x-1', weg='arbeitsstand', kandidaten=('a',), abgeschnitten=('b',))
    bewertung = bewerte_abruf(frage_mit(('a', 'b', 'c')), ergebnis)
    assert bewertung.gefunden == ('a',)
    assert bewertung.fehlend == ('b', 'c')
    assert bewertung.abgeschnitten == ('b',), 'c wurde nie geliefert: nicht gefunden, nicht abgeschnitten'


def test_ein_abgeschnittener_beleg_der_doch_ueber_ein_angebot_gefunden_wurde_zaehlt_nicht():
    ergebnis = AbrufErgebnis(frage_id='x-1', weg='arbeitsstand', kandidaten=(), abgeschnitten=('b',),
                             termine_kalender=('b',))
    assert bewerte_abruf(frage_mit(('b',)), ergebnis).abgeschnitten == ()


def test_ohne_stelle_zaehlt_nur_belege_die_im_kontext_standen_und_zu_lang_nur_nicht_gefundene():
    ergebnis = AbrufErgebnis(frage_id='x-1', weg='arbeitsstand', kandidaten=('a', 'b'), ohne_stelle=('a', 'c'),
                             zu_lang=('b', 'c'))
    bewertung = bewerte_abruf(frage_mit(('a', 'b', 'c')), ergebnis)
    assert bewertung.ohne_stelle == ('a',), 'c stand nicht im Kontext'
    assert bewertung.zu_lang == ('c',), 'b wurde gefunden'


def test_zaehler_fuehren_fragen_und_belege_getrennt():
    a = bewerte_abruf(frage_mit(('a', 'b')), AbrufErgebnis(frage_id='x-1', kandidaten=('a',), abgeschnitten=('b',),
                                                          ohne_stelle=('a',)))
    b = bewerte_abruf(frage_mit(('a',)), AbrufErgebnis(frage_id='x-2', kandidaten=('a',)))
    zaehler = zaehle_abruf([a, b])
    assert (zaehler.fragen_abgeschnitten, zaehler.belege_abgeschnitten) == (1, 1)
    assert (zaehler.fragen_ohne_stelle, zaehler.belege_ohne_stelle) == (1, 1)
    assert (zaehler.fragen_zu_lang, zaehler.belege_zu_lang) == (0, 0)


# -- 3. Die tragende Stelle --------------------------------------------------------------------------------------


GRUPPEN = (('12. November',), ('12 Uhr', '12:00'))


def test_tragende_stelle_fehlt_wenn_nichts_von_dem_zu_sehen_ist_was_der_volltext_traegt():
    voll = 'Die Frist endet am 12. November. Gruß\n\n-- Signatur'
    assert ohne_tragende_stelle(voll, 'Betreff\nGruß\n-- Signatur', GRUPPEN)
    assert not ohne_tragende_stelle(voll, 'Betreff\nDie Frist endet am 12. November.', GRUPPEN)


def test_eine_der_getragenen_aussagen_genuegt_und_wer_nichts_traegt_hat_nichts_zu_verlieren():
    voll = 'Am 12. November um 12 Uhr.'
    assert not ohne_tragende_stelle(voll, 'nur um 12 Uhr', GRUPPEN)
    assert not ohne_tragende_stelle('Kein Datum hier.', 'irgendwas', GRUPPEN)


def test_die_vergleichsform_ignoriert_gross_und_kleinschreibung_und_leerraum():
    assert not ohne_tragende_stelle('Am 12.  November', 'am 12. november', (('12. November',),))


# -- 1. Der Produktpfad ------------------------------------------------------------------------------------------


def texte_der(bestand):
    return {q.id: quellentext(q) for q in bestand.welt.quellen}


def test_das_produkt_nennt_die_vom_budget_verdraengten_quellen(bestand, monkeypatch):
    from icarus_memory import working_memory_answers as wma
    texte = texte_der(bestand)
    voll = abrufen(bestand.instanz, bestand.frage('mainz-01'), bestand.rueck, texte)
    assert voll.abgeschnitten == () and len(voll.kandidaten) >= 6
    monkeypatch.setattr(wma, 'MAX_CONTEXT', 2500)
    eng = abrufen(bestand.instanz, bestand.frage('mainz-01'), bestand.rueck, texte)
    assert eng.abgeschnitten, 'Bei engem Budget fallen Quellen weg'
    assert set(eng.abgeschnitten).isdisjoint(eng.kandidaten)
    assert set(eng.abgeschnitten) | set(eng.kandidaten) == set(voll.kandidaten), 'Nichts geht verloren, was vorher da war'
    # Die Reihenfolge des Budgets ist die Rangfolge: Verdrängt wird von hinten.
    assert list(voll.kandidaten)[:len(eng.kandidaten)] == list(eng.kandidaten)


def test_ein_erwarteter_beleg_hinter_dem_budget_ist_abgeschnitten_nicht_nicht_gefunden(bestand, monkeypatch):
    from icarus_memory import working_memory_answers as wma
    monkeypatch.setattr(wma, 'MAX_CONTEXT', 2500)
    frage = replace(bestand.frage('mainz-01'),
                    erwartet=Erwartet('antworten', (('x',),), belege=('mainz-003', 'mainz-004')))
    ergebnis = abrufen(bestand.instanz, frage, bestand.rueck, texte_der(bestand))
    bewertung = bewerte_abruf(frage, ergebnis)
    assert bewertung.gefunden == ('mainz-003',) and bewertung.abgeschnitten == ('mainz-004',)


def test_im_kontext_fehlt_die_stelle_nur_wenn_der_volltext_sie_traegt(bestand):
    texte = texte_der(bestand)
    wort = next(w for w in texte['mainz-003'].split() if len(w) > 6)
    # Heute zeigt der Kontext die ganze Quelle: Die Stelle, die der Volltext trägt, ist zu sehen.
    frage = replace(bestand.frage('mainz-01'), erwartet=Erwartet('antworten', ((wort,),), belege=('mainz-003',)))
    assert abrufen(bestand.instanz, frage, bestand.rueck, texte).ohne_stelle == ()
    # Eine Aussage, die der Volltext nicht trägt, ist nie „verloren“.
    frage = replace(bestand.frage('mainz-01'),
                    erwartet=Erwartet('antworten', (('gibtesnirgends',),), belege=('mainz-003',)))
    assert abrufen(bestand.instanz, frage, bestand.rueck, texte).ohne_stelle == ()


def test_zu_lange_erwartete_quellen_sind_eine_eigene_luecke(bestand):
    texte = texte_der(bestand)
    texte['mainz-003'] = 'x' * (MAX_SOURCE_CHARS + 1)  # über der Obergrenze der Einordnung, nicht mehr über 12.000
    ergebnis = abrufen(bestand.instanz, bestand.frage('mainz-01'), bestand.rueck, texte)
    assert ergebnis.zu_lang == ('mainz-003',)
    assert abrufen(bestand.instanz, bestand.frage('mainz-01'), bestand.rueck).zu_lang == (), 'Ohne Volltexte nicht messbar'
