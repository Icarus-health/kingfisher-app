"""Der Bericht führt „Kontext abgeschnitten“ und „ohne tragende Textstelle“ aus (eigene Datei: eine Messinstanz je Prozess)."""
from __future__ import annotations

from conftest import MINI_WELT

from messlatte import bericht
from messlatte.lauf import Optionen, durchfuehren


def test_der_bericht_fuehrt_beide_kennzahlen_aus():
    lauf = durchfuehren(Optionen(welten=(str(MINI_WELT),), kontext_zeichen=2500))
    text = bericht.markdown(lauf)
    assert '**Kontext abgeschnitten**' in text and 'ohne tragende Textstelle' in text
    z = lauf.abruf_gesamt
    assert z.belege_abgeschnitten == sum(len(f.abruf_bewertung.abgeschnitten) for f in lauf.fragen)
    assert f'{z.belege_abgeschnitten} von {z.belege_erwartet} Belegen' in text
    assert bericht.zu_dict(lauf)['abruf']['gesamt']['belege_abgeschnitten'] == z.belege_abgeschnitten
