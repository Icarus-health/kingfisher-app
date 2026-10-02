"""Aufnahme-Sonderfälle mit je eigener, frisch gebauter Instanz.

Getrennt von `test_aufnahme.py`, weil eine Messinstanz prozessweit Uhr und Umgebung
besetzt: Die modulweite Instanz dort darf nicht noch leben, wenn hier eine startet.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest

from messlatte import rauschen
from messlatte.aufnahme import _im_gedaechtnisfenster, aufnehmen, ist_rauschen
from messlatte.instanz import instanz_starten
from messlatte.welt import lade_welt

MINI = Path(__file__).parent / 'mini_welt'


@pytest.fixture
def welt():
    return lade_welt(MINI)


def test_uhr_und_umgebung_werden_zurueckgegeben(welt):
    from icarus_memory import model
    vorher = dict(os.environ)
    zeit_vorher = model.datetime
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone):
        assert (model.now().year, model.now().month, model.now().day) == (2026, 9, 29)
        assert 'ICARUS_DATA_DIR' in os.environ
    assert model.datetime is zeit_vorher
    assert dict(os.environ) == vorher
    assert abs((model.now() - datetime.now(model.now().tzinfo)).total_seconds()) < 5


def test_zugangsdaten_aus_der_umgebung_gelangen_nicht_in_die_instanz(welt, monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'geheim')
    monkeypatch.setenv('ICARUS_MAIL_PASSWORD', 'geheim')
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone):
        assert 'ANTHROPIC_API_KEY' not in os.environ and 'ICARUS_MAIL_PASSWORD' not in os.environ
    assert os.environ['ANTHROPIC_API_KEY'] == 'geheim'


def test_zwei_instanzen_zugleich_werden_abgelehnt(welt):
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone):
        with pytest.raises(RuntimeError, match='Messinstanz'):
            with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone):
                pass


def test_serverfehler_beim_abruf_wird_ueber_den_wiederholungsweg_des_produkts_behoben(welt):
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone) as instanz:
        ergebnis = aufnehmen(instanz, welt.quellen, welt.stichtag,
                             postfach_haken=lambda p: p.scheitern_einmal.add(('INBOX', 1)))
        assert ergebnis.fehlgeschlagen == 0 and ergebnis.aufgenommen == 15


def test_dauerhaft_fehlender_abruf_wird_als_fehlgeschlagen_gezaehlt_und_benannt(welt):
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone) as instanz:
        ergebnis = aufnehmen(instanz, welt.quellen, welt.stichtag,
                             postfach_haken=lambda p: p.scheitern_immer.add(('INBOX', 1)))
        assert ergebnis.fehlgeschlagen == 1 and ergebnis.aufgenommen == 14
        (fehlend,) = ergebnis.nicht_angekommen
        assert fehlend.startswith(('mainz-', 'rechnung-'))


def test_rauschen_wird_mit_aufgenommen_und_gezaehlt(welt):
    lauter = rauschen.erzeuge(60, [welt], seed=3)
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone) as instanz:
        ergebnis = aufnehmen(instanz, [*welt.quellen, *lauter], welt.stichtag)
    angekommen = [k for k in ergebnis.episoden if ist_rauschen(k)]
    termine = [q for q in lauter if q.art == 'termin']
    im_fenster = [q for q in termine if _im_gedaechtnisfenster(q, welt.stichtag)]
    erwartet = [q for q in lauter if q.art != 'termin'] + im_fenster
    assert ergebnis.rauschen == 60
    assert len(angekommen) == len(erwartet)
    # Was außerhalb des Gedächtnisfensters liegt, wird ehrlich als solches ausgewiesen, nicht als Ausfall.
    assert ergebnis.termine_ausserhalb_fenster == len(termine) - len(im_fenster)
    assert ergebnis.fehlgeschlagen == ergebnis.termine_ausserhalb_fenster
