"""Der lokale Modus gegen eine TestClient-App statt echtem HTTP; der Bericht enthält keine Inhalte."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from skriptmodell import SkriptModell

from messlatte import lokal
from messlatte.__main__ import main
from messlatte.aufnahme import aufnehmen
from messlatte.instanz import instanz_starten
from messlatte.welt import WeltFehler, lade_welt, pruefe_fragen_lokal

MINI = Path(__file__).parent / 'mini_welt'
BEISPIEL = Path(__file__).resolve().parents[1] / 'beispiel-eigene-fragen.json'

FRAGEN = {'fragen': [
    {'id': 'e-1', 'frage': 'Bis wann muss die Umsatzsteuervoranmeldung abgegeben werden?', 'kategorie': 'frist',
     'schwere': 'kritisch', 'erwartet': {'verhalten': 'antworten', 'aussagen': [['10. Oktober']],
                                         'belege': ['gibt-es-nicht-1']},
     'verboten': {'aussagen': ['Finanzamt Mitte'], 'belege': ['gibt-es-nicht-2']}},
    {'id': 'e-2', 'frage': 'Wann ist mein Termin beim Finanzamt?', 'erwartet': {'verhalten': 'nicht_bekannt'},
     'verboten': {'aussagen': ['10. Oktober']}},
]}


class OhneSchliessen:
    """Reicht Anfragen an den TestClient durch, schließt ihn aber nicht (die Instanz gehört dem Test)."""

    def __init__(self, client):
        self._client = client

    def request(self, methode, url, **kwargs):
        return self._client.request(methode, url, **kwargs)

    def close(self):
        pass


@pytest.fixture(scope='module')
def instanz():
    welt = lade_welt(MINI)
    modell = SkriptModell({'Umsatzsteuervoranmeldung': ['Umsatzsteuervoranmeldung']})
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, provider=modell) as instanz:
        aufnehmen(instanz, welt.quellen, welt.stichtag, modell=modell)
        yield instanz


@pytest.fixture
def fragen():
    return pruefe_fragen_lokal(FRAGEN)


def test_fragen_werden_ueber_die_konversations_api_gestellt_und_bewertet(instanz, fragen):
    ergebnis = lokal.messen(instanz.client, fragen)
    klassen = {f.id: b.klasse for f, _, b in ergebnis.fragen}
    assert klassen == {'e-1': 'richtig', 'e-2': 'richtig'}
    assert ergebnis.auswertung.gesamt.n == 2 and ergebnis.auswertung.gesamt.richtig == 2


def test_belege_der_fragen_datei_werden_ignoriert(instanz, fragen):
    # „gibt-es-nicht-1“ ließe sich nie zuordnen; die Antwort darf deshalb nicht unvollständig wirken.
    ergebnis = lokal.messen(instanz.client, fragen)
    assert ergebnis.fragen[0][2].klasse == 'richtig' and ergebnis.fragen[0][2].fehlende_belege == ()


def test_bericht_enthaelt_keine_texte_keine_fragen_keine_erwartungen(instanz, fragen):
    ergebnis = lokal.messen(instanz.client, fragen)
    ausgabe = json.dumps(lokal.zu_dict(ergebnis), ensure_ascii=False) + lokal.markdown(ergebnis)
    for verboten in ('Umsatzsteuervoranmeldung', 'Finanzamt', '10. Oktober', 'Steuerberater Weber', 'Karl Weber',
                     'Quelle berichtet', 'Dazu liegt', 'gibt-es-nicht', 'Telefonat', 'Lea Hartmann'):
        assert verboten not in ausgabe, verboten
    # Was drinsteht: IDs, Klassen, Zähler, Zeiten.
    assert 'e-1' in ausgabe and 'richtig' in ausgabe and 'Falsche Aussagen: 0 von 2 Antworten' in ausgabe


def test_zeigen_bekommt_die_antworten_nur_ueber_den_rueckruf(instanz, fragen):
    gesehen = []
    lokal.messen(instanz.client, fragen, zeigen=lambda frage, antwort: gesehen.append((frage.id, antwort.text)))
    assert [k for k, _ in gesehen] == ['e-1', 'e-2'] and 'Umsatzsteuervoranmeldung' in gesehen[0][1]


def test_falsche_aussage_wird_im_lokalen_bericht_nur_als_zaehler_gemeldet(instanz):
    fragen = pruefe_fragen_lokal([{'id': 'f-1', 'frage': 'Bis wann muss die Umsatzsteuervoranmeldung abgegeben werden?',
                                   'erwartet': {'verhalten': 'antworten', 'aussagen': [['10. Oktober']]},
                                   'verboten': {'aussagen': ['Karl Weber']}}])
    ergebnis = lokal.messen(instanz.client, fragen)
    assert ergebnis.auswertung.gesamt.falsche_aussagen == 1
    daten = lokal.zu_dict(ergebnis)
    assert daten['fragen'][0]['falsche_aussage'] is True and 'Karl Weber' not in json.dumps(daten, ensure_ascii=False)
    assert 'FALSCHE AUSSAGE' in lokal.markdown(ergebnis)


def test_ein_abgelehnter_einzelaufruf_ist_ein_fehler_nicht_das_ende(fragen):
    class Halb:
        def request(self, methode, url, **kwargs):
            class Antwort:
                status_code = 500
                def json(self): return {}
            return Antwort()

    ergebnis = lokal.messen(Halb(), fragen)
    assert {b.klasse for _, _, b in ergebnis.fragen} == {'fehler'}


def test_keine_instanz_ist_eine_verstaendliche_meldung(fragen):
    class Tot:
        def request(self, *args, **kwargs):
            raise ConnectionError('refused')

    with pytest.raises(lokal.KeineInstanz, match='make start'):
        lokal.messen(Tot(), fragen)


def test_abgelehntes_token_ist_eine_verstaendliche_meldung(fragen):
    class Verboten:
        def request(self, *args, **kwargs):
            class Antwort:
                status_code = 401
            return Antwort()

    with pytest.raises(lokal.KeineInstanz, match='Token'):
        lokal.messen(Verboten(), fragen)


def test_token_aus_der_umgebung_sonst_aus_kingfisher_env(tmp_path):
    (tmp_path / '.kingfisher.env').write_text('ANDERES=1\nICARUS_SIDECAR_TOKEN="abc123"\nWEITERES=2\n', encoding='utf-8')
    assert lokal.lese_token(tmp_path, {}) == 'abc123'
    assert lokal.lese_token(tmp_path, {'ICARUS_SIDECAR_TOKEN': 'aus-umgebung'}) == 'aus-umgebung'
    assert lokal.lese_token(tmp_path / 'leer', {}) is None
    (tmp_path / '.kingfisher.env').write_text('ICARUS_SIDECAR_TOKEN=\n', encoding='utf-8')
    assert lokal.lese_token(tmp_path, {}) is None


def test_beispieldatei_hat_drei_erfundene_fragen_und_ist_gueltig():
    fragen = lokal.lade_fragen(BEISPIEL)
    assert [f.id for f in fragen] == ['eigene-01', 'eigene-02', 'eigene-03']
    assert {f.erwartet.verhalten for f in fragen} == {'antworten', 'rueckfrage', 'nicht_bekannt'}


def test_kaputte_fragen_datei_wird_verstaendlich_abgelehnt(tmp_path):
    datei = tmp_path / 'f.json'
    datei.write_text('{"fragen": [{"id": "x"}]}', encoding='utf-8')
    with pytest.raises(WeltFehler, match='Pflichtfeld'):
        lokal.lade_fragen(datei)
    with pytest.raises(WeltFehler, match='Datei fehlt'):
        lokal.lade_fragen(tmp_path / 'gibt-es-nicht.json')


def test_cli_lokal_schreibt_nur_einen_bericht_ohne_inhalte(instanz, monkeypatch, tmp_path, capsys):
    datei = tmp_path / 'fragen.json'
    datei.write_text(json.dumps(FRAGEN, ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(lokal, 'oeffne', lambda adresse, token: OhneSchliessen(instanz.client))
    ziel = tmp_path / 'bericht'
    assert main(['lokal', '--fragen', str(datei), '--ausgabe', str(ziel)]) == 0
    ausgabe = capsys.readouterr()
    for pfad in ziel.iterdir():
        inhalt = pfad.read_text(encoding='utf-8')
        assert 'Umsatzsteuervoranmeldung' not in inhalt and 'Finanzamt' not in inhalt
    assert 'Umsatzsteuervoranmeldung' not in ausgabe.out and 'Gespräch „Messlatte“' in ausgabe.err
    assert sorted(p.suffix for p in ziel.iterdir()) == ['.json', '.md']


def test_cli_lokal_zeigen_gibt_antworten_nur_im_terminal_aus(instanz, monkeypatch, tmp_path, capsys):
    datei = tmp_path / 'fragen.json'
    datei.write_text(json.dumps(FRAGEN, ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(lokal, 'oeffne', lambda adresse, token: OhneSchliessen(instanz.client))
    ziel = tmp_path / 'bericht'
    assert main(['lokal', '--fragen', str(datei), '--zeigen', '--ausgabe', str(ziel)]) == 0
    assert 'Quelle berichtet' in capsys.readouterr().out
    assert all('Quelle berichtet' not in p.read_text(encoding='utf-8') for p in ziel.iterdir())


def test_cli_lokal_ohne_instanz_endet_mit_code_1(monkeypatch, tmp_path, capsys):
    datei = tmp_path / 'fragen.json'
    datei.write_text(json.dumps(FRAGEN, ensure_ascii=False), encoding='utf-8')

    class Tot:
        def request(self, *args, **kwargs):
            raise ConnectionError('refused')

        def close(self):
            pass

    monkeypatch.setattr(lokal, 'oeffne', lambda adresse, token: Tot())
    assert main(['lokal', '--fragen', str(datei)]) == 1
    assert 'make start' in capsys.readouterr().err
