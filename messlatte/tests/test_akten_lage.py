"""Stufe Akten, Lage (D3): erzeugt mit einem Skriptmodell und geprüft an den Aktualitätserwartungen.

Die Lage entsteht nur mit einem lokalen Modell der Rolle „hintergrund“. Ohne Modell steht sie als
„nicht gemessen“ im Bericht, nie als bestanden. Eine **verbotene Aussage** (der überholte Wert als
heutiger Stand) macht die Lage falsch, auch wenn die Satzprüfung sie durchlässt: Sie steht ja in einem Beleg.
"""
from __future__ import annotations

import json
import re

import pytest

from messlatte import akten as stufe
from messlatte.akten import FAELLE
from messlatte.tests.test_akten import instanz_welt  # noqa: F401 - Fixture: die aufgenommene Welt


class SkriptLage:
    """Lokales Skriptmodell der Rolle „hintergrund“ für die Lage. `wahl` bekommt die Belege (Nummer, Rolle, Text)."""

    is_local = True
    name = 'messlatte-test'

    def __init__(self, model, wahl):
        self.model, self.wahl = model, wahl
        self.aufrufe = 0

    def complete_json(self, messages, *, max_tokens=256, schema=None):
        from icarus_memory.providers import Reply
        self.aufrufe += 1
        belege = [(int(n), rolle, text.strip()) for n, rolle, text in
                  re.findall(r'\[(\d+)\] ([^:\n]+):[^\n]*\n\s+([^\n]*)', messages[1]['content'])]
        saetze = [{'text': text[:280].rsplit(' ', 1)[0] if len(text) > 280 else text, 'belege': [n]}
                  for n, text in self.wahl(belege)]
        return Reply(text=json.dumps({'saetze': saetze}))


def treu(belege):
    """Ein sorgfältiges Modell: sagt den Stand, wie die Akte ihn zeigt."""
    stand = [(n, text) for n, rolle, text in belege if rolle == 'Stand' and text]
    return stand[:1] or [(n, text) for n, _, text in belege[:1] if text]


def schlampig(belege):
    """Ein unaufmerksames Modell: gibt die als „Vorher (überholt)“ gekennzeichnete Zeile als heutigen Stand aus."""
    alt = [(n, text) for n, rolle, text in belege if rolle.startswith('Vorher') and text]
    return alt[:1] or [(n, text) for n, _, text in belege[-1:] if text]


def test_lage_ohne_modell_ist_nicht_gemessen_nie_bestanden(instanz_welt):  # noqa: F811
    instanz, aufgenommen, _ = instanz_welt
    ergebnis = stufe.messen(instanz, aufgenommen)
    assert ergebnis['lage']['gemessen'] is False and ergebnis['lage']['faelle'] == []
    text = stufe.markdown(ergebnis)
    assert '### Lage (Ebene 3)' in text and '**Nicht gemessen.**' in text and '--modell-hintergrund' in text
    assert 'Falsche Aussagen' not in text


def test_lage_mit_nicht_lokalem_modell_ist_nicht_gemessen(instanz_welt):  # noqa: F811
    instanz, aufgenommen, _ = instanz_welt
    modell = SkriptLage('cloud', treu)
    modell.is_local = False
    ergebnis = stufe.messen(instanz, aufgenommen, lage_modell=modell)
    assert ergebnis['lage']['gemessen'] is False and 'nicht lokal' in ergebnis['lage']['grund'] and modell.aufrufe == 0


def test_lage_mit_sorgfaeltigem_modell_hat_keine_falsche_aussage(instanz_welt):  # noqa: F811
    instanz, aufgenommen, _ = instanz_welt
    ergebnis = stufe.messen(instanz, aufgenommen, lage_modell=SkriptLage('treu', treu))
    lage = ergebnis['lage']
    assert lage['gemessen'] is True and lage['gesamt'] == len(FAELLE) == 5
    assert lage['falsch'] == 0 and lage['erzeugt'] >= 4, [(f.id, f.status, f.saetze) for f in lage['faelle']]
    stiftung = next(f for f in lage['faelle'] if f.id == 'frist-verschoben-stiftung')
    assert stiftung.saetze and '12. November 2026' in stiftung.saetze[0] and stiftung.vollstaendig
    text = stufe.markdown(ergebnis)
    assert '**Falsche Aussagen: 0**' in text and '| frist-verschoben-stiftung | erzeugt |' in text


def test_lage_die_den_ueberholten_wert_als_stand_nennt_ist_falsch(instanz_welt):  # noqa: F811
    """Die Satzprüfung lässt ihn durch (er steht in einem Beleg); erst die Messlatte kennt ihn als überholt."""
    instanz, aufgenommen, _ = instanz_welt
    ergebnis = stufe.messen(instanz, aufgenommen, lage_modell=SkriptLage('schlampig', schlampig))
    lage = ergebnis['lage']
    assert lage['falsch'] >= 1, [(f.id, f.saetze) for f in lage['faelle']]
    text = stufe.markdown(ergebnis)
    assert 'falsch: „' in text and '**Falsche Aussagen: 0**' not in text


def test_lage_pruefung_kennt_den_vorher_hinweis_und_fehlendes():
    fall = stufe.Fall('t', 'T', 'organisation:x', aktuell=(('12. November 2026',),), nicht_aktuell=('15. Oktober 2026',))
    falsch, fehlend = stufe.pruefe_lage(['Die Einreichfrist war vorher der 15. Oktober 2026.'], fall)
    assert falsch == [] and fehlend == ['12. November 2026']
    falsch, fehlend = stufe.pruefe_lage(['Die Einreichfrist ist der 15. Oktober 2026.',
                                         'Neu ist der 12. November 2026.'], fall)
    assert falsch == ['Die Einreichfrist ist der 15. Oktober 2026.'] and fehlend == []


def test_kommandozeile_kennt_modell_hintergrund_und_meldet_falsche_wahl(capsys):
    from messlatte.__main__ import _parser, main
    args = _parser().parse_args(['akten', '--welt', 'x', '--modell-hintergrund', 'ollama:qwen'])
    assert args.modell_hintergrund == 'ollama:qwen'
    assert main(['akten', '--welt', 'messlatte/welt', '--modell-hintergrund', 'unsinn']) == 2
    assert 'Unbekanntes Modell' in capsys.readouterr().err


@pytest.mark.parametrize('spec', ['', 'keins'])
def test_ohne_angabe_bleibt_die_lage_aus(spec):
    from messlatte.__main__ import _parser
    args = _parser().parse_args(['akten', '--welt', 'x', '--modell-hintergrund', spec])
    assert args.modell_hintergrund == spec
