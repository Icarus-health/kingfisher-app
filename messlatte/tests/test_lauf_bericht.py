"""Ganzer Lauf, Bericht und Kommandozeile auf der Mini-Welt."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from skriptmodell import SkriptModell

from messlatte import bericht
from messlatte.__main__ import main
from messlatte.lauf import Optionen, durchfuehren

MINI = Path(__file__).parent / 'mini_welt'
REGELN = {'Umsatzsteuervoranmeldung': ['Umsatzsteuervoranmeldung'], 'Angebot für das Klinikum Mainz raus': ['26. Oktober'],
          'Wann entscheidet das Klinikum': ['Anfang November'], 'Stromrechnung im August': ['Rechnungsbetrag']}


@pytest.fixture(scope='module')
def ohne_modell():
    return durchfuehren(Optionen(welten=(str(MINI),)))


@pytest.fixture(scope='module')
def mit_modell():
    modell = SkriptModell(dict(REGELN), chat='Bis Freitag ' + 'sehr ausführlich ' * 60)
    return durchfuehren(Optionen(welten=(str(MINI),), modell='ollama:skript'), anbieter_bauen=lambda wahl: modell)


def test_ohne_modell_ist_die_antwortstufe_nicht_gemessen_nie_bestanden(ohne_modell):
    assert ohne_modell.antwort_gemessen is False and ohne_modell.antwort_auswertung is None
    text = bericht.markdown(ohne_modell)
    assert 'Falsche Aussagen: nicht gemessen' in text and 'Richtig: nicht gemessen' in text
    assert 'Nicht gemessen: 8 von 8 Fragen' in text
    assert 'bestanden' not in text.casefold()
    assert all(f.antwort is None and f.antwort_bewertung is None for f in ohne_modell.fragen)


def test_abruf_wird_auch_ohne_modell_gemessen(ohne_modell):
    z = ohne_modell.abruf_gesamt
    assert z.fragen == 8 and z.belege_erwartet == 8 and z.belege_gefunden >= 5
    assert 'Erwartete Belege gefunden: ' in bericht.markdown(ohne_modell)


def test_kopf_nennt_commit_modell_weltversion_rauschen_datum(ohne_modell):
    kopf = ohne_modell.kopf
    assert kopf['commit'] and kopf['modell'] == 'keins' and kopf['welten'][0]['version'] == 1
    assert kopf['rauschen'] == {'anzahl': 0, 'seed': 1} and kopf['datum'].startswith('20')
    text = bericht.markdown(ohne_modell)
    for wert in (kopf['commit'], 'keins', 'welt v1', '0 Quellen (seed 1)', kopf['datum']):
        assert wert in text.split('## Ergebnis')[0]


def test_json_ist_vollstaendig_und_maschinenlesbar(ohne_modell, tmp_path):
    json_pfad, md_pfad = bericht.schreibe(ohne_modell, tmp_path)
    daten = json.loads(json_pfad.read_text(encoding='utf-8'))
    assert set(daten) == {'kopf', 'aufnahme', 'abruf', 'antwort', 'hinweise_der_weltpruefung', 'fragen', 'privat'}
    assert daten['privat'] is None   # die Mini-Welt erwartet keine Kreise, Arten oder Fristen
    assert len(daten['fragen']) == 8 and daten['antwort']['gemessen'] is False
    erste = daten['fragen'][0]
    assert erste['frage']['id'] == 'mainz-01' and erste['abruf']['kandidaten'] and erste['antwort'] is None
    assert md_pfad.read_text(encoding='utf-8').startswith('# Messlatte: Bericht')
    # Ein zweiter Bericht überschreibt den ersten nie.
    zweiter, _ = bericht.schreibe(ohne_modell, tmp_path)
    assert zweiter != json_pfad and json_pfad.exists()


def test_mit_modell_stehen_die_drei_zahlen_als_x_von_n_oben(mit_modell):
    text = bericht.markdown(mit_modell)
    kopf = text.split('## Aufnahme')[0]
    assert 'Falsche Aussagen: 0 von 8 Antworten' in kopf
    assert 'Richtig: ' in kopf and ' von 8 Antworten' in kopf and 'Nicht gemessen: 0 Fragen' in kopf
    assert '%' not in kopf, 'Keine Prozentwerte'


def test_je_kategorie_je_schwere_und_fehlerliste(mit_modell):
    text = bericht.markdown(mit_modell)
    assert '### Je Kategorie' in text and '### Je Schwere' in text
    assert '| aktualitaet | 2 |' in text and '| kritisch |' in text
    assert '## Fehlerliste Antwort' in text and '### mainz-04' in text
    assert '- Erwartet: antworten; Aussagen: 10:00/10 Uhr; Belege: mainz-006' in text


def test_antwort_in_der_fehlerliste_ist_gekuerzt(mit_modell):
    text = bericht.markdown(mit_modell)
    zeile = next(z for z in text.splitlines() if z.startswith('- Antwort (gekürzt): Bis Freitag'))
    assert len(zeile) < 400 and zeile.endswith('…')


def test_zeiten_kalt_und_warm_getrennt(mit_modell):
    zeiten = json.loads(json.dumps(bericht.zu_dict(mit_modell)))['antwort']['zeiten']
    assert zeiten['kalt_s'] is not None and zeiten['warm_n'] == 7 and zeiten['warm_median_s'] is not None
    assert sum(f.antwort.kalt for f in mit_modell.fragen) == 1


def test_falsche_aussage_erscheint_oben_im_bericht_und_in_der_fehlerliste():
    # Das Skript wählt beide Fristen aus: Der Bericht muss die alte als falsche Aussage zählen.
    modell = SkriptModell({**REGELN, 'Angebot für das Klinikum Mainz raus': ['Oktober']})
    ergebnis = durchfuehren(Optionen(welten=(str(MINI),), modell='ollama:skript'), anbieter_bauen=lambda wahl: modell)
    text = bericht.markdown(ergebnis)
    assert 'Falsche Aussagen: 1 von 8 Antworten' in text.split('## Aufnahme')[0]
    assert '### mainz-01: falsch · FALSCHE AUSSAGE' in text
    assert ergebnis.antwort_auswertung.kritisch_nicht_richtig[0] == 'mainz-01'
    daten = bericht.zu_dict(ergebnis)
    assert daten['antwort']['auswertung']['gesamt']['falsche_aussagen'] == 1


def test_nur_eine_kategorie(mit_modell):
    ergebnis = durchfuehren(Optionen(welten=(str(MINI),), nur='frist'))
    assert [f.frage.id for f in ergebnis.fragen] == ['rechnung-02']
    with pytest.raises(ValueError, match='Keine Frage'):
        durchfuehren(Optionen(welten=(str(MINI),), nur='profil'))


def test_holdout_wird_getrennt_ausgewiesen(tmp_path):
    holdout = tmp_path / 'holdout'
    (holdout / 'szenarien').mkdir(parents=True)
    shutil.copy(MINI / 'welt.json', holdout / 'welt.json')
    (holdout / 'szenarien' / 'zaun.json').write_text(json.dumps({
        'id': 'zaun', 'titel': 'Zaun', 'beschreibung': 'Ein Gartenzaun.',
        'quellen': [{'id': 'zaun-001', 'art': 'notiz', 'zeit': '2026-09-01T10:00:00+02:00', 'titel': 'Gartenzaun',
                     'text': 'Der Gartenzaun wird am 5. November gestrichen.'}],
        'fragen': [{'id': 'zaun-01', 'frage': 'Wann wird der Gartenzaun gestrichen?', 'kategorie': 'rueckblick',
                    'schwere': 'normal', 'erwartet': {'verhalten': 'antworten', 'aussagen': [['5. November']],
                                                      'belege': ['zaun-001']}}]}, ensure_ascii=False), encoding='utf-8')
    modell = SkriptModell({**REGELN, 'Gartenzaun': ['Gartenzaun']})
    ergebnis = durchfuehren(Optionen(welten=(str(MINI), f'holdout={holdout}'), modell='ollama:skript'),
                            anbieter_bauen=lambda wahl: modell)
    text = bericht.markdown(ergebnis)
    assert 'Je Herkunft (Holdout getrennt ausgewiesen)' in text
    assert '| holdout | 1 |' in text and '| welt | 8 |' in text
    assert 'holdout v1' in text and 'welt v1' in text
    assert ergebnis.kopf['welten'][1]['name'] == 'holdout'
    assert ergebnis.antwort_auswertung.je_herkunft['holdout'].richtig == 1


# -- Kommandozeile ------------------------------------------------------------------------


def test_cli_lauf_ohne_modell_schreibt_bericht(tmp_path, capsys):
    assert main(['lauf', '--welt', str(MINI), '--modell', 'keins', '--ausgabe', str(tmp_path)]) == 0
    ausgabe = capsys.readouterr().out
    assert ausgabe.startswith('# Messlatte: Bericht') and 'nicht gemessen' in ausgabe
    assert len(list(tmp_path.glob('bericht-*.json'))) == 1 and len(list(tmp_path.glob('bericht-*.md'))) == 1


def test_cli_ungueltige_welt_gibt_meldung_und_code_2(tmp_path, capsys):
    (tmp_path / 'welt.json').write_text('{kaputt', encoding='utf-8')
    assert main(['lauf', '--welt', str(tmp_path)]) == 2
    assert 'welt.json' in capsys.readouterr().err


def test_cli_unbekanntes_modell_gibt_code_2(capsys):
    assert main(['lauf', '--welt', str(MINI), '--modell', 'zauberei']) == 2
    assert 'Unbekanntes Modell' in capsys.readouterr().err


def test_cli_pruefen(capsys):
    assert main(['pruefen', '--welt', str(MINI)]) == 0
    assert '2 Szenarien, 15 Quellen, 8 Fragen, gültig' in capsys.readouterr().out


def test_modell_hintergrund_baut_ein_eigenes_modell_fuer_die_einordnung():
    gebaut = []
    antwort = SkriptModell(dict(REGELN), chat='Bis Freitag')

    def bauen(wahl):
        gebaut.append(wahl.bezeichnung)
        return antwort

    ergebnis = durchfuehren(Optionen(welten=(str(MINI),), modell='ollama:skript', modell_hintergrund='ollama:gross'),
                            anbieter_bauen=bauen)
    assert gebaut == ['ollama:skript', 'ollama:gross']
    assert ergebnis.kopf['modell_hintergrund'] == 'ollama:gross'


class FrageModell:
    """Anbieter der Rolle „frage“: übersetzt jede Frage so, wie es der Rückfall täte, aber als „Modell“."""
    name = 'frage'
    model = 'frage-skript'
    is_local = True
    supports_json = True

    def __init__(self):
        self.fragen = []

    def complete_json(self, messages, *, max_tokens=256, schema=None):
        from icarus_memory.frage import rueckfall
        from icarus_memory.providers import Reply
        frage = json.loads(messages[-1]['content'])['frage']
        self.fragen.append(frage)
        anfrage = rueckfall(frage)
        return Reply(text=json.dumps({'sachen': list(anfrage.sachen), 'zeitraum': anfrage.zeitraum or 'keiner',
                                      'absicht': anfrage.absicht, 'suchworte': [], 'umschreibungen': []}))


def test_modell_frage_baut_ein_eigenes_modell_fuer_die_rolle_frage_und_der_bericht_weist_es_aus():
    gebaut = []
    frage = FrageModell()

    def bauen(wahl):
        gebaut.append(wahl.bezeichnung)
        return frage

    ergebnis = durchfuehren(Optionen(welten=(str(MINI),), modell_frage='ollama:klein'), anbieter_bauen=bauen)
    assert gebaut == ['keins', 'ollama:klein']
    assert ergebnis.kopf['modell_frage'] == 'ollama:klein'
    z = ergebnis.abruf_gesamt
    assert z.verstanden_modell > 0 and z.verstanden_modell + z.verstanden_rueckfall == z.fragen
    assert set(frage.fragen) <= {f.frage.frage for f in ergebnis.fragen}
    assert all(f.abruf.verstanden in {'modell', 'rueckfall'} for f in ergebnis.fragen)
    text = bericht.markdown(ergebnis)
    assert 'Modell (Rolle „frage“) | ollama:klein' in text
    assert f'Frage verstanden mit Modell: {z.verstanden_modell} von {z.fragen}' in text


def test_ohne_modell_versteht_der_rueckfall_jede_frage_und_der_bericht_nennt_den_grund(ohne_modell):
    z = ohne_modell.abruf_gesamt
    assert z.verstanden_modell == 0 and z.verstanden_rueckfall == z.fragen == 8
    text = bericht.markdown(ohne_modell)
    assert 'Frage verstanden mit Modell: 0 von 8, mit Rückfall: 8 von 8 (kein Modell: 8)' in text
    assert 'Unnötige Rückfragen bei eindeutigen Fragen:' in text and 'freien Chat' in text
    assert ohne_modell.kopf['modell_frage'] == 'keins (Rückfall)'


def test_ein_lokales_modell_der_antworten_versteht_die_frage_nicht_ohne_eigene_wahl(mit_modell):
    # Wie im Produkt: Ohne Zuweisung der Rolle „frage“ versteht der Rückfall, auch wenn ein Modell antwortet.
    assert mit_modell.kopf['modell_frage'] == 'keins (Rückfall)'
    assert all(f.abruf.verstanden == 'rueckfall' for f in mit_modell.fragen)


def test_cli_modell_frage_unbekanntes_modell_gibt_code_2(capsys):
    assert main(['lauf', '--welt', str(MINI), '--modell-frage', 'zauberei']) == 2
    assert 'Unbekanntes Modell' in capsys.readouterr().err
