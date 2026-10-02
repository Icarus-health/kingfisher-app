"""Stufe „Akten“: die Akte enthält die erwarteten Quellen und zeigt den NEUEN Stand.

Anders als die übrigen Tests der Messlatte läuft dieser gegen die **echte Welt**
(`messlatte/welt`), weil er festhält, was die Akte zu den dortigen Erzählsträngen
(`frist-verschoben`, `adresse-geaendert`, `zusage-abgesagt`) zeigen muss. Die Welt
wird nur gelesen; ein Test prüft, dass ihre Dateien unverändert bleiben.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from messlatte import akten as stufe
from messlatte.akten import FAELLE, RegelEinordnung, aktuelle_texte, fruehere_texte, pruefe

WELT = Path(__file__).resolve().parents[1] / 'welt'


def _pruefsumme() -> str:
    summe = hashlib.sha256()
    for datei in sorted(WELT.rglob('*.json')):
        summe.update(datei.read_bytes())
    return summe.hexdigest()


@pytest.fixture(scope='module')
def instanz_welt():
    """Die aufgenommene Welt in einer Messinstanz (höchstens eine je Prozess); die Welt darf sich nicht ändern."""
    from messlatte.aufnahme import aufnehmen
    from messlatte.instanz import instanz_starten
    from messlatte.welt import lade_welt

    vorher = _pruefsumme()
    welt = lade_welt(WELT)
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, eigene=tuple(welt.nutzer.adressen)) as instanz:
        aufgenommen = aufnehmen(instanz, welt.quellen, welt.stichtag, modell=RegelEinordnung())
        yield instanz, aufgenommen, vorher
    assert _pruefsumme() == vorher


@pytest.fixture(scope='module')
def messung(instanz_welt):
    instanz, aufgenommen, vorher = instanz_welt
    ergebnis = stufe.messen(instanz, aufgenommen)
    akten = _akten(instanz)
    episode_zu_welt = {e: w for w, e in aufgenommen.episoden.items()}
    return ergebnis, akten, episode_zu_welt, vorher


def _akten(instanz):
    from icarus_memory.akten import Akten
    from icarus_memory.bezuege import Bezuege
    bezuege = Bezuege(instanz.episodes, workspace=instanz.app.state.workspace, eigene=lambda: list(instanz.eigene))
    bezuege.aktualisieren()
    return Akten(instanz.episodes, bezuege, claims=instanz.claims)


def test_alle_faelle_bestehen_und_jede_erwartete_quelle_steht_im_verlauf(messung):
    ergebnis, *_ = messung
    fehlgeschlagen = [f'{f.id}: {f.hinweise}' for f in ergebnis['faelle'] if not f.bestanden]
    assert not fehlgeschlagen, fehlgeschlagen
    assert ergebnis['quellen_gefunden'] == ergebnis['quellen_erwartet'] == 15
    assert ergebnis['bestanden'] == ergebnis['gesamt'] == len(FAELLE) == 5


def test_frist_verschoben_zeigt_die_neue_frist_und_nur_die_neue(messung):
    _, akten, _, _ = messung
    akte = akten.akte('organisation:stiftungzgrm', alle=True)
    assert [f['datum'] for f in akte['fristen']['kommend']] == ['2026-11-12']
    aktuell = ' '.join(aktuelle_texte(akte))
    assert '12. November 2026' in aktuell and '15. Oktober' not in aktuell


def test_zusage_abgesagt_zeigt_die_absage_und_der_kalendereintrag_ist_gekennzeichnet(messung):
    _, akten, zu_welt, _ = messung
    akte = akten.akte('organisation:akademietaunus', alle=True)
    assert 'absagen' in akte['stand_der_dinge']['aktuell']['text']
    erledigt = akte['offen']['erledigt']['eintraege']
    # Die Anfrage der Akademie und die Zusage der Nutzerin gelten beide als durch die Absage erledigt.
    assert sorted(zu_welt[e['episode_id']] for e in erledigt if e['grund'] == 'absage') == [
        'zusage-abgesagt-001', 'zusage-abgesagt-002']
    termine = akte['termine']['kommend'] + akte['termine']['vergangen']
    assert [zu_welt[t['episode_id']] for t in termine if t['vermutlich_abgesagt']] == ['zusage-abgesagt-003']
    assert 'absagen' in termine[0]['vermutlich_abgesagt']['text']
    assert 'sage zu' in ' '.join(fruehere_texte(akte))


def test_adresse_geaendert_neue_anschrift_und_neue_mailadresse_sind_der_stand(messung):
    _, akten, _, _ = messung
    neu = akten.akte('organisation:vitalzentrumkassel', alle=True)
    assert 'Lindenallee 22' in ' '.join(aktuelle_texte(neu)) and 'Klinikstraße' not in ' '.join(aktuelle_texte(neu))
    alt = akten.akte('person:a:j.krueger@kreisklinik-rheingau.example', alle=True)
    assert 'j.krueger@vitalzentrum-kassel.example' in ' '.join(aktuelle_texte(alt))


def test_die_welt_bleibt_unveraendert(messung):
    # Die Fixture prüft die Prüfsumme nach der Messung; hier nur die Bedingung, dass sie überhaupt läuft.
    assert messung[3] == _pruefsumme()


# -- Die Prüfung selbst muss Fehler fangen (Sabotageproben als Tests) -----------------------


def _akte(aktuell='Die neue Einreichfrist ist der 12. November 2026.', kommend=(), vorher=(), offen=(), verlauf=()):
    zeile = lambda text, episode='e1': {'text': text, 'episode_id': episode}  # noqa: E731
    return {
        'quellen': {'gesamt': len(verlauf)},
        'verlauf': {'eintraege': [{'episode_id': e} for e in verlauf]},
        'stand_der_dinge': {'aktuell': zeile(aktuell) if aktuell else None, 'weitere': [],
                            'vorher': [zeile(t) for t in vorher]},
        'fristen': {'kommend': [zeile(t) for t in kommend], 'ersetzt': [], 'verstrichen': []},
        'offen': {'eintraege': [zeile(t, e) for t, e in offen], 'erledigt': {'eintraege': []}},
        'termine': {'kommend': [], 'vergangen': []},
    }


FALL = stufe.Fall('t', 'Test', 'organisation:x', quellen=('w-1', 'w-2'), aktuell=(('12. November 2026',),),
                  nicht_aktuell=('15. Oktober 2026',), nicht_offen=('w-2',))
ZU_WELT = {'e1': 'w-1', 'e2': 'w-2'}


def test_pruefung_besteht_bei_richtiger_akte():
    ergebnis = pruefe(_akte(verlauf=('e1', 'e2')), FALL, {}, ZU_WELT)
    assert ergebnis.bestanden and ergebnis.quellen_gefunden == 2


def test_pruefung_faengt_fehlende_quelle():
    ergebnis = pruefe(_akte(verlauf=('e1',)), FALL, {}, ZU_WELT)
    assert not ergebnis.bestanden and ergebnis.fehlende_quellen == ['w-2']


def test_pruefung_faengt_den_alten_wert_als_aktuellen_stand():
    ergebnis = pruefe(_akte(aktuell='Einreichfrist ist der 15. Oktober 2026.', verlauf=('e1', 'e2')), FALL, {}, ZU_WELT)
    assert not ergebnis.nicht_aktuell_ok and not ergebnis.aktuell_ok and not ergebnis.bestanden


def test_pruefung_faengt_den_alten_wert_als_kommende_frist():
    ergebnis = pruefe(_akte(kommend=('bis 15. Oktober 2026',), verlauf=('e1', 'e2')), FALL, {}, ZU_WELT)
    assert not ergebnis.nicht_aktuell_ok


def test_pruefung_faengt_eine_noch_offene_zusage():
    ergebnis = pruefe(_akte(offen=(('Ich sage zu.', 'e2'),), verlauf=('e1', 'e2')), FALL, {}, ZU_WELT)
    assert not ergebnis.nicht_offen_ok


def test_pruefung_ohne_akte_ist_nicht_bestanden():
    assert not pruefe(None, FALL, {}, ZU_WELT).bestanden


def test_regel_einordnung_ordnet_die_arten_zu():
    art = RegelEinordnung.art
    assert art('Sehr geehrte Frau Hartmann,') == 'irrelevant'
    assert art('Die neue Einreichfrist ist der 12. November 2026.') == 'change'
    assert art('Leider müssen wir den Workshop absagen.') == 'change'
    assert art('Sehr gern, ich sage zu!') == 'commitment'
    assert art('Bitte schicken Sie uns die Unterlagen.') == 'request'
    assert art('Aktuell haben wir 11 Anmeldungen.') == 'status'
    assert art('Lindenallee 22\n34117 Kassel') == 'status'
    assert art('Die Förderhöhe beträgt maximal 80.000 Euro.') == 'fact'
