"""Stufe „Lint“: alle erwarteten Befunde der Welt, kein Fehlalarm, kein Fakt ohne Klick.

Wie `test_akten.py` gegen die **echte Welt** (`messlatte/welt`), weil er festhält, was der Lint dort
finden muss (Szenario `widersprueche`, `kontakt-vor-jahren`). Die Welt wird nur gelesen.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from messlatte import lint as stufe
from messlatte.daten import LINT_ARTEN, LintErwartung
from messlatte.welt import WeltFehler, lade_welt

WELT = Path(__file__).resolve().parents[1] / 'welt'
STICHTAG = datetime(2026, 9, 29, 7, 30, tzinfo=timezone.utc)


@pytest.fixture(scope='module')
def messung():
    from messlatte import handlungen
    from messlatte.akten import RegelEinordnung
    from messlatte.aufnahme import aufnehmen
    from messlatte.instanz import instanz_starten

    welt = lade_welt(WELT)
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, eigene=tuple(welt.nutzer.adressen)) as instanz:
        aufgenommen = aufnehmen(instanz, welt.quellen, welt.stichtag, modell=RegelEinordnung())
        taten = handlungen.ausfuehren(instanz, [welt], aufgenommen.episoden)
        yield stufe.messen(instanz, [welt], aufgenommen), taten


def test_alle_erwarteten_befunde_ohne_fehlalarm(messung):
    m, _ = messung
    assert [(e.art, e.unterart) for e in m.erwartet if not e.gefunden] == []
    assert m.gefunden == len(m.erwartet) >= 5
    assert m.fehlalarme == []
    assert {e.art for e in m.erwartet} >= {'widerspruch', 'aussage_gegen_quelle', 'waise', 'querverweis'}


def test_der_lint_schreibt_keinen_fakt_widersprueche_sind_offene_vorschlaege(messung):
    m, taten = messung
    assert m.fakten_unveraendert and len(m.aussagen_vorher) == len(taten.angenommen) == 1
    # Widerspruch zweier Akten: zwei Vorschläge (alt, neu); angenommene Aussage gegen Mail: einer.
    assert m.vorschlaege_offen == 3


def test_handlungen_der_welt_laufen_ueber_die_routen(messung):
    _, taten = messung
    assert list(taten.projekte) == ['widersprueche-fortbildung'] and taten.zugeordnet == 2
    assert taten.fehler == []


def test_bericht_nennt_gefunden_fehlalarme_und_grenzen(messung):
    m, _ = messung
    text = stufe.markdown(m)
    assert f'Erwartete Befunde gefunden: {m.gefunden} von {len(m.erwartet)}' in text and 'Fehlalarme: 0' in text
    assert 'nicht gemessen (ohne Modell entsteht keine Lage)' in text and 'unverändert: ja' in text


def _befund(art, belege, unterart='', datum='2026-09-01T00:00:00+00:00'):
    return {'art': art, 'unterart': unterart, 'text': 'x',
            'belege': [{'episode_id': e, 'datum': datum} for e in belege]}


def test_zuordnung_zaehlt_fehlalarme_und_verfehltes_streng():
    erwartungen = [LintErwartung('widerspruch', ('w-1', 'w-2')), LintErwartung('waise', ('w-3',), 'ruhend')]
    zu_welt = {'e1': 'w-1', 'e2': 'w-2', 'e3': 'w-3', 'e4': 'w-4', 'r1': 'rauschen-000001'}
    # Ein Befund mit allen erwarteten Quellen trifft; einer mit nur einer Quelle nicht.
    treffer, fehl, ruhend = stufe.zuordnen([_befund('widerspruch', ['e1', 'e2'])], erwartungen, zu_welt, STICHTAG)
    assert [t.gefunden for t in treffer] == [True, False] and fehl == [] and ruhend == 0
    treffer, fehl, _ = stufe.zuordnen([_befund('widerspruch', ['e1'])], erwartungen, zu_welt, STICHTAG)
    assert [t.gefunden for t in treffer] == [False, False] and len(fehl) == 1
    # Falsche Art oder Unterart ist ein Fehlalarm, kein Treffer.
    treffer, fehl, _ = stufe.zuordnen([_befund('waise', ['e3'], 'ohne_akte'), _befund('querverweis', ['e4'])],
                                      erwartungen, zu_welt, STICHTAG)
    assert [t.gefunden for t in treffer] == [False, False] and [f[0] for f in fehl] == ['waise', 'querverweis']
    # Im Rauschen ist nur ein stimmender Hinweis „ruhend“ kein Fehlalarm.
    alt = '2024-01-01T00:00:00+00:00'
    _, fehl, ruhend = stufe.zuordnen([_befund('waise', ['r1'], 'ruhend', alt), _befund('waise', ['r1'], 'ruhend'),
                                      _befund('widerspruch', ['r1'])], erwartungen, zu_welt, STICHTAG)
    assert ruhend == 1 and [f[0] for f in fehl] == ['waise', 'widerspruch']


def test_arten_der_welt_und_des_produkts_sind_dieselben():
    from icarus_memory.lint import ARTEN
    assert LINT_ARTEN == ARTEN


def test_welt_prueft_projekte_angenommenes_und_erwartete_befunde(welt_kopie):
    def kaputt(daten):
        daten['projekte'] = [{'id': 'falsch-praefix', 'name': 'Projekt'}]
        daten['quellen'][0]['projekt'] = 'gibt-es-nicht'
        daten['angenommen'] = [{'id': 'mainz-a1', 'beleg': daten['quellen'][0]['id'], 'zitat': 'steht da nicht',
                                'subjekt': 'unsinn', 'praedikat': 'p', 'wert': 'w', 'aussage': 'a'}]
        daten['lint'] = [{'art': 'erfunden', 'quellen': ['mainz-001']},
                         {'art': 'waise', 'quellen': ['gibt-es-nicht']}]

    welt_kopie('mainz', kaputt)
    with pytest.raises(WeltFehler) as fehler:
        lade_welt(welt_kopie.pfad)
    text = str(fehler.value)
    for teil in ('Projekt-ID muss mit dem Szenario-Präfix', '„projekt“ verweist auf „gibt-es-nicht“',
                 '„zitat“ steht nicht wörtlich', '„subjekt“ muss eine Sache sein', '„art“ muss eine von',
                 'Quelle „gibt-es-nicht“ gibt es nicht'):
        assert teil in text, teil
